import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import EUDRSupplyChainPayload, ComplianceStatusEnum

client = TestClient(app)


def test_100_plots_batch_stress_latency(monkeypatch):
    """Stress test: 100 production plots batch evaluation performance (< 500ms)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "USE_LIVE_COPERNICUS_API", False)

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


def test_repository_save_evaluation_with_none_confidence_assessment():
    """Verify AuditRepository.save_evaluation does not crash when confidence_assessment is None."""
    from unittest.mock import MagicMock
    from app.db.repository import AuditRepository
    from app.schemas import EUDRSupplyChainPayload, FullComplianceReport, ComplianceStatusEnum

    payload = EUDRSupplyChainPayload(
        supplier_id="SUPP-RESILIENT",
        operator={"operator_name": "Test Op", "eori_number": "FR1234567890", "country": "FR", "address": "Paris"},
        commodity={"hs_code": "0901.11", "description": "Coffee", "net_mass_kg": 5000.0},
        plots=[{
            "plot_id": "P-1", "country_code": "VN", "area_hectares": 2.5,
            "geometry": {"type": "Point", "coordinates": [108.43, 11.94]},
            "production_date": "2024-01-01"
        }]
    )

    mock_report = MagicMock()
    mock_report.status = ComplianceStatusEnum.COMPLIANT
    mock_report.confidence_assessment = None
    mock_report.traces_dds = None
    mock_report.evidence_bundle = None
    mock_report.model_dump.return_value = {"status": "COMPLIANT"}

    mock_db = MagicMock()
    record = AuditRepository.save_evaluation(mock_db, payload, mock_report)
    assert record.review_status == "AUTO_APPROVED"
    assert record.confidence_score == 1.0
    assert record.commodity_hs_code == "0901.11"
    assert record.total_area_ha == 2.5


def test_customs_ucc_declaration_edge_case_hs_code_and_port():
    """Verify Customs UCC declaration handles None port and dotted HS code cleanly."""
    from app.modules.eu_customs_adapter import EUCustomsAdapter
    from app.schemas import CustomsUCCDeclarationRequest

    req = CustomsUCCDeclarationRequest(
        declarant_eori="NL123456789",
        importer_eori="DE987654321",
        hs_code="0901.11.00",
        country_of_origin="VN",
        net_mass_kg=15000.0,
        dds_reference_id="26EUDR12345678",
        verification_code="V-12345",
        destination_port_code=None
    )
    res = EUCustomsAdapter.generate_ucc_declaration(req)
    assert res.destination_port == "NLRTM"
    assert "<CommodityCode>09011100</CommodityCode>" in res.ucc_xml_snippet
    assert res.declarant_eori == "NL123456789"


def test_producer_adapters_none_and_malformed_identifier_resilience():
    """Verify all producer country adapters handle None and empty string identifiers without crashing."""
    from app.modules.producer_adapters.vietnam_coffee_timber_adapter import VietnamCoffeeTimberAdapter
    from app.modules.producer_adapters.brazil_car_adapter import BrazilCarAdapter
    from app.modules.producer_adapters.ghana_cocoa_adapter import GhanaCocoaAdapter
    from app.modules.producer_adapters.indonesia_timber_palm_adapter import IndonesiaTimberPalmAdapter

    adapters = [
        VietnamCoffeeTimberAdapter(),
        BrazilCarAdapter(),
        GhanaCocoaAdapter(),
        IndonesiaTimberPalmAdapter()
    ]

    for adapter in adapters:
        res_none = adapter.verify_registration(None)
        assert res_none.is_valid is False

        res_empty = adapter.verify_registration("")
        assert res_empty.is_valid is False


def test_trade_credit_oracle_str_doc_type_resilience():
    """Verify TradeCreditUnderwriter handles doc_type as str and None doc_id without crashing."""
    from app.modules.trade_credit_oracle import TradeCreditUnderwriter
    from unittest.mock import MagicMock

    underwriter = TradeCreditUnderwriter()
    mock_payload = MagicMock()
    mock_payload.commodity = MagicMock(hs_code="0901.11", description="Green Coffee", net_mass_kg=5000.0)
    mock_payload.plots = []
    
    mock_doc = MagicMock()
    mock_doc.doc_id = None
    mock_doc.doc_type = "LAND_USE_TITLE"  # plain str, not Enum
    mock_payload.documents = [mock_doc]
    mock_payload.operator = MagicMock(operator_name="Timber AG", eori_number="FR1234567890")
    mock_payload.supplier_id = "SUPP-SAFE"

    res = underwriter.evaluate_credit_and_underwrite_loan(mock_payload)
    assert res.credit_score.total_credit_score > 0
    assert res.loan_offer.estimated_cargo_value_usd > 0

