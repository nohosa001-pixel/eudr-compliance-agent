import pytest
from datetime import date
from app.schemas import ProductionPlotInput, SpatialPlotResult
from app.modules.satellite_compliance_checker import DeforestationAnalyzer

def test_clean_plot_deforestation_free():
    """Stable canopy plot should pass deforestation-free check."""
    plot = ProductionPlotInput(
        plot_id="PLOT-CLEAN-01",
        country_code="ID",
        area_hectares=3.0,
        geometry={"type": "Point", "coordinates": [102.0, 1.0]},
        production_date=date(2024, 2, 1)
    )
    spatial_res = SpatialPlotResult(
        plot_id="PLOT-CLEAN-01",
        is_valid=True,
        geometry_type="Point",
        declared_area_ha=3.0,
        is_polygon_required=False
    )
    sat_res = DeforestationAnalyzer.analyze_plot(plot, spatial_res)
    assert sat_res.compliance_passed is True
    assert sat_res.deforestation_detected is False

def test_post_2020_deforestation_flagged():
    """Plot with forest loss in 2022 (after 2020-12-31 cutoff) must be flagged DEFORESTATION_DETECTED."""
    plot = ProductionPlotInput(
        plot_id="PLOT-FAIL-deforestation_2022",
        country_code="BR",
        area_hectares=10.0,
        geometry={"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]},
        production_date=date(2024, 2, 1),
        notes="Satellite alert: deforestation_2022"
    )
    spatial_res = SpatialPlotResult(
        plot_id=plot.plot_id,
        is_valid=True,
        geometry_type="Polygon",
        declared_area_ha=10.0,
        is_polygon_required=True
    )
    sat_res = DeforestationAnalyzer.analyze_plot(plot, spatial_res)
    assert sat_res.compliance_passed is False
    assert sat_res.deforestation_detected is True
    assert sat_res.forest_loss_year == 2022
    assert "NON-COMPLIANT" in sat_res.audit_notes

def test_pre_2020_historical_loss_compliant():
    """Plot with historical clearance before 2020-12-31 (e.g. 2018) complies with EUDR cutoff date."""
    plot = ProductionPlotInput(
        plot_id="PLOT-HISTORIC-deforestation_2018",
        country_code="CI",
        area_hectares=2.0,
        geometry={"type": "Point", "coordinates": [-5.0, 6.0]},
        production_date=date(2024, 2, 1),
        notes="deforestation_2018"
    )
    spatial_res = SpatialPlotResult(
        plot_id=plot.plot_id,
        is_valid=True,
        geometry_type="Point",
        declared_area_ha=2.0,
        is_polygon_required=False
    )
    sat_res = DeforestationAnalyzer.analyze_plot(plot, spatial_res)
    assert sat_res.compliance_passed is True
    assert sat_res.deforestation_detected is False
    assert sat_res.forest_loss_year == 2018
    assert "Pre-2020 conversion" in sat_res.audit_notes


# ---------------------------------------------------------------------------
# Copernicus CDSE / Sentinel Hub Live Account Mode & Resilience Tests
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock
from app.modules.satellite_providers.copernicus_sentinel_client import CopernicusSentinelClient
from app.core.config import settings


def test_copernicus_oauth2_token_caching():
    """Verify CDSE OAuth2 token exchange and in-memory caching."""
    CopernicusSentinelClient._token_cache.clear()
    
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {
        "access_token": "mock-cdse-jwt-token-12345",
        "expires_in": 3600
    }

    with patch("httpx.Client.post", return_value=mock_token_resp) as mock_post:
        token1 = CopernicusSentinelClient.get_access_token("test-client-id", "test-secret")
        assert token1 == "mock-cdse-jwt-token-12345"
        assert mock_post.call_count == 1

        # Second call should use cache without HTTP request
        token2 = CopernicusSentinelClient.get_access_token("test-client-id", "test-secret")
        assert token2 == "mock-cdse-jwt-token-12345"
        assert mock_post.call_count == 1


def test_copernicus_live_statistics_response_parsing():
    """Verify parsing of ESA Sentinel Hub Statistical API multi-year payload."""
    raw_stat_response = {
        "data": [
            {
                "interval": {"from": "2019-01-01T00:00:00Z", "to": "2019-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.8123, "stDev": 0.04}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.4789, "stDev": 0.02}}}}
                }
            },
            {
                "interval": {"from": "2020-01-01T00:00:00Z", "to": "2020-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.8245, "stDev": 0.03}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.4850, "stDev": 0.02}}}}
                }
            },
            {
                "interval": {"from": "2021-01-01T00:00:00Z", "to": "2021-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.8090, "stDev": 0.04}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.4710, "stDev": 0.03}}}}
                }
            },
            {
                "interval": {"from": "2024-01-01T00:00:00Z", "to": "2024-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.8200, "stDev": 0.03}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.4800, "stDev": 0.02}}}}
                }
            }
        ]
    }

    parsed = CopernicusSentinelClient.parse_statistics_response(raw_stat_response)
    
    assert parsed["ndvi_time_series"]["2019"] == 0.81
    assert parsed["ndvi_time_series"]["2020"] == 0.82
    assert parsed["ndvi_time_series"]["2024"] == 0.82
    assert parsed["ndmi_moisture_index"] == 0.48
    assert parsed["canopy_stability"] == "STABLE_HIGH_DENSITY"


def test_copernicus_live_account_query_success():
    """Verify live account workflow with authenticated Copernicus CDSE API response."""
    geom = {"type": "Point", "coordinates": [101.5, 0.5]}

    mock_stat_resp = MagicMock()
    mock_stat_resp.status_code = 200
    mock_stat_resp.json.return_value = {
        "data": [
            {
                "interval": {"from": "2020-01-01T00:00:00Z", "to": "2020-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.83}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.50}}}}
                }
            },
            {
                "interval": {"from": "2024-01-01T00:00:00Z", "to": "2024-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.82}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.49}}}}
                }
            }
        ]
    }

    with patch.object(CopernicusSentinelClient, "get_access_token", return_value="mock-token"):
        with patch("httpx.Client.post", return_value=mock_stat_resp):
            res = CopernicusSentinelClient.query_time_series_trajectory(
                geometry=geom,
                client_id="cdse-live-user",
                client_secret="cdse-live-secret"
            )

            assert res["is_live_data"] is True
            assert "Copernicus CDSE Live" in res["provider"]
            assert res["ndvi_time_series"]["2020"] == 0.83
            assert res["canopy_stability"] == "STABLE_HIGH_DENSITY"


def test_copernicus_network_error_graceful_fallback():
    """Verify graceful fallback to local deterministic simulator when CDSE API fails or credentials invalid."""
    geom = {"type": "Point", "coordinates": [101.5, 0.5]}

    # Simulate 401 Unauthorized or network timeout
    with patch.object(CopernicusSentinelClient, "get_access_token", return_value=None):
        res = CopernicusSentinelClient.query_time_series_trajectory(
            geometry=geom,
            client_id="invalid-client",
            client_secret="invalid-secret"
        )

        assert res["is_live_data"] is False
        assert "Statistical Service" in res["provider"]
        assert "ndvi_time_series" in res
        assert "2020" in res["ndvi_time_series"]


def test_copernicus_deforestation_drop_detection():
    """Verify live API detecting post-2020 forest clearance from NDVI collapse."""
    raw_deforested_resp = {
        "data": [
            {
                "interval": {"from": "2020-01-01T00:00:00Z", "to": "2020-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.82}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.52}}}}
                }
            },
            {
                "interval": {"from": "2024-01-01T00:00:00Z", "to": "2024-12-31T23:59:59Z"},
                "outputs": {
                    "ndvi": {"bands": {"B0": {"stats": {"mean": 0.45}}}},
                    "ndmi": {"bands": {"B0": {"stats": {"mean": 0.18}}}}
                }
            }
        ]
    }

    parsed = CopernicusSentinelClient.parse_statistics_response(raw_deforested_resp)
    assert parsed["canopy_stability"] == "DEFORESTATION_DETECTED"
    assert parsed["ndvi_time_series"]["2024"] == 0.45
