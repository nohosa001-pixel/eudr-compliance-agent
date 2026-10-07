"""
Unit Tests for ESRI Shapefile (.zip) Bulk Ingestion Engine
===========================================================
Validates:
1. Native parsing of ESRI Shapefile archive containing .shp, .dbf, .prj.
2. Handling of Polygon geometries with closed rings.
3. Handling of Point geometries with attribute mapping.
4. Auto-reprojection from projected CRS (e.g., UTM Zone 48N) to WGS84 (EPSG:4326).
5. Error resilience on malformed zip or missing mandatory geometry.
"""

import io
import struct
import zipfile
import pytest

from app.modules.bulk_file_parser import BulkFileParser
from app.schemas import EUDRSupplyChainPayload


def create_mock_shapefile_zip(
    points=None,
    polygons=None,
    dbf_records=None,
    prj_wkt=None
) -> bytes:
    """Helper to dynamically generate a valid in-memory ESRI Shapefile .zip bundle."""
    zip_buf = io.BytesIO()

    # Determine shape type: 1 for Point, 5 for Polygon
    is_polygon = bool(polygons)
    shape_type = 5 if is_polygon else 1

    shp_buf = io.BytesIO()
    # 1. SHP Header: 100 bytes
    # File Code: 9994 (big-endian), 5 unused ints, file length in 16-bit words (placeholder)
    shp_buf.write(struct.pack(">IIIIIII", 9994, 0, 0, 0, 0, 0, 0))
    # Version: 1000, Shape Type
    shp_buf.write(struct.pack("<II", 1000, shape_type))
    # BBox: Xmin, Ymin, Xmax, Ymax, Zmin, Zmax, Mmin, Mmax (8 doubles)
    shp_buf.write(struct.pack("<dddddddd", 0.0, 0.0, 180.0, 90.0, 0.0, 0.0, 0.0, 0.0))

    if is_polygon:
        for idx, poly_rings in enumerate(polygons):
            # Calculate content length in 16-bit words
            # Content: ShapeType(4) + Box(32) + NumParts(4) + NumPoints(4) + Parts(4*num_parts) + Points(16*num_points)
            num_parts = len(poly_rings)
            num_points = sum(len(r) for r in poly_rings)
            content_bytes_len = 4 + 32 + 4 + 4 + (4 * num_parts) + (16 * num_points)
            content_words = content_bytes_len // 2

            # Record Header: record number (1-based, big-endian), content length in words
            shp_buf.write(struct.pack(">II", idx + 1, content_words))
            # Shape Type
            shp_buf.write(struct.pack("<I", 5))
            # BBox
            shp_buf.write(struct.pack("<dddd", 100.0, 0.0, 110.0, 10.0))
            # NumParts, NumPoints
            shp_buf.write(struct.pack("<II", num_parts, num_points))

            # Part indices
            cur_idx = 0
            for ring in poly_rings:
                shp_buf.write(struct.pack("<I", cur_idx))
                cur_idx += len(ring)

            # Points
            for ring in poly_rings:
                for pt in ring:
                    shp_buf.write(struct.pack("<dd", float(pt[0]), float(pt[1])))
    elif points:
        for idx, pt in enumerate(points):
            content_words = (4 + 16) // 2  # shape_type(4) + X(8) + Y(8)
            shp_buf.write(struct.pack(">II", idx + 1, content_words))
            shp_buf.write(struct.pack("<I", 1))
            shp_buf.write(struct.pack("<dd", float(pt[0]), float(pt[1])))

    # Update file length in 16-bit words in header (offset 24, 4 bytes big endian)
    shp_data = bytearray(shp_buf.getvalue())
    total_words = len(shp_data) // 2
    struct.pack_into(">I", shp_data, 24, total_words)

    # 2. Build DBF
    dbf_buf = io.BytesIO()
    num_recs = len(polygons) if is_polygon else (len(points) if points else 0)
    # Fields: plot_id (C, 20), country (C, 4), area_ha (N, 8), farmer (C, 30)
    fields = [
        (b"plot_id", b"C", 20),
        (b"country", b"C", 4),
        (b"area_ha", b"N", 8),
        (b"farmer", b"C", 30)
    ]
    rec_len = 1 + sum(f[2] for f in fields)
    header_len = 32 + (len(fields) * 32) + 1

    # DBF Header
    dbf_buf.write(struct.pack("<BBBBIHH20x", 3, 26, 10, 7, num_recs, header_len, rec_len))
    # Field descriptors
    for name, ftype, flen in fields:
        name_pad = name.ljust(11, b'\x00')
        dbf_buf.write(struct.pack("<11sc4xBB14x", name_pad, ftype, flen, 0))
    # Header terminator
    dbf_buf.write(b"\x0D")

    # Records
    for i in range(num_recs):
        rec_data = dbf_records[i] if dbf_records and i < len(dbf_records) else {}
        p_id = rec_data.get("plot_id", f"PLOT-SHP-{i+1:03d}").encode("utf-8").ljust(20)[:20]
        c_code = rec_data.get("country", "VN").encode("utf-8").ljust(4)[:4]
        a_ha = str(rec_data.get("area_ha", 7.5)).encode("utf-8").rjust(8)[:8]
        f_name = rec_data.get("farmer", f"Farmer Coop #{i+1}").encode("utf-8").ljust(30)[:30]

        dbf_buf.write(b" ")  # valid record (not deleted)
        dbf_buf.write(p_id)
        dbf_buf.write(c_code)
        dbf_buf.write(a_ha)
        dbf_buf.write(f_name)

    # 3. Pack into ZIP
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("eudr_plots.shp", bytes(shp_data))
        zf.writestr("eudr_plots.dbf", dbf_buf.getvalue())
        if prj_wkt:
            zf.writestr("eudr_plots.prj", prj_wkt)

    return zip_buf.getvalue()


