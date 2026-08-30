import pytest
from starlette.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.schemas import (
    EUDRSupplyChainPayload,
    OperatorInfo,
    CommodityInfo,
    ProductionPlotInput,
    LegalDocumentInput,
    ComplianceStatusEnum
)
from app.modules.report_i18n import ReportLanguage, get_i18n_dict, get_supported_languages
from app.modules.dds_generator import DDSGenerator
from app.modules.spatial_validator import SpatialValidator
from app.modules.traceability_collector import TraceabilityCollector
from app.modules.deforestation_simulator import DeforestationSimulator
from app.modules.legal_document_auditor import LegalAuditor


client = TestClient(app)


@pytest.fixture
def sample_payload():
    return EUDRSupplyChainPayload(
        supplier_id="SUPP-MULTI-LANG-01",
        operator=OperatorInfo(
            operator_name="Global Sustainable Commodities BV",
            eori_number="NL123456789000",
            country="NL",
            address="Keizersgracht 100, Amsterdam"
        ),
        commodity=CommodityInfo(
            hs_code="180100",
            description="Cocoa beans, whole or broken, raw",
            net_mass_kg=25000.0
        ),
        plots=[
            ProductionPlotInput(
                plot_id="PLOT-GH-001",
                country_code="GH",
                area_hectares=3.2,
                geometry={
                    "type": "Point",
                    "coordinates": [-1.6244, 6.6885]
                },
                production_date="2024-02-15"
            )
        ],
        documents=[
            LegalDocumentInput(
                doc_id="DOC-GH-01",
                doc_type="LAND_USE_TITLE",
                issuing_authority="Lands Commission Ghana",
                issue_date="2021-01-01"
            ),
            LegalDocumentInput(
                doc_id="DOC-GH-02",
                doc_type="HARVEST_PERMIT",
                issuing_authority="Forestry Commission",
                issue_date="2023-01-01",
                expiry_date="2026-12-31"
            ),
            LegalDocumentInput(
                doc_id="DOC-GH-03",
                doc_type="BUSINESS_LICENSE",
                issuing_authority="Registrar General",
                issue_date="2020-01-01"
            )
        ]
    )


def test_i18n_dictionary_coverage():
    """Validates that all supported languages have all required translation keys."""
    supported = get_supported_languages()
    assert len(supported) >= 6
    assert "en" in supported
    assert "ko" in supported
    assert "fr" in supported
    assert "es" in supported
    assert "de" in supported
    assert "pt" in supported

    base_keys = set(get_i18n_dict("en").keys())
    for lang in supported.keys():
        lang_dict = get_i18n_dict(lang)
        missing_keys = base_keys - set(lang_dict.keys())
        assert len(missing_keys) == 0, f"Language '{lang}' missing keys: {missing_keys}"


def test_multi_language_html_report_generation(sample_payload):
    """Tests generating HTML reports across EN, KO, FR, ES, DE, PT."""
    start_time = datetime.now(timezone.utc)
    
    # Run evaluation modules
    spatial_valid, spatial_results, spatial_summary = TraceabilityCollector.collect_and_validate(sample_payload.plots)
    deforest_free, sat_results, sat_summary = DeforestationSimulator.analyze_all_plots(sample_payload.plots, spatial_results)
    legal_res = LegalAuditor.audit_documents(sample_payload.documents, sample_payload.plots, sample_payload.commodity)

    report = DDSGenerator.assemble_report(
        payload=sample_payload,
        spatial_valid=spatial_valid,
        spatial_results=spatial_results,
        spatial_summary=spatial_summary,
        deforestation_free=deforest_free,
        satellite_results=sat_results,
        satellite_summary=sat_summary,
        legal_audit=legal_res,
        start_time=start_time
    )

    # 1. English (Default)
    html_en = DDSGenerator.generate_html_report(report, lang="en")
    assert "EUDR Due Diligence Audit Report" in html_en
    assert "COMPLIANT" in html_en
    assert "DEFOREST-FREE" in html_en

    # 2. Korean
    html_ko = DDSGenerator.generate_html_report(report, lang="ko")
    assert "EUDR 공급망 실사 종합 감사 보고서" in html_ko
    assert "적합 (COMPLIANT)" in html_ko
    assert "무벌채 확인" in html_ko

    # 3. French
    html_fr = DDSGenerator.generate_html_report(report, lang="fr")
    assert "Rapport d'Audit de Diligence Raisonnée EUDR" in html_fr
    assert "CONFORME" in html_fr
    assert "SANS DÉFORESTATION" in html_fr

    # 4. Spanish
    html_es = DDSGenerator.generate_html_report(report, lang="es")
    assert "Informe de Auditoría de Diligencia Debida EUDR" in html_es
    assert "CONFORME" in html_es
    assert "LIBRE DE DEFORESTACIÓN" in html_es

    # 5. German
    html_de = DDSGenerator.generate_html_report(report, lang="de")
    assert "EUDR Sorgfaltspflicht-Auditbericht" in html_de
    assert "KONFORM" in html_de
    assert "ENTWALDUNGSFREI" in html_de

    # 6. Portuguese
    html_pt = DDSGenerator.generate_html_report(report, lang="pt")
    assert "Relatório de Auditoria de Diligência Prévia EUDR" in html_pt
    assert "CONFORME" in html_pt
    assert "LIVRE DE DESMATAMENTO" in html_pt


def test_api_supported_languages_endpoint():
    """Tests GET /api/v1/eudr/report/languages endpoint."""
    response = client.get("/api/v1/eudr/report/languages")
    assert response.status_code == 200
    data = response.json()
    assert "en" in data
    assert "ko" in data
    assert "fr" in data
    assert "es" in data
    assert "de" in data
    assert "pt" in data


def test_api_evaluate_html_report_with_lang_param(sample_payload):
    """Tests POST /api/v1/eudr/evaluate/html-report with lang query param."""
    # Test KO
    resp_ko = client.post(
        "/api/v1/eudr/evaluate/html-report?lang=ko",
        json=sample_payload.model_dump(mode="json")
    )
    assert resp_ko.status_code == 200
    assert "text/html" in resp_ko.headers["content-type"]
    assert "EUDR 공급망 실사 종합 감사 보고서" in resp_ko.text

    # Test FR
    resp_fr = client.post(
        "/api/v1/eudr/evaluate/html-report?lang=fr",
        json=sample_payload.model_dump(mode="json")
    )
    assert resp_fr.status_code == 200
    assert "Rapport d'Audit de Diligence Raisonnée EUDR" in resp_fr.text


def test_api_history_html_report_endpoint(sample_payload):
    """Tests GET /api/v1/eudr/history/{execution_id}/html-report endpoint."""
    # 1. First run evaluation to persist to DB
    eval_resp = client.post("/api/v1/eudr/evaluate", json=sample_payload.model_dump(mode="json"))
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    exec_id = eval_data["execution_id"]
    assert exec_id is not None

    # 2. Retrieve history HTML in Spanish
    hist_html_resp = client.get(f"/api/v1/eudr/history/{exec_id}/html-report?lang=es")
    assert hist_html_resp.status_code == 200
    assert "text/html" in hist_html_resp.headers["content-type"]
    assert "Informe de Auditoría de Diligencia Debida EUDR" in hist_html_resp.text
