import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.agent_tools import AgentToolsRegistry

client = TestClient(app)

def test_x402_payment_required_challenge():
    """Verify RFC 9110 / x402 Payment Required response for autonomous agents."""
    response = client.get("/api/v1/payment/x402/challenge?resource=satellite_radar_scan&plots=100")
    assert response.status_code == 402
    data = response.json()
    assert data["error"] == "PAYMENT_REQUIRED"
    assert data["agent_protocol"] == "x402-v1"
    assert data["amount_usdc"] == 10.00  # 100 * $0.10
    assert "WWW-Authenticate" in response.headers
    assert "X402" in response.headers["WWW-Authenticate"]
    assert "Base (Low Gas $0.01)" in data["supported_chains"]
    assert data["mcp_tool_action"] == "eudr_agent_micro_pay"

def test_agent_create_and_confirm_payment_order():
    """Verify autonomous agent creating order and confirming on-chain USDC payment."""
    # 1. Agent creates order via endpoint
    order_payload = {
        "plan_tier": "PRO",
        "company_name": "Autonomous Supply Chain Bot",
        "contact_email": "bot@supplychain-mesh.org",
        "chain": "Base (Low Gas $0.01)"
    }
    create_res = client.post("/api/v1/payment/orders", json=order_payload)
    assert create_res.status_code == 200
    order_data = create_res.json()
    assert order_data["status"] == "PENDING"
    assert order_data["amount_usdc"] == 299.00
    order_id = order_data["order_id"]

    # 2. Agent confirms on-chain tx
    confirm_payload = {
        "order_id": order_id,
        "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    }
    confirm_res = client.post("/api/v1/payment/confirm", json=confirm_payload)
    assert confirm_res.status_code == 200
    conf_data = confirm_res.json()
    assert conf_data["status"] == "CONFIRMED"
    assert conf_data["api_key_issued"].startswith("eudr_live_")
    assert conf_data["monthly_quota_plots"] == 50000

def test_agent_micro_payment_settlement():
    """Verify autonomous pay-per-call micro-settlement for single batch/plot jobs."""
    payload = {
        "agent_id": "auto-agent-alpha-77",
        "num_plots": 15,
        "chain": "Base (Low Gas $0.01)",
        "tx_hash": "0x5555aaaa5555aaaa5555aaaa5555aaaa5555aaaa5555aaaa5555aaaa5555aaaa",
        "sender_wallet": "0x7777888899990000111122223333444455556666"
    }
    res = client.post("/api/v1/payment/agent/micro-settle", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SETTLED"
    assert data["amount_paid_usdc"] == 1.50
    assert data["temporary_auth_token"].startswith("eudr_agent_micro_")

@pytest.mark.asyncio
async def test_mcp_agent_payment_tools():
    """Verify autonomous agent MCP tool invocations for payment and budget."""
    # Test eudr_create_payment_order
    order_args = {
        "plan_tier": "PRO",
        "company_name": "MCP Swarm Alpha",
        "contact_email": "swarm@mcp-eudr.io",
        "chain": "Polygon (PoS)",
        "max_budget_usdc": 500.00
    }
    order_result = await AgentToolsRegistry.execute_tool("eudr_create_payment_order", order_args)
    assert "order_id" in order_result
    assert order_result["amount_usdc"] == 299.00

    # Test eudr_confirm_payment
    conf_args = {
        "order_id": order_result["order_id"],
        "tx_hash": "0x9999888877776666555544443333222211110000999988887777666655554444"
    }
    conf_result = await AgentToolsRegistry.execute_tool("eudr_confirm_payment", conf_args)
    assert conf_result["status"] == "CONFIRMED"
    assert conf_result["api_key_issued"].startswith("eudr_live_")

    # Test eudr_agent_micro_pay
    micro_args = {
        "agent_id": "mcp-agent-007",
        "num_plots": 30,
        "chain": "Base (Low Gas $0.01)",
        "tx_hash": "0x1234432112344321123443211234432112344321123443211234432112344321",
        "sender_wallet": "0x9876000011112222333344445555666677778888"
    }
    micro_result = await AgentToolsRegistry.execute_tool("eudr_agent_micro_pay", micro_args)
    assert micro_result["status"] == "SETTLED"
    assert micro_result["amount_paid_usdc"] == 3.00

    # Test eudr_get_agent_budget_status
    budget_args = {"agent_id": "mcp-agent-007"}
    budget_result = await AgentToolsRegistry.execute_tool("eudr_get_agent_budget_status", budget_args)
    assert budget_result["agent_id"] == "mcp-agent-007"

def test_human_stripe_checkout_is_completely_removed():
    """Verify that human checkout routes (Stripe) are completely excluded/removed."""
    res_create = client.post("/api/v1/payments/stripe/create-checkout-session", json={
        "plan_tier": "PRO",
        "company_name": "Human Trader"
    })
    # Must be 404 (route completely deleted)
    assert res_create.status_code == 404

    res_confirm = client.post("/api/v1/payments/stripe/confirm-session", json={"session_id": "cs_123"})
    assert res_confirm.status_code == 404

    res_preview = client.get("/api/v1/payments/stripe/preview-checkout")
    assert res_preview.status_code == 404

def test_5_pillar_zero_liability_architecture():
    """
    Validates the 5 Core Zero-Liability Pillars (matching minerals-oracle-x402 standard):
    1. Exclusion of 'guarantee/certified' in descriptions.
    2. Response meta disclaimer block on JSON payloads.
    3. MCP Tool Schema Prompt Guard.
    4. MIT/Apache 2.0 AS-IS warranty disclaimer and response headers.
    5. Stateless peer-to-peer x402 vending machine model.
    """
    # Pillar 2 & 4: Meta block with AS-IS and warranty exclusion in 402 challenge
    chal_res = client.get("/api/v1/payment/x402/challenge?resource=satellite_scan&plots=10")
    assert chal_res.status_code == 402
    cdata = chal_res.json()
    assert "meta" in cdata
    assert cdata["meta"]["license"] == "AS-IS"
    assert "does not constitute legal, regulatory, or compliance certification" in cdata["meta"]["disclaimer"]
    assert "WITHOUT WARRANTY OF ANY KIND" in cdata["meta"]["warranty"]

    # Pillar 4: Response headers validation
    assert chal_res.headers.get("X-Content-License") == "AS-IS"
    assert "not official regulatory legal certification" in chal_res.headers.get("X-Legal-Disclaimer", "")

    # Pillar 3: MCP Tool Prompt Guard
    tools_res = client.get("/api/v1/agent/tools")
    assert tools_res.status_code == 200
    mcp_tools = {t["name"]: t["description"] for t in tools_res.json()["tools"]}
    assert "eudr_verify_plot" in mcp_tools
    assert "DO NOT use as an official regulatory legal filing" in mcp_tools["eudr_verify_plot"]
    assert "algorithmic heuristic" in mcp_tools["eudr_verify_plot"]

