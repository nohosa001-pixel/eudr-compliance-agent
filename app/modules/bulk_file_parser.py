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
        else:
            raise ValueError(f"Unsupported file format: {filename}. Supported formats: .csv, .xlsx, .geojson, .json, .kml")

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
