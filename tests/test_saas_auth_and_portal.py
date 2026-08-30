import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_landing_page_serving():
    """Verify that root / serves the official eudragent.com SaaS landing page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "EUDRAgent" in response.text
    assert "EUDR Compliance" in response.text
    assert "Regulation (EU) 2023/1115" in response.text
    assert "Pricing" in response.text


def test_dashboard_console_serving():
    """Verify that /dashboard serves the compliance workbench."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "EUDR Compliance" in response.text


def test_saas_api_key_creation_and_verification():
    """Test generating a SaaS API Key and verifying its quota."""
    # 1. Create Key
    create_payload = {
        "company_name": "Nordic Timber & Pulp AB",
        "contact_email": "compliance@nordictimber.se",
        "tier": "PRO"
    }
    create_resp = client.post("/api/v1/auth/api-keys", json=create_payload)
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["company_name"] == "Nordic Timber & Pulp AB"
    assert data["tier"] == "PRO"
    assert data["monthly_quota_plots"] == 50000
    assert data["api_key"].startswith("eudr_live_")
    
    raw_api_key = data["api_key"]

    # 2. Verify Key Valid
    verify_resp = client.post("/api/v1/auth/verify-key", data={"api_key": raw_api_key})
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert v_data["is_valid"] is True
    assert v_data["company_name"] == "Nordic Timber & Pulp AB"
    assert v_data["tier"] == "PRO"
    assert v_data["remaining_quota_plots"] == 50000

    # 3. Verify Invalid Key
    invalid_resp = client.post("/api/v1/auth/verify-key", data={"api_key": "eudr_live_invalid_key_12345"})
    assert invalid_resp.status_code == 200
    assert invalid_resp.json()["is_valid"] is False
