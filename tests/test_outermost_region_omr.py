import pytest
from datetime import date, datetime, timezone
import xml.etree.ElementTree as ET

from app.modules.legal_document_auditor import LegalAuditor
from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper
from app.modules.dds_generator import DDSGenerator
from app.schemas import (
    CommodityInfo,
    OperatorInfo,
    ProductionPlotInput,
    EUDRSupplyChainPayload,
    LegalDocumentInput,
    DocumentTypeEnum,
    RiskTierEnum,
    SpatialPlotResult,
    SatellitePlotResult,
    ComplianceStatusEnum
)

def test_omr_status_evaluation_logic():
    """Verify OMR status evaluation for domestic, border trade, and EU mainland transit."""
    # 1. Non-OMR countries (e.g. Brazil alone, Germany alone)
    is_exempt, risk, stmt = LegalAuditor.evaluate_outermost_region_status(["BR"], "DE")
    assert is_exempt is False
    assert risk is False
    assert stmt is None

    # 2. French Guiana (GF) local consumption (GF -> GF)
    is_exempt_local, risk_local, stmt_local = LegalAuditor.evaluate_outermost_region_status(["GF"], "GF")
    assert is_exempt_local is True
    assert risk_local is False
    assert "Statutory OMR Exemption (TFEU Art. 349)" in stmt_local
    assert "French Guiana" in stmt_local

    # 3. French Guiana with default destination (None)
    is_exempt_def, risk_def, stmt_def = LegalAuditor.evaluate_outermost_region_status(["GF"], None)
    assert is_exempt_def is True
    assert risk_def is False
    assert "Statutory OMR Exemption" in stmt_def

    # 4. French Guiana border trade with Brazil (GF -> BR)
    is_exempt_br, risk_br, stmt_br = LegalAuditor.evaluate_outermost_region_status(["GF"], "BR")
    assert is_exempt_br is True
    assert risk_br is False
    assert "border partners" in stmt_br

    # 5. French Guiana border trade with Suriname (GF -> SR)
    is_exempt_sr, risk_sr, stmt_sr = LegalAuditor.evaluate_outermost_region_status(["GF"], "SR")
    assert is_exempt_sr is True
    assert risk_sr is False

    # 6. French Guiana to EU Mainland (GF -> FR or GF -> DE)
    is_exempt_fr, risk_fr, stmt_fr = LegalAuditor.evaluate_outermost_region_status(["GF"], "FR")
    assert is_exempt_fr is False
    assert risk_fr is True
    assert "EU Mainland Transit / Transshipment Risk Notice" in stmt_fr
    assert "Enhanced customs scrutiny applies" in stmt_fr

def test_french_guiana_local_consumption_full_exemption():
    """Verify that French Guiana local production & consumption requires zero permits under TFEU Art. 349."""
    plot_gf = ProductionPlotInput(
        plot_id="PLOT-GF-CAYENNE-01",
        country_code="GF",
        area_hectares=12.5,
        geometry={"type": "Point", "coordinates": [-52.33, 4.93]},
        production_date=date(2026, 3, 10)
    )
    wood_commodity = CommodityInfo(
        hs_code="440711",
        description="Tropical Wood Sawn",
        net_mass_kg=12000.0,
        scientific_name="Eperua falcata"
    )

    # Calling legal audit with zero documents provided and destination "GF"
    audit_res = LegalAuditor.audit_documents(
        documents=[],
        plots=[plot_gf],
        commodity=wood_commodity,
        destination_country="GF"
    )

    assert audit_res.overall_compliant is True
    assert audit_res.is_exempt_from_eudr is True
    assert audit_res.outermost_region_exemption_applied is True
    assert audit_res.transshipment_risk_flag is False
    assert audit_res.risk_score == 0.0
    assert any("Statutory OMR Exemption (TFEU Art. 349)" in n for n in audit_res.notes)

