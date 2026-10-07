"""
Unit & Integration Tests for EUDR Article 2(5) Forest Degradation Detection.
=============================================================================
Validates:
1. Detection of Primary/Old-Growth forest conversion into commercial plantation.
2. Compliance of sustainably managed natural forests (multi-tier canopy preserved).
3. Batch evaluation API and statutory Article 2(5) infraction flags.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.modules.forest_degradation_detector import ForestDegradationDetector
from app.schemas import ProductionPlotInput

client = TestClient(app)


def test_primary_forest_to_plantation_degradation_detected():
    """Validates that converting primary forest to commercial plantation triggers degradation infraction."""
    plot = ProductionPlotInput(
        plot_id="DEGRADE-SARAWAK-001",
        country_code="MY",
        area_hectares=15.0,
        geometry={
            "type": "Polygon",
            "coordinates": [[[113.50, 3.20], [113.52, 3.20], [113.52, 3.22], [113.50, 3.22], [113.50, 3.20]]]
        },
        production_date=date(2024, 4, 1),
        notes="degradation_primary_to_plantation"
    )

    res = ForestDegradationDetector.assess_plot_degradation(plot, commodity="WOOD")
    assert res.degradation_detected is True
    assert res.article2_5_infraction is True
    assert res.degradation_category == "PRIMARY_TO_PLANTATION_CONVERSION"
    assert res.primary_forest_conversion_flag is True
    assert res.canopy_heterogeneity_score < 0.3


def test_natural_forest_clean_preservation():
    """Validates that unbroken natural forest without plantation conversion is deemed degradation-free."""
    plot = ProductionPlotInput(
        plot_id="CLEAN-FINLAND-TAIGA-001",
        country_code="FI",
        area_hectares=20.0,
        geometry={
            "type": "Polygon",
            "coordinates": [[[27.10, 62.50], [27.12, 62.50], [27.12, 62.52], [27.10, 62.52], [27.10, 62.50]]]
        },
        production_date=date(2024, 2, 1),
        notes="fsc_certified_continuous_cover"
    )

    res = ForestDegradationDetector.assess_plot_degradation(plot, commodity="WOOD")
    assert res.degradation_detected is False
    assert res.article2_5_infraction is False
    assert res.canopy_heterogeneity_score > 0.7


def test_api_batch_degradation_assessment_endpoint():
    """Validates FastAPI REST endpoint for batch degradation screening."""
    payload = {
        "commodity": "WOOD",
        "plots": [
            {
                "plot_id": "PLOT-BATCH-CLEAN",
                "country_code": "VN",
                "area_hectares": 5.0,
                "geometry": {"type": "Point", "coordinates": [108.43, 11.94]},
                "production_date": "2024-03-01",
                "notes": "clean"
            },
            {
                "plot_id": "PLOT-BATCH-DEGRADED",
                "country_code": "ID",
                "area_hectares": 12.0,
                "geometry": {"type": "Point", "coordinates": [101.50, 0.50]},
                "production_date": "2024-03-01",
                "notes": "degradation_primary_to_plantation"
            }
        ]
    }

    resp = client.post("/api/v1/compliance/forest-degradation/assess", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_plots_assessed"] == 2
    assert data["degradation_free_count"] == 1
    assert data["degradation_infractions_count"] == 1
    assert data["overall_degradation_compliant"] is False
    assert "Article 2(5)" in data["statutory_article"]
