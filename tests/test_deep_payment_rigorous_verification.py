import pytest
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.modules.agent_tools import AgentToolsRegistry
from app.modules.payment_manager import PaymentManager, AGENT_PAYMENT_VAULTS, USDC_CONTRACT_ADDRESSES
from app.core.exceptions import AgentSelfCorrectionError
from app.core.config import settings

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Autonomous Agent Budget Guardrail Verification
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_budget_cap_guardrail_rejection():
    """Verify autonomous agent cannot exceed programmed max_budget_usdc."""
    # Attempting to order PRO ($299.00) with a max budget cap of $100.00
    args = {
        "plan_tier": "PRO",
        "company_name": "Autonomous Supply Corp",
        "contact_email": "agent@autosupply.io",
        "chain": "Base (Low Gas $0.01)",
        "max_budget_usdc": 100.00
    }
    with pytest.raises(AgentSelfCorrectionError) as exc_info:
        await AgentToolsRegistry.execute_tool("eudr_create_payment_order", args)
    
    assert exc_info.value.code == "BUDGET_CAP_EXCEEDED"
    assert "exceeds agent budget cap" in exc_info.value.message
    assert exc_info.value.recoverable is False


@pytest.mark.asyncio
async def test_budget_cap_guardrail_allowance():
    """Verify autonomous agent order creation succeeds when within budget cap."""
    args = {
        "plan_tier": "PRO",
        "company_name": "Autonomous Supply Corp",
        "contact_email": "agent@autosupply.io",
        "chain": "Base (Low Gas $0.01)",
        "max_budget_usdc": 350.00
    }
    result = await AgentToolsRegistry.execute_tool("eudr_create_payment_order", args)
    assert "order_id" in result
    assert result["amount_usdc"] == 299.00
    assert result["status"] == "PENDING"


# ---------------------------------------------------------------------------
# 2. Payment Confirmation Idempotency & Re-Confirm Resilience
# ---------------------------------------------------------------------------
def test_payment_confirmation_idempotency():
    """Verify re-confirming an already confirmed order is idempotent and safe."""
    # Step 1: Create an order
    create_res = client.post("/api/v1/payment/orders", json={
        "plan_tier": "PRO",
        "company_name": "Idempotent Agentic Ops",
        "contact_email": "ops@idempotent-agent.org",
        "chain": "Polygon (PoS)"
    })
    assert create_res.status_code == 200
    order_id = create_res.json()["order_id"]

    # Step 2: First confirmation
    tx_hash = "0x" + "11" * 32
    conf1 = client.post("/api/v1/payment/confirm", json={
        "order_id": order_id,
        "tx_hash": tx_hash
    })
    assert conf1.status_code == 200
    data1 = conf1.json()
    assert data1["status"] == "CONFIRMED"
    api_key_1 = data1["api_key_issued"]
    assert api_key_1.startswith("eudr_live_")

    # Step 3: Second confirmation (idempotent call)
    conf2 = client.post("/api/v1/payment/confirm", json={
        "order_id": order_id,
        "tx_hash": tx_hash
    })
    assert conf2.status_code == 200
    data2 = conf2.json()
    assert data2["status"] == "CONFIRMED"
    # Must preserve the exact same issued API key without creating a duplicate
    assert data2["api_key_issued"] == api_key_1
    assert "already confirmed and active" in data2["message"].lower()


