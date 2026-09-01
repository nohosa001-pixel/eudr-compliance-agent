import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, init_db
from app.db.repository import LeadRepository
from app.modules.notification_manager import NotificationManager

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    yield
    # Cleanup test records so production DB remains pure
    db = SessionLocal()
    try:
        from app.db.models import LeadInquiryRecord
        db.query(LeadInquiryRecord).filter(
            LeadInquiryRecord.contact_email.in_([
                "lars@nordicwood.se",
                "sophie.v@eurococoa.nl",
                "carlos@bioenergy.br"
            ])
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

def test_lead_repository_create_and_list():
    db = SessionLocal()
    try:
        record = LeadRepository.create_inquiry(
            db=db,
            company_name="Nordic Wood & Pulp Ltd",
            contact_name="Lars Svensson",
            contact_email="lars@nordicwood.se",
            phone="+46 8 123 4567",
            commodity_type="Timber",
            estimated_monthly_plots="5,000 - 50,000",
            message="We need EUDR TRACES-NT automated submission for Swedish forestry."
        )
        assert record.id is not None
        assert record.inquiry_id.startswith("lead_")
        assert record.company_name == "Nordic Wood & Pulp Ltd"
        assert record.status == "NEW"

        # List inquiries
        inquiries = LeadRepository.list_inquiries(db=db, limit=10)
        assert any(i.inquiry_id == record.inquiry_id for i in inquiries)

        # Get by id
        fetched = LeadRepository.get_by_inquiry_id(db=db, inquiry_id=record.inquiry_id)
        assert fetched is not None
        assert fetched.contact_email == "lars@nordicwood.se"
    finally:
        db.close()

def test_submit_lead_inquiry_api():
    payload = {
        "company_name": "EuroCocoa Trading BV",
        "contact_name": "Sophie Van Der Beek",
        "contact_email": "sophie.v@eurococoa.nl",
        "phone": "+31 20 555 0199",
        "commodity_type": "Cocoa",
        "estimated_monthly_plots": "500 - 5,000",
        "message": "Interested in pilot audit for Ivory Coast cocoa supply chain."
    }
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "inquiry_id" in data
    assert data["status"] == "NEW"
    assert data["company_name"] == "EuroCocoa Trading BV"
    assert data["contact_email"] == "sophie.v@eurococoa.nl"
    assert "Thank you" in data["message"]

def test_list_lead_inquiries_api():
    client.post("/api/v1/leads", json={
        "company_name": "Test Listing Corp",
        "contact_name": "Tester",
        "contact_email": "sophie.v@eurococoa.nl",
        "commodity_type": "Timber",
        "estimated_monthly_plots": "500 - 5,000"
    })
    response = client.get("/api/v1/leads")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_lead_inquiry_validation_error():
    # Missing required field company_name
    invalid_payload = {
        "contact_name": "John Doe",
        "contact_email": "not-an-email"
    }
    response = client.post("/api/v1/leads", json=invalid_payload)
    assert response.status_code == 422

def test_notification_manager_logger_fallback():
    # Test notification dispatch with no telegram/webhook (should fallback gracefully to logger)
    result = NotificationManager.notify_lead_received(
        company_name="BioEnergy S.A.",
        contact_name="Carlos Mendez",
        contact_email="carlos@bioenergy.br",
        phone="+55 11 98765 4321",
        commodity_type="Soy",
        estimated_monthly_plots="50,000+",
        message="Urgent inquiry for 2026 EUDR compliance.",
        inquiry_id="lead_test123"
    )
    assert result is True
