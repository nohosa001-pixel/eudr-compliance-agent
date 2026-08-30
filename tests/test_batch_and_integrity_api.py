import pytest
import time
import json
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import ComplianceStatusEnum
from app.modules.traces_b2g_client import TracesNTB2GClient


client = TestClient(app)


def test_batch_job_submit_and_polling():
    """Tests asynchronous batch job submission and status polling."""
    payload = {
        "supplier_id": "SUPP-BATCH-TEST-01",
        "operator": {
            "operator_name": "Euro Choc Import SA",
            "eori_number": "FR123456789012",
            "country": "FR",
            "address": "12 Rue de Paris, 75001 Paris, France"
        },
        "commodity": {
            "hs_code": "180100",
            "description": "Raw Cocoa Beans",
            "net_mass_kg": 5000.0
        },
        "plots": [
            {
                "plot_id": "PLOT-BATCH-1",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-62.1234, -3.4567],
                            [-62.1220, -3.4567],
                            [-62.1220, -3.4550],
                            [-62.1234, -3.4550],
                            [-62.1234, -3.4567]
                        ]
                    ]
                },
                "country_code": "BR",
                "producer_name": "Fazenda Amazonia Test",
                "area_hectares": 3.2,
                "production_date": "2024-04-15"
            }
        ],
        "documents": [
            {
                "doc_id": "DOC-BATCH-1",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Swedish Forest Agency",
                "issue_date": "2021-01-10"
            }
        ]
    }

    # 1. Submit Batch Job
    resp = client.post("/api/v1/eudr/batch/submit", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    job_id = data["job_id"]
    assert data["status"] in ["QUEUED", "PROCESSING", "COMPLETED"]

    # 2. Poll Status until COMPLETED or timeout
    completed = False
    for _ in range(30):
        status_resp = client.get(f"/api/v1/eudr/batch/{job_id}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        if status_data["status"] == "COMPLETED":
            completed = True
            assert status_data["progress_pct"] == 100.0
            assert status_data["execution_id"] is not None
            assert status_data["overall_status"] in ["COMPLIANT", "NON_COMPLIANT", "ACTION_REQUIRED"]
            break
        time.sleep(0.1)

    assert completed, "Batch job did not complete in expected time window."



def test_batch_file_upload():
    """Tests bulk file upload for batch processing."""
    geojson_content = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "plot_id": "PLOT-GEOJSON-1",
                    "producer_name": "Fazenda Rio",
                    "country_code": "SE",
                    "area_hectares": 2.5
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [18.0600, 59.3200],
                            [18.0620, 59.3200],
                            [18.0620, 59.3220],
                            [18.0600, 59.3220],
                            [18.0600, 59.3200]
                        ]
                    ]
                }
            }
        ]
    }
    
    files = {
        "file": ("plots.geojson", json.dumps(geojson_content).encode("utf-8"), "application/geo+json")
    }
    data = {
        "supplier_id": "SUPP-UPLOAD-BATCH",
        "operator_name": "Global Timber SA",
        "hs_code": "440711",
        "commodity_desc": "Coniferous Wood"
    }

    resp = client.post("/api/v1/eudr/batch/upload", files=files, data=data)
    assert resp.status_code == 200
    resp_data = resp.json()
    assert "job_id" in resp_data


def test_audit_integrity_verification_workflow():
    """Tests evaluating a payload, persisting it, and cryptographically verifying its Article 31 audit integrity."""
    payload = {
        "supplier_id": "SUPP-INTEGRITY-AUDIT",
        "operator": {
            "operator_name": "European Coffee Roasters BV",
            "eori_number": "NL889977665544",
            "country": "NL",
            "address": "Keizersgracht 100, 1015 Amsterdam, Netherlands"
        },
        "commodity": {
            "hs_code": "090111",
            "description": "Green Arabica Coffee",
            "net_mass_kg": 10000.0
        },
        "plots": [
            {
                "plot_id": "PLOT-AUDIT-1",
                "geometry": {
                    "type": "Point",
                    "coordinates": [18.0600, 59.3200]
                },
                "country_code": "SE",
                "producer_name": "Agro Audit Test",
                "area_hectares": 3.0,
                "production_date": "2024-04-15"
            }
        ],
        "documents": [
            {
                "doc_id": "DOC-LAND-01",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Swedish Forest Agency",
                "issue_date": "2021-01-10"
            },
            {
                "doc_id": "DOC-LAND-02",
                "doc_type": "BUSINESS_LICENSE",
                "issuing_authority": "Swedish Registry",
                "issue_date": "2020-05-01"
            }
        ]
    }

    # 1. Execute full evaluation
    eval_resp = client.post("/api/v1/eudr/evaluate", json=payload)
    assert eval_resp.status_code == 200
    report = eval_resp.json()
    exec_id = report.get("execution_id")
    assert exec_id is not None

    # 2. Query Cryptographic Integrity Check
    integrity_resp = client.get(f"/api/v1/eudr/audit/integrity/{exec_id}")
    assert integrity_resp.status_code == 200
    integrity_data = integrity_resp.json()

    assert integrity_data["execution_id"] == exec_id
    assert integrity_data["is_valid"] is True
    assert integrity_data["verification_status"] == "INTEGRITY_VERIFIED"
    assert integrity_data["checks_passed_count"] == integrity_data["checks_total_count"]
    assert integrity_data["digital_signature_verified"] is True
    assert len(integrity_data["tamper_alerts"]) == 0


