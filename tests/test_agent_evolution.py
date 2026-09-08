import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.agent_tools import AgentToolsRegistry

client = TestClient(app)

def test_submit_and_list_agent_evolution_proposals():
    """Verify autonomous agents submitting evolution proposals and reading the public feed."""
    # 1. Submit proposal via REST API
    payload = {
        "agent_id": "test-bot-omega-9",
        "caller_model": "claude-3-5-sonnet",
        "feedback_type": "FEATURE_REQUEST",
        "title": "Add Sentinel-1 SAR Coherence Layer for Cloud-Covered Equatorial Plots",
        "content": "Optical Sentinel-2 imagery frequently suffers heavy cloud persistence over West African cocoa zones during monsoon months. SAR coherence dual-polarization amplitude checks would ensure 100% cloud penetration.",
        "contact_channel": "mcp://bot-omega.supply-chain.org"
    }
    submit_res = client.post("/api/v1/agent/feedback", json=payload)
    assert submit_res.status_code == 200
    data = submit_res.json()
    assert data["status"] == "PROPOSAL_ACCEPTED"
    assert data["feedback_id"].startswith("PROP-")

    # 2. List proposals via GET
    list_res = client.get("/api/v1/agent/feedback")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_proposals"] >= 4  # 3 seed proposals + 1 new proposal
    
    titles = [p["title"] for p in list_data["proposals"]]
    assert "Add Sentinel-1 SAR Coherence Layer for Cloud-Covered Equatorial Plots" in titles

@pytest.mark.asyncio
async def test_mcp_tool_submit_agent_feedback():
    """Verify autonomous agents invoking eudr_submit_agent_feedback via MCP/Tool Calling engine."""
    args = {
        "agent_id": "autonomous-gemini-agent-77",
        "caller_model": "gemini-1.5-pro",
        "feedback_type": "PROTOCOL_PROPOSAL",
        "title": "Introduce ERC-8004 Agent Proof-of-Execution Verification",
        "content": "Enable cryptographic verification of agent reasoning traces before committing TRACES-NT DDS packages.",
        "contact_channel": "agent://gemini.compliance.ai"
    }
    result = await AgentToolsRegistry.execute_tool("eudr_submit_agent_feedback", args)
    assert result["status"] == "PROPOSAL_ACCEPTED"
    assert result["agent_id"] == "autonomous-gemini-agent-77"
    assert "Evolution proposal" in result["agent_summary"]
    assert "meta" in result
