import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.modules.agent_tools import AgentToolsRegistry
from app.modules.payment_manager import PaymentManager

client = TestClient(app)


def test_x402_challenge_contains_eip3009_specs():
    """Verify RFC 9110 / x402 challenge response advertises gasless EIP-3009 1-turn capability."""
    response = client.get("/api/v1/payment/x402/challenge?resource=satellite_scan&plots=25")
    assert response.status_code == 402
    data = response.json()

    assert data["error"] == "PAYMENT_REQUIRED"
    assert data["eip3009_supported"] is True
    assert data["eip3009_endpoint"] == "/api/v1/payment/agent/eip3009-authorize"
    assert "eip3009_specs" in data
    specs = data["eip3009_specs"]
    assert "TransferWithAuthorization" in specs["type_definition"]
    assert "Base (Low Gas $0.01)" in specs["supported_chains"]
    assert "Polygon (PoS)" in specs["supported_chains"]


def test_eip3009_authorization_endpoint_success():
    """Verify autonomous agent 1-turn gasless settlement via EIP-3009."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    random_nonce = "0x" + uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars
    mock_sig = "0x" + "aa" * 65  # 130 hex chars + 0x = 132 chars (65 bytes)

    payload = {
        "from_address": "0x1111222233334444555566667777888899990000",
        "value_usdc": 2.50,
        "valid_after": 0,
        "valid_before": now_ts + 3600,
        "nonce": random_nonce,
        "signature": mock_sig,
        "chain": "Base (Low Gas $0.01)",
        "agent_id": "auto-agent-eudr-001"
    }

    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "AUTHORIZED_AND_REDEEMED"
    assert data["authorization_type"] == "EIP-3009_TRANSFER_WITH_AUTHORIZATION"
    assert data["gasless_for_agent"] is True
    assert data["amount_usdc"] == 2.50
    assert data["num_plots_credited"] == 25  # $2.50 / $0.10
    assert data["auth_token"].startswith("eudr_eip3009_")
    assert data["nonce"] == random_nonce.lower()
    assert "usdc_contract" in data
    assert "agent_payment_vault" in data


def test_eip3009_replay_attack_rejected():
    """Verify that reusing the same nonce is rejected as a replay attack."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    reused_nonce = "0x" + "dd" * 32
    mock_sig = "0x" + "bb" * 65

    payload = {
        "from_address": "0x2222333344445555666677778888999900001111",
        "value_usdc": 1.00,
        "valid_after": 0,
        "valid_before": now_ts + 1800,
        "nonce": reused_nonce,
        "signature": mock_sig,
        "chain": "Polygon (PoS)",
        "agent_id": "auto-agent-replay-test"
    }

    # 1. First authorization succeeds
    res1 = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res1.status_code == 200

    # 2. Second authorization with the same nonce must fail
    res2 = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res2.status_code == 400
    detail = res2.json()["detail"]
    assert "Replay Attack" in detail or "already been consumed" in detail


def test_eip3009_expired_authorization_rejected():
    """Verify that an expired authorization (valid_before < now) is rejected."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    expired_nonce = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    mock_sig = "0x" + "cc" * 65

    payload = {
        "from_address": "0x3333444455556666777788889999000011112222",
        "value_usdc": 3.00,
        "valid_after": 0,
        "valid_before": now_ts - 100,  # Already expired in the past
        "nonce": expired_nonce,
        "signature": mock_sig,
        "chain": "Arbitrum One",
        "agent_id": "auto-agent-expired-test"
    }

    res = client.post("/api/v1/payment/agent/eip3009-authorize", json=payload)
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mcp_agent_eip3009_tool():
    """Verify autonomous agent MCP tool invocation for gasless EIP-3009 payment."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    tool_nonce = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    mock_sig = "0x" + "ee" * 65

    args = {
        "from_address": "0x4444555566667777888899990000111122223333",
        "value_usdc": 5.00,
        "valid_before": now_ts + 7200,
        "nonce": tool_nonce,
        "signature": mock_sig,
        "chain": "Base (Low Gas $0.01)",
        "agent_id": "claude-desktop-eip3009"
    }

    result = await AgentToolsRegistry.execute_tool("eudr_agent_eip3009_pay", args)
    assert result["status"] == "AUTHORIZED_AND_REDEEMED"
    assert result["authorization_type"] == "EIP-3009_TRANSFER_WITH_AUTHORIZATION"
    assert result["gasless_for_agent"] is True
    assert result["amount_usdc"] == 5.00
    assert result["num_plots_credited"] == 50
    assert result["auth_token"].startswith("eudr_eip3009_")
    assert "Gasless EIP-3009 authorization confirmed" in result["agent_summary"]
