import pytest
import os
import uuid
from unittest.mock import patch

from app.core.config import settings
from app.db.session import get_database_url, create_db_engine, init_db, SessionLocal
from app.db.models import SpatialPlotRecord
from app.db.spatial_repository import SpatialPlotRepository
from app.schemas import ProductionPlotInput, SpatialPlotResult


def test_database_url_resolution():
    """Verify DATABASE_URL resolution from settings, environment, and defaults."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://testuser:testpass@localhost:5432/testdb"}):
        with patch.object(settings, "DATABASE_URL", ""):
            url = get_database_url()
            assert url == "postgresql://testuser:testpass@localhost:5432/testdb"

    with patch.dict(os.environ, {"USE_POSTGRES": "true", "DATABASE_URL": ""}):
        with patch.object(settings, "DATABASE_URL", ""):
            url = get_database_url()
            assert url.startswith("postgresql://")
            assert "5432" in url


def test_create_db_engine_pooling_config():
    """Verify PostgreSQL engine is created with connection pooling settings."""
    pg_url = "postgresql://user:pass@localhost:5432/db"
    # Create engine mock test
    engine = create_db_engine(pg_url)
    assert engine.pool.size() == 10

    sqlite_url = "sqlite:///:memory:"
    sq_engine = create_db_engine(sqlite_url)
    assert sq_engine.name == "sqlite"


def test_spatial_plot_record_and_repository_bulk_save():
    """Verify SpatialPlotRecord creation and bulk save operations."""
    init_db()
    db = SessionLocal()
    exec_id = f"EXEC-SPATIAL-TEST-{uuid.uuid4().hex[:6].upper()}"

    plots = [
        ProductionPlotInput(
            plot_id="PLOT-SPATIAL-001",
            country_code="ID",
            area_hectares=1.5,
            geometry={"type": "Point", "coordinates": [101.5, 0.5]},
            production_date="2024-05-01"
        ),
        ProductionPlotInput(
            plot_id="PLOT-SPATIAL-002",
            country_code="ID",
            area_hectares=8.0,
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [101.5, 0.5],
                    [101.51, 0.5],
                    [101.51, 0.51],
                    [101.5, 0.51],
                    [101.5, 0.5]
                ]]
            },
            production_date="2024-05-01"
        )
    ]

    spatial_results = [
        SpatialPlotResult(
            plot_id="PLOT-SPATIAL-001",
            is_valid=True,
            geometry_type="Point",
            declared_area_ha=1.5,
            calculated_area_ha=1.5,
            area_discrepancy_pct=0.0
        ),
        SpatialPlotResult(
            plot_id="PLOT-SPATIAL-002",
            is_valid=True,
            geometry_type="Polygon",
            declared_area_ha=8.0,
            calculated_area_ha=8.0,
            area_discrepancy_pct=0.0,
            healing_applied=True,
            healing_actions=["Closed polygon ring"]
        )
    ]

    try:
        saved = SpatialPlotRepository.bulk_save_plots(
            db=db,
            plots=plots,
            spatial_results=spatial_results,
            execution_id=exec_id,
            supplier_id="SUPP-SPATIAL-01"
        )

        assert len(saved) == 2
        assert saved[0].plot_id == "PLOT-SPATIAL-001"
        assert saved[0].geometry_type == "Point"
        assert saved[1].plot_id == "PLOT-SPATIAL-002"
        assert saved[1].is_self_healed is True

        # Query by execution ID
        retrieved = SpatialPlotRepository.get_plots_by_execution(db, exec_id)
        assert len(retrieved) == 2

        # Bounding box query
        bbox_results = SpatialPlotRepository.find_plots_in_bbox(
            db=db,
            min_lon=101.0,
            min_lat=0.0,
            max_lon=102.0,
            max_lat=1.0
        )
        assert len(bbox_results) >= 2

    finally:
        db.close()
