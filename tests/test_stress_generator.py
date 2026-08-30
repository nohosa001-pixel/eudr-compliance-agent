import pytest
import time
from datetime import date
from typing import List, Dict, Any
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    ProductionPlotInput, 
    SpatialPlotResult,
    ComplianceStatusEnum,
    EUDRSupplyChainPayload
)
from app.modules.spatial_validator import SpatialValidator, SelfHealingEngine
from app.modules.deforestation_simulator import DeforestationSimulator

client = TestClient(app)


def generate_50_malicious_plots() -> List[Dict[str, Any]]:
    """
    Generates 50 distinct malicious, deformed, or edge-case plot test geometries.
    """
    cases = []

    # --- Category 1: Coordinate Inversion ([lat, lon] instead of [lon, lat]) ---
    # 1. Point inverted lat/lon (Indonesia)
    cases.append({
        "plot_id": "STRESS-01-INV-PT-ID",
        "country_code": "ID",
        "area_hectares": 2.5,
        "geometry": {"type": "Point", "coordinates": [0.500000, 101.500000]},  # [lat, lon]
        "production_date": "2024-05-01",
        "notes": "inverted coordinates"
    })
    # 2. Polygon inverted lat/lon (Brazil)
    cases.append({
        "plot_id": "STRESS-02-INV-POLY-BR",
        "country_code": "BR",
        "area_hectares": 15.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-12.500000, -55.500000],
                [-12.500000, -55.490000],
                [-12.490000, -55.490000],
                [-12.490000, -55.500000],
                [-12.500000, -55.500000]
            ]]
        },
        "production_date": "2024-05-01",
        "notes": "inverted polygon coords"
    })
    # 3. Point inverted (Vietnam)
    cases.append({
        "plot_id": "STRESS-03-INV-PT-VN",
        "country_code": "VN",
        "area_hectares": 1.8,
        "geometry": {"type": "Point", "coordinates": [11.941200, 108.438500]},
        "production_date": "2024-05-01"
    })
    # 4. Polygon inverted (Ivory Coast)
    cases.append({
        "plot_id": "STRESS-04-INV-POLY-CI",
        "country_code": "CI",
        "area_hectares": 8.5,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [6.850000, -5.300000],
                [6.850000, -5.290000],
                [6.860000, -5.290000],
                [6.860000, -5.300000],
                [6.850000, -5.300000]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 5. MultiPolygon with inverted coordinates
    cases.append({
        "plot_id": "STRESS-05-INV-MULTI-ID",
        "country_code": "ID",
        "area_hectares": 20.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[
                    [0.500000, 101.500000],
                    [0.500000, 101.510000],
                    [0.510000, 101.510000],
                    [0.510000, 101.500000],
                    [0.500000, 101.500000]
                ]],
                [[
                    [0.520000, 101.520000],
                    [0.520000, 101.530000],
                    [0.530000, 101.530000],
                    [0.530000, 101.520000],
                    [0.520000, 101.520000]
                ]]
            ]
        },
        "production_date": "2024-05-01"
    })

    # --- Category 2: Topological Defects (Bowtie, Hourglass, Self-Intersections, Spikes) ---
    # 6. Classic Hourglass / Bowtie (Self-intersection)
    cases.append({
        "plot_id": "STRESS-06-BOWTIE-POLY",
        "country_code": "BR",
        "area_hectares": 12.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-55.000000, -12.000000],
                [-54.990000, -11.990000],
                [-55.000000, -11.990000],
                [-54.990000, -12.000000],
                [-55.000000, -12.000000]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 7. Double Bowtie Polygon (Figure-8 with multiple crossings)
    cases.append({
        "plot_id": "STRESS-07-DOUBLE-BOWTIE",
        "country_code": "ID",
        "area_hectares": 18.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [100.0, 0.0],
                [100.02, 0.02],
                [100.0, 0.02],
                [100.02, 0.0],
                [100.04, 0.02],
                [100.04, 0.0],
                [100.0, 0.0]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 8. Self-tangent polygon (touching itself at one point)
    cases.append({
        "plot_id": "STRESS-08-SELF-TANGENT",
        "country_code": "GH",
        "area_hectares": 10.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-1.50, 6.50],
                [-1.49, 6.50],
                [-1.49, 6.51],
                [-1.50, 6.51],
                [-1.50, 6.50],
                [-1.51, 6.50],
                [-1.51, 6.49],
                [-1.50, 6.49],
                [-1.50, 6.50]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 9. Self-overlapping along edge
    cases.append({
        "plot_id": "STRESS-09-EDGE-OVERLAP",
        "country_code": "CI",
        "area_hectares": 14.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-5.50, 6.50],
                [-5.48, 6.50],
                [-5.49, 6.50],
                [-5.49, 6.52],
                [-5.50, 6.52],
                [-5.50, 6.50]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 10. Needle Spike Sliver (< 0.1m width, long extension)
    cases.append({
        "plot_id": "STRESS-10-NEEDLE-SPIKE",
        "country_code": "VN",
        "area_hectares": 9.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [108.40, 11.90],
                [108.41, 11.90],
                [108.45, 11.9000005],  # Needle spike
                [108.41, 11.9000008],
                [108.41, 11.91],
                [108.40, 11.91],
                [108.40, 11.90]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 11. Collapsed degenerate edge
    cases.append({
        "plot_id": "STRESS-11-COLLAPSED-EDGE",
        "country_code": "MY",
        "area_hectares": 6.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [101.0, 3.0],
                [101.01, 3.0],
                [101.01, 3.01],
                [101.01, 3.0],  # Collapse
                [101.0, 3.01],
                [101.0, 3.0]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 12. 5-pointed star with self-crossings
    cases.append({
        "plot_id": "STRESS-12-STAR-SELF-CROSS",
        "country_code": "BR",
        "area_hectares": 15.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-50.0, -10.0],
                [-49.98, -9.95],
                [-49.96, -10.0],
                [-50.0, -9.97],
                [-49.96, -9.97],
                [-50.0, -10.0]
            ]]
        },
        "production_date": "2024-05-01"
    })

    # --- Category 3: Linear Ring Closure & Vertex Defects ---
    # 13. Unclosed linear ring (missing closing coord)
    cases.append({
        "plot_id": "STRESS-13-UNCLOSED-RING",
        "country_code": "ID",
        "area_hectares": 11.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [102.00, 0.50],
                [102.01, 0.50],
                [102.01, 0.51],
                [102.00, 0.51]
                # Missing [102.00, 0.50]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 14. Linear ring with only 3 points
    cases.append({
        "plot_id": "STRESS-14-TRIANGLE-UNCLOSED",
        "country_code": "GH",
        "area_hectares": 5.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-1.50, 6.50],
                [-1.49, 6.50],
                [-1.49, 6.51]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 15. Consecutive duplicate vertices (<0.1m)
    cases.append({
        "plot_id": "STRESS-15-DUP-VERTICES",
        "country_code": "CI",
        "area_hectares": 7.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-6.000000, 5.000000],
                [-6.000000, 5.000000],  # Duplicate
                [-5.990000, 5.000000],
                [-5.990000, 5.000000],  # Duplicate
                [-5.990000, 5.010000],
                [-6.000000, 5.010000],
                [-6.000000, 5.000000]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 16. Multi-duplicate collinear redundant vertices
    cases.append({
        "plot_id": "STRESS-16-MULTI-DUP",
        "country_code": "VN",
        "area_hectares": 12.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [108.0, 12.0],
                [108.0, 12.0],
                [108.0, 12.0],
                [108.01, 12.0],
                [108.01, 12.01],
                [108.0, 12.01],
                [108.0, 12.0]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 17. MultiPolygon with 1 unclosed ring and 1 closed ring
    cases.append({
        "plot_id": "STRESS-17-MULTI-PARTIAL-UNCLOSED",
        "country_code": "BR",
        "area_hectares": 25.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[
                    [-54.0, -10.0],
                    [-53.99, -10.0],
                    [-53.99, -9.99],
                    [-54.0, -9.99]  # unclosed
                ]],
                [[
                    [-54.02, -10.0],
                    [-54.01, -10.0],
                    [-54.01, -9.99],
                    [-54.02, -9.99],
                    [-54.02, -10.0]  # closed
                ]]
            ]
        },
        "production_date": "2024-05-01"
    })
    # 18. Jitter vertices (< 1e-7 deg)
    cases.append({
        "plot_id": "STRESS-18-MICRO-JITTER",
        "country_code": "ID",
        "area_hectares": 8.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [101.5000000, 0.5000000],
                [101.5000001, 0.5000001],
                [101.5100000, 0.5000000],
                [101.5100000, 0.5100000],
                [101.5000000, 0.5100000],
                [101.5000000, 0.5000000]
            ]]
        },
        "production_date": "2024-05-01"
    })

    # --- Category 4: MultiPolygon Decomposition & Wrappers ---
    # 19. Valid MultiPolygon 3-parcels
    cases.append({
        "plot_id": "STRESS-19-MULTI-3PARCEL",
        "country_code": "ID",
        "area_hectares": 35.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[100.0, 0.0], [100.01, 0.0], [100.01, 0.01], [100.0, 0.01], [100.0, 0.0]]],
                [[[100.02, 0.0], [100.03, 0.0], [100.03, 0.01], [100.02, 0.01], [100.02, 0.0]]],
                [[[100.04, 0.0], [100.05, 0.0], [100.05, 0.01], [100.04, 0.01], [100.04, 0.0]]]
            ]
        },
        "production_date": "2024-05-01"
    })
    # 20. MultiPolygon with 1 degenerate zero-area sliver part
    cases.append({
        "plot_id": "STRESS-20-MULTI-DEGENERATE-PART",
        "country_code": "GH",
        "area_hectares": 12.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[-1.50, 6.50], [-1.49, 6.50], [-1.49, 6.51], [-1.50, 6.51], [-1.50, 6.50]]],
                [[[-1.60, 6.60], [-1.60, 6.60], [-1.60, 6.60], [-1.60, 6.60]]]  # Point degenerate
            ]
        },
        "production_date": "2024-05-01"
    })
    # 21. MultiPolygon with overlapping sibling polygons
    cases.append({
        "plot_id": "STRESS-21-MULTI-SIBLING-OVERLAP",
        "country_code": "BR",
        "area_hectares": 30.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[-50.0, -10.0], [-49.98, -10.0], [-49.98, -9.98], [-50.0, -9.98], [-50.0, -10.0]]],
                [[[-49.99, -10.0], [-49.97, -10.0], [-49.97, -9.98], [-49.99, -9.98], [-49.99, -10.0]]]
            ]
        },
        "production_date": "2024-05-01"
    })
    # 22. GeoJSON Feature envelope
    cases.append({
        "plot_id": "STRESS-22-FEATURE-ENVELOPE",
        "country_code": "CI",
        "area_hectares": 6.5,
        "geometry": {
            "type": "Feature",
            "properties": {"supplier": "Coop A"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-5.5, 6.5], [-5.49, 6.5], [-5.49, 6.51], [-5.5, 6.51], [-5.5, 6.5]
                ]]
            }
        },
        "production_date": "2024-05-01"
    })
    # 23. GeoJSON FeatureCollection envelope
    cases.append({
        "plot_id": "STRESS-23-FEATURECOLLECTION-WRAPPER",
        "country_code": "VN",
        "area_hectares": 5.0,
        "geometry": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [108.0, 12.0], [108.01, 12.0], [108.01, 12.01], [108.0, 12.01], [108.0, 12.0]
                        ]]
                    }
                }
            ]
        },
        "production_date": "2024-05-01"
    })
    # 24. MultiPolygon with inverted lat/lon and unclosed rings
    cases.append({
        "plot_id": "STRESS-24-COMPOUND-MULTI",
        "country_code": "ID",
        "area_hectares": 22.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[
                    [0.50, 101.50], [0.50, 101.51], [0.51, 101.51], [0.51, 101.50]  # inverted & unclosed
                ]]
            ]
        },
        "production_date": "2024-05-01"
    })

    # --- Category 5: 4ha Threshold & Geometry Rules ---
    # 25. Single Point with 5.5 ha (> 4ha violation)
    cases.append({
        "plot_id": "STRESS-25-POINT-5HA-VIOLATION",
        "country_code": "BR",
        "area_hectares": 5.5,
        "geometry": {"type": "Point", "coordinates": [-55.0, -12.0]},
        "production_date": "2024-05-01"
    })
    # 26. Single Point with 150.0 ha (> 4ha violation)
    cases.append({
        "plot_id": "STRESS-26-POINT-150HA-VIOLATION",
        "country_code": "ID",
        "area_hectares": 150.0,
        "geometry": {"type": "Point", "coordinates": [101.5, 0.5]},
        "production_date": "2024-05-01"
    })
    # 27. Single Point with exactly 4.00 ha (boundary threshold)
    cases.append({
        "plot_id": "STRESS-27-POINT-EXACT-4HA",
        "country_code": "GH",
        "area_hectares": 4.0,
        "geometry": {"type": "Point", "coordinates": [-1.5, 6.5]},
        "production_date": "2024-05-01"
    })
    # 28. Single Point with 3.99 ha (< 4ha valid smallholder)
    cases.append({
        "plot_id": "STRESS-28-POINT-VALID-3_99HA",
        "country_code": "CI",
        "area_hectares": 3.99,
        "geometry": {"type": "Point", "coordinates": [-5.5, 6.5]},
        "production_date": "2024-05-01"
    })
    # 29. Polygon declaring 1.5 ha (< 4ha is permissible as polygon)
    cases.append({
        "plot_id": "STRESS-29-POLY-SMALL-1_5HA",
        "country_code": "VN",
        "area_hectares": 1.5,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [108.0, 12.0], [108.005, 12.0], [108.005, 12.005], [108.0, 12.005], [108.0, 12.0]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 30. LineString provided (unsupported)
    cases.append({
        "plot_id": "STRESS-30-LINESTRING-UNSUPPORTED",
        "country_code": "BR",
        "area_hectares": 10.0,
        "geometry": {
            "type": "LineString",
            "coordinates": [[-55.0, -12.0], [-55.01, -12.01]]
        },
        "production_date": "2024-05-01"
    })
    # 31. MultiPoint provided (unsupported)
    cases.append({
        "plot_id": "STRESS-31-MULTIPOINT-UNSUPPORTED",
        "country_code": "ID",
        "area_hectares": 15.0,
        "geometry": {
            "type": "MultiPoint",
            "coordinates": [[101.5, 0.5], [101.6, 0.6]]
        },
        "production_date": "2024-05-01"
    })

    # --- Category 6: Coordinate Bounds & Value Malformations ---
    # 32. Out of bounds Longitude (lon = 250)
    cases.append({
        "plot_id": "STRESS-32-OOB-LON",
        "country_code": "ID",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [250.0, 0.5]},
        "production_date": "2024-05-01"
    })
    # 33. Out of bounds Latitude (lat = 120)
    cases.append({
        "plot_id": "STRESS-33-OOB-LAT",
        "country_code": "BR",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [-55.0, 120.0]},
        "production_date": "2024-05-01"
    })
    # 34. Global negative out of bounds
    cases.append({
        "plot_id": "STRESS-34-OOB-NEG",
        "country_code": "GH",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [-200.0, -100.0]},
        "production_date": "2024-05-01"
    })
    # 35. Empty coordinates array
    cases.append({
        "plot_id": "STRESS-35-EMPTY-COORDS",
        "country_code": "CI",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": []},
        "production_date": "2024-05-01"
    })
    # 36. Single dimension point coordinate
    cases.append({
        "plot_id": "STRESS-36-SINGLE-COORD-PT",
        "country_code": "VN",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [108.0]},
        "production_date": "2024-05-01"
    })
    # 37. 3D coordinates with altitude (should strip 3D)
    cases.append({
        "plot_id": "STRESS-37-3D-ELEVATION-PT",
        "country_code": "ID",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [101.5, 0.5, 450.0]},
        "production_date": "2024-05-01"
    })
    # 38. 3D coordinates in Polygon ring
    cases.append({
        "plot_id": "STRESS-38-3D-POLY",
        "country_code": "BR",
        "area_hectares": 12.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-55.0, -12.0, 100.0],
                [-54.99, -12.0, 110.0],
                [-54.99, -11.99, 105.0],
                [-55.0, -11.99, 102.0],
                [-55.0, -12.0, 100.0]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 39. Zero-area collapsed single-point polygon
    cases.append({
        "plot_id": "STRESS-39-COLLAPSED-PT-POLY",
        "country_code": "GH",
        "area_hectares": 8.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-1.5, 6.5], [-1.5, 6.5], [-1.5, 6.5], [-1.5, 6.5]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 40. 2-point line collapsed polygon
    cases.append({
        "plot_id": "STRESS-40-LINE-COLLAPSED-POLY",
        "country_code": "CI",
        "area_hectares": 10.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-5.5, 6.5], [-5.49, 6.5], [-5.5, 6.5]
            ]]
        },
        "production_date": "2024-05-01"
    })

    # --- Category 7: Casing & Schema Robustness ---
    # 41. Lowercase "polygon"
    cases.append({
        "plot_id": "STRESS-41-LOWERCASE-TYPE",
        "country_code": "VN",
        "area_hectares": 10.0,
        "geometry": {
            "type": "polygon",
            "coordinates": [[
                [108.0, 12.0], [108.01, 12.0], [108.01, 12.01], [108.0, 12.01], [108.0, 12.0]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 42. Uppercase "POINT"
    cases.append({
        "plot_id": "STRESS-42-UPPERCASE-TYPE",
        "country_code": "ID",
        "area_hectares": 2.0,
        "geometry": {"type": "POINT", "coordinates": [101.5, 0.5]},
        "production_date": "2024-05-01"
    })
    # 43. Lowercase "multipolygon"
    cases.append({
        "plot_id": "STRESS-43-LOWERCASE-MULTI",
        "country_code": "BR",
        "area_hectares": 20.0,
        "geometry": {
            "type": "multipolygon",
            "coordinates": [
                [[[-55.0, -12.0], [-54.99, -12.0], [-54.99, -11.99], [-55.0, -11.99], [-55.0, -12.0]]]
            ]
        },
        "production_date": "2024-05-01"
    })
    # 44. Coarse integer coords [100, 0] (precision warning check)
    cases.append({
        "plot_id": "STRESS-44-COARSE-INTEGER-PRECISION",
        "country_code": "ID",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [101, 0]},
        "production_date": "2024-05-01"
    })
    # 45. Ultra-high precision (14 decimal places with float jitter)
    cases.append({
        "plot_id": "STRESS-45-ULTRA-PRECISION",
        "country_code": "GH",
        "area_hectares": 2.0,
        "geometry": {"type": "Point", "coordinates": [-1.50000000000001, 6.50000000000002]},
        "production_date": "2024-05-01"
    })

    # --- Category 8: Area Discrepancies, Cloud Fallback & Compound Faults ---
    # 46. Extreme Area Discrepancy (Declared 500 ha, GIS 1.2 ha)
    cases.append({
        "plot_id": "STRESS-46-AREA-DISCREPANCY",
        "country_code": "CI",
        "area_hectares": 500.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-5.5, 6.5], [-5.49, 6.5], [-5.49, 6.51], [-5.5, 6.51], [-5.5, 6.5]
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 47. Cloud Cover Fallback (90% cloud cover triggering Sentinel-1 SAR radar)
    cases.append({
        "plot_id": "STRESS-47-SAR-CLOUD-FALLBACK",
        "country_code": "ID",
        "area_hectares": 15.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [101.5, 0.5], [101.51, 0.5], [101.51, 0.51], [101.5, 0.51], [101.5, 0.5]
            ]]
        },
        "production_date": "2024-05-01",
        "notes": "high_cloud_cover_90pct_cloud_fallback"
    })
    # 48. 10m Buffer Boundary Collision / Interference
    cases.append({
        "plot_id": "STRESS-48-BUFFER-INTERFERENCE",
        "country_code": "BR",
        "area_hectares": 12.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-55.0, -12.0], [-54.99, -12.0], [-54.99, -11.99], [-55.0, -11.99], [-55.0, -12.0]
            ]]
        },
        "production_date": "2024-05-01",
        "notes": "buffer_collision_edge_loss"
    })
    # 49. Triple Compound Defect: Unclosed + Inverted + Duplicate Vertices
    cases.append({
        "plot_id": "STRESS-49-TRIPLE-COMPOUND-DEFECT",
        "country_code": "ID",
        "area_hectares": 14.0,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [0.500000, 101.500000],  # inverted [lat, lon]
                [0.500000, 101.500000],  # duplicate
                [0.500000, 101.510000],
                [0.510000, 101.510000],
                [0.510000, 101.500000]   # unclosed
            ]]
        },
        "production_date": "2024-05-01"
    })
    # 50. MultiPolygon with 2 Bowtie parcels + inverted coords
    cases.append({
        "plot_id": "STRESS-50-EXTREME-MULTI-BOWTIE",
        "country_code": "BR",
        "area_hectares": 35.0,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[
                    [-12.0, -55.0], [-11.99, -54.99], [-11.99, -55.0], [-12.0, -54.99], [-12.0, -55.0]  # Inverted & bowtie
                ]],
                [[
                    [-12.02, -55.02], [-12.01, -55.01], [-12.01, -55.02], [-12.02, -55.01], [-12.02, -55.02]
                ]]
            ]
        },
        "production_date": "2024-05-01"
    })

    return cases


