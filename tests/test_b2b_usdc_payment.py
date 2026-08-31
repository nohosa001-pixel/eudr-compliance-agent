import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_usdc_payment_order_pro():
    payload = {
        "plan_tier": "PRO",
        "company_name": "Global Coffee Importers GmbH",
        "contact_email": "compliance@globalcoffee.de",
        "chain": "Base (Low Gas $0.01)",
        "billing_country": "DE",
        "vat_number": "DE123456789"
    }
    response = client.post("/api/v1/payment/orders", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "ORD-" in data["order_id"]
    assert data["amount_usdc"] == 299.00
    assert "0x" in data["deposit_wallet_address"]
    assert data["status"] == "PENDING"
    assert "INV-EUDR-2026-" in data["invoice_number"]

def test_confirm_usdc_payment_and_provision_key():
    # 1. Create order
    order_payload = {
        "plan_tier": "PRO",
        "company_name": "Hamburg Timber AG",
        "contact_email": "ops@hamburg-timber.de",
        "chain": "Polygon (PoS)",
        "billing_country": "DE"
    }
    order_res = client.post("/api/v1/payment/orders", json=order_payload)
    order_id = order_res.json()["order_id"]

    # 2. Confirm order with Tx Hash
    confirm_payload = {
        "order_id": order_id,
        "tx_hash": "0x8f3c7b2a1e9d0c5a4b3f2e1d0c9b8a7f6e5d4c3b2a1e0f9d8c7b6a5f4e3d2c1b"
    }
    confirm_res = client.post("/api/v1/payment/confirm", json=confirm_payload)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "CONFIRMED"
    assert confirm_data["plan_tier"] == "PRO"
    assert confirm_data["monthly_quota_plots"] == 50000
    assert confirm_data["api_key_issued"].startswith("eudr_live_")

    # 3. Retrieve EU tax invoice
    invoice_res = client.get(f"/api/v1/payment/invoice/{order_id}")
    assert invoice_res.status_code == 200
    invoice_data = invoice_res.json()
    assert invoice_data["company_name"] == "Hamburg Timber AG"
    assert invoice_data["amount_usdc"] == 299.00
    assert len(invoice_data["hmac_audit_signature"]) == 64
    assert "Reverse Charge" in invoice_data["vat_tax_statement"]

def test_invalid_order_confirmation():
    payload = {
        "order_id": "ORD-NONEXISTENT",
        "tx_hash": "0x123"
    }
    response = client.post("/api/v1/payment/confirm", json=payload)
    assert response.status_code == 400
