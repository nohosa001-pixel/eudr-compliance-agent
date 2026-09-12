import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.producer_adapters.brazil_car_adapter import BrazilCarAdapter
from app.modules.producer_adapters.ghana_cocoa_adapter import GhanaCocoaAdapter
from app.modules.producer_adapters.indonesia_timber_palm_adapter import IndonesiaTimberPalmAdapter
from app.modules.producer_adapters.registry_hub import ProducerCountryRegistryHub

client = TestClient(app)

SAMPLE_PAYLOAD = {
    "supplier_id": "SUPP-KFS-KR-001",
    "operator": {
        "operator_name": "Dongwha Enterprise Co., Ltd.",
        "eori_number": "KR123456789012",
        "country": "KR",
        "address": "Incheon, South Korea"
    },
    "commodity": {
        "hs_code": "440710",
        "description": "Coniferous wood sawn or chipped",
        "net_mass_kg": 12500.0
    },
    "execution_id": "BATCH-KFS-2026-TEST",
    "plots": [
        {
            "plot_id": "PLOT-KR-001",
            "country_code": "KR",
            "area_hectares": 5.2,
            "production_date": "2024-05-15",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [127.123456, 37.123456],
                        [127.124456, 37.123456],
                        [127.124456, 37.124456],
                        [127.123456, 37.124456],
                        [127.123456, 37.123456]
                    ]
                ]
            }
        }
    ],
    "documents": [
        {
            "doc_id": "DOC-TENURE-001",
            "doc_type": "LAND_USE_TITLE",
            "issuing_authority": "Korea Forest Service",
            "issue_date": "2021-01-10"
        },
        {
            "doc_id": "DOC-HARVEST-002",
            "doc_type": "HARVEST_PERMIT",
            "issuing_authority": "Gangwon Provincial Forestry Office",
            "issue_date": "2024-03-01"
        },
        {
            "doc_id": "DOC-ENV-003",
            "doc_type": "BUSINESS_LICENSE",
            "issuing_authority": "Ministry of Trade",
            "issue_date": "2022-05-15"
        }
    ],
    "suppliers": [
        {
            "supplier_id": "SUP-01",
            "name": "Gangwon Forestry Cooperative",
            "country": "KR"
        }
    ]
}


def test_brazil_car_adapter():
    adapter = BrazilCarAdapter()
    
    # Valid CAR
    valid_id = "MT-5107909-E9110B6BA7034B769399FF9915F79328"
    res = adapter.verify_registration(valid_id)
    assert res.is_valid is True
    assert res.status == "ACTIVE_AND_REGULAR"
    assert res.country_code == "BR"
    assert res.deforestation_infraction_flag is False

    # Embargoed CAR
    embargo_id = "PA-1500107-EMBARGO999999999999999999999999"
    res_emb = adapter.verify_registration(embargo_id)
    assert res_emb.is_valid is False
    assert "EMBARGO" in res_emb.status
    assert res_emb.deforestation_infraction_flag is True

    # Malformed CAR
    res_mal = adapter.verify_registration("INVALID-FORMAT")
    assert res_mal.is_valid is False
    assert res_mal.status == "INVALID_FORMAT"


def test_ghana_cocoa_adapter():
    adapter = GhanaCocoaAdapter()
    
    # Valid Cocoa ID
    res = adapter.verify_registration("GH-CMS-WNR-482019-01")
    assert res.is_valid is True
    assert res.country_code == "GH"
    assert res.status == "ACTIVE_CERTIFIED_COCOA_FARM"

    # Encroachment ID
    res_enc = adapter.verify_registration("GH-CMS-ASH-999000-01")
    assert res_enc.is_valid is False
    assert res_enc.status == "REJECTED_FOREST_RESERVE_ENCROACHMENT"


def test_indonesia_timber_palm_adapter():
    adapter = IndonesiaTimberPalmAdapter()
    
    # Valid SIPUHH Timber
    res_timber = adapter.verify_registration("ID-SIPUHH-RIU-8829102-A")
    assert res_timber.is_valid is True
    assert res_timber.country_code == "ID"
    assert "Timber" in res_timber.details["commodity"]

    # Peatland Violation
    res_peat = adapter.verify_registration("ID-ISPO-KTN-PEAT999999")
    assert res_peat.is_valid is False
    assert res_peat.status == "VIOLATION_PEATLAND_MORATORIUM"


def test_registry_hub_auto_routing():
    hub = ProducerCountryRegistryHub()
    
    # Auto-detect Brazil
    res_br = hub.verify("BR-MT-5107909-E9110B6BA7034B769399FF9915F79328")
    assert res_br.country_code == "BR"
    assert res_br.is_valid is True

    # Auto-detect Ghana
    res_gh = hub.verify("GH-CMS-ASH-102938-02")
    assert res_gh.country_code == "GH"
    assert res_gh.is_valid is True

    # Unsupported country
    res_un = hub.verify("XX-999999")
    assert res_un.is_valid is False
    assert res_un.status == "UNSUPPORTED_PRODUCER_REGISTRY"


def test_api_producer_registry_verify():
    resp = client.post(
        "/api/v1/compliance/producer-registry/verify",
        json={"identifier": "MT-5107909-E9110B6BA7034B769399FF9915F79328"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["country_code"] == "BR"
    assert data["is_valid"] is True
    assert data["status"] == "ACTIVE_AND_REGULAR"


def test_api_kfs_checklist_score():
    resp = client.post(
        "/api/v1/compliance/kfs-checklist/score",
        json={"payload": SAMPLE_PAYLOAD}
    )
    if resp.status_code != 200:
        print("KFS SCORE 422 ERROR:", resp.json())
    assert resp.status_code == 200
    data = resp.json()
    assert "framework_version" in data
    assert data["total_score"] >= 80.0
    assert data["compliance_tier"] == "PASS_COMPLIANT"
    assert len(data["items"]) == 4


def test_api_one_click_export_bundle_and_html_view():
    resp = client.post(
        "/api/v1/compliance/export-bundle/generate",
        json={
            "payload": SAMPLE_PAYLOAD,
            "producer_registry_id": "MT-5107909-E9110B6BA7034B769399FF9915F79328"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_cleared_for_eu_import"] is True
    assert data["overall_clearance_status"] == "CLEARED_FOR_EU_IMPORT"
    assert data["bundle_id"].startswith("EXP-BUNDLE-")
    assert "dossier_html_url" in data
    assert data["producer_registry_verification"] is not None
    assert data["kfs_checklist_assessment"]["total_score"] >= 80.0

    # Test HTML view endpoint
    bundle_id = data["bundle_id"]
    html_resp = client.get(f"/api/v1/compliance/export-bundle/{bundle_id}/html")
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "EUDR Official Due Diligence & Legal Defense Dossier" in html_resp.text
    assert bundle_id in html_resp.text
    assert "산림청(KFS) EUDR 4대 핵심 분야 표준 점검 결과" in html_resp.text
