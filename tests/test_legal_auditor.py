import pytest
from datetime import date, timedelta
from app.schemas import LegalDocumentInput, ProductionPlotInput, DocumentTypeEnum, RiskTierEnum
from app.modules.legal_document_auditor import LegalAuditor

def test_high_risk_country_missing_fpic():
    """High risk country (e.g. BR) requires FPIC; missing FPIC fails audit."""
    plots = [
        ProductionPlotInput(
            plot_id="PLOT-BR-01",
            country_code="BR",
            area_hectares=2.0,
            geometry={"type": "Point", "coordinates": [-50.0, -10.0]},
            production_date=date(2024, 1, 1)
        )
    ]
    # Missing FPIC_CONSENT
    docs = [
        LegalDocumentInput(
            doc_id="DOC-1",
            doc_type=DocumentTypeEnum.LAND_USE_TITLE,
            issuing_authority="INCRA",
            issue_date=date(2022, 1, 1),
            expiry_date=date(2030, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-2",
            doc_type=DocumentTypeEnum.HARVEST_PERMIT,
            issuing_authority="IBAMA",
            issue_date=date(2023, 1, 1),
            expiry_date=date(2028, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-3",
            doc_type=DocumentTypeEnum.BUSINESS_LICENSE,
            issuing_authority="Federal Revenue",
            issue_date=date(2020, 1, 1)
        )
    ]
    result = LegalAuditor.audit_documents(docs, plots, reference_date=date(2024, 6, 1))
    assert result.country_risk_tier == RiskTierEnum.HIGH
    assert result.overall_compliant is False
    assert "FPIC_CONSENT" in result.missing_required_documents

def test_expired_harvest_permit():
    """Expired permit should fail legal audit."""
    plots = [
        ProductionPlotInput(
            plot_id="PLOT-GH-01",
            country_code="GH",
            area_hectares=2.0,
            geometry={"type": "Point", "coordinates": [-1.0, 6.0]},
            production_date=date(2024, 1, 1)
        )
    ]
    docs = [
        LegalDocumentInput(
            doc_id="DOC-TITLE",
            doc_type=DocumentTypeEnum.LAND_USE_TITLE,
            issuing_authority="Lands Commission",
            issue_date=date(2020, 1, 1),
            expiry_date=date(2030, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-EXPIRED-PERMIT",
            doc_type=DocumentTypeEnum.HARVEST_PERMIT,
            issuing_authority="Forestry Commission",
            issue_date=date(2021, 1, 1),
            expiry_date=date(2023, 1, 1)  # Expired relative to 2024
        ),
        LegalDocumentInput(
            doc_id="DOC-LIC",
            doc_type=DocumentTypeEnum.BUSINESS_LICENSE,
            issuing_authority="Registrar General",
            issue_date=date(2020, 1, 1)
        )
    ]
    result = LegalAuditor.audit_documents(docs, plots, reference_date=date(2024, 6, 1))
    assert result.overall_compliant is False
    assert len(result.expired_documents) > 0

def test_fully_compliant_documents():
    """All required valid documents for standard risk country should pass."""
    plots = [
        ProductionPlotInput(
            plot_id="PLOT-CI-01",
            country_code="CI",
            area_hectares=2.0,
            geometry={"type": "Point", "coordinates": [-5.0, 6.0]},
            production_date=date(2024, 1, 1)
        )
    ]
    docs = [
        LegalDocumentInput(
            doc_id="DOC-CI-TITLE",
            doc_type=DocumentTypeEnum.LAND_USE_TITLE,
            issuing_authority="Ministry of Agriculture",
            issue_date=date(2021, 1, 1),
            expiry_date=date(2035, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-CI-HARVEST",
            doc_type=DocumentTypeEnum.HARVEST_PERMIT,
            issuing_authority="Forestry Ministry",
            issue_date=date(2022, 1, 1),
            expiry_date=date(2027, 1, 1)
        ),
        LegalDocumentInput(
            doc_id="DOC-CI-LIC",
            doc_type=DocumentTypeEnum.BUSINESS_LICENSE,
            issuing_authority="Chamber of Commerce",
            issue_date=date(2020, 1, 1)
        )
    ]
    result = LegalAuditor.audit_documents(docs, plots, reference_date=date(2024, 6, 1))
    assert result.overall_compliant is True
    assert len(result.missing_required_documents) == 0
    assert len(result.expired_documents) == 0