# ---------------------------------------------------------------------------
# 3. Micro-Settlement Auth Token & Verification Invariance
# ---------------------------------------------------------------------------
def test_agent_micro_payment_token_usability():
    """Verify micro-payment token is persisted and validated through /auth/verify-key."""
    agent_id = f"mesh-agent-{uuid.uuid4().hex[:8]}"
    payload = {
        "agent_id": agent_id,
        "num_plots": 25,
        "chain": "Base (Low Gas $0.01)",
        "tx_hash": "0x" + "22" * 32,
        "sender_wallet": "0x3333444455556666777788889999000011112222"
    }
    # 1. Micro settle
    res = client.post("/api/v1/payment/agent/micro-settle", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SETTLED"
    assert data["num_plots_credited"] == 25
    assert data["amount_paid_usdc"] == 2.50
    token = data["temporary_auth_token"]
    assert token.startswith("eudr_agent_micro_")

    # 2. Verify token via API key verification endpoint
    verify_res = client.post("/api/v1/auth/verify-key", data={"api_key": token})
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["is_valid"] is True
    assert vdata["tier"] == "MICRO"
    assert vdata["remaining_quota_plots"] == 25

    # 3. Query agent budget status
    budget_res = client.get(f"/api/v1/payment/agent/budget-status?agent_id={agent_id}")
    assert budget_res.status_code == 200
    bdata = budget_res.json()
    assert bdata["agent_id"] == agent_id
    assert bdata["is_active"] is True
    assert bdata["remaining_quota_plots"] == 25
    assert bdata["total_usdc_spent"] == 2.50


# ---------------------------------------------------------------------------
# 4. Gasless EIP-3009 1-Turn Settlement Auth Token Usability
# ---------------------------------------------------------------------------
def test_eip3009_token_usability_and_budget_tracking():
    """Verify EIP-3009 authorization token works with /auth/verify-key and budget status."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    agent_id = f"eip3009-agent-{uuid.uuid4().hex[:6]}"
    unique_nonce = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    mock_sig = "0x" + "55" * 65

    payload = {
        "from_address": "0x5555666677778888999900001111222233334444",
        "value_usdc": 4.00,
        "valid_after": 0,
        "valid_before": now_ts + 3600,
        "nonce": unique_nonce,
        "signature": mock_sig,
        "chain": "Arbitrum One",
        "agent_id": agent_id,
        "num_plots": 40
    }

    # 1. Authorize
    auth_res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert auth_res.status_code == 200
    adata = auth_res.json()
    assert adata["status"] == "AUTHORIZED_AND_REDEEMED"
    token = adata["auth_token"]
    assert token.startswith("eudr_eip3009_")

    # 2. Verify token
    verify_res = client.post("/api/v1/auth/verify-key", data={"api_key": token})
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["is_valid"] is True
    assert vdata["tier"] == "EIP3009_GASLESS"
    assert vdata["remaining_quota_plots"] == 40

    # 3. Check budget status
    budget_res = client.get(f"/api/v1/payment/agent/budget-status?agent_id={agent_id}")
    assert budget_res.status_code == 200
    bdata = budget_res.json()
    assert bdata["agent_id"] == agent_id
    assert bdata["is_active"] is True
    assert bdata["remaining_quota_plots"] == 40
    assert bdata["total_usdc_spent"] == 4.00


# ---------------------------------------------------------------------------
# 5. EIP-3009 Cryptographic & Invariant Edge Cases
# ---------------------------------------------------------------------------
def test_eip3009_future_valid_after_rejection():
    """Verify that authorizations with valid_after in the future are rejected."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "from_address": "0x6666777788889999000011112222333344445555",
        "value_usdc": 1.00,
        "valid_after": now_ts + 600,  # 10 minutes in the future
        "valid_before": now_ts + 3600,
        "nonce": "0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        "signature": "0x" + "66" * 65,
        "chain": "Base (Low Gas $0.01)"
    }
    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 400
    assert "not yet valid" in res.json()["detail"].lower()


def test_eip3009_invalid_address_rejection():
    """Verify that malformed EVM addresses are rejected."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "from_address": "0xInvalidShortAddress",
        "value_usdc": 1.00,
        "valid_after": 0,
        "valid_before": now_ts + 3600,
        "nonce": "0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        "signature": "0x" + "77" * 65,
        "chain": "Polygon (PoS)"
    }
    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 400
    assert "42-character 0x EVM address" in res.json()["detail"]


def test_eip3009_invalid_nonce_format_rejection():
    """Verify that nonces not conforming to 32 bytes (64 hex characters) are rejected."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "from_address": "0x7777888899990000111122223333444455556666",
        "value_usdc": 1.00,
        "valid_after": 0,
        "valid_before": now_ts + 3600,
        "nonce": "0xShortNonce123",
        "signature": "0x" + "88" * 65,
        "chain": "Polygon (PoS)"
    }
    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 400
    assert "Invalid nonce format" in res.json()["detail"]


