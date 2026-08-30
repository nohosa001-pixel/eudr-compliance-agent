from fastapi.testclient import TestClient
from app.main import app
from app.modules.golden_benchmark import GoldenBenchmarkSuite
from app.modules.satellite_providers.jrc_forest_cover_provider import JRCBaselineProvider
from app.modules.satellite_providers.planet_nicfi_provider import PlanetNICFIProvider
from app.modules.traceability_collector import TraceabilityCollector, SpatialValidator
from app.schemas import ProductionPlotInput, ReviewStatusEnum

client = TestClient(app)

def test_pillar1_jrc_and_planet_providers():
    """Pillar 1: Multi-source satellite verification providers."""
    jrc = JRCBaselineProvider.query_jrc_baseline_status(108.44, 11.94, "VN")
    assert jrc["forest_present_2020"] is True
    assert jrc["resolution_m"] == 10.0
    assert "JRC" in jrc["provider"]

    planet = PlanetNICFIProvider.query_nicfi_metadata(108.44, 11.94)
    assert planet["resolution_m"] == 4.77
    assert planet["visual_confidence_score"] > 0.8
    assert "PlanetScope" in planet["provider"]

def test_pillar2_spatial_overlap_collision_detection():
    """Pillar 2: OGC inter-plot collision / dual claim prevention."""
    plots = [
        ProductionPlotInput(
            plot_id="PLOT-COLLISION-1",
            country_code="MY",
            area_hectares=5.0,
            geometry={
                "type": "Polygon",
                "coordinates": [[[101.40, 3.10], [101.45, 3.10], [101.45, 3.15], [101.40, 3.15], [101.40, 3.10]]]
            },
            production_date="2024-01-01"
        ),
        ProductionPlotInput(
            plot_id="PLOT-COLLISION-2",
            country_code="MY",
            area_hectares=5.0,
            geometry={
                "type": "Polygon",
                "coordinates": [[[101.42, 3.12], [101.47, 3.12], [101.47, 3.17], [101.42, 3.17], [101.42, 3.12]]]
            },
            production_date="2024-01-01"
        )
    ]
    all_valid, results, summary = TraceabilityCollector.collect_and_validate(plots)
    assert summary["overlapping_plots_count"] == 2
    assert results[0].overlap_detected is True
    assert "PLOT-COLLISION-2" in results[0].overlapping_plot_ids

def test_pillar3_cryptographic_evidence_bundle_endpoint():
    """Pillar 3: Non-repudiation cryptographic evidence bundle generated in evaluate endpoint."""
    payload = {
        "supplier_id": "SUPP-EVIDENCE-TEST",
        "operator": {"operator_name": "Evidence Test Corp", "eori_number": "FR1122334455", "country": "FR", "address": "Paris"},
        "commodity": {"hs_code": "090111", "description": "Coffee beans", "net_mass_kg": 10000.0},
        "plots": [{
            "plot_id": "PLOT-EV-1", "country_code": "VN", "area_hectares": 2.0,
            "geometry": {"type": "Point", "coordinates": [108.438, 11.940]}, "production_date": "2024-01-01"
        }],
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "VN Land", "issue_date": "2020-01-01"}
        ]
    }
    res = client.post("/api/v1/eudr/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "evidence_bundle" in data
    bundle = data["evidence_bundle"]
    assert bundle is not None
    assert bundle["non_repudiation_status"] == "IMMUTABLE_AND_VERIFIED"
    assert len(bundle["sha256_input_payload"]) == 64
    assert len(bundle["digital_signature_hmac_sha256"]) == 64
    assert len(bundle["satellite_telemetry_manifest"]) == 1

def test_pillar4_confidence_assessment_and_hitl_review():
    """Pillar 4: Confidence scoring and HITL expert review sign-off."""
    review_req = {
        "execution_id": "exec-hitl-test-99",
        "decision": "EXPERT_APPROVED",
        "expert_name": "Dr. Hans Mueller, Senior GIS Auditor",
        "expert_notes": "Cloud shadow artifact manually verified via PlanetScope NICFI 4.77m imagery. No true forest loss.",
        "override_reason": "False Positive due to cloud edge artifact"
    }
    res = client.post("/api/v1/eudr/hitl/review", json=review_req)
    assert res.status_code == 200
    data = res.json()
    assert data["review_status"] == "EXPERT_APPROVED"
    assert data["new_status"] == "COMPLIANT"
    assert "Dr. Hans Mueller" in data["reviewed_by"]

def test_pillar5_golden_benchmark_execution():
    """Pillar 5: Golden Benchmark suite 10 cases execution and 100% accuracy validation."""
    report = GoldenBenchmarkSuite.run_suite()
    assert report.total_cases == 10
    assert report.passed_cases == 10
    assert report.accuracy_pct == 100.0
    assert report.precision_pct == 100.0
    assert report.recall_pct == 100.0
    assert report.f1_score == 1.0

    # Test API Endpoint
    api_res = client.get("/api/v1/eudr/benchmark/run")
    assert api_res.status_code == 200
    api_data = api_res.json()
    assert api_data["accuracy_pct"] == 100.0
    assert len(api_data["case_results"]) == 10
