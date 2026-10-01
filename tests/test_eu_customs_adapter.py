"""
Unit and Integration Tests for European Union Customs & EU SWE-C Gateway.
==========================================================================
Validates:
1. TARIC Document Codes (C081, C082, Y120, Y121, Y122) per Regulation (EU) 2023/1115.
2. Union Customs Code (UCC) Data Element 12 03 000 000 payload & XML generation.
3. Automated EU SWE-C port pre-clearance simulation (Green Lane vs Inspection hold).
4. Article 16 statutory inspection quota calculations (9% High, 3% Standard, 1% Low).
5. REST API endpoints and autonomous agent MCP tools.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.eu_customs_adapter import EUCustomsAdapter
from app.schemas import (
    CustomsTaricEvaluateRequest,
    CustomsUCCDeclarationRequest,
    CustomsSWECPreClearanceRequest
)
from app.modules.agent_tools import AgentToolsRegistry

client = TestClient(app)


def test_taric_evaluation_c081_standard_eudr():
    """Validates that a regulated commodity generates TARIC Document Code C081."""
    req = CustomsTaricEvaluateRequest(
        hs_code="0901.11.00",
        dds_reference_id="26EUDR0000088219",
        verification_code="V-88219-X"
    )
    res = EUCustomsAdapter.evaluate_taric_document_code(req)
    assert res.taric_document_code == "C081"
    assert "26EUDR0000088219/V-88219-X" in res.box44_reference_code
    assert res.is_eudr_mandated is True
    assert "Box 44" in res.action_required_for_customs


def test_taric_evaluation_c082_downstream_operator():
    """Validates that a downstream operator pass-through generates C082."""
    req = CustomsTaricEvaluateRequest(
        hs_code="1806.32.00",  # Chocolate bar
        is_downstream_operator=True,
        upstream_dds_reference="26EUDR-UPSTREAM-COCOA-991"
    )
    res = EUCustomsAdapter.evaluate_taric_document_code(req)
    assert res.taric_document_code == "C082"
    assert "C082:26EUDR-UPSTREAM-COCOA-991" in res.box44_reference_code
    assert res.is_eudr_mandated is True


def test_taric_evaluation_y120_non_eudr():
    """Validates that an unregulated commodity generates Y120 (Out of Scope)."""
    req = CustomsTaricEvaluateRequest(hs_code="7208.10.00")  # Iron & Steel
    res = EUCustomsAdapter.evaluate_taric_document_code(req)
    assert res.taric_document_code == "Y120"
    assert res.is_eudr_mandated is False
    assert "outside the substantive scope" in res.box44_formatted_statement


def test_taric_evaluation_y121_recycled_waste():
    """Validates 100% post-consumer recycled waste exemption (Y121)."""
    req = CustomsTaricEvaluateRequest(
        hs_code="4802.56.00",  # Paper
        is_recycled=True
    )
    res = EUCustomsAdapter.evaluate_taric_document_code(req)
    assert res.taric_document_code == "Y121"
    assert res.is_eudr_mandated is False
    assert "Footnote 1" in res.box44_formatted_statement


def test_taric_evaluation_y122_packaging_material():
    """Validates protective transport packaging exemption (Y122)."""
    req = CustomsTaricEvaluateRequest(
        hs_code="4415.20.00",  # Wooden pallets
        is_packaging_only=True
    )
    res = EUCustomsAdapter.evaluate_taric_document_code(req)
    assert res.taric_document_code == "Y122"
    assert res.is_eudr_mandated is False
    assert "Transport packaging" in res.box44_formatted_statement


def test_ucc_declaration_generation():
    """Validates standard Union Customs Code (UCC) Data Element 12 03 structure."""
    req = CustomsUCCDeclarationRequest(
        declarant_eori="NL823456789",
        importer_eori="DE987654321",
        hs_code="0901.11.00",
        country_of_origin="VN",
        net_mass_kg=21600.0,
        dds_reference_id="26EUDR0000099411",
        verification_code="V-99411-K",
        destination_port_code="NLRTM"
    )
    res = EUCustomsAdapter.generate_ucc_declaration(req)
    assert res.destination_port == "NLRTM"
    assert "Rotterdam" in res.port_name
    assert len(res.data_element_1203_supporting_documents) == 1
    doc = res.data_element_1203_supporting_documents[0]
    assert doc["typeCode"] == "C081"
    assert doc["documentIdentifier"] == "26EUDR0000099411/V-99411-K"
    assert "<SupportingDocument>" in res.ucc_xml_snippet
    assert "26EUDR0000099411/V-99411-K" in res.ucc_xml_snippet


def test_swe_c_pre_clearance_green_lane():
    """Validates automated Green Lane clearance for standard-risk country."""
    req = CustomsSWECPreClearanceRequest(
        dds_reference_id="26EUDR0000010044",
        verification_code="V-10044-Z",
        eori_number="NL123456789",
        hs_code="180100",  # Cocoa
        net_mass_kg=15000.0,
        country_code="GH",  # Standard risk
        destination_port="BEANR"  # Antwerp
    )
    res = EUCustomsAdapter.simulate_swe_c_pre_clearance(req)
    assert res.clearance_status == "GREEN_LANE_CLEARED"
    assert res.green_lane_cleared is True
    assert "EU-SWEC-CLEARED" in res.customs_ack_code
    assert res.destination_port == "BEANR"
    assert "Antwerp" in res.port_name
    assert res.article16_inspection_rate_pct == 3.0


def test_swe_c_pre_clearance_high_risk_routed():
    """Validates routing to documentary inspection for high-risk origins."""
    req = CustomsSWECPreClearanceRequest(
        dds_reference_id="26EUDR0000010044",
        verification_code="V-10044-Z",
        eori_number="DE987654321",
        hs_code="440711",  # Timber
        net_mass_kg=35000.0,
        country_code="MM",  # High risk country
        destination_port="DEHAM"  # Hamburg
    )
    res = EUCustomsAdapter.simulate_swe_c_pre_clearance(req)
    assert res.clearance_status == "ROUTED_FOR_INSPECTION"
    assert res.green_lane_cleared is False
    assert res.country_risk_tier == "HIGH"
    assert res.article16_inspection_rate_pct == 9.0
    assert "Hamburg" in res.port_name


def test_swe_c_pre_clearance_invalid_credentials_rejected():
    """Validates rejection hold when EORI or DDS is invalid."""
    req = CustomsSWECPreClearanceRequest(
        dds_reference_id="SHORT",  # Invalid short DDS
        verification_code="V",
        eori_number="INVALID_EORI",
        hs_code="0901",
        net_mass_kg=100.0,
        country_code="BR",
        destination_port="ESVLC"
    )
    res = EUCustomsAdapter.simulate_swe_c_pre_clearance(req)
    assert res.clearance_status == "CUSTOMS_HOLD_REJECTED"
    assert res.green_lane_cleared is False
    assert "EU-SWEC-HOLD" in res.customs_ack_code


def test_customs_risk_rates_directory():
    """Validates directory of inspection rates, major ports, and TARIC codes."""
    res = EUCustomsAdapter.get_risk_rates_and_ports()
    assert res.article16_inspection_rates["high_risk_tier_pct"] == 9.0
    assert res.article16_inspection_rates["standard_risk_tier_pct"] == 3.0
    assert res.article16_inspection_rates["low_risk_tier_pct"] == 1.0
    assert len(res.major_entry_ports) >= 6
    assert "C081" in res.official_taric_codes
    assert "Y121" in res.official_taric_codes


def test_rest_api_customs_endpoints():
    """Tests FastAPI HTTP REST endpoints for customs operations."""
    # 1. Evaluate TARIC
    r1 = client.post("/api/v1/customs/taric-evaluate", json={"hs_code": "0901.11.00"})
    assert r1.status_code == 200
    assert r1.json()["taric_document_code"] == "C081"

    # 2. Generate UCC
    r2 = client.post("/api/v1/customs/ucc-declaration", json={
        "declarant_eori": "NL123456789",
        "importer_eori": "NL123456789",
        "hs_code": "090111",
        "country_of_origin": "VN",
        "net_mass_kg": 5000.0,
        "dds_reference_id": "26EUDR0000088111",
        "verification_code": "V-88111-Q",
        "destination_port_code": "NLRTM"
    })
    assert r2.status_code == 200
    assert "Rotterdam" in r2.json()["port_name"]

    # 3. Pre-Clearance
    r3 = client.post("/api/v1/customs/swe-c/pre-clearance", json={
        "dds_reference_id": "26EUDR0000088111",
        "verification_code": "V-88111-Q",
        "eori_number": "NL123456789",
        "hs_code": "090111",
        "net_mass_kg": 5000.0,
        "country_code": "VN",
        "destination_port": "NLRTM"
    })
    assert r3.status_code == 200
    assert r3.json()["clearance_status"] == "GREEN_LANE_CLEARED"

    # 4. Risk Rates
    r4 = client.get("/api/v1/customs/risk-rates")
    assert r4.status_code == 200
    assert r4.json()["article16_inspection_rates"]["high_risk_tier_pct"] == 9.0


@pytest.mark.asyncio
async def test_agent_tools_customs_execution():
    """Validates MCP execution of customs tools via AgentToolsRegistry."""
    # 1. eudr_evaluate_customs_taric
    taric_res = await AgentToolsRegistry.execute_tool("eudr_evaluate_customs_taric", {
        "hs_code": "4407.11.00",
        "dds_reference_id": "26EUDR-TIMBER-001",
        "verification_code": "V-991"
    })
    assert taric_res["taric_document_code"] == "C081"
    assert "Box 44" in taric_res["agent_summary"]

    # 2. eudr_simulate_swe_c_customs_clearance
    swe_res = await AgentToolsRegistry.execute_tool("eudr_simulate_swe_c_customs_clearance", {
        "dds_reference_id": "26EUDR-TIMBER-001",
        "verification_code": "V-991",
        "eori_number": "NL123456789",
        "hs_code": "440711",
        "net_mass_kg": 18500.0,
        "country_code": "ID",
        "destination_port": "NLRTM"
    })
    assert swe_res["clearance_status"] == "GREEN_LANE_CLEARED"
    assert "EU SWE-C Customs Pre-Clearance" in swe_res["agent_summary"]
