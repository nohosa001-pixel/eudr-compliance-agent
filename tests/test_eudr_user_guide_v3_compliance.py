"""Integration Tests for EUDR Information System User Guide v3.0 Digital Workflow.
=============================================================================
Validates:
1. Dual-Key Architecture (DDS Reference Number + Verification Number).
2. 5 Role-Based Workflows (Primary Operator, MSPO, SME, Non-SME Downstream, Authorised Rep).
3. Micro/Small Producer (MSPO) Simplified Declaration (SD) Identifier.
4. DDS Grouping Engine & Group Head Binding Statutory Liability.
5. GeoJSON 6-decimal-place precision sanitizer (1e-6 WGS84).
6. REST API Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.eudr_information_system_v3 import (
    eudr_info_system_v3,
    EUDRRole,
    DDSLifecycleStatus
)
from app.modules.downstream_chain_manager import DownstreamChainManager

client = TestClient(app)


def test_dual_key_issue_and_verification_success():
    """Verify paired DDS Reference Number + Verification Number generation and validation."""
    receipt = eudr_info_system_v3.issue_available_dds(
        operator_eori="FR12345678901234",
        operator_role=EUDRRole.PRIMARY_OPERATOR,
        commodity_code="0901.11.00",
        country_of_production="CO",
        net_mass_kg=18500.0
    )

    assert receipt.status == DDSLifecycleStatus.AVAILABLE
    assert receipt.dds_reference_number.startswith("26EUDR-DDS-") or "EUDR-DDS-" in receipt.dds_reference_number
    assert receipt.verification_number.startswith("VERIF-")

    # Positive Dual-Key Verification
    res_valid = eudr_info_system_v3.verify_dual_key_pair(
        dds_reference_number=receipt.dds_reference_number,
        verification_number=receipt.verification_number,
        verifier_role=EUDRRole.NON_SME_DOWNSTREAM
    )
    assert res_valid["is_verified"] is True
    assert res_valid["customs_clearance_eligible"] is True
    assert res_valid["detailed_upstream_inspection_unlocked"] is True
    assert res_valid["operator_eori"] == "FR12345678901234"


def test_dual_key_verification_tamper_defense():
    """Verify system rejects invalid or mismatched verification numbers."""
    receipt = eudr_info_system_v3.issue_available_dds(
        operator_eori="DE98765432109876",
        operator_role=EUDRRole.PRIMARY_OPERATOR,
        commodity_code="1801.00.00",
        country_of_production="CI",
        net_mass_kg=25000.0
    )

    # Forged verification key
    res_tampered = eudr_info_system_v3.verify_dual_key_pair(
        dds_reference_number=receipt.dds_reference_number,
        verification_number="VERIF-FAKE-0000-9999",
        verifier_role=EUDRRole.NON_SME_DOWNSTREAM
    )
    assert res_tampered["is_verified"] is False
    assert res_tampered["status"] == "VERIFICATION_NUMBER_MISMATCH"
    assert res_tampered["customs_clearance_eligible"] is False


def test_downstream_chain_manager_dual_key_integration():
    """Verify DownstreamChainManager leverages dual-key verification for Non-SME inheritance."""
    receipt = eudr_info_system_v3.issue_available_dds(
        operator_eori="NL11223344556677",
        operator_role=EUDRRole.PRIMARY_OPERATOR,
        commodity_code="4407.10.00",
        country_of_production="BR",
        net_mass_kg=50000.0
    )

    res = DownstreamChainManager.validate_dual_key_upstream_inheritance(
        dds_reference_number=receipt.dds_reference_number,
        verification_number=receipt.verification_number,
        is_non_sme=True
    )
    assert res["is_verified"] is True
    assert res["detailed_upstream_inspection_unlocked"] is True


def test_mspo_simplified_declaration_identifier():
    """Verify 1-time Simplified Declaration identifier issuance for smallholders."""
    sd = eudr_info_system_v3.issue_simplified_declaration(
        producer_name="Bapak Wayan Smallholder Collective",
        country_code="ID",
        commodity_code="1511.10.00",
        plots_count=1
    )
    assert sd.declaration_identifier.startswith("EU-SD-")
    assert "ID" in sd.declaration_identifier
    assert sd.is_active is True

    retrieved = eudr_info_system_v3.get_simplified_declaration(sd.declaration_identifier)
    assert retrieved is not None
    assert retrieved.producer_name == "Bapak Wayan Smallholder Collective"


def test_dds_grouping_and_group_head_statutory_liability():
    """Verify large-scale grouping and legal liability declaration of Group Head."""
    child_refs = [f"EUDR-DDS-CHILD-{i:03d}" for i in range(1, 6)]
    child_sds = ["EU-SD-2026-GH-001", "EU-SD-2026-GH-002"]

    group_head = eudr_info_system_v3.create_grouped_statement(
        group_name="Nestle-Cargill Consolidated Cocoa Ingestion Group",
        head_operator_eori="BE099887766554",
        child_dds_references=child_refs,
        child_sd_identifiers=child_sds,
        estimated_plots_count=12500
    )

    assert group_head.group_head_reference.startswith("EU-DDS-GRP-")
    assert group_head.total_constituent_dds_count == 5
    assert len(group_head.constituent_sd_identifiers) == 2
    assert "primary statutory legal liability" in group_head.legal_liability_declaration
    assert group_head.head_operator_eori == "BE099887766554"


def test_geojson_6_decimal_place_sanitizer():
    """Verify GeoJSON coordinates are rounded to 6 decimal places and unclosed rings are healed."""
    raw_geojson = {
        "type": "Polygon",
        "coordinates": [
            [
                [102.123456789, 2.987654321],
                [102.124567891, 2.988765432],
                [102.125678912, 2.987654321]
                # Unclosed ring missing 4th vertex
            ]
        ]
    }

    sanitized, is_valid, warnings = eudr_info_system_v3.sanitize_geojson_precision(raw_geojson)
    assert is_valid is True
    ring = sanitized["coordinates"][0]

    # Verify 6-decimal rounding
    assert ring[0][0] == 102.123457
    assert ring[0][1] == 2.987654

    # Verify ring auto-closure
    assert len(ring) == 4
    assert ring[0] == ring[-1]
    assert any("Auto-closed" in w for w in warnings)


def test_api_v3_dual_key_issue_and_verify_endpoints():
    """Integration test for POST /api/v1/eudr/v3/dds/issue-dual-key & verify-dual-key."""
    # 1. Issue
    resp_issue = client.post(
        "/api/v1/eudr/v3/dds/issue-dual-key",
        json={
            "operator_eori": "IT99887766554433",
            "operator_role": "PRIMARY_OPERATOR",
            "commodity_code": "0901.11.00",
            "country_of_production": "ET",
            "net_mass_kg": 21000.0
        }
    )
    assert resp_issue.status_code == 200
    issue_data = resp_issue.json()
    dds_ref = issue_data["dds_reference_number"]
    verif_no = issue_data["verification_number"]

    # 2. Verify
    resp_verify = client.post(
        "/api/v1/eudr/v3/dds/verify-dual-key",
        json={
            "dds_reference_number": dds_ref,
            "verification_number": verif_no,
            "verifier_role": "NON_SME_DOWNSTREAM"
        }
    )
    assert resp_verify.status_code == 200
    verify_data = resp_verify.json()
    assert verify_data["is_verified"] is True
    assert verify_data["customs_clearance_eligible"] is True
    assert verify_data["operator_eori"] == "IT99887766554433"


def test_api_v3_mspo_simplified_declaration_endpoint():
    """Integration test for POST /api/v1/eudr/v3/mspo/simplified-declaration."""
    resp = client.post(
        "/api/v1/eudr/v3/mspo/simplified-declaration",
        json={
            "producer_name": "Nguyen Van Smallholder Estate",
            "country_code": "VN",
            "commodity_code": "0901.11.00",
            "plots_count": 2
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "VN" in data["declaration_identifier"]
    assert data["producer_name"] == "Nguyen Van Smallholder Estate"


def test_api_v3_group_head_endpoint():
    """Integration test for POST /api/v1/eudr/v3/dds/group-head."""
    resp = client.post(
        "/api/v1/eudr/v3/dds/group-head",
        json={
            "group_name": "Barry Callebaut Bulk West Africa Ingestion",
            "head_operator_eori": "DE1234500000",
            "child_dds_references": ["26EUDR-DDS-001", "26EUDR-DDS-002"],
            "child_sd_identifiers": ["EU-SD-2026-CI-001"],
            "estimated_plots_count": 3000
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["group_head_reference"].startswith("EU-DDS-GRP-")
    assert data["total_constituent_dds_count"] == 2
    assert "primary statutory legal liability" in data["legal_liability_declaration"]
