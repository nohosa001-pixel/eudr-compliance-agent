"""
Comprehensive Verification Suite: Autonomous Agent Entry & Interoperability.
Verifies that autonomous AI agents (Claude Desktop, Cursor, Antigravity, AutoGen, CrewAI, LangChain)
can discover, negotiate, and execute all EUDR capabilities with zero friction:
1. Standard Discovery: /llms.txt, /.well-known/agent.json, server-card.json, glama.json
2. Model Context Protocol (MCP v2024-11-05): JSON-RPC 2.0 handshake & 21 tools
3. Elevation Tools via MCP & Direct Agent Execution API
4. Self-Correction & Actionable Error Envelope (agent_action_hint, suggested_fix)
5. Mandatory Top-Level Zero-Liability Meta Block
6. Machine-to-Machine (M2M) X402 Payment Challenge & Autonomous Agent Mesh Interoperability
"""
import pytest
import json
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.modules.mcp_server import MCPServer
from app.modules.agent_tools import AgentToolsRegistry
from app.modules.inter_agent_mesh import InterAgentMeshCoordinator, PolygonMetaMaskConfig

client = TestClient(app)


def test_agent_discovery_standards():
    """Verifies that autonomous crawlers and agents find standard discovery manifests."""
    # 1. llms.txt
    res_llms = client.get("/llms.txt")
    assert res_llms.status_code == 200
    assert "text/plain" in res_llms.headers.get("content-type", "")
    assert "eudr_benchmark_country" in res_llms.text
    assert "eudr_link_downstream_chain" in res_llms.text
    assert "eudr_issue_statutory_exemption" in res_llms.text
    assert "eudr_slice_parcel" in res_llms.text

    # 2. llms-full.txt
    res_full = client.get("/llms-full.txt")
    assert res_full.status_code == 200
    assert "Model Context Protocol" in res_full.text

    # 3. .well-known/agent.json
    res_agent = client.get("/.well-known/agent.json")
    assert res_agent.status_code == 200
    assert res_agent.headers.get("content-type", "").startswith("application/json")
    data_agent = res_agent.json()
    assert "name_for_model" in data_agent
    assert data_agent["name_for_model"] == "eudr_compliance_agent"

    # 4. .well-known/mcp/server-card.json
    res_card = client.get("/.well-known/mcp/server-card.json")
    assert res_card.status_code == 200
    data_card = res_card.json()
    assert data_card["serverInfo"]["name"] == "eudr-compliance-agent"

    # 5. glama.json
    res_glama = client.get("/glama.json")
    assert res_glama.status_code == 200
    data_glama = res_glama.json()
    assert data_glama["name"] == "eudr-compliance-agent"


