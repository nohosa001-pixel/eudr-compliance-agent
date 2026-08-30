from fastapi.testclient import TestClient
from datetime import date
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/eudr/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["eudr_cutoff_date"] == "2020-12-31"

def test_dashboard_serving():
    response = client.get("/")
    assert response.status_code == 200
    assert "EUDR Compliance" in response.text

    static_res = client.get("/static/app.js")
    assert static_res.status_code == 200

def test_classify_commodity_endpoint():
    # Cocoa
    res1 = client.get("/api/v1/eudr/classify-commodity?hs_code=180100")
    assert res1.status_code == 200
    assert "Cocoa" in res1.json()["eudr_category"]

    # Wood
    res2 = client.get("/api/v1/eudr/classify-commodity?hs_code=440711")
    assert res2.status_code == 200
    assert "Wood" in res2.json()["eudr_category"]

def test_validate_spatial_endpoint():
    payload = {
        "plot_id": "PLOT-P1",
        "country_code": "ID",
        "area_hectares": 1.5,
        "geometry": {
            "type": "Point",
            "coordinates": [101.500000, 0.500000]
        },
        "production_date": "2024-05-01"
    }
    response = client.post("/api/v1/eudr/validate-spatial", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["plot_id"] == "PLOT-P1"

def test_e2e_evaluate_pipeline_compliant_and_html():
    """Complete supply chain payload resulting in COMPLIANT status, TRACES-NT DDS, and HTML report."""
    payload = {
        "execution_id": "exec-test-12345",
        "supplier_id": "SUPPLIER-ID-789",
        "operator": {
            "operator_name": "EuroWood Importers GmbH",
            "eori_number": "DE123456789012345",
            "vat_number": "DE987654321",
            "country": "DE",
            "address": "Holzweg 10, 20095 Hamburg, Germany"
        },
        "commodity": {
            "hs_code": "440711",
            "description": "Coniferous wood sawn or chipped lengthwise",
            "net_mass_kg": 25000.0,
            "volume_m3": 45.0,
            "scientific_name": "Pinus sylvestris"
        },
        "plots": [
            {
                "plot_id": "PLOT-SE-001",
                "country_code": "SE",
                "area_hectares": 2.8,
                "geometry": {
                    "type": "Point",
                    "coordinates": [18.060000, 59.320000]
                },
                "production_date": "2024-04-15",
                "producer_name": "Nordic Timber Coop"
            }
        ],
        "documents": [
            {
                "doc_id": "DOC-SE-TITLE",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Swedish Forest Agency (Skogsstyrelsen)",
                "issue_date": "2021-01-10",
                "expiry_date": "2031-01-10",
                "file_hash": "a1b2c3d4e5f67890"
            },
            {
                "doc_id": "DOC-SE-LIC",
                "doc_type": "BUSINESS_LICENSE",
                "issuing_authority": "Swedish Companies Registration Office",
                "issue_date": "2020-05-01"
            }
        ]
    }

    # JSON evaluation
    response = client.post("/api/v1/eudr/evaluate", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["execution_id"] == "exec-test-12345"
    assert res["status"] == "COMPLIANT"
    assert res["traces_dds"] is not None
    assert res["traces_dds"]["operator_eori"] == "DE123456789012345"
    assert res["traces_dds"]["deforestation_free_declaration"] is True
    assert res["traces_dds"]["legally_produced_declaration"] is True
    assert "digital_signature_sha256" in res["traces_dds"]
    assert res["audit_trail"]["execution_id"] == "exec-test-12345"

    # HTML Report generation
    html_res = client.post("/api/v1/eudr/evaluate/html-report", json=payload)
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers["content-type"]
    assert "EUDR Due Diligence Audit Report" in html_res.text
    assert "DE123456789012345" in html_res.text

def test_e2e_evaluate_pipeline_non_compliant():
    """Supply chain payload with deforestation trigger resulting in NON_COMPLIANT status."""
    payload = {
        "supplier_id": "SUPPLIER-NONCOMPLIANT",
        "operator": {
            "operator_name": "Tropical Imports BV",
            "eori_number": "NL987654321098765",
            "country": "NL",
            "address": "Haven 5, Rotterdam, Netherlands"
        },
        "commodity": {
            "hs_code": "151110",
            "description": "Crude palm oil",
            "net_mass_kg": 50000.0
        },
        "plots": [
            {
                "plot_id": "PLOT-FLAGGED-deforestation_2022",
                "country_code": "ID",
                "area_hectares": 2.0,
                "geometry": {
                    "type": "Point",
                    "coordinates": [101.500000, 0.500000]
                },
                "production_date": "2024-03-01",
                "notes": "deforestation_2022"
            }
        ],
        "documents": [
            {
                "doc_id": "DOC-ID-TITLE",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Ministry of Agrarian Affairs",
                "issue_date": "2021-01-01",
                "expiry_date": "2030-01-01"
            }
        ]
    }

    response = client.post("/api/v1/eudr/evaluate", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "NON_COMPLIANT"
    assert res["traces_dds"] is None
    assert "Deforestation detected" in res["summary_message"] or "deforestation" in res["summary_message"].lower()
