import pytest
from datetime import date
from app.schemas import ProductionPlotInput
from app.modules.traceability_collector import SpatialValidator, TraceabilityCollector

def test_valid_small_point_plot():
    """Plot < 4 ha with valid Point coordinates should pass."""
    plot = ProductionPlotInput(
        plot_id="PLOT-PT-001",
        country_code="ID",
        area_hectares=2.5,
        geometry={
            "type": "Point",
            "coordinates": [101.500000, 0.500000]  # [lon, lat]
        },
        production_date=date(2024, 5, 10),
        producer_name="Smallholder Farm A"
    )
    result = SpatialValidator.validate_plot(plot)
    assert result.is_valid is True
    assert result.geometry_type == "Point"
    assert result.is_polygon_required is False
    assert len(result.errors) == 0
    assert result.standardized_geojson is not None

def test_large_plot_point_violation():
    """Plot >= 4 ha with Point geometry must be flagged as violation."""
    plot = ProductionPlotInput(
        plot_id="PLOT-PT-INVALID",
        country_code="BR",
        area_hectares=12.0,  # >= 4.0 ha
        geometry={
            "type": "Point",
            "coordinates": [-55.0, -12.0]
        },
        production_date=date(2024, 6, 1)
    )
    result = SpatialValidator.validate_plot(plot)
    assert result.is_valid is False
    assert result.is_polygon_required is True
    assert any("strictly requires a Polygon" in err for err in result.errors)

def test_valid_polygon_plot():
    """Valid polygon with area >= 4ha should pass and compute geodesic area."""
    poly_coords = [
        [
            [100.0, 0.0],
            [100.01, 0.0],
            [100.01, 0.01],
            [100.0, 0.01],
            [100.0, 0.0]
        ]
    ]
    plot = ProductionPlotInput(
        plot_id="PLOT-POLY-001",
        country_code="ID",
        area_hectares=120.0,
        geometry={
            "type": "Polygon",
            "coordinates": poly_coords
        },
        production_date=date(2024, 6, 1)
    )
    result = SpatialValidator.validate_plot(plot)
    assert result.is_valid is True
    assert result.geometry_type == "Polygon"
    assert result.calculated_area_ha is not None
    assert result.calculated_area_ha > 100.0

def test_valid_multipolygon_plot():
    """Valid MultiPolygon geometry should pass and aggregate area across parts."""
    multi_coords = [
        # Polygon 1
        [
            [[10.0, 0.0], [10.01, 0.0], [10.01, 0.01], [10.0, 0.01], [10.0, 0.0]]
        ],
        # Polygon 2
        [
            [[10.02, 0.0], [10.03, 0.0], [10.03, 0.01], [10.02, 0.01], [10.02, 0.0]]
        ]
    ]
    plot = ProductionPlotInput(
        plot_id="PLOT-MULTI-001",
        country_code="CI",
        area_hectares=240.0,
        geometry={
            "type": "MultiPolygon",
            "coordinates": multi_coords
        },
        production_date=date(2024, 5, 1)
    )
    result = SpatialValidator.validate_plot(plot)
    assert result.is_valid is True
    assert result.geometry_type == "MultiPolygon"
    assert result.calculated_area_ha > 200.0

def test_self_intersecting_polygon():
    """Self-intersecting polygon (bowtie) should fail raw topological validation without auto-heal, and heal successfully with auto_heal."""
    bowtie_coords = [
        [
            [0.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [1.0, 0.0],
            [0.0, 0.0]
        ]
    ]
    plot = ProductionPlotInput(
        plot_id="PLOT-POLY-BOWTIE",
        country_code="BR",
        area_hectares=5.0,
        geometry={
            "type": "Polygon",
            "coordinates": bowtie_coords
        },
        production_date=date(2024, 6, 1)
    )
    # Raw validation without healing should flag topological invalidity
    raw_result = SpatialValidator.validate_plot(plot, auto_heal=False)
    assert raw_result.is_valid is False
    assert any("Invalid geometry topology" in err or "Self-intersection" in err for err in raw_result.errors)

    # Self-healing validation should repair the bowtie polygon
    healed_result = SpatialValidator.validate_plot(plot, auto_heal=True)
    assert healed_result.is_valid is True
    assert healed_result.healing_applied is True
    assert len(healed_result.healing_actions) > 0

def test_traceability_collector_batch():
    """Batch collection summary calculations."""
    plots = [
        ProductionPlotInput(
            plot_id="P1",
            country_code="GH",
            area_hectares=1.5,
            geometry={"type": "Point", "coordinates": [-1.500000, 6.500000]},
            production_date=date(2024, 1, 1)
        ),
        ProductionPlotInput(
            plot_id="P2",
            country_code="GH",
            area_hectares=2.0,
            geometry={"type": "Point", "coordinates": [-1.600000, 6.600000]},
            production_date=date(2024, 1, 1)
        )
    ]
    all_valid, results, summary = TraceabilityCollector.collect_and_validate(plots)
    assert all_valid is True
    assert summary["total_plots_analyzed"] == 2
    assert summary["valid_plots_count"] == 2
    assert summary["total_declared_area_ha"] == 3.5