@pytest.mark.asyncio
async def test_mcp_protocol_full_handshake():
    """Verifies MCP JSON-RPC 2.0 lifecycle methods without network latency."""
    # 1. initialize
    init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    init_res = await MCPServer.handle_jsonrpc_request(init_req)
    assert init_res["id"] == 1
    assert init_res["result"]["protocolVersion"] == "2024-11-05"
    assert init_res["result"]["serverInfo"]["name"] == "eudr-compliance-mcp-server"

    # 2. ping
    ping_res = await MCPServer.handle_jsonrpc_request({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert ping_res["result"] == {}

    # 3. tools/list: Must contain all 21 tools
    tools_res = await MCPServer.handle_jsonrpc_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    tools = tools_res["result"]["tools"]
    assert len(tools) >= 21
    tool_names = [t["name"] for t in tools]

    # Verify original core tools
    assert "eudr_verify_plot" in tool_names
    assert "eudr_check_deforestation" in tool_names
    assert "eudr_verify_vies_vat" in tool_names
    assert "eudr_generate_dds" in tool_names
    assert "eudr_evaluate_compact" in tool_names

    # Verify newly exposed elevation tools
    assert "eudr_benchmark_country" in tool_names
    assert "eudr_link_downstream_chain" in tool_names
    assert "eudr_issue_statutory_exemption" in tool_names
    assert "eudr_slice_parcel" in tool_names

    # 4. resources/list and resources/read
    res_list = await MCPServer.handle_jsonrpc_request({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
    assert len(res_list["result"]["resources"]) >= 2

    res_read = await MCPServer.handle_jsonrpc_request({
        "jsonrpc": "2.0", "id": 5, "method": "resources/read",
        "params": {"uri": "eudr://regulation/eu-2023-1115"}
    })
    assert len(res_read["result"]["contents"]) > 0


@pytest.mark.asyncio
async def test_mcp_elevation_tools_execution():
    """Verifies that an autonomous agent can invoke the 4 new elevation tools via MCP."""
    # 1. eudr_benchmark_country
    bench_req = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "eudr_benchmark_country",
            "arguments": {"country_code": "DE"}
        }
    }
    bench_res = await MCPServer.handle_jsonrpc_request(bench_req)
    assert bench_res["result"]["isError"] is False
    content_bench = json.loads(bench_res["result"]["content"][0]["text"])
    assert content_bench["country_code"] == "DE"
    assert content_bench["simplified_due_diligence_eligible"] is True
    assert content_bench["customs_inspection_rate_pct"] == 1.0

    # 2. eudr_issue_statutory_exemption
    exempt_req = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {
            "name": "eudr_issue_statutory_exemption",
            "arguments": {
                "hs_code": "4101",
                "product_description": "Raw bovine hides and skins",
                "consignment_id": "BL-HAMBURG-2026-99",
                "operator_name": "Lufthansa Cargo Logistics"
            }
        }
    }
    exempt_res = await MCPServer.handle_jsonrpc_request(exempt_req)
    assert exempt_res["result"]["isError"] is False
    content_exempt = json.loads(exempt_res["result"]["content"][0]["text"])
    assert content_exempt["is_exempt_from_eudr"] is True
    assert "EU-EXEMPT-CERT" in content_exempt["certificate_id"]

    # 3. eudr_link_downstream_chain
    chain_req = {
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tools/call",
        "params": {
            "name": "eudr_link_downstream_chain",
            "arguments": {
                "operator_id": "OP-DOWNSTREAM-42",
                "operator_name": "Nestle EU Distribution",
                "operator_eori": "CH123456789",
                "upstream_dds_reference": "EU-DDS-2026-VALID-UPSTREAM-88",
                "consignment_mass_kg": 25000.0
            }
        }
    }
    chain_res = await MCPServer.handle_jsonrpc_request(chain_req)
    assert chain_res["result"]["isError"] is False
    content_chain = json.loads(chain_res["result"]["content"][0]["text"])
    assert content_chain["cascade_risk_status"] == "CLEAN_UPSTREAM"
    assert content_chain["is_cleared_for_eu_free_circulation"] is True

    # 4. eudr_slice_parcel
    slice_req = {
        "jsonrpc": "2.0",
        "id": 104,
        "method": "tools/call",
        "params": {
            "name": "eudr_slice_parcel",
            "arguments": {
                "plot_id": "COOP-ID-OVERSIZED-12HA",
                "country_code": "ID",
                "commodity": "oil_palm",
                "area_hectares": 12.0,
                "coordinates": [
                    [101.40, 0.50],
                    [101.44, 0.50],
                    [101.44, 0.54],
                    [101.40, 0.54],
                    [101.40, 0.50]
                ]
            }
        }
    }
    slice_res = await MCPServer.handle_jsonrpc_request(slice_req)
    assert slice_res["result"]["isError"] is False
    content_slice = json.loads(slice_res["result"]["content"][0]["text"])
    assert content_slice["slices_count"] >= 4
    assert content_slice["all_slices_under_4ha"] is True


def test_agent_tools_direct_http_execution():
    """Verifies that an autonomous agent can execute elevation tools via REST POST."""
    # 1. Country Benchmarking for High Risk Country
    payload_bench = {
        "tool_name": "eudr_benchmark_country",
        "arguments": {"country_code": "BR"}
    }
    res = client.post("/api/v1/agent/tools/execute", json=payload_bench)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["result"]["customs_inspection_rate_pct"] == 9.0
    assert data["result"]["mandatory_fpic_required"] is True

    # 2. Smallholder Parcel Auto-Slicing
    payload_slice = {
        "tool_name": "eudr_slice_parcel",
        "arguments": {
            "plot_id": "SUMATRA-COOP-AGGREGATED",
            "country_code": "ID",
            "commodity": "rubber",
            "area_hectares": 7.5,
            "coordinates": [
                [102.0, -1.0],
                [102.02, -1.0],
                [102.02, -0.98],
                [102.0, -0.98],
                [102.0, -1.0]
            ]
        }
    }
    res_slice = client.post("/api/v1/agent/tools/execute", json=payload_slice)
    assert res_slice.status_code == 200
    data_slice = res_slice.json()
    assert data_slice["status"] == "success"
    assert data_slice["result"]["all_slices_under_4ha"] is True
    assert len(data_slice["result"]["sliced_parcels"]) >= 2


def test_agent_self_healing_error_contract():
    """Verifies that an autonomous agent receives self-healing guidance on malformed payloads."""
    # Unknown tool name -> returns TOOL_NOT_FOUND with available tools list
    payload_unknown = {
        "tool_name": "non_existent_satellite_scan",
        "arguments": {}
    }
    res_unknown = client.post("/api/v1/agent/tools/execute", json=payload_unknown)
    assert res_unknown.status_code == 400
    data_err = res_unknown.json()
    assert "error" in data_err
    assert data_err["error"]["code"] == "TOOL_NOT_FOUND"
    assert "suggested_fix" in data_err["error"]
    assert "agent_action_hint" in data_err["error"]

    # Missing required argument for eudr_verify_plot
    payload_missing = {
        "tool_name": "eudr_verify_plot",
        "arguments": {
            "plot_id": "PLOT-TEST-MISSING-ARGS"
            # Missing country_code, commodity, coordinates
        }
    }
    res_missing = client.post("/api/v1/agent/tools/execute", json=payload_missing)
    assert res_missing.status_code == 400
    data_missing = res_missing.json()
    assert data_missing["error"]["code"] == "MISSING_REQUIRED_PARAMETER"
    assert "country_code" in data_missing["error"]["message"]


def test_zero_liability_meta_block_contract():
    """Verifies that every autonomous agent tool response includes the 5-pillar AS-IS meta block."""
    tools_to_test = [
        ("eudr_verify_plot", {
            "plot_id": "PLOT-META-TEST",
            "country_code": "VN",
            "commodity": "coffee",
            "coordinates": [108.0, 12.0],
            "area_hectares": 1.5
        }),
        ("eudr_benchmark_country", {"country_code": "GH"}),
        ("eudr_issue_statutory_exemption", {
            "hs_code": "4104",
            "product_description": "Tanned leather without wool",
            "consignment_id": "BL-META-1",
            "operator_name": "Bavaria Automotive Parts"
        })
    ]

    for tool_name, args in tools_to_test:
        res = client.post("/api/v1/agent/tools/execute", json={"tool_name": tool_name, "arguments": args})
        assert res.status_code == 200, f"Failed on {tool_name}"
        res_data = res.json()["result"]
        assert "meta" in res_data, f"Meta block missing in {tool_name}"
        meta = res_data["meta"]
        assert meta["license"] == "AS-IS"
        assert "disclaimer" in meta
        assert "disclaimer_hash" in meta


def test_m2m_x402_and_autonomous_mesh_interoperability():
    """
    Verifies that autonomous agents can interact via machine-to-machine payment rails
    and communicate across the 4-agent autonomous mesh without human session blockers.
    """
    # 1. RFC 9110 / x402 Machine-readable payment challenge (HTTP 402 Payment Required)
    res_x402 = client.get("/api/v1/payment/x402/challenge?service=eudr-dds-issue")
    assert res_x402.status_code in (402, 200)
    data_x402 = res_x402.json()
    assert data_x402["agent_protocol"] == "x402-v1"
    assert data_x402["deposit_wallet"].startswith("0x")
    assert data_x402["eip3009_supported"] is True
    assert "Polygon (PoS)" in data_x402["supported_chains"]

    # 2. Autonomous Agent Mesh status
    res_mesh = client.get("/api/v1/eudr/mesh/status")
    assert res_mesh.status_code == 200
    data_mesh = res_mesh.json()
    assert data_mesh["chain_id"] == 137
    assert len(data_mesh["services"]) == 4

    # 3. Polygon MetaMask Settlement Parameters
    assert PolygonMetaMaskConfig.CHAIN_ID == 137
    assert PolygonMetaMaskConfig.NATIVE_CURRENCY == "POL"
    assert PolygonMetaMaskConfig.WALLET_ADDRESS.startswith("0x")
