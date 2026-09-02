import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.stripe_manager import StripeManager

client = TestClient(app)

def test_stripe_create_checkout_session():
    payload = {
        "plan_tier": "PRO",
        "company_name": "EuroCocoa Trading BV",
        "contact_email": "procurement@eurococoa.nl",
        "vat_number": "NL849201948B01"
    }
    response = client.post("/api/v1/payments/stripe/create-checkout-session", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "checkout_url" in data
    assert data["amount_eur"] == 1490.00
    assert data["currency"] == "EUR"
    assert data["company_name"] == "EuroCocoa Trading BV"

def test_stripe_confirm_session():
    # First create session
    create_resp = client.post("/api/v1/payments/stripe/create-checkout-session", json={
        "plan_tier": "STARTER",
        "company_name": "Nordic Timber AB",
        "contact_email": "lars@nordictimber.se"
    })
    session_id = create_resp.json()["session_id"]

    # Confirm session
    confirm_resp = client.post("/api/v1/payments/stripe/confirm-session", json={
        "session_id": session_id
    })
    assert confirm_resp.status_code == 200
    data = confirm_resp.json()
    assert data["status"] == "completed"
    assert "api_key" in data
    assert data["api_key"].startswith("eudr_live_")

def test_stripe_preview_checkout_page():
    response = client.get("/api/v1/payments/stripe/preview-checkout?session_id=cs_test_12345&tier=PRO&amount=1490.00")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Stripe Checkout" in response.text

def test_stripe_webhook_handler():
    webhook_payload = {
        "id": "evt_test_webhook",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_webhook_session",
                "customer_email": "finance@global-coffee.com"
            }
        }
    }
    response = client.post("/api/v1/payments/stripe-webhook", json=webhook_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event"] == "checkout.session.completed"