def test_50_malicious_cases_generator_count():
    """Verify exactly 50 distinct malicious test cases are generated."""
    cases = generate_50_malicious_plots()
    assert len(cases) == 50, f"Expected 50 cases, got {len(cases)}"


def test_50_malicious_cases_pipeline_resilience():
    """
    Stress test: Feed all 50 malicious cases into the EUDR compliance engine.
    Criteria for 100% resilience:
    1. Zero unhandled server crashes (no 500 error / unhandled exception).
    2. Every case is either 'Self-Healed & Validated' or returned with a 'Clear Pre-validation Error Report'.
    3. Self-healing logs correctly track healing actions.
    """
    cases = generate_50_malicious_plots()

    healed_count = 0
    clean_error_count = 0
    passed_count = 0

    for idx, plot_data in enumerate(cases, 1):
        plot = ProductionPlotInput(**plot_data)
        
        # Validate via spatial validator
        result = SpatialValidator.validate_plot(plot, auto_heal=True)
        assert isinstance(result, SpatialPlotResult)
        assert isinstance(result.is_valid, bool)

        if result.healing_applied:
            healed_count += 1
            assert len(result.healing_actions) > 0

        if result.is_valid:
            passed_count += 1
        else:
            clean_error_count += 1
            assert len(result.errors) > 0
            # Ensure error is structured and human-readable
            for err in result.errors:
                assert isinstance(err, str) and len(err) > 5

    # Out of 50 extreme cases, a substantial portion should be automatically healed
    assert healed_count >= 20, f"Expected at least 20 auto-healed cases, got {healed_count}"
    assert (passed_count + clean_error_count) == 50, "All 50 cases must be deterministically accounted for"


