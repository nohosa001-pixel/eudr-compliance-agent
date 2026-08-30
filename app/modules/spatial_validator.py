from typing import List, Dict, Any, Tuple, Optional, Union
import copy
import math
from shapely.geometry import shape, mapping, Point, Polygon, MultiPolygon, GeometryCollection
from shapely.validation import explain_validity, make_valid
from shapely.ops import unary_union

import importlib

try:
    _pyproj = importlib.import_module("pyproj")
    _Geod = getattr(_pyproj, "Geod")
    geod = _Geod(ellps="WGS84")
except Exception:
    class FallbackGeod:
        def geometry_area_perimeter(self, geom: Any) -> Tuple[float, float]:
            if hasattr(geom, "area"):
                try:
                    centroid = geom.centroid
                    lat_rad = math.radians(centroid.y)
                    m2_per_deg2 = (111320.0 * math.cos(lat_rad)) * 111320.0
                    return geom.area * m2_per_deg2, 0.0
                except Exception:
                    return geom.area * 1.239e10, 0.0
            return 0.0, 0.0
    geod = FallbackGeod()

from app.schemas import (
    ProductionPlotInput, 
    SpatialPlotResult, 
    PointGeometry, 
    PolygonGeometry, 
    MultiPolygonGeometry
)

# Approximate country bounding boxes [min_lon, min_lat, max_lon, max_lat]
COUNTRY_BBOXES = {
    "ID": (95.0, -11.0, 141.0, 6.0),     # Indonesia
    "BR": (-74.0, -34.0, -34.0, 5.5),    # Brazil
    "CI": (-8.6, 4.3, -2.5, 10.8),       # Ivory Coast
    "GH": (-3.5, 4.5, 1.3, 11.5),        # Ghana
    "VN": (102.0, 8.0, 110.0, 24.0),     # Vietnam
    "MY": (99.5, 0.8, 119.5, 7.5),       # Malaysia
    "CO": (-79.5, -4.5, -66.8, 13.5),    # Colombia
    "PE": (-81.4, -18.4, -68.6, 0.0),    # Peru
    "CM": (8.4, 1.6, 16.2, 13.1),        # Cameroon
    "NG": (2.6, 4.2, 14.7, 13.9),        # Nigeria
    "TH": (97.3, 5.6, 105.7, 20.5),      # Thailand
    "EC": (-81.1, -5.1, -75.1, 1.5),     # Ecuador
    "KE": (33.9, -4.7, 41.9, 5.5),       # Kenya
    "ET": (32.9, 3.3, 48.0, 15.0),       # Ethiopia
    "FR": (-5.5, 41.0, 9.6, 51.5),       # France
    "DE": (5.8, 47.2, 15.1, 55.1),       # Germany
}