def test_eip3009_invalid_signature_length_rejection():
    """Verify that compact signatures with invalid length are rejected."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "from_address": "0x8888999900001111222233334444555566667777",
        "value_usdc": 1.00,
        "valid_after": 0,
        "valid_before": now_ts + 3600,
        "nonce": "0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        "signature": "0xBadSignatureTooShort",
        "chain": "Base (Low Gas $0.01)"
    }
    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 400
    assert "Invalid compact signature format" in res.json()["detail"]


def test_eip3009_vrs_invalid_recovery_id_rejection():
    """Verify that (v, r, s) signature components with invalid v != (27, 28) are rejected."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "from_address": "0x9999000011112222333344445555666677778888",
        "value_usdc": 1.00,
        "valid_after": 0,
        "valid_before": now_ts + 3600,
        "nonce": "0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        "v": 31,  # Invalid ECDSA recovery ID (must be 27 or 28)
        "r": "0x" + "11" * 32,
        "s": "0x" + "22" * 32,
        "chain": "Arbitrum One"
    }
    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 400
    assert "Invalid ECDSA recovery ID" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 6. B2B Tax Invoice HMAC-SHA256 Cryptographic Verification
# ---------------------------------------------------------------------------
def test_invoice_hmac_sha256_audit_cryptographic_verification():
    """Verify B2B tax invoice HMAC audit signature validity and tamper-resistance."""
    # 1. Create order
    comp_name = "Nordic Timber & Pulp OY"
    c_res = client.post("/api/v1/payment/orders", json={
        "plan_tier": "PRO",
        "company_name": comp_name,
        "contact_email": "finance@nordictimber.fi",
        "chain": "Polygon (PoS)",
        "billing_country": "FI"
    })
    order_id = c_res.json()["order_id"]

    # 2. Confirm order
    tx_hash = "0x" + "ab" * 32
    client.post("/api/v1/payment/confirm", json={
        "order_id": order_id,
        "tx_hash": tx_hash
    })

    # 3. Retrieve invoice
    inv_res = client.get(f"/api/v1/payment/invoice/{order_id}")
    assert inv_res.status_code == 200
    inv = inv_res.json()

    # 4. Cryptographically recalculate expected HMAC-SHA256
    raw_msg = f"{inv['invoice_number']}|{inv['amount_usdc']}|{tx_hash}|{comp_name}"
    expected_hmac = hmac.new(
        settings.SECRET_KEY_FOR_SIGNING.encode("utf-8"),
        raw_msg.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    assert inv["hmac_audit_signature"] == expected_hmac, "Invoice HMAC signature does not match secret key calculation!"

    # 5. Verify tamper detection: any modified value yields a completely different signature
    tampered_msg = f"{inv['invoice_number']}|{inv['amount_usdc'] + 10.0}|{tx_hash}|{comp_name}"
    tampered_hmac = hmac.new(
        settings.SECRET_KEY_FOR_SIGNING.encode("utf-8"),
        tampered_msg.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    assert inv["hmac_audit_signature"] != tampered_hmac, "HMAC failed to detect invoice payload tampering!"


# ---------------------------------------------------------------------------
# 7. Multi-Chain Vault & USDC Contract Mapping Invariance
# ---------------------------------------------------------------------------
def test_multichain_vault_registry_invariance():
    """Verify that multi-chain payment vaults and USDC contract addresses adhere to EVM standards."""
    vaults_res = client.get("/api/v1/payment/vaults")
    assert vaults_res.status_code == 200
    data = vaults_res.json()

    assert "agent_payment_vaults" in data
    assert "usdc_token_contracts" in data
    assert "supported_networks" in data

    # Polygon, Base, Arbitrum must exist
    for net in ["Polygon (PoS)", "Base (Low Gas $0.01)", "Arbitrum One"]:
        vault_addr = data["agent_payment_vaults"].get(net)
        assert vault_addr is not None
        assert vault_addr.startswith("0x") and len(vault_addr) == 42, f"Invalid vault address for {net}: {vault_addr}"

        usdc_addr = data["usdc_token_contracts"].get(net)
        assert usdc_addr is not None
        assert usdc_addr.startswith("0x") and len(usdc_addr) == 42, f"Invalid USDC address for {net}: {usdc_addr}"
