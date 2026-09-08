import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.modules.vies_validator import ViesValidator
from app.modules.webhook_dispatcher import WebhookDispatcher

client = TestClient(app)

# -------------------------------------------------------------
# 1. Autonomous Agent M2M Settlement & x402 Protocol
# -------------------------------------------------------------
def test_x402_challenge_agent_endpoint():
    """Verify that RFC 9110 / x402 HTTP challenge is returned for autonomous agents."""
    response = client.get("/api/v1/payment/x402/challenge?resource=plot_verification&plots=50")
    assert response.status_code == 402
    data = response.json()
    assert data["error"] == "PAYMENT_REQUIRED"
    assert data["agent_protocol"] == "x402-v1"
    assert data["amount_usdc"] == 5.00
    assert "WWW-Authenticate" in response.headers
    assert "X402" in response.headers["WWW-Authenticate"]
    assert "0x" in data["deposit_wallet"]

def test_agent_micro_settlement_and_budget_status():
    """Verify autonomous agent micro-settlement per plot without human friction."""
    settle_payload = {
        "agent_id": "agent-mesh-test-001",
        "num_plots": 20,
        "chain": "Base (Low Gas $0.01)",
        "tx_hash": "0x9876543210abcdef9876543210abcdef9876543210abcdef9876543210abcdef",
        "sender_wallet": "0x1111222233334444555566667777888899990000"
    }
    response = client.post("/api/v1/payment/agent/micro-settle", json=settle_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SETTLED"
    assert data["num_plots_credited"] == 20
    assert data["amount_paid_usdc"] == 2.00
    assert data["temporary_auth_token"].startswith("eudr_agent_micro_")

    # Check budget status endpoint
    budget_res = client.get("/api/v1/payment/agent/budget-status?agent_id=agent-mesh-test-001")
    assert budget_res.status_code == 200
    bdata = budget_res.json()
    assert bdata["agent_id"] == "agent-mesh-test-001"


# -------------------------------------------------------------
# 2. EU VIES Real-Time VAT Verification (0% Reverse-Charge)
# -------------------------------------------------------------
def test_vies_vat_validation_endpoint():
    """Test EU VIES VAT verification endpoint with mock and format check."""
    # Test valid Dutch VAT pattern
    with patch.object(ViesValidator, "validate_vat_async", return_value={
        "valid": True,
        "country_code": "NL",
        "vat_number": "849201948B01",
        "name": "EuroCocoa Trading BV",
        "address": "Keizersgracht 123, Amsterdam",
        "reverse_charge_eligible": True,
        "is_reverse_charge_eligible": True,
        "vies_live_verified": True,
        "message": "Verified against European Commission VIES"
    }):
        response = client.get("/api/v1/payments/verify-vat?vat_number=NL849201948B01")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["country_code"] == "NL"
        assert data["is_reverse_charge_eligible"] is True
        assert "EuroCocoa" in data["name"]

def test_vies_vat_invalid_format():
    """Test response when an invalid or non-EU VAT is provided."""
    response = client.get("/api/v1/payments/verify-vat?vat_number=INVALID123")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["is_reverse_charge_eligible"] is False

# -------------------------------------------------------------
# 3. B2B Outbound Webhook Dispatcher
# -------------------------------------------------------------
def test_webhook_subscription_and_test_ping():
    """Test webhook subscription registration and test event dispatch."""
    sub_payload = {
        "target_url": "https://erp.example-global.com/api/eudr-webhook",
        "company_name": "Global ERP Corp",
        "events": ["batch.completed", "dds.generated", "compliance.alert"],
        "secret_token": "test_hmac_secret_key_12345"
    }
    sub_resp = client.post("/api/v1/webhooks/subscribe", json=sub_payload)
    assert sub_resp.status_code == 201
    sub_data = sub_resp.json()
    assert sub_data["status"] == "active"
    assert sub_data["webhook_id"].startswith("whk_")

    # List webhooks
    list_resp = client.get("/api/v1/webhooks")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Test dispatch ping
    test_req = {
        "target_url": "https://erp.example-global.com/api/eudr-webhook",
        "secret_token": "test_hmac_secret_key_12345"
    }
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        ping_resp = client.post("/api/v1/webhooks/test", json=test_req)
        assert ping_resp.status_code == 200
        ping_data = ping_resp.json()
        assert ping_data["success"] is True

def test_webhook_hmac_signature():
    """Verify HMAC-SHA256 signature generation."""
    secret = "my_super_secret"
    payload = '{"event":"system.ping"}'
    sig = WebhookDispatcher.generate_signature(payload, secret)
    assert len(sig) == 64  # standard hex length of SHA256

# -------------------------------------------------------------
# 4. ESA Copernicus Sentinel Satellite Status
# -------------------------------------------------------------
def test_copernicus_sentinel_status():
    """Verify ESA Copernicus Sentinel-2 diagnostics endpoint returns operational health."""
    response = client.get("/api/v1/satellite/copernicus-status")
    assert response.status_code == 200
    data = response.json()
    assert "Copernicus" in data["provider"]
    assert data["status"] in ["LIVE_AUTHENTICATED", "CREDENTIALS_SET", "DETERMINISTIC_SIMULATION_READY"]
    assert data["resolution_meters"] == 10
    assert "NDVI" in data["spectral_indices"][0]
    assert data["free_quota_monthly_credits"] == 10000