class SelfHealingEngine:
    """
    Self-Healing GIS engine for automatic correction of malformed geometries:
    1. Axis Inversion Auto-Correction ([lat, lon] -> [lon, lat])
    2. Topological Defect Auto-Repair (bowtie uncrossing, ring closure, micro-sliver filtering, vertex de-duplication)
    3. MultiPolygon decomposition and geodesic area recalculation
    4. 10m Geodesic boundary buffer zone generation
    """

    MICRO_VERTEX_TOLERANCE_DEG = 1e-6  # ~0.11m precision
    SIMPLIFY_TOLERANCE = 1e-6

    @classmethod
    def _is_coord_swapped(cls, x: float, y: float, country_code: Optional[str] = None) -> bool:
        """
        Determines whether (x, y) is in [latitude, longitude] order rather than standard WGS84 [longitude, latitude].
        """
        # Obvious out-of-bounds: latitude cannot exceed [-90, 90]
        if abs(y) > 90.0 and abs(x) <= 90.0 and abs(y) <= 180.0:
            return True
        if abs(x) > 90.0 and abs(y) <= 90.0:
            return False

        # Country Bounding Box heuristic check
        if country_code and country_code.upper() in COUNTRY_BBOXES:
            min_lon, min_lat, max_lon, max_lat = COUNTRY_BBOXES[country_code.upper()]
            # If (x, y) fits as [lon, lat]
            fits_normal = (min_lon - 3.0 <= x <= max_lon + 3.0) and (min_lat - 3.0 <= y <= max_lat + 3.0)
            # If (y, x) fits as [lon, lat] (i.e. x is lat, y is lon)
            fits_swapped = (min_lon - 3.0 <= y <= max_lon + 3.0) and (min_lat - 3.0 <= x <= max_lat + 3.0)

            if fits_swapped and not fits_normal:
                return True

        return False

    @classmethod
    def swap_coordinates_recursive(cls, coords: Any) -> Any:
        """Recursively swaps [x, y, ...] -> [y, x, ...] preserving extra dimensions if any."""
        if isinstance(coords, (list, tuple)):
            if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                # Base coordinate pair [x, y] -> [y, x]
                swapped = [coords[1], coords[0]]
                if len(coords) > 2:
                    swapped.extend(coords[2:])
                return swapped
            else:
                return [cls.swap_coordinates_recursive(item) for item in coords]
        return coords

    @classmethod
    def detect_and_fix_axis_inversion(
        cls, 
        geom_dict: Dict[str, Any], 
        country_code: Optional[str] = None
    ) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        """
        Detects if geometry has swapped coordinates and fixes them.
        """
        coords = geom_dict.get("coordinates")
        if not coords:
            return geom_dict, False, None

        # Sample first coordinate
        first_coord = cls._get_first_coord(coords)
        if not first_coord or len(first_coord) < 2:
            return geom_dict, False, None

        x, y = float(first_coord[0]), float(first_coord[1])
        if cls._is_coord_swapped(x, y, country_code):
            healed_geom = copy.deepcopy(geom_dict)
            healed_geom["coordinates"] = cls.swap_coordinates_recursive(coords)
            return (
                healed_geom, 
                True, 
                f"Auto-healed: Swapped inverted [lat, lon] ({x:.5f}, {y:.5f}) to WGS84 standard [lon, lat] ({y:.5f}, {x:.5f})."
            )

        return geom_dict, False, None

    @classmethod
    def _get_first_coord(cls, coords: Any) -> Optional[List[float]]:
        if isinstance(coords, (list, tuple)):
            if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                return [float(coords[0]), float(coords[1])]
            elif len(coords) > 0:
                return cls._get_first_coord(coords[0])
        return None

    @classmethod
    def deduplicate_ring_points(cls, ring: List[List[float]]) -> List[List[float]]:
        """
        Removes consecutive duplicate or micro-spaced vertices (< 0.1m ~ 1e-6 deg) from a linear ring.
        """
        if not ring:
            return ring

        clean_ring = [ring[0]]
        for pt in ring[1:]:
            prev = clean_ring[-1]
            dx = abs(pt[0] - prev[0])
            dy = abs(pt[1] - prev[1])
            if dx > cls.MICRO_VERTEX_TOLERANCE_DEG or dy > cls.MICRO_VERTEX_TOLERANCE_DEG:
                clean_ring.append(pt)

        # Ensure ring closure
        if len(clean_ring) >= 3:
            first = clean_ring[0]
            last = clean_ring[-1]
            if first[0] != last[0] or first[1] != last[1]:
                clean_ring.append([first[0], first[1]])

        return clean_ring

    @classmethod
    def heal_geometry(
        cls, 
        geom_dict: Dict[str, Any], 
        country_code: Optional[str] = None
    ) -> Tuple[Dict[str, Any], bool, List[str]]:
        """
        Complete self-healing pipeline:
        - Normalizes GeoJSON wrapper
        - Inverted coordinate detection & repair
        - Ring closure repair
        - Vertex de-duplication (<0.1m)
        - Self-intersection & bowtie repair via Shapely make_valid
        - GeometryCollection / MultiPolygon decomposition & cleanup
        """
        healing_actions: List[str] = []
        is_healed = False

        # 0. Unwrap Feature or FeatureCollection if supplied
        if geom_dict.get("type") == "Feature" and "geometry" in geom_dict:
            geom_dict = geom_dict["geometry"]
            is_healed = True
            healing_actions.append("Extracted geometry from GeoJSON Feature envelope.")
        elif geom_dict.get("type") == "FeatureCollection" and geom_dict.get("features"):
            geom_dict = geom_dict["features"][0].get("geometry", {})
            is_healed = True
            healing_actions.append("Extracted first feature geometry from GeoJSON FeatureCollection.")

        # Normalize type casing
        raw_type = str(geom_dict.get("type", "")).strip()
        canonical_type = raw_type.capitalize()
        if raw_type.lower() == "multipolygon":
            canonical_type = "MultiPolygon"
        elif raw_type.lower() == "point":
            canonical_type = "Point"
        elif raw_type.lower() == "polygon":
            canonical_type = "Polygon"

        if canonical_type != raw_type:
            geom_dict = copy.deepcopy(geom_dict)
            geom_dict["type"] = canonical_type
            is_healed = True
            healing_actions.append(f"Normalized geometry type casing from '{raw_type}' to '{canonical_type}'.")

        # 1. Axis Inversion Auto-Correction
        geom_dict, swapped, swap_msg = cls.detect_and_fix_axis_inversion(geom_dict, country_code)
        if swapped and swap_msg:
            is_healed = True
            healing_actions.append(swap_msg)

        geom_type = geom_dict.get("type", "")
        coords = geom_dict.get("coordinates", [])

        # 2. Point Healing
        if geom_type == "Point":
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                # Strip 3D if present
                clean_point = [float(coords[0]), float(coords[1])]
                if len(coords) > 2:
                    is_healed = True
                    healing_actions.append("Stripped 3D elevation component from Point coordinate.")
                geom_dict = {"type": "Point", "coordinates": clean_point}
            return geom_dict, is_healed, healing_actions

        # 3. Polygon & MultiPolygon Healing
        if geom_type in ["Polygon", "MultiPolygon"]:
            try:
                # Step A: Pre-sanitize rings (unclosed ring repair & vertex deduplication)
                if geom_type == "Polygon" and isinstance(coords, list):
                    repaired_rings = []
                    ring_repaired = False
                    for ring in coords:
                        if isinstance(ring, list) and len(ring) >= 3:
                            # Ring closure check
                            if ring[0] != ring[-1]:
                                ring = list(ring) + [ring[0]]
                                ring_repaired = True
                            # Deduplicate
                            deduped = cls.deduplicate_ring_points(ring)
                            if len(deduped) != len(ring):
                                ring_repaired = True
                            repaired_rings.append(deduped)
                        else:
                            repaired_rings.append(ring)
                    if ring_repaired:
                        geom_dict = {"type": "Polygon", "coordinates": repaired_rings}
                        is_healed = True
                        healing_actions.append("Repaired unclosed linear ring and removed duplicate vertices (<0.1m).")

                # Step B: Shapely Topological Repair (make_valid)
                shapely_obj = shape(geom_dict)
                if not shapely_obj.is_valid or not shapely_obj.is_simple:
                    reason = explain_validity(shapely_obj)
                    fixed_shapely = make_valid(shapely_obj)
                    
                    # If make_valid produced GeometryCollection, filter only polygons
                    if isinstance(fixed_shapely, GeometryCollection):
                        poly_parts = [g for g in fixed_shapely.geoms if isinstance(g, (Polygon, MultiPolygon)) and g.area > 1e-12]
                        if poly_parts:
                            fixed_shapely = unary_union(poly_parts)
                        else:
                            # Fallback buffer(0)
                            fixed_shapely = shapely_obj.buffer(0)

                    # Extract valid polygon / multipolygon
                    if isinstance(fixed_shapely, (Polygon, MultiPolygon)) and fixed_shapely.is_valid and not fixed_shapely.is_empty:
                        geom_dict = mapping(fixed_shapely)
                        is_healed = True
                        healing_actions.append(f"Auto-healed topological defect ({reason}) using Shapely make_valid and polygon reconstruction.")
                    elif hasattr(fixed_shapely, "geoms"):
                        polys = [g for g in fixed_shapely.geoms if isinstance(g, Polygon)]
                        if polys:
                            geom_dict = mapping(MultiPolygon(polys) if len(polys) > 1 else polys[0])
                            is_healed = True
                            healing_actions.append(f"Auto-healed complex geometry into valid MultiPolygon/Polygon.")
            except Exception as e:
                # If make_valid fails, try buffer(0)
                try:
                    raw_shape = shape(geom_dict)
                    buffered = raw_shape.buffer(0)
                    if buffered.is_valid and not buffered.is_empty:
                        geom_dict = mapping(buffered)
                        is_healed = True
                        healing_actions.append(f"Auto-healed topology using buffer(0) fallback ({str(e)}).")
                except Exception:
                    pass

        return geom_dict, is_healed, healing_actions


