import pytest
import xml.etree.ElementTree as ET
from datetime import datetime, date, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    EUDRSupplyChainPayload,
    OperatorInfo,
    CommodityInfo,
    ProductionPlotInput,
    LegalDocumentInput,
    DocumentTypeEnum,
    ComplianceStatusEnum
)
from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper
from app.modules.dds_generator import DDSGenerator
from app.modules.traceability_collector import TraceabilityCollector
from app.modules.deforestation_simulator import DeforestationSimulator
from app.modules.legal_document_auditor import LegalAuditor

client = TestClient(app)

@pytest.fixture
def sample_compliant_payload():
    return EUDRSupplyChainPayload(
        execution_id="TEST-EXEC-TRACES-001",
        supplier_id="SUPP-IVORY-COAST-01",
        operator=OperatorInfo(
            operator_name="ChocoEurope BV",
            eori_number="NL123456789000",
            vat_number="NL123456789B01",
            country="NL",
            address="Keizersgracht 100, Amsterdam"
        ),
        commodity=CommodityInfo(
            hs_code="180100",
            description="Cocoa beans, whole or broken, raw or roasted",
            scientific_name="Theobroma cacao",
            net_mass_kg=25000.0,
            volume_m3=30.0
        ),
        plots=[
            ProductionPlotInput(
                plot_id="PLOT-CIV-001",
                country_code="CI",
                producer_name="Kouassi Farms Coop",
                production_date=date(2024, 5, 10),
                area_hectares=5.2,
                geometry={
                    "type": "Polygon",
                    "coordinates": [[
                        [-5.5471, 7.5399],
                        [-5.5450, 7.5399],
                        [-5.5450, 7.5420],
                        [-5.5471, 7.5420],
                        [-5.5471, 7.5399]
                    ]]
                }
            )
        ],
        documents=[
            LegalDocumentInput(
                doc_id="DOC-LAND-01",
                doc_type=DocumentTypeEnum.LAND_USE_TITLE,
                issuing_authority="Ministry of Agriculture Côte d'Ivoire",
                issue_date=date(2023, 1, 1),
                expiry_date=date(2030, 1, 1),
                associated_plot_ids=["PLOT-CIV-001"]
            ),
            LegalDocumentInput(
                doc_id="DOC-HARVEST-01",
                doc_type=DocumentTypeEnum.HARVEST_PERMIT,
                issuing_authority="National Forest Commission",
                issue_date=date(2024, 1, 1),
                expiry_date=date(2029, 1, 1),
                associated_plot_ids=["PLOT-CIV-001"]
            ),
            LegalDocumentInput(
                doc_id="DOC-LICENSE-01",
                doc_type=DocumentTypeEnum.BUSINESS_LICENSE,
                issuing_authority="Chamber of Commerce",
                issue_date=date(2022, 1, 1),
                expiry_date=date(2030, 1, 1),
                associated_plot_ids=["PLOT-CIV-001"]
            )
        ]
    )

def test_traces_xml_schema_generation(sample_compliant_payload):
    spatial_valid, spatial_results, _ = TraceabilityCollector.collect_and_validate(sample_compliant_payload.plots)
    deforest_free, satellite_results, _ = DeforestationSimulator.analyze_all_plots(sample_compliant_payload.plots, spatial_results)
    legal_audit = LegalAuditor.audit_documents(sample_compliant_payload.documents, sample_compliant_payload.plots, sample_compliant_payload.commodity)

    xml_str = TracesNTSchemaMapper.map_to_traces_xml(
        payload=sample_compliant_payload,
        spatial_results=spatial_results,
        satellite_results=satellite_results,
        legal_audit=legal_audit,
        dds_reference_id="DDS-EUDR-2026-TEST01"
    )

    assert xml_str.startswith("<?xml")
    assert "DueDiligenceStatement" in xml_str
    assert "http://ec.europa.eu/tracesnt/eudr/v1" in xml_str
    assert "DDS-EUDR-2026-TEST01" in xml_str
    assert "NL123456789000" in xml_str
    assert "180100" in xml_str
    assert "PLOT-CIV-001" in xml_str
    assert "HMAC-SHA256" in xml_str

    # Verify XML is well-formed
    root = ET.fromstring(xml_str)
    assert root.tag.endswith("DueDiligenceStatement")
    assert root.attrib.get("schemaVersion") == "1.0.0-EUDR"

def test_customs_certificate_html_generation(sample_compliant_payload):
    spatial_valid, spatial_results, spatial_summary = TraceabilityCollector.collect_and_validate(sample_compliant_payload.plots)
    deforest_free, satellite_results, satellite_summary = DeforestationSimulator.analyze_all_plots(sample_compliant_payload.plots, spatial_results)
    legal_audit = LegalAuditor.audit_documents(sample_compliant_payload.documents, sample_compliant_payload.plots, sample_compliant_payload.commodity)

    report = DDSGenerator.assemble_report(
        payload=sample_compliant_payload,
        spatial_valid=spatial_valid,
        spatial_results=spatial_results,
        spatial_summary=spatial_summary,
        deforestation_free=deforest_free,
        satellite_results=satellite_results,
        satellite_summary=satellite_summary,
        legal_audit=legal_audit,
        start_time=datetime.now(timezone.utc)
    )

    html_cert = DDSGenerator.generate_customs_clearance_certificate_html(
        report=report,
        ack_number="EU-TRACES-ACK-2026-ABC123",
        customs_declaration_code="EU-SWEC-CLEARED-XYZ999",
        lang="en"
    )

    assert "EU Single Window Environment for Customs" in html_cert
    assert "CUSTOMS DUE DILIGENCE CLEARANCE CERTIFICATE" in html_cert
    assert "EU-TRACES-ACK-2026-ABC123" in html_cert
    assert "EU-SWEC-CLEARED-XYZ999" in html_cert
    assert "NL123456789000" in html_cert
    assert "GREEN LANE CLEARED" in html_cert

def test_api_evaluate_traces_xml_endpoint(sample_compliant_payload):
    payload_dict = sample_compliant_payload.model_dump(mode="json")
    response = client.post("/api/v1/eudr/evaluate/traces-xml", json=payload_dict)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "DueDiligenceStatement" in response.text
    assert "attachment; filename=" in response.headers.get("content-disposition", "")

def test_api_evaluate_customs_certificate_endpoint(sample_compliant_payload):
    payload_dict = sample_compliant_payload.model_dump(mode="json")
    response = client.post("/api/v1/eudr/evaluate/customs-certificate", json=payload_dict)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CUSTOMS DUE DILIGENCE CLEARANCE CERTIFICATE" in response.text
