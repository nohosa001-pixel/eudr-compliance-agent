from typing import List, Dict, Any, Tuple
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.validation import explain_validity
import json

from app.schemas import (
    ProductionPlotInput, 
    SpatialPlotResult, 
    PointGeometry, 
    PolygonGeometry, 
    MultiPolygonGeometry
)
from app.core.exceptions import SpatialValidationError
from app.modules.spatial_validator import SpatialValidator, SelfHealingEngine


class TraceabilityCollector:
    """
    Collector and orchestrator for supply chain plot geometries with OGC overlap collision detection.
    """

    @classmethod
    def check_inter_plot_overlaps(cls, plots: List[ProductionPlotInput], results: List[SpatialPlotResult]) -> None:
        """
        Detects dual-claim polygon collisions / overlaps among plots in the supply chain payload.
        """
        shapely_polys = {}
        for p in plots:
            try:
                g = shape(p.geometry)
                if isinstance(g, (Polygon, MultiPolygon)) and g.is_valid:
                    shapely_polys[p.plot_id] = g
            except Exception:
                pass

        result_map = {r.plot_id: r for r in results}

        plot_ids = list(shapely_polys.keys())
        for i in range(len(plot_ids)):
            for j in range(i + 1, len(plot_ids)):
                id_a = plot_ids[i]
                id_b = plot_ids[j]
                poly_a = shapely_polys[id_a]
                poly_b = shapely_polys[id_b]

                if poly_a.intersects(poly_b):
                    inter = poly_a.intersection(poly_b)
                    if isinstance(inter, (Polygon, MultiPolygon)) and inter.area > 1e-8:
                        res_a = result_map.get(id_a)
                        res_b = result_map.get(id_b)
                        if res_a:
                            res_a.overlap_detected = True
                            res_a.overlapping_plot_ids.append(id_b)
                            res_a.precision_warnings.append(f"Dual-Claim Collision: Plot overlaps with {id_b}.")
                        if res_b:
                            res_b.overlap_detected = True
                            res_b.overlapping_plot_ids.append(id_a)
                            res_b.precision_warnings.append(f"Dual-Claim Collision: Plot overlaps with {id_a}.")

    @classmethod
    def collect_and_validate(cls, plots: List[ProductionPlotInput]) -> Tuple[bool, List[SpatialPlotResult], Dict[str, Any]]:
        results: List[SpatialPlotResult] = []
        all_valid = True
        total_declared_area = 0.0
        total_calculated_area = 0.0

        for p in plots:
            res = SpatialValidator.validate_plot(p)
            if not res.is_valid:
                all_valid = False
            results.append(res)
            total_declared_area += p.area_hectares
            if res.area_hectares:
                total_calculated_area += res.area_hectares

        # Run inter-plot overlap collision detector
        cls.check_inter_plot_overlaps(plots, results)

        summary = {
            "total_plots": len(plots),
            "total_plots_analyzed": len(plots),
            "valid_plots_count": sum(1 for r in results if r.is_valid),
            "invalid_plots_count": sum(1 for r in results if not r.is_valid),
            "healed_plots_count": sum(1 for r in results if r.healing_applied),
            "overlapping_plots_count": sum(1 for r in results if r.overlap_detected),
            "total_declared_area_ha": round(total_declared_area, 2),
            "total_calculated_area_ha": round(total_calculated_area, 2),
            "spatial_compliance": all_valid
        }

        return all_valid, results, summary