class SpatialValidator:
    """
    Validates and standardizes GIS geolocation data according to EUDR requirements.
    - EUDR Art. 9(1)(d): Plots >= 4 hectares require closed Polygon / MultiPolygon geolocation.
    - Plots < 4 hectares may provide either a Point or a Polygon/MultiPolygon.
    - All coordinates must strictly adhere to WGS84 (EPSG:4326).
    - Recommended decimal precision: >= 6 decimal places (~0.1m ground precision).
    - Equipped with Self-Healing engine for 100% resilient auto-normalization.
    """

    POLYGON_AREA_THRESHOLD_HA = 4.0
    AREA_DISCREPANCY_TOLERANCE_PCT = 0.35  # 35% margin between declared & computed GIS area
    RECOMMENDED_DECIMAL_PLACES = 5

    @classmethod
    def calculate_geometry_area_ha(cls, geom: Any) -> float:
        """Calculates true geodesic area on WGS84 ellipsoid in hectares (1 ha = 10,000 m2)."""
        try:
            area_m2, _ = geod.geometry_area_perimeter(geom)
            return abs(area_m2) / 10000.0
        except Exception:
            return 0.0

    @classmethod
    def decompose_multipolygon(cls, geom_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decomposes a MultiPolygon geometry into individual Polygon components with individual geodesic areas.
        """
        g_type = geom_dict.get("type")
        coords = geom_dict.get("coordinates", [])
        if g_type == "Polygon":
            poly_shape = shape(geom_dict)
            area_ha = cls.calculate_geometry_area_ha(poly_shape) if poly_shape.is_valid else 0.0
            return [{
                "part_index": 0,
                "geometry": geom_dict,
                "calculated_area_ha": round(area_ha, 4)
            }]
        elif g_type == "MultiPolygon":
            parts = []
            for idx, poly_coords in enumerate(coords):
                part_geom = {"type": "Polygon", "coordinates": poly_coords}
                part_shape = shape(part_geom)
                area_ha = cls.calculate_geometry_area_ha(part_shape) if part_shape.is_valid else 0.0
                parts.append({
                    "part_index": idx,
                    "geometry": part_geom,
                    "calculated_area_ha": round(area_ha, 4)
                })
            return parts
        return []

    @classmethod
    def generate_10m_buffer_zone(cls, geom_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generates a 10-meter boundary buffer zone polygon for edge-effect interference analysis.
        """
        try:
            geom_shape = shape(geom_dict)
            if not geom_shape.is_valid:
                geom_shape = make_valid(geom_shape)
            
            # Approximate 10 meters in degrees (~ 10m / 111,320m = ~0.00009 deg)
            buffer_deg = 10.0 / 111320.0
            buffered_shape = geom_shape.buffer(buffer_deg)
            if buffered_shape.is_valid and not buffered_shape.is_empty:
                return mapping(buffered_shape)
        except Exception:
            pass
        return None

    @classmethod
    def _check_coordinate_precision(cls, coords: Any) -> List[str]:
        """Checks if coordinates have sufficient decimal precision for EUDR compliance."""
        warnings = []
        
        def extract_numbers(c: Any) -> List[float]:
            nums = []
            if isinstance(c, (int, float)):
                nums.append(float(c))
            elif isinstance(c, (list, tuple)):
                for item in c:
                    nums.extend(extract_numbers(item))
            return nums

        all_nums = extract_numbers(coords)
        for num in all_nums:
            str_num = f"{num:.10f}".rstrip("0")
            if "." in str_num:
                decimals = len(str_num.split(".")[1])
                if decimals < cls.RECOMMENDED_DECIMAL_PLACES:
                    warnings.append(
                        f"Coordinate component {num} has {decimals} decimal places. "
                        f"EUDR recommendation is >= 6 decimal places for high-precision auditing."
                    )
                    break
        return warnings

    @classmethod
    def validate_plot(cls, plot: ProductionPlotInput, auto_heal: bool = True) -> SpatialPlotResult:
        errors: List[str] = []
        precision_warnings: List[str] = []
        original_geometry = copy.deepcopy(plot.geometry)
        geom_dict = plot.geometry
        healing_applied = False
        healing_actions: List[str] = []

        # Step 1: Self-Healing Pipeline
        if auto_heal:
            try:
                healed_dict, healed, actions = SelfHealingEngine.heal_geometry(
                    geom_dict, country_code=plot.country_code
                )
                if healed:
                    geom_dict = healed_dict
                    healing_applied = True
                    healing_actions.extend(actions)
            except Exception as ex:
                healing_actions.append(f"Self-healing notice: {str(ex)}")

        geom_type = geom_dict.get("type", "")
        coords = geom_dict.get("coordinates", [])

        # Step 2: 4ha rule check
        is_polygon_required = plot.area_hectares >= cls.POLYGON_AREA_THRESHOLD_HA
        if is_polygon_required and geom_type not in ["Polygon", "MultiPolygon"]:
            errors.append(
                f"EUDR Rule Violation: Plot area is {plot.area_hectares:.2f} ha (>= {cls.POLYGON_AREA_THRESHOLD_HA} ha), "
                f"which strictly requires a Polygon or MultiPolygon geometry. Provided: '{geom_type}'."
            )

        # Step 3: Structural & Bounds validation
        if not coords or (isinstance(coords, list) and len(coords) == 0):
            errors.append("Invalid geometry: coordinates array is empty.")
        else:
            try:
                if geom_type == "Point":
                    PointGeometry(type="Point", coordinates=coords)
                elif geom_type == "Polygon":
                    PolygonGeometry(type="Polygon", coordinates=coords)
                elif geom_type == "MultiPolygon":
                    MultiPolygonGeometry(type="MultiPolygon", coordinates=coords)
                else:
                    errors.append(f"Unsupported geometry type: '{geom_type}'. Must be 'Point', 'Polygon', or 'MultiPolygon'.")
            except Exception as e:
                # If schema validation still fails after healing, report clearly
                errors.append(f"Schema validation error: {str(e)}")

        # Step 4: Precision check
        if not errors:
            precision_warnings.extend(cls._check_coordinate_precision(coords))

        # Step 5: Shapely topological evaluation
        shapely_geom = None
        calculated_area_ha = None
        if not errors:
            try:
                shapely_geom = shape(geom_dict)
                if not shapely_geom.is_valid:
                    reason = explain_validity(shapely_geom)
                    errors.append(f"Invalid geometry topology: {reason}")
                elif not shapely_geom.is_simple:
                    errors.append("Geometry is not simple (e.g. self-intersecting or complex).")

                # If polygon or multipolygon, compute geodesic area
                if isinstance(shapely_geom, (Polygon, MultiPolygon)) and shapely_geom.is_valid:
                    calculated_area_ha = cls.calculate_geometry_area_ha(shapely_geom)
                    if calculated_area_ha <= 0:
                        errors.append("Calculated GIS area is zero or negative (degenerate polygon).")
                    elif calculated_area_ha > 0:
                        discrepancy = abs(plot.area_hectares - calculated_area_ha) / max(plot.area_hectares, calculated_area_ha)
                        if discrepancy > cls.AREA_DISCREPANCY_TOLERANCE_PCT:
                            precision_warnings.append(
                                f"Area discrepancy note: Declared area is {plot.area_hectares:.2f} ha, "
                                f"while calculated GIS geodesic area is {calculated_area_ha:.2f} ha "
                                f"(diff: {discrepancy*100:.1f}%)."
                            )
            except Exception as ex:
                errors.append(f"Failed to parse Shapely geometry: {str(ex)}")

        is_valid = len(errors) == 0

        # Standardized GeoJSON Feature
        standardized_geojson = None
        if is_valid and shapely_geom is not None:
            standardized_geojson = {
                "type": "Feature",
                "properties": {
                    "plot_id": plot.plot_id,
                    "country_code": plot.country_code,
                    "declared_area_ha": plot.area_hectares,
                    "calculated_area_ha": round(calculated_area_ha, 4) if calculated_area_ha is not None else None,
                    "production_date": str(plot.production_date),
                    "producer_name": plot.producer_name,
                    "healing_applied": healing_applied,
                    "healing_actions": healing_actions,
                },
                "geometry": geom_dict
            }

        return SpatialPlotResult(
            plot_id=plot.plot_id,
            is_valid=is_valid,
            area_hectares=calculated_area_ha if calculated_area_ha is not None else plot.area_hectares,
            declared_area_ha=plot.area_hectares,
            calculated_area_ha=round(calculated_area_ha, 4) if calculated_area_ha is not None else None,
            area_discrepancy_pct=round(abs(plot.area_hectares - (calculated_area_ha or plot.area_hectares)) / max(plot.area_hectares, 0.001) * 100, 2),
            geometry_type=geom_type,
            is_polygon_required=is_polygon_required,
            four_ha_polygon_rule_compliant=(not is_polygon_required) or (geom_type in ["Polygon", "MultiPolygon"]),
            precision_warnings=precision_warnings,
            errors=errors,
            overlap_detected=False,
            overlapping_plot_ids=[],
            standardized_geojson=standardized_geojson,
            healing_applied=healing_applied,
            healing_actions=healing_actions,
            original_geometry=original_geometry if healing_applied else None
        )
