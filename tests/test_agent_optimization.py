"""
Tests for Autonomous AI Agent Optimization & Model Context Protocol (MCP) Integration.
Verifies /llms.txt, MCP JSON-RPC 2.0, Agent Tools registry, and Self-Correction error handling.
"""
import pytest
from fastapi.testclient import TestClient
import json

from app.main import app

client = TestClient(app)


def test_llms_txt_and_manifest_endpoints():
    """Verifies that llms.txt, llms-full.txt and agent.json are served correctly."""
    # 1. llms.txt
    res = client.get("/llms.txt")
    assert res.status_code == 200
    assert "EUDR.agent" in res.text
    assert "eudr_verify_plot" in res.text

    # 2. llms-full.txt
    res_full = client.get("/llms-full.txt")
    assert res_full.status_code == 200
    assert "Model Context Protocol" in res_full.text
    assert "EU 2023/1115" in res_full.text

    # 3. .well-known/agent.json
    res_agent = client.get("/.well-known/agent.json")
    assert res_agent.status_code == 200
    data = res_agent.json()
    assert data["name_for_model"] == "eudr_compliance_agent"
    assert "mcp" in data

    # 4. .well-known/mcp/server-card.json (Smithery.ai fallback)
    res_card = client.get("/.well-known/mcp/server-card.json")
    assert res_card.status_code == 200
    card_data = res_card.json()
    assert card_data["serverInfo"]["name"] == "eudr-compliance-agent"
    assert len(card_data["tools"]) >= 9

    # 5. GET /api/v1/mcp and /mcp (prevent 405 Method Not Allowed)
    res_mcp_get = client.get("/api/v1/mcp")
    assert res_mcp_get.status_code == 200
    res_root_mcp = client.get("/mcp")
    assert res_root_mcp.status_code == 200


def test_agent_tools_listing():
    """Verifies /api/v1/agent/tools returns valid OpenAI/Anthropic/Gemini compatible schemas."""
    res = client.get("/api/v1/agent/tools")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["tool_count"] >= 6

    tool_names = [t["name"] for t in data["tools"]]
    assert "eudr_verify_plot" in tool_names
    assert "eudr_check_deforestation" in tool_names
    assert "eudr_verify_vies_vat" in tool_names
    assert "eudr_generate_dds" in tool_names
    assert "eudr_verify_audit_integrity" in tool_names
    assert "eudr_estimate_compliance_cost" in tool_names