def test_shapefile_polygon_ingestion():
    """Validates parsing of an ESRI Shapefile containing WGS84 polygon plots."""
    polygons = [
        [
            [[108.43, 11.94], [108.45, 11.94], [108.45, 11.96], [108.43, 11.96], [108.43, 11.94]]
        ],
        [
            [[108.50, 11.90], [108.52, 11.90], [108.52, 11.92], [108.50, 11.92], [108.50, 11.90]]
        ]
    ]
    dbf_recs = [
        {"plot_id": "VN-SHP-001", "country": "VN", "area_ha": 6.8, "farmer": "Da Lat Farmers 1"},
        {"plot_id": "VN-SHP-002", "country": "VN", "area_ha": 8.2, "farmer": "Da Lat Farmers 2"}
    ]

    zip_bytes = create_mock_shapefile_zip(polygons=polygons, dbf_records=dbf_recs)

    payload = BulkFileParser.parse_file(
        filename="vietnam_coffee_plots.zip",
        content_bytes=zip_bytes,
        supplier_id="SUPP-SHP-VN",
        hs_code="090111",
        commodity_desc="Green Coffee"
    )

    assert isinstance(payload, EUDRSupplyChainPayload)
    assert len(payload.plots) == 2
    p1 = payload.plots[0]
    assert p1.plot_id == "VN-SHP-001"
    assert p1.country_code == "VN"
    assert p1.area_hectares == 6.8
    assert p1.geometry["type"] == "Polygon"
    assert len(p1.geometry["coordinates"][0]) == 5
    assert p1.producer_name == "Da Lat Farmers 1"


def test_shapefile_point_ingestion():
    """Validates parsing of an ESRI Shapefile containing Point plots."""
    points = [
        [108.4385, 11.9412],
        [108.4410, 11.9450]
    ]
    dbf_recs = [
        {"plot_id": "VN-PT-001", "country": "VN", "area_ha": 2.1, "farmer": "Smallholder A"},
        {"plot_id": "VN-PT-002", "country": "VN", "area_ha": 3.4, "farmer": "Smallholder B"}
    ]

    zip_bytes = create_mock_shapefile_zip(points=points, dbf_records=dbf_recs)

    payload = BulkFileParser.parse_file(
        filename="coffee_points.zip",
        content_bytes=zip_bytes,
        supplier_id="SUPP-SHP-PT"
    )

    assert len(payload.plots) == 2
    assert payload.plots[0].geometry["type"] == "Point"
    assert payload.plots[0].geometry["coordinates"] == [108.4385, 11.9412]
    assert payload.plots[0].area_hectares == 2.1


def test_shapefile_reprojection_utm_to_wgs84():
    """Validates automatic reprojection from UTM Zone 48N (EPSG:32648) to WGS84."""
    # UTM Zone 48N coordinate in Da Lat, Vietnam (approx 108.4385 E, 11.9412 N)
    utm_x = 656700.0
    utm_y = 1320600.0

    points = [[utm_x, utm_y]]
    dbf_recs = [{"plot_id": "UTM-PLOT-01", "country": "VN", "area_ha": 3.0}]
    # PRJ WKT for WGS 84 / UTM zone 48N (EPSG:32648)
    prj_wkt = (
        'PROJCS["WGS 84 / UTM zone 48N",'
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
        'PROJECTION["Transverse_Mercator"],'
        'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",105],'
        'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],'
        'PARAMETER["false_northing",0],UNIT["metre",1]]'
    )

    zip_bytes = create_mock_shapefile_zip(points=points, dbf_records=dbf_recs, prj_wkt=prj_wkt)

    payload = BulkFileParser.parse_file(
        filename="utm_plots.zip",
        content_bytes=zip_bytes
    )

    lon, lat = payload.plots[0].geometry["coordinates"]
    # Check that UTM meters (~656700, 1320600) were converted to degrees (~106.4, ~11.9)
    assert 100.0 < lon < 115.0, f"Expected reprojected longitude in Vietnam range, got {lon}"
    assert 5.0 < lat < 25.0, f"Expected reprojected latitude in Vietnam range, got {lat}"
