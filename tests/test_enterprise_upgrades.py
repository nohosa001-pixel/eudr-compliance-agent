import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.modules.stripe_manager import StripeManager
from app.modules.vies_validator import ViesValidator
from app.modules.webhook_dispatcher import WebhookDispatcher

client = TestClient(app)

# -------------------------------------------------------------
# 1. Multi-Currency Stripe Checkout (EUR & USD)
# -------------------------------------------------------------
def test_stripe_checkout_multi_currency_usd():
    """Verify that Stripe checkout session supports USD with 1:1 pricing parity."""
    payload = {
        "plan_tier": "PRO",
        "company_name": "Global Timber Corp (USA)",
        "contact_email": "ops@globaltimber.com",
        "currency": "USD"
    }
    response = client.post("/api/v1/payments/stripe/create-checkout-session", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "USD"
    assert data["amount_eur"] == 1490.00
    assert "currency=USD" in data["checkout_url"]

def test_stripe_checkout_default_currency_eur():
    """Verify default currency remains EUR when not specified."""
    payload = {
        "plan_tier": "STARTER",
        "company_name": "Antwerp Cocoa Traders NV",
        "contact_email": "desk@antwerpcocoa.be"
    }
    response = client.post("/api/v1/payments/stripe/create-checkout-session", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "EUR"
    assert data["amount_eur"] == 490.00

def test_stripe_preview_checkout_usd_symbol():
    """Verify preview checkout HTML displays the dollar symbol and USD payment method."""
    response = client.get("/api/v1/payments/stripe/preview-checkout?session_id=cs_test_usd_123&tier=PRO&amount=1490.00&currency=USD")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "$1,490.00" in response.text
    assert "Credit / Debit Card (USD)" in response.text

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