def test_agent_tool_execution_verify_plot():
    """Verifies direct execution of eudr_verify_plot via /api/v1/agent/tools/execute."""
    payload = {
        "tool_name": "eudr_verify_plot",
        "arguments": {
            "plot_id": "PLOT-ID-2026-X1",
            "country_code": "ID",
            "commodity": "oil_palm",
            "coordinates": [101.45, 0.52],
            "area_hectares": 2.5
        }
    }
    res = client.post("/api/v1/agent/tools/execute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["result"]["is_valid"] is True
    assert data["result"]["compliance_status"] == "COMPLIANT"


def test_agent_tool_execution_self_correction_error():
    """Verifies that out-of-bounds coordinates return actionable self-correction hints."""
    payload = {
        "tool_name": "eudr_verify_plot",
        "arguments": {
            "plot_id": "PLOT-BAD-COORD",
            "country_code": "BR",
            "commodity": "soya",
            "coordinates": [250.0, 15.0]  # Longitude > 180!
        }
    }
    res = client.post("/api/v1/agent/tools/execute", json=payload)
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "COORDINATE_OUT_OF_BOUNDS"
    assert data["error"]["recoverable"] is True
    assert "suggested_fix" in data["error"]
    assert "agent_action_hint" in data["error"]


from unittest.mock import patch

def test_agent_tool_execution_vat_and_dds():
    """Verifies execution of VIES VAT check and TRACES-NT DDS compilation."""
    # 1. VIES check
    vat_payload = {
        "tool_name": "eudr_verify_vies_vat",
        "arguments": {
            "country_code": "FR",
            "vat_number": "12345678901"
        }
    }
    with patch("app.modules.agent_tools.ViesValidator.validate_vat_async", return_value={
        "valid": True,
        "raw_vat": "FR12345678901",
        "country_code": "FR",
        "vat_number": "12345678901",
        "company_name": "Agro Import Paris SAS",
        "address": "12 Rue de la Paix, 75001 Paris",
        "vies_live_verified": True,
        "reverse_charge_eligible": True
    }):
        res = client.post("/api/v1/agent/tools/execute", json=vat_payload)
        assert res.status_code == 200
        assert res.json()["result"]["is_valid"] is True

    # 2. DDS generation
    dds_payload = {
        "tool_name": "eudr_generate_dds",
        "arguments": {
            "operator_name": "EuroCocoa Trading BV",
            "operator_vat": "NL859403829B01",
            "commodity": "cocoa",
            "total_net_mass_kg": 25000.0,
            "plot_ids": ["PLOT-CI-001", "PLOT-CI-002"]
        }
    }
    res = client.post("/api/v1/agent/tools/execute", json=dds_payload)
    assert res.status_code == 200
    dds_res = res.json()["result"]
    assert dds_res["traces_ready"] is True
    assert "EUDR-DDS-" in dds_res["dds_reference_id"]
    assert "<DueDiligenceStatement" in dds_res["xml_declaration"]


def test_mcp_protocol_initialize():
    """Verifies Model Context Protocol (MCP) initialize handshake."""
    mcp_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestClaudeClient", "version": "1.0"}
        }
    }
    res = client.post("/api/v1/mcp", json=mcp_req)
    assert res.status_code == 200
    data = res.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert data["result"]["protocolVersion"] == "2024-11-05"
    assert data["result"]["serverInfo"]["name"] == "eudr-compliance-mcp-server"


def test_mcp_tools_list_and_call():
    """Verifies MCP tools/list and tools/call functionality."""
    # 1. tools/list
    list_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    res = client.post("/api/v1/mcp", json=list_req)
    assert res.status_code == 200
    tools = res.json()["result"]["tools"]
    assert len(tools) >= 6
    assert any(t["name"] == "eudr_estimate_compliance_cost" for t in tools)

    # 2. tools/call
    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "eudr_estimate_compliance_cost",
            "arguments": {
                "num_plots": 20,
                "satellite_resolution": "sentinel_10m",
                "include_traces_submission": True
            }
        }
    }
    res = client.post("/api/v1/mcp", json=call_req)
    assert res.status_code == 200
    call_res = res.json()["result"]
    assert call_res["isError"] is False
    content_text = call_res["content"][0]["text"]
    parsed = json.loads(content_text)
    assert parsed["num_plots"] == 20
    assert parsed["total_estimate_eur"] > 0


def test_mcp_prompts_list_and_get():
    """Verifies MCP prompts/list and prompts/get for agent workflow initiation."""
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "prompts/list"
    }
    res = client.post("/api/v1/mcp", json=req)
    assert res.status_code == 200
    assert len(res.json()["result"]["prompts"]) >= 1

    get_req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "prompts/get",
        "params": {
            "name": "eudr_compliance_audit_prompt",
            "arguments": {
                "operator_name": "Global Coffee Imports Ltd",
                "commodity": "coffee"
            }
        }
    }
    res = client.post("/api/v1/mcp", json=get_req)
    assert res.status_code == 200
    msg = res.json()["result"]["messages"][0]["content"]["text"]
    assert "Global Coffee Imports Ltd" in msg
    assert "eudr_verify_plot" in msg


def test_mcp_resources_list_and_read():
    """Verifies MCP resources/list and resources/read functionality."""
    # 1. resources/list
    list_req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "resources/list"
    }
    res = client.post("/api/v1/mcp", json=list_req)
    assert res.status_code == 200
    resources = res.json()["result"]["resources"]
    assert len(resources) >= 2
    assert any(r["uri"] == "eudr://regulation/eu-2023-1115" for r in resources)

    # 2. resources/read
    read_req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "resources/read",
        "params": {
            "uri": "eudr://regulation/eu-2023-1115"
        }
    }
    res = client.post("/api/v1/mcp", json=read_req)
    assert res.status_code == 200
    contents = res.json()["result"]["contents"]
    assert len(contents) == 1
    assert "2020" in contents[0]["text"]


