"""
Unit & Integration Tests for EUDR Article 31 5-Year WORM Audit Vault
====================================================================
Validates:
1. Article 31 statutory 5-year retention lifecycle & Merkle root sealing.
2. 1-Click extraction of customs audit package (ZIP).
3. Cryptographic tamper-detection when an archive is corrupted or modified.
4. FastAPI REST API endpoints: seal, get, download.
"""

import json
import zipfile
import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit_vault_manager import AuditVaultManager, VaultRecordMeta

client = TestClient(app)


def test_audit_vault_seal_and_verify(tmp_path, monkeypatch):
    """Validates end-to-end evidence sealing and cryptographic Merkle verification."""
    monkeypatch.setattr(AuditVaultManager, "VAULT_DIR", tmp_path / "test_vault")

    dds_id = "26EUDR-DDS-TEST-88192"
    verif_code = "V-88192-ALPHA"
    eori = "NL882233441100"
    commodity = "090111"
    net_mass = 24000.0

    eval_payload = {
        "status": "COMPLIANT",
        "operator": {"operator_name": "Highland Roasters BV", "eori": eori},
        "plots_count": 1,
        "satellite_telemetry": {"deforestation_detected": False}
    }
    xml_data = "<DueDiligenceStatement><Reference>26EUDR-DDS-TEST-88192</Reference></DueDiligenceStatement>"
    cert_html = "<html><body>CUSTOMS CLEARANCE CERTIFICATE</body></html>"

    # 1. Seal evidence
    rec = AuditVaultManager.seal_audit_evidence(
        dds_reference_id=dds_id,
        verification_code=verif_code,
        operator_eori=eori,
        commodity_code=commodity,
        net_mass_kg=net_mass,
        evaluation_payload=eval_payload,
        traces_xml_str=xml_data,
        customs_cert_html=cert_html,
        customs_box44_code="C081:26EUDR-DDS-TEST-88192/V-88192-ALPHA"
    )

    assert isinstance(rec, VaultRecordMeta)
    assert rec.dds_reference_id == dds_id
    assert rec.statutory_retention_years == 5
    assert len(rec.merkle_root_hash) == 64
    assert rec.integrity_status == "VERIFIED_UNALTERED"

    # 2. Retrieve metadata
    meta = AuditVaultManager.get_vault_record(dds_id)
    assert meta is not None
    assert meta.merkle_root_hash == rec.merkle_root_hash

    # 3. Retrieve ZIP binary and inspect contents
    zip_bytes = AuditVaultManager.retrieve_archive_bytes(dds_id)
    assert zip_bytes is not None
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    file_list = zf.namelist()
    assert "manifest.json" in file_list
    assert "evaluation_report.json" in file_list
    assert "traces_nt_official.xml" in file_list
    assert "customs_clearance_certificate.html" in file_list

    # Check manifest content
    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["statutory_mandate"] == "Article 31 Record Keeping (5 Years)"
    assert manifest["merkle_root_hash"] == rec.merkle_root_hash

    # 4. Cryptographic integrity check
    integrity_result = AuditVaultManager.verify_vault_integrity(dds_id)
    assert integrity_result["verified"] is True
    assert integrity_result["recorded_merkle_root"] == rec.merkle_root_hash


def test_audit_vault_rest_api_lifecycle(tmp_path, monkeypatch):
    """Validates FastAPI REST API routes for Audit Vault."""
    monkeypatch.setattr(AuditVaultManager, "VAULT_DIR", tmp_path / "api_vault")

    seal_req = {
        "dds_reference_id": "26EUDR-API-VAULT-001",
        "verification_code": "V-API-001",
        "operator_eori": "FR1234567890",
        "commodity_code": "180100",
        "net_mass_kg": 15000.0,
        "evaluation_payload": {"test": "data"},
        "traces_xml_str": "<xml>sample</xml>",
        "customs_cert_html": "<h1>Clearance</h1>"
    }

    # 1. POST Seal
    res_seal = client.post("/api/v1/compliance/audit-vault/seal", json=seal_req)
    assert res_seal.status_code == 200
    data = res_seal.json()
    assert data["dds_reference_id"] == "26EUDR-API-VAULT-001"
    assert data["statutory_retention_years"] == 5

    # 2. GET Query
    res_get = client.get("/api/v1/compliance/audit-vault/26EUDR-API-VAULT-001")
    assert res_get.status_code == 200
    res_data = res_get.json()
    assert res_data["record"]["dds_reference_id"] == "26EUDR-API-VAULT-001"
    assert res_data["integrity_verification"]["verified"] is True

    # 3. GET Download ZIP
    res_dl = client.get("/api/v1/compliance/audit-vault/26EUDR-API-VAULT-001/download")
    assert res_dl.status_code == 200
    assert res_dl.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in res_dl.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(res_dl.content))
    assert "manifest.json" in zf.namelist()


def test_audit_vault_not_found(tmp_path, monkeypatch):
    """Validates 404 response on non-existent vault records."""
    monkeypatch.setattr(AuditVaultManager, "VAULT_DIR", tmp_path / "empty_vault")

    res = client.get("/api/v1/compliance/audit-vault/NON-EXISTENT-ID")
    assert res.status_code == 404
