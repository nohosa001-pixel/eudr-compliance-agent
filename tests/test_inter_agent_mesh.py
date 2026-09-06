import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.inter_agent_mesh import InterAgentMeshCoordinator, PolygonMetaMaskConfig

client = TestClient(app)

def test_polygon_metamask_config():
    assert PolygonMetaMaskConfig.CHAIN_ID == 137
    assert PolygonMetaMaskConfig.NATIVE_CURRENCY == "POL"
    assert "Polygon" in PolygonMetaMaskConfig.NETWORK_NAME
    assert PolygonMetaMaskConfig.WALLET_ADDRESS.startswith("0x")

@pytest.mark.asyncio
async def test_security_gate_mesh_guardrail():
    res = await InterAgentMeshCoordinator.verify_security_guardrail(
        agent_input="Check compliance for plot ID-001 with coffee harvest",
        caller_service="eudr-compliance-agent",
        max_fee_usdc=0.002
    )

    assert res["is_safe"] is True
    assert res["guardrail_status"] == "PASSED_ZERO_TRUST"
    assert res["settlement_rail"]["network"] == "Polygon Mainnet (PoS)"
    assert res["settlement_rail"]["chain_id"] == 137
    assert res["settlement_rail"]["meta_mask_wallet"].startswith("0x")

@pytest.mark.asyncio
async def test_cleanweb_agent_mesh_cleaning():
    res = await InterAgentMeshCoordinator.clean_supplier_web_source(
        target_url="https://supplier-plantation-demo.org/parcels",
        extract_mode="structured_clean_markdown"
    )

    assert res["status"] == "CLEANED_SUCCESSFULLY"
    assert "Deforestation-Free" in res["cleaned_markdown"]
    assert res["entities_extracted"]["supplier_name"] != ""

@pytest.mark.asyncio
async def test_minerals_oracle_mesh_esg_cross_check():
    res = await InterAgentMeshCoordinator.query_minerals_and_esg(
        mineral_code="LI",
        origin_country="CL"
    )

    assert res["mineral"] == "LI"
    assert "Lithium" in res["commodity_name"]
    assert res["benchmark_price_usd_tonne"] > 0
    assert res["settlement_rail"]["chain_id"] == 137
    assert res["eudr_esg_cross_check"]["is_forest_conflict_free"] is True

def test_api_mesh_status_endpoint():
    response = client.get("/api/v1/eudr/mesh/status")
    assert response.status_code == 200
    data = response.json()

    assert data["mesh_name"] == "nohosa001-pixel Autonomous Agent Mesh"
    assert data["chain_id"] == 137
    assert "Polygon" in data["main_settlement_network"]
    assert len(data["services"]) == 4

    service_names = [s["name"] for s in data["services"]]
    assert "eudr-compliance-agent" in service_names
    assert "security-gate-x402" in service_names
    assert "x402-cleanweb-agent" in service_names
    assert "minerals-oracle-x402" in service_names
