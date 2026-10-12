import io
import os
import sys
import zipfile
import struct
import json

sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app
from app.modules.bulk_file_parser import BulkFileParser
from app.modules.audit_vault_manager import AuditVaultManager
from tests.test_shapefile_bulk_ingestion import create_mock_shapefile_zip

def run_rehearsal():
    client = TestClient(app)
    print("=" * 65)
    print("🌲 EUDR 2026 End-to-End Enterprise Rehearsal Simulation")
    print("=" * 65)

    # 1. Shapefile Bulk Ingestion
    print("\n[Step 1] Ingesting ESRI Shapefile (.zip)...")
    polygons = [
        [
            [[100.0, 0.0], [100.1, 0.0], [100.1, 0.1], [100.0, 0.1], [100.0, 0.0]]
        ]
    ]
    dbf_records = [
        {"plot_id": "PLOT-REHEARSAL-001", "country": "ID", "area_ha": 3.8, "farmer": "Sumatra Smallholder 1"}
    ]
    raw_zip = create_mock_shapefile_zip(polygons=polygons, dbf_records=dbf_records)
    payload = BulkFileParser.parse_file(
        filename="sumatra_plantations.zip",
        content_bytes=raw_zip,
        supplier_id="SUPP-SUMATRA-PALM",
        hs_code="151110",
        commodity_desc="Crude Palm Oil"
    )
    print(f" -> Plots Extracted: {len(payload.plots)}")
    p0 = payload.plots[0]
    print(f" -> Plot ID: {p0.plot_id}")
    print(f" -> Coordinates: {p0.geometry}")

    # 2. Forest Degradation & Plantation Conversion Detection
    print("\n[Step 2] Scanning EUDR Art. 2(5) Forest Degradation (Primary -> Plantation)...")
    deg_payload = {
        "commodity": "OIL_PALM",
        "plots": [
            {
                "plot_id": p0.plot_id,
                "country_code": "ID",
                "area_hectares": 3.5,
                "geometry": p0.geometry,
                "production_date": "2024-05-01",
                "notes": "fsc_sustainable_oil_palm"
            }
        ]
    }
    deg_resp = client.post("/api/v1/compliance/forest-degradation/assess", json=deg_payload)
    assert deg_resp.status_code == 200, f"Degradation assess failed: {deg_resp.text}"
    deg_res = deg_resp.json()
    print(f" -> Total Assessed: {deg_res['total_plots_assessed']}")
    print(f" -> Degradation Compliant: {deg_res['overall_degradation_compliant']}")
    print(f" -> Statutory Basis: {deg_res['statutory_article']}")

    # 3. Seal Statutory 5-Year WORM Audit Vault
    print("\n[Step 3] Sealing Statutory 5-Year WORM Audit Vault (EUDR Art. 31)...")
    vault_payload = {
        "dds_reference_id": "26EUDR-REHEARSAL-001",
        "verification_code": "V-REHEARSAL-2026",
        "operator_eori": "NL882233441100",
        "commodity_code": "151110",
        "net_mass_kg": 25000.0,
        "evaluation_payload": {
            "status": "COMPLIANT",
            "plots": [p0.model_dump(mode="json")],
            "degradation": deg_res
        },
        "traces_xml_str": "<DueDiligenceStatement><Reference>26EUDR-REHEARSAL-001</Reference></DueDiligenceStatement>",
        "customs_cert_html": "<html><body>EU SWE-C APPROVED CERTIFICATE</body></html>",
        "customs_box44_code": "C081:26EUDR-REHEARSAL-001/V-REHEARSAL-2026"
    }
    seal_resp = client.post("/api/v1/compliance/audit-vault/seal", json=vault_payload)
    assert seal_resp.status_code == 200, f"Vault seal failed: {seal_resp.text}"
    seal_res = seal_resp.json()
    print(f" -> Vault DDS ID: {seal_res['dds_reference_id']}")
    print(f" -> Statutory Retention: {seal_res['statutory_retention_years']} Years")
    print(f" -> Sealed At (UTC): {seal_res['sealed_at_utc']}")
    print(f" -> Expiry Date (5 Years): {seal_res['retention_expires_utc']}")
    print(f" -> Merkle Root Hash: {seal_res['merkle_root_hash']}")

    # 4. Verify Immutability & Tamper Resistance
    print("\n[Step 4] Verifying WORM Vault Integrity...")
    check_resp = client.get(f"/api/v1/compliance/audit-vault/{seal_res['dds_reference_id']}")
    assert check_resp.status_code == 200
    check_res = check_resp.json()
    verified = check_res['integrity_verification']['verified']
    print(f" -> Tamper Verification: verified={verified}, status={check_res['record']['integrity_status']}")

    # 5. Download 1-Click Customs Inspection ZIP Bundle
    print("\n[Step 5] Downloading 1-Click Official EU Customs Evidence Package...")
    dl_resp = client.get(f"/api/v1/compliance/audit-vault/{seal_res['dds_reference_id']}/download")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/zip"
    zip_bytes = io.BytesIO(dl_resp.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
    print(f" -> ZIP Archive Size: {len(dl_resp.content):,} bytes")
    print(f" -> Packaged Evidence in Bundle: {namelist}")

    print("\n" + "=" * 65)
    print("🎉 ALL 5 E2E REHEARSAL STEPS COMPLETED WITH ZERO ERRORS!")
    print("=" * 65)

if __name__ == "__main__":
    run_rehearsal()
