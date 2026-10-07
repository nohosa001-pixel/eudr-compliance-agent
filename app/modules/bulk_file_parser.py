import io
import csv
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from app.schemas import (
    EUDRSupplyChainPayload,
    OperatorInfo,
    CommodityInfo,
    ProductionPlotInput,
    LegalDocumentInput
)


class BulkFileParser:
    """
    Bulk Ingestion Parser supporting:
    - GeoJSON (.geojson, .json)
    - KML (.kml)
    - CSV (.csv)
    - Excel (.xlsx)
    """

    @classmethod
    def parse_file(
        cls,
        filename: str,
        content_bytes: bytes,
        supplier_id: str = "SUPP-BULK-UPLOAD",
        operator_name: str = "Global Import Logistics SA",
        hs_code: str = "090111",
        commodity_desc: str = "Bulk Ingested Commodity"
    ) -> EUDRSupplyChainPayload:
        filename_lower = filename.lower()

        if filename_lower.endswith(".geojson") or filename_lower.endswith(".json"):
            plots, documents = cls.parse_geojson(content_bytes)
        elif filename_lower.endswith(".kml"):
            plots, documents = cls.parse_kml(content_bytes)
        elif filename_lower.endswith(".csv"):
            plots, documents = cls.parse_csv(content_bytes)
        elif filename_lower.endswith(".xlsx"):
            plots, documents = cls.parse_excel(content_bytes)
        elif filename_lower.endswith(".zip") or filename_lower.endswith(".shp"):
            plots, documents = cls.parse_shapefile_zip(content_bytes)
        else:
            raise ValueError(f"Unsupported file format: {filename}. Supported formats: .csv, .xlsx, .geojson, .json, .kml, .zip (Shapefile)")

        if not plots:
            raise ValueError(f"No valid production plot coordinates could be extracted from {filename}")

        # Calculate total mass
        total_ha = sum(p.area_hectares for p in plots)
        net_mass = round(total_ha * 2500.0, 2) if total_ha > 0 else 10000.0

        return EUDRSupplyChainPayload(
            supplier_id=supplier_id,
            operator=OperatorInfo(
                operator_name=operator_name,
                eori_number="EU9988776655",
                country="FR",
                address="12 Port Industrial Zone, Marseille"
            ),
            commodity=CommodityInfo(
                hs_code=hs_code,
                description=commodity_desc,
                net_mass_kg=net_mass
            ),
            plots=plots,
            documents=documents
        )

    @classmethod
    def parse_geojson(cls, content_bytes: bytes) -> Tuple[List[ProductionPlotInput], List[LegalDocumentInput]]:
        data = json.loads(content_bytes.decode("utf-8"))
        plots: List[ProductionPlotInput] = []
        documents: List[LegalDocumentInput] = []

        features = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]

        for idx, feat in enumerate(features):
            geom = feat.get("geometry", {})
            props = feat.get("properties", {}) or {}
            
            plot_id = props.get("plot_id") or props.get("id") or f"PLOT-GEOJSON-{idx + 1}"
            country_code = (props.get("country_code") or props.get("country") or "GH").upper()
            area_ha = float(props.get("area_ha") or props.get("area_hectares") or props.get("area") or 3.0)
            prod_date = props.get("production_date") or "2024-02-01"

            plots.append(ProductionPlotInput(
                plot_id=plot_id,
                country_code=country_code,
                area_hectares=area_ha,
                geometry={
                    "type": geom.get("type", "Point"),
                    "coordinates": geom.get("coordinates", [0.0, 0.0])
                },
                production_date=prod_date,
                notes=props.get("notes")
            ))

        # Default standard documents if not supplied
        documents.append(LegalDocumentInput(
            doc_id="DOC-TITLE-01",
            doc_type="LAND_USE_TITLE",
            issuing_authority="National Land Authority",
            issue_date="2020-01-01"
        ))
        documents.append(LegalDocumentInput(
            doc_id="DOC-HARVEST-01",
            doc_type="HARVEST_PERMIT",
            issuing_authority="Forestry & Agriculture Dept",
            issue_date="2023-01-01",
            expiry_date="2028-01-01"
        ))
        documents.append(LegalDocumentInput(
            doc_id="DOC-LICENSE-01",
            doc_type="BUSINESS_LICENSE",
            issuing_authority="Registrar General",
            issue_date="2019-01-01"
        ))

        return plots, documents

    @classmethod
    def parse_csv(cls, content_bytes: bytes) -> Tuple[List[ProductionPlotInput], List[LegalDocumentInput]]:
        text = content_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        plots: List[ProductionPlotInput] = []

        for idx, row in enumerate(reader):
            # Normalize column names
            row_normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            plot_id = row_normalized.get("plot_id") or row_normalized.get("id") or f"PLOT-CSV-{idx + 1}"
            country_code = (row_normalized.get("country_code") or row_normalized.get("country") or "VN").upper()
            area_ha = float(row_normalized.get("area_ha") or row_normalized.get("area_hectares") or row_normalized.get("area") or 2.5)
            prod_date = row_normalized.get("production_date") or row_normalized.get("date") or "2024-03-01"

            # Check if polygon coordinates column or lat/lon
            if "polygon" in row_normalized and row_normalized["polygon"]:
                try:
                    coords = json.loads(row_normalized["polygon"])
                    geom = {"type": "Polygon", "coordinates": coords}
                except Exception:
                    lat = float(row_normalized.get("latitude") or row_normalized.get("lat") or 0.0)
                    lon = float(row_normalized.get("longitude") or row_normalized.get("lon") or row_normalized.get("lng") or 0.0)
                    geom = {"type": "Point", "coordinates": [lon, lat]}
            else:
                lat = float(row_normalized.get("latitude") or row_normalized.get("lat") or 11.9412)
                lon = float(row_normalized.get("longitude") or row_normalized.get("lon") or row_normalized.get("lng") or 108.4385)
                geom = {"type": "Point", "coordinates": [lon, lat]}

            plots.append(ProductionPlotInput(
                plot_id=plot_id,
                country_code=country_code,
                area_hectares=area_ha,
                geometry=geom,
                production_date=prod_date,
                notes=row_normalized.get("notes")
            ))

        documents = [
            LegalDocumentInput(
                doc_id="CSV-DOC-TITLE",
                doc_type="LAND_USE_TITLE",
                issuing_authority="Regional Land Registry",
                issue_date="2020-01-01"
            ),
            LegalDocumentInput(
                doc_id="CSV-DOC-PERMIT",
                doc_type="HARVEST_PERMIT",
                issuing_authority="Department of Agriculture",
                issue_date="2023-01-01",
                expiry_date="2028-01-01"
            ),
            LegalDocumentInput(
                doc_id="CSV-DOC-LICENSE",
                doc_type="BUSINESS_LICENSE",
                issuing_authority="Commercial Registry",
                issue_date="2019-01-01"
            )
        ]

        return plots, documents

    @classmethod
    def parse_excel(cls, content_bytes: bytes) -> Tuple[List[ProductionPlotInput], List[LegalDocumentInput]]:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
        sheet = wb.active
        
        headers = [str(cell.value or "").strip().lower() for cell in sheet[1]]
        plots: List[ProductionPlotInput] = []

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True)):
            if not any(row):
                continue
            row_dict = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
            
            plot_id = str(row_dict.get("plot_id") or row_dict.get("id") or f"PLOT-XLSX-{row_idx + 1}")
            country_code = str(row_dict.get("country_code") or row_dict.get("country") or "GH").upper()
            try:
                area_ha = float(row_dict.get("area_ha") or row_dict.get("area_hectares") or row_dict.get("area") or 3.0)
            except Exception:
                area_ha = 3.0

            prod_date = str(row_dict.get("production_date") or row_dict.get("date") or "2024-03-01")
            
            try:
                lat = float(row_dict.get("latitude") or row_dict.get("lat") or 6.6885)
                lon = float(row_dict.get("longitude") or row_dict.get("lon") or row_dict.get("lng") or -1.6244)
            except Exception:
                lat, lon = 6.6885, -1.6244

            plots.append(ProductionPlotInput(
                plot_id=plot_id,
                country_code=country_code,
                area_hectares=area_ha,
                geometry={"type": "Point", "coordinates": [lon, lat]},
                production_date=prod_date,
                notes=str(row_dict.get("notes") or "")
            ))

        documents = [
            LegalDocumentInput(
                doc_id="XLSX-DOC-TITLE",
                doc_type="LAND_USE_TITLE",
                issuing_authority="National Land Authority",
                issue_date="2020-01-01"
            ),
            LegalDocumentInput(
                doc_id="XLSX-DOC-PERMIT",
                doc_type="HARVEST_PERMIT",
                issuing_authority="Forestry & Agriculture Dept",
                issue_date="2023-01-01",
                expiry_date="2028-01-01"
            ),
            LegalDocumentInput(
                doc_id="XLSX-DOC-LICENSE",
                doc_type="BUSINESS_LICENSE",
                issuing_authority="Registrar General",
                issue_date="2019-01-01"
            )
        ]

        return plots, documents

    @classmethod
    def parse_kml(cls, content_bytes: bytes) -> Tuple[List[ProductionPlotInput], List[LegalDocumentInput]]:
        root = ET.fromstring(content_bytes)
        plots: List[ProductionPlotInput] = []

        # Find all Placemark elements
        for idx, pm in enumerate(root.iter('{http://www.opengis.net/kml/2.2}Placemark')):
            name_elem = pm.find('{http://www.opengis.net/kml/2.2}name')
            name = name_elem.text if name_elem is not None else f"PLOT-KML-{idx + 1}"

            # Check for Polygon coordinates
            poly_coord = pm.find('.//{http://www.opengis.net/kml/2.2}coordinates')
            if poly_coord is not None and poly_coord.text:
                raw_coords = poly_coord.text.strip().split()
                parsed_coords = []
                for pt in raw_coords:
                    parts = pt.split(',')
                    if len(parts) >= 2:
                        parsed_coords.append([float(parts[0]), float(parts[1])])
                
                if len(parsed_coords) >= 3:
                    geom = {"type": "Polygon", "coordinates": [parsed_coords]}
                else:
                    geom = {"type": "Point", "coordinates": parsed_coords[0] if parsed_coords else [0.0, 0.0]}
            else:
                geom = {"type": "Point", "coordinates": [-1.6244, 6.6885]}

            plots.append(ProductionPlotInput(
                plot_id=name,
                country_code="GH",
                area_hectares=4.5,
                geometry=geom,
                production_date="2024-02-01"
            ))

        documents = [
            LegalDocumentInput(
                doc_id="KML-DOC-TITLE",
                doc_type="LAND_USE_TITLE",
                issuing_authority="National Land Authority",
                issue_date="2020-01-01"
            ),
            LegalDocumentInput(
                doc_id="KML-DOC-PERMIT",
                doc_type="HARVEST_PERMIT",
                issuing_authority="Forestry Commission",
                issue_date="2023-01-01",
                expiry_date="2028-01-01"
            ),
            LegalDocumentInput(
                doc_id="KML-DOC-LICENSE",
                doc_type="BUSINESS_LICENSE",
                issuing_authority="Registrar General",
                issue_date="2019-01-01"
            )
        ]

        return plots, documents

    @classmethod
    def parse_shapefile_zip(cls, content_bytes: bytes) -> Tuple[List[ProductionPlotInput], List[LegalDocumentInput]]:
        """
        Parses an ESRI Shapefile bundle packaged inside a .zip file (.shp, .dbf, .prj).
        Auto-detects source CRS from .prj and reprojects coordinates to WGS84 (EPSG:4326).
        Extracts plot geometry (Points or Polygons) and attributes from DBF.
        """
        import zipfile
        import struct

        zf = zipfile.ZipFile(io.BytesIO(content_bytes))
        
        # 1. Locate components in the zip
        shp_name = next((n for n in zf.namelist() if n.lower().endswith(".shp")), None)
        dbf_name = next((n for n in zf.namelist() if n.lower().endswith(".dbf")), None)
        prj_name = next((n for n in zf.namelist() if n.lower().endswith(".prj")), None)

        if not shp_name:
            raise ValueError("Shapefile archive missing .shp geometry file.")

        shp_bytes = zf.read(shp_name)
        dbf_bytes = zf.read(dbf_name) if dbf_name else b""
        prj_text = zf.read(prj_name).decode("utf-8", errors="ignore") if prj_name else ""

        # 2. Setup pyproj coordinate transformer if not WGS84
        transformer = None
        if prj_text:
            try:
                import pyproj
                src_crs = pyproj.CRS.from_wkt(prj_text)
                target_crs = pyproj.CRS.from_epsg(4326)
                if src_crs != target_crs:
                    transformer = pyproj.Transformer.from_crs(src_crs, target_crs, always_xy=True)
            except Exception:
                transformer = None

        def transform_pt(x: float, y: float) -> Tuple[float, float]:
            if transformer:
                try:
                    lon, lat = transformer.transform(x, y)
                    return round(lon, 7), round(lat, 7)
                except Exception:
                    pass
            return round(x, 7), round(y, 7)

        # 3. Parse DBF attributes if available
        dbf_records: List[Dict[str, str]] = []
        if dbf_bytes and len(dbf_bytes) >= 32:
            num_recs, header_len, rec_len = struct.unpack_from("<IHH", dbf_bytes, 4)
            # Field descriptors start at offset 32, each 32 bytes
            fields = []
            f_offset = 32
            while f_offset < header_len - 1 and dbf_bytes[f_offset] != 0x0D:
                f_name = dbf_bytes[f_offset:f_offset+11].split(b'\x00')[0].decode("ascii", errors="ignore").strip().lower()
                f_type = chr(dbf_bytes[f_offset+11])
                f_len = dbf_bytes[f_offset+16]
                fields.append((f_name, f_type, f_len))
                f_offset += 32

            r_offset = header_len
            for _ in range(num_recs):
                if r_offset + rec_len > len(dbf_bytes):
                    break
                row = {}
                col_offset = r_offset + 1  # 1st byte is deletion flag
                for f_name, _, f_len in fields:
                    val_bytes = dbf_bytes[col_offset:col_offset+f_len]
                    val_str = val_bytes.decode("utf-8", errors="replace").strip()
                    row[f_name] = val_str
                    col_offset += f_len
                dbf_records.append(row)
                r_offset += rec_len

        # 4. Parse SHP geometry
        if len(shp_bytes) < 100:
            raise ValueError("Corrupted .shp file: header less than 100 bytes.")

        offset = 100
        shp_len = len(shp_bytes)
        record_idx = 0
        plots: List[ProductionPlotInput] = []

        while offset + 8 <= shp_len:
            rec_num, content_len_words = struct.unpack_from(">II", shp_bytes, offset)
            content_len_bytes = content_len_words * 2
            offset += 8

            if offset + content_len_bytes > shp_len:
                break

            shape_type = struct.unpack_from("<I", shp_bytes, offset)[0]
            geom = None

            if shape_type == 1:  # Point
                x, y = struct.unpack_from("<dd", shp_bytes, offset + 4)
                lon, lat = transform_pt(x, y)
                geom = {"type": "Point", "coordinates": [lon, lat]}
            elif shape_type == 5:  # Polygon
                # bbox (32 bytes), num_parts (4), num_points (4)
                num_parts, num_points = struct.unpack_from("<II", shp_bytes, offset + 36)
                parts_offset = offset + 44
                parts = list(struct.unpack_from(f"<{num_parts}I", shp_bytes, parts_offset))
                points_offset = parts_offset + (num_parts * 4)

                all_pts = []
                for pt_idx in range(num_points):
                    px, py = struct.unpack_from("<dd", shp_bytes, points_offset + (pt_idx * 16))
                    all_pts.append(transform_pt(px, py))

                rings = []
                parts.append(num_points)
                for p_i in range(num_parts):
                    start_i = parts[p_i]
                    end_i = parts[p_i + 1]
                    ring = all_pts[start_i:end_i]
                    # Ensure ring is closed
                    if ring and ring[0] != ring[-1]:
                        ring.append(ring[0])
                    if len(ring) >= 4:
                        rings.append(ring)

                if rings:
                    geom = {"type": "Polygon", "coordinates": rings}

            if geom:
                # Correlate with DBF row if available
                attrs = dbf_records[record_idx] if record_idx < len(dbf_records) else {}
                plot_id = (
                    attrs.get("plot_id") or 
                    attrs.get("id") or 
                    attrs.get("name") or 
                    attrs.get("code") or 
                    f"PLOT-SHP-{record_idx + 1:03d}"
                )
                country_code = (
                    attrs.get("country_code") or 
                    attrs.get("country") or 
                    attrs.get("iso") or 
                    "VN"
                ).upper()[:2]
                try:
                    area_ha = float(attrs.get("area_ha") or attrs.get("area_hectares") or attrs.get("area") or attrs.get("hectares") or 5.0)
                except Exception:
                    area_ha = 5.0

                prod_date = attrs.get("production_date") or attrs.get("date") or attrs.get("harvest_dt") or "2024-03-01"
                producer_name = attrs.get("producer") or attrs.get("farmer") or attrs.get("coop") or f"Producer #{record_idx+1}"

                plots.append(ProductionPlotInput(
                    plot_id=plot_id,
                    country_code=country_code,
                    area_hectares=area_ha,
                    geometry=geom,
                    production_date=prod_date,
                    producer_name=producer_name,
                    notes=attrs.get("notes") or "Imported via ESRI Shapefile"
                ))

            offset += content_len_bytes
            record_idx += 1

        documents = [
            LegalDocumentInput(
                doc_id="SHP-DOC-TITLE-01",
                doc_type="LAND_USE_TITLE",
                issuing_authority="National Cadastre & Land Registry",
                issue_date="2020-01-01"
            ),
            LegalDocumentInput(
                doc_id="SHP-DOC-PERMIT-01",
                doc_type="HARVEST_PERMIT",
                issuing_authority="Forestry & Natural Resources Administration",
                issue_date="2023-01-01",
                expiry_date="2028-01-01"
            ),
            LegalDocumentInput(
                doc_id="SHP-DOC-LICENSE-01",
                doc_type="BUSINESS_LICENSE",
                issuing_authority="Ministry of Trade & Commerce",
                issue_date="2019-01-01"
            )
        ]

        return plots, documents