def test_agent_create_payment_order_and_budget_cap():
    """Verifies that an agent can create a payment order and safety budget caps are enforced."""
    # 1. Successful order within budget
    payload = {
        "tool_name": "eudr_create_payment_order",
        "arguments": {
            "plan_tier": "PRO",
            "company_name": "Autonomous Cocoa Agents LLC",
            "contact_email": "bot@cocoa-agents.io",
            "chain": "Base (Low Gas $0.01)",
            "max_budget_usdc": 500.0  # PRO is 299 USDC <= 500
        }
    }
    res = client.post("/api/v1/agent/tools/execute", json=payload)
    assert res.status_code == 200
    data = res.json()["result"]
    assert "ORD-" in data["order_id"]
    assert data["amount_usdc"] == 299.0
    assert "0x" in data["deposit_wallet_address"]
    assert "qr_code_payload" in data

    # 2. Budget Cap Exceeded guardrail
    budget_exceeded_payload = {
        "tool_name": "eudr_create_payment_order",
        "arguments": {
            "plan_tier": "ENTERPRISE",  # 1990 USDC
            "company_name": "Rogue Agent Inc",
            "contact_email": "rogue@agent.ai",
            "max_budget_usdc": 100.0  # Budget is only 100 USDC!
        }
    }
    res_err = client.post("/api/v1/agent/tools/execute", json=budget_exceeded_payload)
    assert res_err.status_code == 400
    err_data = res_err.json()
    assert err_data["error"]["code"] == "BUDGET_CAP_EXCEEDED"
    assert "exceeds agent budget cap" in err_data["error"]["message"]


def test_agent_confirm_payment():
    """Verifies that an agent can confirm on-chain payment and receive an issued API key."""
    # Create order first
    create_payload = {
        "tool_name": "eudr_create_payment_order",
        "arguments": {
            "plan_tier": "STARTER",
            "company_name": "Green Timber Agent",
            "contact_email": "timber@greentimber.com"
        }
    }
    res_order = client.post("/api/v1/agent/tools/execute", json=create_payload)
    order_id = res_order.json()["result"]["order_id"]

    # Confirm order with tx_hash
    confirm_payload = {
        "tool_name": "eudr_confirm_payment",
        "arguments": {
            "order_id": order_id,
            "tx_hash": "0x4a938c2b7f01de982136a87b2c5e4f3a8b1c0d9e"
        }
    }
    res_conf = client.post("/api/v1/agent/tools/execute", json=confirm_payload)
    assert res_conf.status_code == 200
    conf_data = res_conf.json()["result"]
    assert conf_data["status"] == "CONFIRMED"
    assert "eudr_live_" in conf_data["api_key_issued"]
    assert conf_data["plan_tier"] == "STARTER"


def test_agent_render_satellite_map():
    """Verifies that an agent can generate satellite imagery metadata and NDVI canopy radar visualization."""
    payload = {
        "tool_name": "eudr_render_satellite_map",
        "arguments": {
            "plot_id": "PLOT-SAR-SUMATRA-01",
            "coordinates": [101.45, 0.52],
            "year": 2020,
            "layer": "ndvi_vegetation"
        }
    }
    res = client.post("/api/v1/agent/tools/execute", json=payload)
    assert res.status_code == 200
    data = res.json()["result"]
    assert data["plot_id"] == "PLOT-SAR-SUMATRA-01"
    assert data["ndvi_canopy_score"] > 0.8
    assert "T48MZC_20201231" in data["sentinel_tile_id"]
    assert "<svg" in data["svg_visualization"]
    assert "https://eudragent.com/api/v1/satellite/map-preview" in data["direct_map_url"]