def test_french_guiana_to_eu_mainland_transshipment_alert():
    """Verify that shipping from French Guiana to EU mainland raises Transshipment Laundering risk flag."""
    plot_gf = ProductionPlotInput(
        plot_id="PLOT-GF-OYAPOCK-02",
        country_code="GF",
        area_hectares=25.0,
        geometry={"type": "Point", "coordinates": [-51.80, 3.93]},
        production_date=date(2026, 4, 15)
    )
    timber = CommodityInfo(
        hs_code="440711",
        description="Amazonian Timber Sawn",
        net_mass_kg=25000.0,
        scientific_name="Dicorynia guianensis"
    )
    valid_docs = [
        LegalDocumentInput(
            doc_id="DOC-GF-TITLE",
            doc_type=DocumentTypeEnum.LAND_USE_TITLE,
            issuing_authority="Prefecture de la Guyane",
            issue_date=date(2025, 1, 1),
            expiry_date=date(2035, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-GF-HARVEST",
            doc_type=DocumentTypeEnum.HARVEST_PERMIT,
            issuing_authority="ONF Guyane (Office National des Forets)",
            issue_date=date(2025, 1, 1),
            expiry_date=date(2030, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-GF-SIRET",
            doc_type=DocumentTypeEnum.BUSINESS_LICENSE,
            issuing_authority="INSEE Guyane",
            issue_date=date(2020, 1, 1)
        )
    ]

    # Destination is France mainland ("FR")
    audit_res = LegalAuditor.audit_documents(
        documents=valid_docs,
        plots=[plot_gf],
        commodity=timber,
        destination_country="FR"
    )

    assert audit_res.overall_compliant is True
    assert audit_res.is_exempt_from_eudr is False
    assert audit_res.outermost_region_exemption_applied is False
    assert audit_res.transshipment_risk_flag is True
    assert audit_res.omr_defense_statement is not None
    assert any("TRANSSHIPMENT_ALERT" in n for n in audit_res.notes)

def test_traces_nt_and_dds_omr_defense_integration():
    """Verify that OMR defense statements propagate correctly to TRACES-NT JSON & XML."""
    operator = OperatorInfo(
        operator_name="Guyane Bois Export SAS",
        eori_number="FR12345678900012",
        country="FR",
        address="Port de Degrad des Cannes, 97354 Remire-Montjoly, Guyane"
    )
    commodity = CommodityInfo(
        hs_code="440711",
        description="Certified Guianan Timber",
        net_mass_kg=15000.0,
        scientific_name="Eperua grandiflora"
    )
    plot = ProductionPlotInput(
        plot_id="PLOT-GF-003",
        country_code="GF",
        area_hectares=15.0,
        geometry={
            "type": "Polygon",
            "coordinates": [
                [[-52.5, 4.8], [-52.4, 4.8], [-52.4, 4.9], [-52.5, 4.9], [-52.5, 4.8]]
            ]
        },
        production_date=date(2026, 5, 20)
    )
    payload = EUDRSupplyChainPayload(
        supplier_id="SUPP-GF-01",
        operator=operator,
        commodity=commodity,
        plots=[plot],
        destination_country="FR"
    )

    docs = [
        LegalDocumentInput(
            doc_id="DOC-TITLE",
            doc_type=DocumentTypeEnum.LAND_USE_TITLE,
            issuing_authority="Prefecture de Guyane",
            issue_date=date(2024, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-LIC",
            doc_type=DocumentTypeEnum.BUSINESS_LICENSE,
            issuing_authority="CCI Guyane",
            issue_date=date(2020, 1, 1)
        )
    ]

    legal_audit = LegalAuditor.audit_documents(
        documents=docs,
        plots=[plot],
        commodity=commodity,
        destination_country=payload.destination_country
    )

    assert legal_audit.transshipment_risk_flag is True

    spatial_res = [
        SpatialPlotResult(
            plot_id=plot.plot_id,
            is_valid=True,
            area_hectares=15.0,
            declared_area_ha=15.0,
            calculated_area_ha=15.0,
            geometry_type="Polygon"
        )
    ]
    sat_res = [
        SatellitePlotResult(
            plot_id=plot.plot_id,
            deforestation_detected=False,
            baseline_forest_cover_pct=98.5,
            loss_ratio_pct=0.0,
            compliance_passed=True,
            audit_notes="Verified Zero Deforestation Post-2020",
            confidence_score=0.99
        )
    ]

    # Test TRACES-NT JSON mapping
    traces_json = TracesNTSchemaMapper.map_to_traces_payload(
        payload=payload,
        spatial_results=spatial_res,
        satellite_results=sat_res,
        legal_audit=legal_audit,
        dds_reference_id="DDS-EUDR-20260915-TESTOMR1"
    )

    attestation_json = traces_json["dueDiligenceAttestation"]
    assert attestation_json["transshipmentRiskFlag"] is True
    assert attestation_json["outermostRegionExemptionApplied"] is False
    assert "EU Mainland Transit" in attestation_json["omrRegulatoryDefenseStatement"]

    # Test TRACES-NT XML mapping
    traces_xml = TracesNTSchemaMapper.map_to_traces_xml(
        payload=payload,
        spatial_results=spatial_res,
        satellite_results=sat_res,
        legal_audit=legal_audit,
        dds_reference_id="DDS-EUDR-20260915-TESTOMR1"
    )

    root = ET.fromstring(traces_xml)
    att_elem = root.find("DueDiligenceAttestation")
    assert att_elem is not None
    assert att_elem.find("TransshipmentRiskFlag").text == "true"
    assert att_elem.find("OutermostRegionExemptionApplied").text == "false"
    assert "EU Mainland Transit" in att_elem.find("OMRRegulatoryDefenseStatement").text

    # Test DDSGenerator report assembly
    report = DDSGenerator.assemble_report(
        payload=payload,
        spatial_valid=True,
        spatial_results=spatial_res,
        spatial_summary={"total_plots": 1, "overlapping_plots_count": 0},
        deforestation_free=True,
        satellite_results=sat_res,
        satellite_summary={"deforestation_detected": False},
        legal_audit=legal_audit,
        start_time=datetime.now(timezone.utc)
    )

    assert report.status == ComplianceStatusEnum.COMPLIANT
    assert report.legal_summary["transshipment_risk_flag"] is True
    assert report.legal_summary["outermost_region_exemption_applied"] is False
    assert "EU Mainland Transit" in report.legal_summary["omr_defense_statement"]
