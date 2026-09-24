"""
Unit and Integration Test Suite for Advanced EUDR Elevation Modules
- Article 29 Country Benchmarking (Low/Standard/High Risk Tiers & Article 13 Simplified Due Diligence)
- Article 4(8) Downstream Operator DDS Reference Chaining & Cascading Risk Monitor
- European Commission Delegated Act Sept 2026 Statutory Exemption Certificate
- Article 9 Smallholder Parcel Auto-Slicing & Sub-division Engine (<4ha closed ring safeguard)
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.country_benchmarking import CountryBenchmarkingService
from app.modules.downstream_chain_manager import DownstreamChainManager
from app.modules.statutory_exemption_issuer import StatutoryExemptionIssuer
from app.modules.parcel_slicing_engine import ParcelSlicingEngine
from app.schemas import (
    CountryBenchmarkingTierEnum,
    DownstreamChainRequest,
    StatutoryExemptionNoticeRequest,
    ParcelSlicingRequest
)

client = TestClient(app)


def test_country_benchmarking_service():
    """Verify Article 29 3-tier risk classification and Article 13 simplified status."""
    # 1. Low Risk (South Korea, Germany, US)
    kr_res = CountryBenchmarkingService.get_benchmarking("KR")
    assert kr_res.risk_tier == CountryBenchmarkingTierEnum.LOW
    assert kr_res.customs_inspection_rate_pct == 1.0
    assert kr_res.simplified_due_diligence_eligible is True
    assert kr_res.risk_assessment_required is False
    assert kr_res.risk_mitigation_required is False
    assert kr_res.mandatory_fpic_required is False

    de_res = CountryBenchmarkingService.get_benchmarking("DE")
    assert de_res.risk_tier == CountryBenchmarkingTierEnum.LOW
    assert de_res.customs_inspection_rate_pct == 1.0
    assert de_res.simplified_due_diligence_eligible is True

    # 2. Standard Risk (Vietnam, Indonesia, Ghana)
    vn_res = CountryBenchmarkingService.get_benchmarking("VN")
    assert vn_res.risk_tier == CountryBenchmarkingTierEnum.STANDARD
    assert vn_res.customs_inspection_rate_pct == 3.0
    assert vn_res.simplified_due_diligence_eligible is False
    assert vn_res.risk_assessment_required is True

    # 3. High Risk (Brazil, Myanmar, Belarus)
    br_res = CountryBenchmarkingService.get_benchmarking("BR")
    assert br_res.risk_tier == CountryBenchmarkingTierEnum.HIGH
    assert br_res.customs_inspection_rate_pct == 9.0
    assert br_res.mandatory_fpic_required is True
    assert br_res.mandatory_radar_cross_check is True

    # 4. Unknown country defaults to STANDARD
    unk_res = CountryBenchmarkingService.get_benchmarking("ZZ")
    assert unk_res.risk_tier == CountryBenchmarkingTierEnum.STANDARD
    assert unk_res.customs_inspection_rate_pct == 3.0


def test_downstream_chain_manager_registration_and_health():
    """Verify downstream operator pass-through reference registration and cascade tracking."""
    req = DownstreamChainRequest(
        downstream_operator_name="EuroChocolate Manufacturers B.V.",
        downstream_operator_eori="NL8877665544",
        commodity_code="1806",
        commodity_description="Finished Confectionery Chocolate",
        net_mass_kg=12500.0,
        upstream_dds_references=[
            "EU.DDS.2026.CI-COCOA-LOT01",
            "EU.DDS.2026.GH-COCOA-LOT02"
        ],
        manufacturing_country="NL"
    )

    res = DownstreamChainManager.register_downstream_chain(req)
    assert res.chain_reference_id.startswith("CHAIN-EUDR-")
    assert res.downstream_dds_id.startswith("EU.DDS.DS.")
    assert res.upstream_dds_count == 2
    assert res.cascade_risk_status == "CLEAN_UPSTREAM"
    assert res.is_cleared_for_eu_free_circulation is True
    assert "verify-chain" in res.customs_chain_qr_url

    # Check health of valid chain
    health = DownstreamChainManager.check_cascade_health(res.chain_reference_id)
    assert health["cascade_risk_status"] == "CLEAN_UPSTREAM"
    assert health["is_safe"] is not False


def test_downstream_chain_revoked_upstream_triggers_alert():
    """Verify that a tainted/revoked upstream DDS immediately triggers a cascade risk alert."""
    req_tainted = DownstreamChainRequest(
        downstream_operator_name="European Furniture Factory GmbH",
        downstream_operator_eori="DE9988776655",
        commodity_code="9403",
        commodity_description="Wooden Dining Tables",
        net_mass_kg=4500.0,
        upstream_dds_references=[
            "EU.DDS.2025.TAINTED-001"  # Known revoked reference
        ],
        manufacturing_country="DE"
    )

    res = DownstreamChainManager.register_downstream_chain(req_tainted)
    assert res.cascade_risk_status == "REVOKED_ALERT"
    assert res.is_cleared_for_eu_free_circulation is False


def test_statutory_exemption_issuer():
    """Verify official Statutory Exemption Certificate generation for bovine leather (HS 4101/4104/4107)."""
    # 1. Exempted bovine leather
    req_leather = StatutoryExemptionNoticeRequest(
        hs_code="4107.12.00",
        product_description="Grain Splits Bovine Leather for Automotive Interior",
        importer_name="Bavaria Auto Components AG",
        importer_eori="DE4455667788",
        origin_country="BR",
        b_l_number="MSCU987654321"
    )

    res = StatutoryExemptionIssuer.issue_certificate(req_leather)
    assert res.is_exempt_from_eudr is True
    assert res.scrutiny_period_completion_date == "2026-09-14"
    assert "FORMAL EXEMPTION CONFIRMED" in res.official_customs_advice
    assert res.certificate_id.startswith("EU-EXEMPT-CERT-")

    # 2. Non-exempt commodity (Coffee 0901)
    req_coffee = StatutoryExemptionNoticeRequest(
        hs_code="0901.11.00",
        product_description="Green Coffee Beans",
        importer_name="Hamburg Coffee Importers",
        importer_eori="DE1122334455",
        origin_country="CO"
    )
    res_coffee = StatutoryExemptionIssuer.issue_certificate(req_coffee)
    assert res_coffee.is_exempt_from_eudr is False
    assert "NOT exempt" in res_coffee.official_customs_advice

    # 3. HTML certificate output
    html = StatutoryExemptionIssuer.generate_html_certificate(
        cert_id="EU-EXEMPT-001",
        hs_code="4107.12.00",
        importer_name="Bavaria Auto Components AG"
    )
    assert "STATUTORILY EXEMPT (ANNEX I DELETED)" in html
    assert "September 14, 2026" in html
    assert "EU Single Window Environment for Customs" in html


def test_parcel_slicing_engine():
    """Verify auto-slicing of oversized (>4ha) aggregated smallholder polygons into compliant sub-parcels."""
    # Aggregated 12.0 ha rectangular polygon in Vietnam
    poly_geom = {
        "type": "Polygon",
        "coordinates": [[
            [108.000000, 12.000000],
            [108.004000, 12.000000],
            [108.004000, 12.003000],
            [108.000000, 12.003000],
            [108.000000, 12.000000]
        ]]
    }

    req = ParcelSlicingRequest(
        parent_plot_id="COOP-VN-DAKLAK-01",
        country_code="VN",
        declared_area_ha=12.0,
        geometry=poly_geom,
        target_parcel_max_ha=3.5
    )

    res = ParcelSlicingEngine.slice_aggregated_plot(req)
    assert res.parent_plot_id == "COOP-VN-DAKLAK-01"
    assert res.original_area_ha == 12.0
    assert res.slices_count >= 4  # 12.0 / 3.5 requires at least 4 slices
    assert res.all_slices_under_4ha is True

    for p in res.sliced_parcels:
        assert p.area_hectares < 4.0
        assert p.coordinates_precision == 6
        assert p.is_closed_ring is True
        assert len(p.centroid) == 2
        # Verify first and last coords match
        coords = p.geometry["coordinates"][0]
        assert coords[0] == coords[-1]

    # FeatureCollection verification
    fc = res.traces_geojson_feature_collection
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == res.slices_count


def test_api_elevation_endpoints():
    """Verify FastAPI integration for the 4 elevated EUDR endpoints."""
    # 1. Benchmarking API
    res1 = client.get("/api/v1/eudr/benchmarking/KR")
    assert res1.status_code == 200
    assert res1.json()["risk_tier"] == "LOW"
    assert res1.json()["customs_inspection_rate_pct"] == 1.0

    res_br = client.get("/api/v1/eudr/benchmarking/BR")
    assert res_br.status_code == 200
    assert res_br.json()["risk_tier"] == "HIGH"
    assert res_br.json()["customs_inspection_rate_pct"] == 9.0

    # 2. Downstream Chaining API
    chain_payload = {
        "downstream_operator_name": "Antwerp Roasters S.A.",
        "downstream_operator_eori": "BE123456789",
        "commodity_code": "090121",
        "commodity_description": "Roasted Decaffeinated Coffee",
        "net_mass_kg": 2000.0,
        "upstream_dds_references": ["EU.DDS.2026.CO-COFFEE-01"],
        "manufacturing_country": "BE"
    }
    res2 = client.post("/api/v1/eudr/downstream/chain-dds", json=chain_payload)
    assert res2.status_code == 200
    cdata = res2.json()
    assert cdata["cascade_risk_status"] == "CLEAN_UPSTREAM"
    chain_id = cdata["chain_reference_id"]

    # 3. Downstream Health API
    res3 = client.get(f"/api/v1/eudr/downstream/chain/{chain_id}/status")
    assert res3.status_code == 200
    assert res3.json()["cascade_risk_status"] == "CLEAN_UPSTREAM"

    # 4. Statutory Exemption Certificate API
    exempt_payload = {
        "hs_code": "4104.11.00",
        "product_description": "Wet Blue Tanned Bovine Hides",
        "importer_name": "Italian Leather Group S.p.A.",
        "importer_eori": "IT99887766",
        "origin_country": "BR"
    }
    res4 = client.post("/api/v1/eudr/exemption/certificate", json=exempt_payload)
    assert res4.status_code == 200
    assert res4.json()["is_exempt_from_eudr"] is True

    # 5. HTML Certificate API
    res5 = client.get("/api/v1/eudr/exemption/certificate/html?hs=4104.11.00&importer=Italian+Leather+Group")
    assert res5.status_code == 200
    assert "Statutory Exemption Certificate" in res5.text

    # 6. Parcel Slicing API
    slice_payload = {
        "parent_plot_id": "COOP-ID-SUMATRA-99",
        "country_code": "ID",
        "declared_area_ha": 9.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [101.500000, 0.500000],
                [101.503000, 0.500000],
                [101.503000, 0.503000],
                [101.500000, 0.503000],
                [101.500000, 0.500000]
            ]]
        },
        "target_parcel_max_ha": 3.0
    }
    res6 = client.post("/api/v1/spatial/slice-aggregated-plot", json=slice_payload)
    assert res6.status_code == 200
    sdata = res6.json()
    assert sdata["slices_count"] >= 3
    assert sdata["all_slices_under_4ha"] is True
