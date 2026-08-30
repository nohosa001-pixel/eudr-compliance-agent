import io
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.bulk_file_parser import BulkFileParser
from app.schemas import EUDRSupplyChainPayload, ComplianceStatusEnum
from app.db.session import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_bulk_file_parser_csv():
    csv_data = """plot_id,country_code,area_ha,latitude,longitude,production_date
VN-COFFEE-01,VN,2.8,11.9412,108.4385,2024-02-01
VN-COFFEE-02,VN,3.2,11.9510,108.4410,2024-02-05
"""
    payload = BulkFileParser.parse_file("farms.csv", csv_data.encode("utf-8"))
    assert payload.supplier_id == "SUPP-BULK-UPLOAD"
    assert len(payload.plots) == 2
    assert payload.plots[0].plot_id == "VN-COFFEE-01"
    assert payload.plots[0].area_hectares == 2.8
    assert payload.plots[0].geometry["type"] == "Point"
    assert payload.plots[0].geometry["coordinates"] == [108.4385, 11.9412]


def test_bulk_file_parser_geojson():
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "plot_id": "GH-COCOA-GEO-1",
                    "country": "GH",
                    "area_ha": 3.5
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-1.625, 6.688],
                        [-1.620, 6.688],
                        [-1.620, 6.692],
                        [-1.625, 6.692],
                        [-1.625, 6.688]
                    ]]
                }
            }
        ]
    }
    payload = BulkFileParser.parse_file("parcels.geojson", json.dumps(geojson_data).encode("utf-8"))
    assert len(payload.plots) == 1
    assert payload.plots[0].plot_id == "GH-COCOA-GEO-1"
    assert payload.plots[0].geometry["type"] == "Polygon"


def test_api_ingest_file_endpoint():
    csv_content = b"plot_id,country,area_ha,latitude,longitude\nCO-COFFEE-1,CO,3.4,2.9273,-75.2819\n"
    response = client.post(
        "/api/v1/eudr/ingest-file",
        files={"file": ("plots.csv", io.BytesIO(csv_content), "text/csv")},
        data={"supplier_id": "SUPP-INGEST-TEST", "hs_code": "090111"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["supplier_id"] == "SUPP-INGEST-TEST"
    assert len(data["plots"]) == 1
    assert data["plots"][0]["plot_id"] == "CO-COFFEE-1"


def test_database_persistence_and_history():
    payload = {
        "supplier_id": "SUPP-DB-TEST-001",
        "operator": {
            "operator_name": "Test Roastery AG",
            "eori_number": "DE1122334455",
            "country": "DE",
            "address": "Bremen Port 1"
        },
        "commodity": {
            "hs_code": "090111",
            "description": "Green coffee",
            "net_mass_kg": 20000.0
        },
        "plots": [{
            "plot_id": "VN-CLEAN-PLOT-DB",
            "country_code": "VN",
            "area_hectares": 2.5,
            "geometry": {"type": "Point", "coordinates": [108.4385, 11.9412]},
            "production_date": "2024-03-01"
        }],
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Land Ministry", "issue_date": "2020-01-01"},
            {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Agri Dept", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
            {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Chamber", "issue_date": "2019-01-01"}
        ]
    }

    # Evaluate
    eval_resp = client.post("/api/v1/eudr/evaluate", json=payload)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    exec_id = eval_data.get("execution_id")
    assert exec_id is not None

    # Check History List
    hist_resp = client.get("/api/v1/eudr/history")
    assert hist_resp.status_code == 200
    hist_list = hist_resp.json()
    assert len(hist_list) >= 1
    found = any(item["execution_id"] == exec_id for item in hist_list)
    assert found is True

    # Check History Detail
    detail_resp = client.get(f"/api/v1/eudr/history/{exec_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["execution_id"] == exec_id
    assert detail_data["payload"]["supplier_id"] == "SUPP-DB-TEST-001"


def test_traces_nt_b2g_direct_submission():
    payload = {
        "supplier_id": "SUPP-B2G-001",
        "operator": {
            "operator_name": "Antwerp Roasters BV",
            "eori_number": "BE9988776655",
            "country": "BE",
            "address": "Antwerp Quay 1"
        },
        "commodity": {
            "hs_code": "090111",
            "description": "Arabica coffee",
            "net_mass_kg": 18000.0
        },
        "plots": [{
            "plot_id": "VN-COFFEE-B2G-CLEAN",
            "country_code": "VN",
            "area_hectares": 3.0,
            "geometry": {"type": "Point", "coordinates": [108.4385, 11.9412]},
            "production_date": "2024-02-01"
        }],
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Land Ministry", "issue_date": "2020-01-01"},
            {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Agri Dept", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
            {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Chamber", "issue_date": "2019-01-01"}
        ]
    }

    # Evaluate
    eval_resp = client.post("/api/v1/eudr/evaluate", json=payload)
    report_data = eval_resp.json()
    assert report_data["status"] == "COMPLIANT"

    # Submit to TRACES-NT
    submit_resp = client.post("/api/v1/eudr/traces-nt/submit", json=report_data)
    assert submit_resp.status_code == 200
    b2g_data = submit_resp.json()
    assert b2g_data["submission_status"] == "SUBMITTED_AND_ACCEPTED"
    assert "EU-TRACES-ACK" in b2g_data["traces_ack_number"]
    assert "EU-SWEC-CLEARED" in b2g_data["customs_declaration_code"]
    assert b2g_data["green_lane_customs_cleared"] is True
