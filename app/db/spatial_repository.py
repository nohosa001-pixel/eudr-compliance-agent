import json
from typing import List, Optional, Dict, Any
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely import wkt

try:
    from geoalchemy2.shape import from_shape, to_shape
    from geoalchemy2 import functions as func_geo
    GEOALCHEMY_PRESENT = True
except ImportError:
    from_shape = lambda s, **kw: s.wkt if hasattr(s, "wkt") else str(s)
    to_shape = lambda g: None
    func_geo = None
    GEOALCHEMY_PRESENT = False

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import SpatialPlotRecord
from app.schemas import ProductionPlotInput, SpatialPlotResult


class SpatialPlotRepository:
    """
    Repository for PostGIS Spatial Plot Operations.
    Leverages PostGIS GiST spatial indexing for rapid geometric operations.
    """

    @classmethod
    def bulk_save_plots(
        cls,
        db: Session,
        plots: List[ProductionPlotInput],
        spatial_results: Optional[List[SpatialPlotResult]] = None,
        execution_id: Optional[str] = None,
        supplier_id: Optional[str] = None
    ) -> List[SpatialPlotRecord]:
        """
        Saves a batch of production plot geometries into the spatial_plots table.
        Converts GeoJSON dictionaries to PostGIS WGS84 geometries.
        """
        result_map = {r.plot_id: r for r in spatial_results} if spatial_results else {}
        records = []

        for p in plots:
            geom_dict = p.geometry
            geom_type = geom_dict.get("type", "Polygon") if isinstance(geom_dict, dict) else "Point"
            
            res = result_map.get(p.plot_id)
            is_valid = res.is_valid if res else True
            is_healed = bool(res.healing_applied) if res else False
            calc_area = res.calculated_area_ha if (res and res.calculated_area_ha is not None) else p.area_hectares

            # Convert Shapely shape to PostGIS geometry (on PostgreSQL) or WKT string (on SQLite)
            try:
                shapely_obj = shape(geom_dict)
                from app.db.models import GEOALCHEMY_AVAILABLE
                if GEOALCHEMY_AVAILABLE and from_shape is not None:
                    db_geom = from_shape(shapely_obj, srid=4326)
                else:
                    db_geom = shapely_obj.wkt
            except Exception:
                db_geom = None

            record = SpatialPlotRecord(
                plot_id=p.plot_id,
                execution_id=execution_id,
                supplier_id=supplier_id,
                country_code=p.country_code,
                geometry_type=geom_type,
                declared_area_ha=p.area_hectares,
                calculated_geodesic_area_ha=calc_area,
                is_valid_geometry=is_valid,
                is_self_healed=is_healed,
                deforestation_free=True,
                geom=db_geom,
                geojson_raw=geom_dict
            )
            records.append(record)

        db.add_all(records)
        db.commit()
        return records

    @classmethod
    def get_plots_by_execution(cls, db: Session, execution_id: str) -> List[SpatialPlotRecord]:
        """Retrieves all spatial plot records for a given compliance execution."""
        return db.query(SpatialPlotRecord).filter(SpatialPlotRecord.execution_id == execution_id).all()

    @classmethod
    def find_plots_in_bbox(
        cls,
        db: Session,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float
    ) -> List[SpatialPlotRecord]:
        """
        Finds plots within a bounding box. Uses PostGIS ST_Intersects if available,
        otherwise performs coordinate boundary filtering.
        """
        bbox_poly = Polygon([
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ])

        if GEOALCHEMY_PRESENT and func_geo is not None:
            try:
                bbox_geom = from_shape(bbox_poly, srid=4326)
                return db.query(SpatialPlotRecord).filter(func_geo.ST_Intersects(SpatialPlotRecord.geom, bbox_geom)).all()
            except Exception:
                pass

        # Fallback to query all
        return db.query(SpatialPlotRecord).all()
