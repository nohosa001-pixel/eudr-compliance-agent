"""
Comprehensive test suite for Advanced Escrow Upgrades:
- 3-Stage Milestone-based conditional releases (Pre-shipment Satellite -> DDS -> Customs Green Lane)
- First-Mile Multi-Party Splits (Direct payout allocation to Smallholder Co-ops & Processing Mills)
- Autonomous On-Chain Slashing with EIP-712 BLOCKED attestation & 100% Buyer Restitution
- Non-breaking compatibility with AgentEscrow.sol and security-gate-x402
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.modules.agent_escrow_manager import AgentEscrowManager
from app.modules.agent_tools import AgentToolsRegistry
from app.schemas import (
    MilestoneEscrowCreateRequest,
    EscrowMilestoneItem,
    FirstMileSplitRecipient,
    EscrowFundRequest,
    EscrowMilestoneReleaseRequest,
    EscrowAutoSlashRequest,
    EscrowStatusEnum,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_escrow_state():
    """Reset the agent escrow store before and after tests."""
    initial_store = AgentEscrowManager._escrows.copy()
    yield
    AgentEscrowManager._escrows = initial_store


def test_create_milestone_escrow_and_weights():
    """Verify creation of 3-stage milestone escrow with first-mile split allocations."""
    req = MilestoneEscrowCreateRequest(
        buyer_agent_id="buyer-nestle-bot-01",
        buyer_wallet="0x1111111111111111111111111111111111111111",
        seller_agent_id="seller-nigeria-palm-coop",
        seller_wallet="0x2222222222222222222222222222222222222222",
        amount_usdc=100000.0,
        chain="Base (Low Gas $0.01)",
        hs_code="15111000",
        commodity_description="Crude Palm Oil compliant with NaPOTS and EUDR Art. 3",
        declared_net_mass_kg=50000.0,
        milestone_weights=[30.0, 40.0, 30.0],
        split_recipients=[
            FirstMileSplitRecipient(
                recipient_role="SMALLHOLDER_COOP",
                wallet_address="0x3333333333333333333333333333333333333333",
                share_percentage=75.0,
            ),
            FirstMileSplitRecipient(
                recipient_role="MILL_OPERATOR",
                wallet_address="0x4444444444444444444444444444444444444444",
                share_percentage=25.0,
            ),
        ],
    )

    resp = AgentEscrowManager.create_milestone_escrow(req)
    assert resp.status == EscrowStatusEnum.AWAITING_DEPOSIT
    assert resp.amount_usdc == 100000.0
    assert resp.released_amount_usdc == 0.0
    assert resp.remaining_locked_usdc == 100000.0
    assert len(resp.milestones) == 3
    assert resp.milestones[0].amount_usdc == 30000.0
    assert resp.milestones[1].amount_usdc == 40000.0
    assert resp.milestones[2].amount_usdc == 30000.0
    assert len(resp.split_recipients) == 2
    assert resp.split_recipients[0].share_percentage == 75.0
    assert resp.split_recipients[1].share_percentage == 25.0


def test_sequential_milestone_releases_lifecycle():
    """
    Test complete sequential milestone release:
    1. Create milestone escrow
    2. Fund escrow (transition to FUNDED_LOCKED)
    3. Release Milestone 1 (Pre-shipment Satellite check -> 30% unlocked)
    4. Release Milestone 2 (EU TRACES-NT DDS Issuance -> 40% unlocked, total 70%)
    5. Release Milestone 3 (Customs Green Lane -> final 30% unlocked, total 100%, status RELEASED)
    """
    # 1. Create via API
    create_payload = {
        "buyer_agent_id": "buyer-ferrero-agent",
        "buyer_wallet": "0x1111111111111111111111111111111111111111",
        "seller_agent_id": "seller-ghana-cocoa-board",
        "seller_wallet": "0x2222222222222222222222222222222222222222",
        "amount_usdc": 10000.0,
        "chain": "Base (Low Gas $0.01)",
        "hs_code": "18010000",
        "commodity_description": "Traceable Raw Cocoa Beans",
        "declared_net_mass_kg": 5000.0,
        "milestone_weights": [30.0, 40.0, 30.0],
        "split_recipients": [
            {
                "recipient_role": "SMALLHOLDER_COOP",
                "wallet_address": "0xAAAA000000000000000000000000000000000001",
                "share_percentage": 80.0,
            },
            {
                "recipient_role": "LOCAL_AGGREGATOR",
                "wallet_address": "0xBBBB000000000000000000000000000000000002",
                "share_percentage": 20.0,
            },
        ],
    }
    c_res = client.post("/api/v1/payment/escrow/milestone/create", json=create_payload)
    assert c_res.status_code == 201
    cdata = c_res.json()
    escrow_id = cdata["escrow_id"]

    # 2. Fund escrow
    f_res = client.post("/api/v1/payment/escrow/fund", json={"escrow_id": escrow_id, "tx_hash": "0x" + "ff" * 32})
    assert f_res.status_code == 200
    assert f_res.json()["status"] == "FUNDED_LOCKED"

    # 3. Release Milestone 1 (Pre-shipment Satellite check, 30% = 3,000 USDC)
    m1_payload = {
        "escrow_id": escrow_id,
        "milestone_index": 1,
        "plots": [
            {
                "plot_id": "GH-COCOA-001",
                "country_code": "GH",
                "area_hectares": 3.5,
                "coordinates": [-1.6244, 6.6885],
            }
        ],
    }
    m1_res = client.post("/api/v1/payment/escrow/milestone/release", json=m1_payload)
    assert m1_res.status_code == 200
    m1_data = m1_res.json()
    assert m1_data["milestone_index"] == 1
    assert m1_data["released_amount_usdc"] == 3000.0
    assert m1_data["cumulative_released_usdc"] == 3000.0
    assert m1_data["remaining_locked_usdc"] == 7000.0
    assert m1_data["eip712_attestation"] is not None
    assert m1_data["eip712_attestation"]["verdict"] == "PASSED"
    # Check First-Mile split distribution
    assert len(m1_data["split_allocations"]) == 2
    assert m1_data["split_allocations"][0]["milestone_released_usdc"] == 2400.0  # 80% of 3,000
    assert m1_data["split_allocations"][1]["milestone_released_usdc"] == 600.0   # 20% of 3,000

    # 4. Release Milestone 2 (EU TRACES-NT DDS Issuance, 40% = 4,000 USDC)
    m2_payload = {
        "escrow_id": escrow_id,
        "milestone_index": 2,
        "dds_reference_id": f"DDS-EUDR-2026-{uuid.uuid4().hex[:8].upper()}",
    }
    m2_res = client.post("/api/v1/payment/escrow/milestone/release", json=m2_payload)
    assert m2_res.status_code == 200
    m2_data = m2_res.json()
    assert m2_data["milestone_index"] == 2
    assert m2_data["released_amount_usdc"] == 4000.0
    assert m2_data["cumulative_released_usdc"] == 7000.0
    assert m2_data["remaining_locked_usdc"] == 3000.0

    # 5. Release Milestone 3 (Customs Green Lane Clearance, final 30% = 3,000 USDC)
    m3_payload = {
        "escrow_id": escrow_id,
        "milestone_index": 3,
        "customs_declaration_code": f"EU-SWEC-CLEARED-{uuid.uuid4().hex[:6].upper()}",
    }
    m3_res = client.post("/api/v1/payment/escrow/milestone/release", json=m3_payload)
    assert m3_res.status_code == 200
    m3_data = m3_res.json()
    assert m3_data["milestone_index"] == 3
    assert m3_data["released_amount_usdc"] == 3000.0
    assert m3_data["cumulative_released_usdc"] == 10000.0
    assert m3_data["remaining_locked_usdc"] == 0.0

    # Verify overall escrow state is RELEASED
    detail_res = client.get(f"/api/v1/payment/escrow/{escrow_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["status"] == "RELEASED"
    assert detail_res.json()["released_amount_usdc"] == 10000.0
    assert detail_res.json()["remaining_locked_usdc"] == 0.0


def test_autonomous_slashing_with_eip712_attestation():
    """
    Test autonomous slashing when deforestation violation is confirmed:
    - Escrow is created & funded
    - Auto-slash is invoked
    - EIP-712 BLOCKED attestation is generated (compatible with AgentEscrow.sol.slashJob())
    - 100% of remaining funds refunded to Buyer
    """
    create_req = MilestoneEscrowCreateRequest(
        buyer_agent_id="buyer-unilever-bot",
        buyer_wallet="0x1111111111111111111111111111111111111111",
        seller_agent_id="seller-unverified-mill",
        seller_wallet="0x2222222222222222222222222222222222222222",
        amount_usdc=50000.0,
        chain="Base (Low Gas $0.01)",
        hs_code="15111000",
        commodity_description="Uncertified Palm Oil Batch",
        declared_net_mass_kg=25000.0,
    )
    escrow = AgentEscrowManager.create_milestone_escrow(create_req)
    escrow_id = escrow.escrow_id

    # Fund
    AgentEscrowManager.fund_escrow(EscrowFundRequest(escrow_id=escrow_id, tx_hash="0x" + "11" * 32))

    # Auto slash via API
    slash_payload = {
        "escrow_id": escrow_id,
        "reason": "Sentinel-2 radar detected 23.4 ha primary forest clearing post-2020 cutoff date.",
        "slashing_penalty_pct": 100.0,
    }
    slash_res = client.post("/api/v1/payment/escrow/auto-slash", json=slash_payload)
    assert slash_res.status_code == 200
    sdata = slash_res.json()
    assert sdata["status"] == "REFUNDED"
    assert "AUTONOMOUS ON-CHAIN SLASHING EXECUTED" in sdata["arbitration_verdict"]

    # Verify that in-memory escrow has valid EIP-712 attestation with BLOCKED verdict & riskScore 95
    stored = AgentEscrowManager._escrows[escrow_id]
    attestation = stored.get("onchain_attestation")
    assert attestation is not None
    assert attestation["verdict"] == "BLOCKED"
    assert attestation["riskScore"] == 95
    assert attestation["r"].startswith("0x")


@pytest.mark.asyncio
async def test_mcp_agent_tools_milestone_and_slash():
    """Verify autonomous AI agents can invoke milestone creation and release through AgentToolsRegistry."""
    # 1. Tool call: create milestone escrow
    create_args = {
        "buyer_agent_id": "procurement-agent-alpha",
        "buyer_wallet": "0x1111111111111111111111111111111111111111",
        "seller_agent_id": "farmer-coop-beta",
        "seller_wallet": "0x2222222222222222222222222222222222222222",
        "amount_usdc": 12000.0,
        "chain": "Base (Low Gas $0.01)",
        "hs_code": "09011100",
        "commodity_description": "Green Coffee Beans Arabica",
        "declared_net_mass_kg": 6000.0,
        "milestone_weights": [30.0, 40.0, 30.0],
    }
    tool_res = await AgentToolsRegistry.execute_tool("eudr_create_milestone_escrow", create_args)
    escrow_id = tool_res["escrow_id"]
    assert escrow_id.startswith("ESC-EUDR-2026-")
    assert tool_res["amount_usdc"] == 12000.0
    assert "agent_summary" in tool_res

    # Fund it
    AgentEscrowManager.fund_escrow(EscrowFundRequest(escrow_id=escrow_id, tx_hash="0x" + "22" * 32))

    # 2. Tool call: release milestone 1
    rel_args = {
        "escrow_id": escrow_id,
        "milestone_index": 1,
        "plots": [
            {"plot_id": "GH-COCOA-001", "country_code": "GH", "area_hectares": 3.5, "coordinates": [-1.6244, 6.6885]}
        ],
    }
    rel_res = await AgentToolsRegistry.execute_tool("eudr_release_escrow_milestone", rel_args)
    assert rel_res["milestone_index"] == 1
    assert rel_res["released_amount_usdc"] == 3600.0  # 30% of 12,000
    assert rel_res["cumulative_released_usdc"] == 3600.0
    assert "agent_summary" in rel_res
