import pytest
import uuid
import hmac
import hashlib
from fastapi.testclient import TestClient

from app.main import app
from app.modules.agent_tools import AgentToolsRegistry
from app.core.config import settings

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Full Smart Escrow Lifecycle: Create -> Fund -> Release on SWE-C Clearance
# ---------------------------------------------------------------------------
def test_escrow_full_happy_path_with_swe_c_clearance():
    """
    Validates complete happy-path lifecycle:
    1. Buyer agent creates an escrow agreement locking $5,000 USDC for cocoa shipment.
    2. Buyer agent deposits funds (verified on Base).
    3. EU Single Window customs clearance code issued (EU-SWEC-CLEARED-*).
    4. Escrow automatically releases funds to seller agent with cryptographic HMAC signature.
    """
    # Step 1: Create Escrow
    create_payload = {
        "buyer_agent_id": "buyer-importer-bot-01",
        "buyer_wallet": "0x1111222233334444555566667777888899990000",
        "seller_agent_id": "seller-cooperative-bot-02",
        "seller_wallet": "0x2222333344445555666677778888999900001111",
        "amount_usdc": 5000.00,
        "chain": "Base (Low Gas $0.01)",
        "hs_code": "18010000",
        "commodity_description": "Fairtrade Certified Raw Cocoa Beans Batch A1",
        "declared_net_mass_kg": 25000.0,
        "expiry_hours": 48
    }
    create_res = client.post("/api/v1/payment/escrow/create", json=create_payload)
    assert create_res.status_code == 201
    cdata = create_res.json()
    escrow_id = cdata["escrow_id"]
    assert escrow_id.startswith("ESC-EUDR-2026-")
    assert cdata["status"] == "AWAITING_DEPOSIT"
    assert cdata["amount_usdc"] == 5000.00
    assert "0x" in cdata["vault_deposit_address"]

    # Step 2: Fund Escrow
    fund_payload = {
        "escrow_id": escrow_id,
        "tx_hash": "0x" + "aa" * 32
    }
    fund_res = client.post("/api/v1/payment/escrow/fund", json=fund_payload)
    assert fund_res.status_code == 200
    fdata = fund_res.json()
    assert fdata["status"] == "FUNDED_LOCKED"
    assert fdata["deposit_tx_hash"] == fund_payload["tx_hash"]

    # Step 3: Trigger Conditional Release upon EU SWE-C clearance
    customs_code = f"EU-SWEC-CLEARED-{uuid.uuid4().hex[:6].upper()}"
    dds_ref = f"DDS-EUDR-2026-{uuid.uuid4().hex[:6].upper()}"
    release_payload = {
        "escrow_id": escrow_id,
        "customs_declaration_code": customs_code,
        "dds_reference_id": dds_ref
    }
    rel_res = client.post("/api/v1/payment/escrow/release-by-compliance", json=release_payload)
    assert rel_res.status_code == 200
    rdata = rel_res.json()
    assert rdata["status"] == "RELEASED"
    assert rdata["release_tx_hash"] is not None
    assert rdata["customs_declaration_code"] == customs_code
    assert rdata["hmac_release_signature"] is not None
    assert len(rdata["hmac_release_signature"]) == 64

    # Verify HMAC release signature authenticity
    expected_msg = f"{escrow_id}|{5000.0}|{create_payload['seller_wallet']}|{dds_ref}|{customs_code}"
    expected_hmac = hmac.new(
        settings.SECRET_KEY_FOR_SIGNING.encode("utf-8"),
        expected_msg.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    assert rdata["hmac_release_signature"] == expected_hmac

    # Step 4: Verify live status query
    get_res = client.get(f"/api/v1/payment/escrow/{escrow_id}")
    assert get_res.status_code == 200
    gdata = get_res.json()
    assert gdata["status"] == "RELEASED"
    assert gdata["release_tx_hash"] == rdata["release_tx_hash"]


# ---------------------------------------------------------------------------
# 2. Deforestation Violation Detection Triggers Dispute
# ---------------------------------------------------------------------------
def test_escrow_deforestation_detection_during_release_triggers_dispute():
    """Verify that if production plots have post-2020 deforestation, release is blocked and dispute triggered."""
    # 1. Create and fund
    create_res = client.post("/api/v1/payment/escrow/create", json={
        "buyer_agent_id": "coffee-buyer-bot",
        "buyer_wallet": "0x3333444455556666777788889999000011112222",
        "seller_agent_id": "plantation-seller-bot",
        "seller_wallet": "0x4444555566667777888899990000111122223333",
        "amount_usdc": 3500.00,
        "chain": "Polygon (PoS)",
        "hs_code": "09011100",
        "commodity_description": "Green Coffee Beans"
    })
    escrow_id = create_res.json()["escrow_id"]

    client.post("/api/v1/payment/escrow/fund", json={
        "escrow_id": escrow_id,
        "tx_hash": "0x" + "bb" * 32
    })

    # 2. Release with plot that triggers deforestation in DeforestationSimulator
    # (coordinates in a known deforestation zone or with plot_id triggering simulation)
    bad_plots = [{
        "plot_id": "PLOT-DEFOREST_2022-TEST",
        "country_code": "BR",
        "area_hectares": 12.0,
        "coordinates": [[-55.12, -11.45], [-55.11, -11.45], [-55.11, -11.44], [-55.12, -11.44], [-55.12, -11.45]]
    }]

    rel_res = client.post("/api/v1/payment/escrow/release-by-compliance", json={
        "escrow_id": escrow_id,
        "plots": bad_plots
    })
    assert rel_res.status_code == 200
    rdata = rel_res.json()
    assert rdata["status"] == "DISPUTED"
    assert "FAILED" in rdata["message"]
    assert "Deforestation" in rdata["arbitration_verdict"] or "deforestation" in rdata["arbitration_verdict"].lower()


# ---------------------------------------------------------------------------
# 3. Autonomous Algorithmic Arbitration
# ---------------------------------------------------------------------------
def test_escrow_autonomous_arbitration_refunds_buyer_on_violation():
    """Verify autonomous dispute arbitration rules 100% refund to Buyer Agent when deforestation is found."""
    # 1. Create and fund
    create_res = client.post("/api/v1/payment/escrow/create", json={
        "buyer_agent_id": "timber-importer-bot",
        "buyer_wallet": "0x5555666677778888999900001111222233334444",
        "seller_agent_id": "timber-logger-bot",
        "seller_wallet": "0x6666777788889999000011112222333344445555",
        "amount_usdc": 12000.00,
        "chain": "Arbitrum One",
        "hs_code": "44071100",
        "commodity_description": "Coniferous Sawn Timber"
    })
    escrow_id = create_res.json()["escrow_id"]

    client.post("/api/v1/payment/escrow/fund", json={
        "escrow_id": escrow_id,
        "tx_hash": "0x" + "cc" * 32
    })

    # 2. Arbitrate dispute with deforestation claim
    arb_res = client.post("/api/v1/payment/escrow/dispute-arbitrate", json={
        "escrow_id": escrow_id,
        "initiator_agent_id": "timber-importer-bot",
        "reason": "Satellite radar confirms unauthorized logging post-2020 on concession area."
    })
    assert arb_res.status_code == 200
    adata = arb_res.json()
    assert adata["status"] == "REFUNDED"
    assert "refunded to Buyer Wallet" in adata["arbitration_verdict"]
    assert adata["release_tx_hash"] is not None


def test_escrow_autonomous_arbitration_dismisses_false_dispute():
    """Verify autonomous dispute arbitration dismisses unjustified disputes and releases to Seller Agent."""
    # 1. Create and fund
    create_res = client.post("/api/v1/payment/escrow/create", json={
        "buyer_agent_id": "rubber-procurement-bot",
        "buyer_wallet": "0x7777888899990000111122223333444455556666",
        "seller_agent_id": "rubber-plantation-bot",
        "seller_wallet": "0x8888999900001111222233334444555566667777",
        "amount_usdc": 4200.00,
        "chain": "Base (Low Gas $0.01)",
        "hs_code": "40011000",
        "commodity_description": "Natural Rubber Latex"
    })
    escrow_id = create_res.json()["escrow_id"]

    client.post("/api/v1/payment/escrow/fund", json={
        "escrow_id": escrow_id,
        "tx_hash": "0x" + "dd" * 32
    })

    # 2. Arbitrate with compliant plot (0% deforestation)
    clean_plots = [{
        "plot_id": "PLOT-CLEAN-01",
        "country_code": "VN",
        "area_hectares": 2.5,
        "coordinates": [106.6297, 10.8231]
    }]

    arb_res = client.post("/api/v1/payment/escrow/dispute-arbitrate", json={
        "escrow_id": escrow_id,
        "initiator_agent_id": "rubber-procurement-bot",
        "reason": "Late delivery concern (no deforestation)",
        "plots": clean_plots
    })
    assert arb_res.status_code == 200
    adata = arb_res.json()
    assert adata["status"] == "RELEASED"
    assert "released to Seller Wallet" in adata["arbitration_verdict"]


# ---------------------------------------------------------------------------
# 4. MCP Agent Tools for Smart Escrow
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mcp_agent_escrow_tools():
    """Verify autonomous agents can execute Smart Escrow lifecycle via MCP tools."""
    # 1. eudr_create_agent_escrow
    create_args = {
        "buyer_agent_id": "autonomous-trader-alpha",
        "buyer_wallet": "0x9999000011112222333344445555666677778888",
        "seller_agent_id": "cooperative-agent-bravo",
        "seller_wallet": "0xaaaa111122223333444455556666777788889999",
        "amount_usdc": 8500.00,
        "chain": "Polygon (PoS)",
        "hs_code": "15111000",
        "commodity_description": "Crude Palm Oil RSPO Certified"
    }
    create_res = await AgentToolsRegistry.execute_tool("eudr_create_agent_escrow", create_args)
    assert "escrow_id" in create_res
    escrow_id = create_res["escrow_id"]
    assert create_res["amount_usdc"] == 8500.00

    # 2. eudr_fund_agent_escrow
    fund_args = {
        "escrow_id": escrow_id,
        "tx_hash": "0x" + "ee" * 32
    }
    fund_res = await AgentToolsRegistry.execute_tool("eudr_fund_agent_escrow", fund_args)
    assert fund_res["status"] == "FUNDED_LOCKED"

    # 3. eudr_release_agent_escrow
    release_args = {
        "escrow_id": escrow_id,
        "customs_declaration_code": "EU-SWEC-CLEARED-998877",
        "dds_reference_id": "DDS-EUDR-2026-554433"
    }
    release_res = await AgentToolsRegistry.execute_tool("eudr_release_agent_escrow", release_args)
    assert release_res["status"] == "RELEASED"
    assert "EU Single Window" in release_res["message"]
