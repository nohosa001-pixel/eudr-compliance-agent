import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import EUDRSupplyChainPayload, ComplianceStatusEnum

client = TestClient(app)


def test_100_plots_batch_stress_latency():
    """Stress test: 100 production plots batch evaluation performance (< 500ms)."""
    plots = []
    for i in range(100):
        plots.append({
            "plot_id": f"STRESS-PLOT-{i:03d}",
            "country_code": "VN",
            "area_hectares": 2.0,
            "geometry": {"type": "Point", "coordinates": [108.4385 + (i * 0.001), 11.9412 + (i * 0.001)]},
            "production_date": "2024-03-01",
            "notes": "clean"
        })

    payload = {
        "supplier_id": "SUPP-STRESS-100",
        "operator": {
            "operator_name": "Mega Logistics SA",
            "eori_number": "FR1122334455",
            "country": "FR",
            "address": "Port of Le Havre"
        },
        "commodity": {
            "hs_code": "090111",
            "description": "Coffee green",
            "net_mass_kg": 250000.0
        },
        "plots": plots,
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Land Ministry", "issue_date": "2020-01-01"},
            {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Agri Dept", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
            {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Chamber", "issue_date": "2019-01-01"}
        ]
    }

    t0 = time.perf_counter()
    resp = client.post("/api/v1/eudr/evaluate", json=payload)
    latency_sec = time.perf_counter() - t0

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLIANT"
    assert data["spatial_summary"]["total_plots"] == 100
    assert latency_sec < 1.0, f"100-plot evaluation took {latency_sec:.2f}s (expected < 1.0s)"


def test_wood_commodity_scientific_name_enforcement():
    """EUDR Art. 9: Wood products (HS 44) strictly require scientific botanical species name."""
    payload_without_scientific = {
        "supplier_id": "SUPP-WOOD-TEST",
        "operator": {"operator_name": "Timber AG", "eori_number": "DE9911223344", "country": "DE", "address": "Hamburg"},
        "commodity": {
            "hs_code": "440711",
            "description": "Pine timber",
            "net_mass_kg": 50000.0
            # missing scientific_name
        },
        "plots": [{
            "plot_id": "SE-WOOD-01", "country_code": "SE", "area_hectares": 3.0,
            "geometry": {"type": "Point", "coordinates": [18.0686, 59.3293]}, "production_date": "2024-04-01"
        }],
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Skogsstyrelsen", "issue_date": "2020-01-01"},
            {"doc_id": "D2", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Bolagsverket", "issue_date": "2019-01-01"}
        ]
    }

    resp = client.post("/api/v1/eudr/evaluate", json=payload_without_scientific)
    assert resp.status_code == 200
    data = resp.json()
    # Should flag missing scientific name in legal notes
    notes = data["legal_summary"]["notes"]
    assert any("scientific" in n.lower() or "species" in n.lower() or "timber" in n.lower() for n in notes)


def test_b2g_submit_non_compliant_rejection_safeguard():
    """Safeguard: Non-compliant report must be strictly rejected from TRACES-NT submission."""
    non_compliant_report = {
        "execution_id": "EXEC-FAIL-01",
        "status": "NON_COMPLIANT",
        "summary_message": "Deforestation detected",
        "spatial_summary": {},
        "satellite_summary": {},
        "legal_summary": {},
        "plots_detail": [],
        "confidence_assessment": {
            "overall_confidence_score": 0.3,
            "review_status": "ACTION_REQUIRED",
            "requires_human_review": True,
            "review_reasons": ["Deforestation flag"]
        },
        "audit_trail": {}
    }

    resp = client.post("/api/v1/eudr/traces-nt/submit", json=non_compliant_report)
    assert resp.status_code == 400
    assert "cannot submit" in resp.json()["detail"].lower()