def test_audit_integrity_tamper_detection():
    """Tests that modifying data in evidence bundle triggers tamper alerts."""
    from app.modules.audit_integrity_verifier import AuditIntegrityVerifier

    valid_payload = {"test_key": "original_value"}
    valid_report = {"execution_id": "EXEC-TAMPER-TEST", "status": "COMPLIANT"}
    valid_evidence = {
        "bundle_id": "BUNDLE-01",
        "sha256_input_payload": "fake_sha",
        "merkle_root": "fake_root",
        "digital_signature": "fake_sig"
    }

    # Direct validation of mismatched signatures
    res = AuditIntegrityVerifier.verify_bundle_data(
        execution_id="EXEC-TAMPER-TEST",
        payload_dict=valid_payload,
        report_dict=valid_report,
        evidence_dict=valid_evidence
    )
    assert res.is_valid is False
    assert res.verification_status == "TAMPER_DETECTED"
    assert len(res.tamper_alerts) > 0


def test_b2g_client_with_signature():
    """Tests TracesNTB2GClient signature generation and response fields."""
    payload = {
        "supplier_id": "SUPP-B2G-SIG-TEST",
        "operator": {
            "operator_name": "Hamburg Coffee Import GmbH",
            "eori_number": "DE123456789",
            "country": "DE",
            "address": "Speicherstadt 1, 20457 Hamburg, Germany"
        },
        "commodity": {
            "hs_code": "090111",
            "description": "Coffee Beans",
            "net_mass_kg": 12000.0
        },
        "plots": [
            {
                "plot_id": "VN-COFFEE-B2G-CLEAN",
                "country_code": "VN",
                "area_hectares": 3.0,
                "geometry": {"type": "Point", "coordinates": [108.4385, 11.9412]},
                "production_date": "2024-02-01"
            }
        ],
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Land Ministry", "issue_date": "2020-01-01"},
            {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Agri Dept", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
            {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Chamber", "issue_date": "2019-01-01"}
        ]
    }

    eval_resp = client.post("/api/v1/eudr/evaluate", json=payload)
    assert eval_resp.status_code == 200
    report_data = eval_resp.json()
    assert report_data["status"] == "COMPLIANT"

    submit_resp = client.post("/api/v1/eudr/traces-nt/submit", json=report_data)
    assert submit_resp.status_code == 200
    b2g_data = submit_resp.json()
    assert b2g_data["submission_status"] == "SUBMITTED_AND_ACCEPTED"
    assert b2g_data["digital_signature"] is not None
    assert len(b2g_data["digital_signature"]) == 64
    assert b2g_data["transmission_latency_ms"] is not None
    assert b2g_data["operator_eori"] == "DE123456789"


def test_batch_job_sse_streaming():
    """Tests Server-Sent Events (SSE) streaming endpoint."""
    payload = {
        "supplier_id": "SUPP-SSE-TEST",
        "operator": {
            "operator_name": "Hamburg Cocoa Logistik AG",
            "eori_number": "DE9988776655",
            "country": "DE",
            "address": "Speicherstadt 20, 20457 Hamburg"
        },
        "commodity": {
            "hs_code": "180100",
            "description": "Cocoa Beans",
            "net_mass_kg": 8000.0
        },
        "plots": [
            {
                "plot_id": "GH-COCOA-01",
                "country_code": "SE",
                "area_hectares": 2.2,
                "geometry": {"type": "Point", "coordinates": [18.06, 59.32]},
                "production_date": "2024-03-01"
            }
        ],
        "documents": [
            {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Forest Commission", "issue_date": "2021-01-01"}
        ]
    }

    submit_resp = client.post("/api/v1/eudr/batch/submit", json=payload)
    assert submit_resp.status_code == 200
    job_id = submit_resp.json()["job_id"]

    # Test SSE stream endpoint returns text/event-stream
    with client.stream("GET", f"/api/v1/eudr/batch/{job_id}/stream") as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]
        events_received = 0
        for line in stream_resp.iter_lines():
            if line.startswith("data: "):
                events_received += 1
                event_data = json.loads(line[6:])
                assert "job_id" in event_data
                assert "progress_pct" in event_data
                if event_data["status"] == "COMPLETED" or events_received >= 2:
                    break
        assert events_received >= 1