def test_batch_api_simulate_with_malicious_dataset():
    """
    Test end-to-end API simulation endpoint (/api/v1/eudr/simulate) with the 50 malicious plots.
    Ensures HTTP 200 response, comprehensive summary metrics, and zero server crashes.
    """
    plots = generate_50_malicious_plots()
    payload = {
        "supplier_id": "SUPP-STRESS-50-MALICIOUS",
        "operator": {
            "operator_name": "Resilience Test Corp",
            "eori_number": "NL8899776655",
            "country": "NL",
            "address": "Rotterdam Harbor"
        },
        "commodity": {
            "hs_code": "090111",
            "description": "Green Coffee Beans",
            "net_mass_kg": 150000.0
        },
        "plots": plots,
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Land Ministry", "issue_date": "2020-01-01"},
            {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Agri Ministry", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
            {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Chamber of Commerce", "issue_date": "2019-01-01"}
        ]
    }

    t0 = time.perf_counter()
    resp = client.post("/api/v1/eudr/simulate", json=payload)
    latency_sec = time.perf_counter() - t0

    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["spatial_summary"]["total_plots"] == 50
    assert "healed_plots_count" in data["spatial_summary"]
    assert data["spatial_summary"]["healed_plots_count"] >= 20
    assert len(data["plots_detail"]) == 50
    assert latency_sec < 3.0, f"50-malicious-plot simulation took {latency_sec:.2f}s (expected < 3.0s)"


def test_cloud_fallback_sar_activation():
    """Verify that cloudy plot triggers Sentinel-1 SAR radar backscatter fallback."""
    cloudy_plot = ProductionPlotInput(
        plot_id="PLOT-CLOUD-SAR-TEST",
        country_code="ID",
        area_hectares=10.0,
        geometry={
            "type": "Polygon",
            "coordinates": [[
                [101.5, 0.5], [101.51, 0.5], [101.51, 0.51], [101.5, 0.51], [101.5, 0.5]
            ]]
        },
        production_date=date(2024, 5, 1),
        notes="cloud_fallback_dense_tropical_rain"
    )
    spatial_res = SpatialValidator.validate_plot(cloudy_plot)
    sat_res = DeforestationSimulator.analyze_plot(cloudy_plot, spatial_res)

    assert sat_res.cloud_fallback_applied is True
    assert sat_res.sensor_mode == "SAR_SENTINEL_1_C_BAND"
    assert sat_res.sar_backscatter_analysis is not None
    assert sat_res.sar_backscatter_analysis["cloud_penetration_success"] is True
    assert "Sentinel-1" in sat_res.sar_backscatter_analysis["sar_sensor"]


def test_10m_buffer_zone_interference_calculation():
    """Verify 10m buffer zone interference module calculates boundary buffer correctly."""
    boundary_plot = ProductionPlotInput(
        plot_id="PLOT-BUFFER-TEST",
        country_code="BR",
        area_hectares=15.0,
        geometry={
            "type": "Polygon",
            "coordinates": [[
                [-55.0, -12.0], [-54.99, -12.0], [-54.99, -11.99], [-55.0, -11.99], [-55.0, -12.0]
            ]]
        },
        production_date=date(2024, 5, 1),
        notes="buffer_collision_edge_loss"
    )
    spatial_res = SpatialValidator.validate_plot(boundary_plot)
    sat_res = DeforestationSimulator.analyze_plot(boundary_plot, spatial_res)

    assert sat_res.buffer_zone_analysis is not None
    assert sat_res.buffer_zone_analysis["buffer_distance_meters"] == 10.0
    assert sat_res.buffer_zone_analysis["buffer_interference_detected"] is True
    assert sat_res.buffer_zone_analysis["buffer_area_ha"] > 0.0
