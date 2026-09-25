import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.modules.web3_escrow_adapter import web3_escrow_adapter, Web3EscrowAdapter
from app.modules.agent_escrow_manager import AgentEscrowManager
from app.modules.agent_tools import AgentToolsRegistry
from app.schemas import (
    EscrowCreateRequest,
    EscrowFundRequest,
    EscrowReleaseByComplianceRequest,
    EscrowDisputeArbitrateRequest
)

client = TestClient(app)


def test_web3_escrow_adapter_signing_and_verification():
    """Verify core cryptographic EIP-712 signing and verification."""
    job_id = 101
    deliverable_hash = "0x" + "aa" * 32
    risk_score = 12
    verdict = "PASSED"

    proof = web3_escrow_adapter.sign_attestation(
        job_id=job_id,
        deliverable_hash=deliverable_hash,
        risk_score=risk_score,
        verdict=verdict,
        validity_duration_seconds=3600
    )

    assert proof["jobId"] == job_id
    assert proof["riskScore"] == 12
    assert proof["verdict"] == "PASSED"
    assert proof["oracleSigner"] == web3_escrow_adapter.oracle_address
    assert proof["v"] in (27, 28)
    assert proof["r"].startswith("0x") and len(proof["r"]) == 66
    assert proof["s"].startswith("0x") and len(proof["s"]) == 66

    # Verify signature
    res = web3_escrow_adapter.verify_attestation(proof)
    assert res["is_valid"] is True
    assert res["is_signer_match"] is True
    assert res["is_expired"] is False
    assert res["is_acceptable_risk"] is True
    assert "COMPLETE_JOB" in res["action_recommendation"]


def test_web3_escrow_adapter_slashing_verdict():
    """Verify that BLOCKED verdict or high risk leads to SLASH_JOB recommendation."""
    job_id = 102
    deliverable_hash = "0x" + "bb" * 32
    risk_score = 88
    verdict = "BLOCKED"

    proof = web3_escrow_adapter.sign_attestation(
        job_id=job_id,
        deliverable_hash=deliverable_hash,
        risk_score=risk_score,
        verdict=verdict,
        validity_duration_seconds=3600
    )

    res = web3_escrow_adapter.verify_attestation(proof)
    assert res["is_valid"] is True
    assert res["is_signer_match"] is True
    assert res["is_acceptable_risk"] is False
    assert "SLASH_JOB" in res["action_recommendation"]


def test_web3_escrow_tampered_signature():
    """Verify that tampering with deliverableHash invalidates the EIP-712 signature."""
    job_id = 103
    proof = web3_escrow_adapter.sign_attestation(
        job_id=job_id,
        deliverable_hash="0x" + "cc" * 32,
        risk_score=5,
        verdict="PASSED"
    )

    # Tamper with the hash
    tampered_proof = dict(proof)
    tampered_proof["deliverableHash"] = "0x" + "dd" * 32

    res = web3_escrow_adapter.verify_attestation(tampered_proof)
    assert res["is_valid"] is False
    assert res["is_signer_match"] is False
    assert "REJECT" in res["action_recommendation"]


def test_agent_escrow_manager_onchain_attestation_flow():
    """Verify full lifecycle from escrow creation to onchain EIP-712 attestation issuance."""
    create_req = EscrowCreateRequest(
        amount_usdc=2500.0,
        chain="Base (Low Gas $0.01)",
        buyer_agent_id="AGENT-BUYER-TEST",
        buyer_wallet="0x1111111111111111111111111111111111111111",
        seller_agent_id="AGENT-SELLER-TEST",
        seller_wallet="0x2222222222222222222222222222222222222222",
        hs_code="1511.10.00",
        commodity_description="Crude Palm Oil Tanker Cargo",
        declared_net_mass_kg=40000.0,
        expiry_hours=48
    )
    escrow = AgentEscrowManager.create_escrow(create_req)
    escrow_id = escrow.escrow_id

    # Fund
    fund_req = EscrowFundRequest(
        escrow_id=escrow_id,
        tx_hash="0x" + "33" * 32
    )
    AgentEscrowManager.fund_escrow(fund_req)

    # Release by compliance
    rel_req = EscrowReleaseByComplianceRequest(
        escrow_id=escrow_id,
        customs_declaration_code="EU-SWEC-CLEARED-998877",
        dds_reference_id="DDS-EUDR-2026-VALIDSIG"
    )
    AgentEscrowManager.release_by_compliance(rel_req)

    # Issue On-Chain Attestation for AgentEscrow.sol (jobId=55)
    attestation = AgentEscrowManager.issue_onchain_attestation(
        escrow_id=escrow_id,
        job_id=55,
        risk_score=10
    )

    assert attestation["jobId"] == 55
    assert attestation["verdict"] == "PASSED"
    assert attestation["riskScore"] == 10
    assert attestation["oracleSigner"] == web3_escrow_adapter.oracle_address

    # Verify
    verify_res = AgentEscrowManager.verify_onchain_attestation(attestation)
    assert verify_res["is_valid"] is True
    assert "COMPLETE_JOB" in verify_res["action_recommendation"]


def test_rest_api_onchain_attestation_endpoints():
    """Verify REST API endpoints for issuing and verifying on-chain EIP-712 attestations."""
    # 1. Create an escrow via REST
    resp_create = client.post(
        "/api/v1/payment/escrow/create",
        json={
            "amount_usdc": 1000.0,
            "chain": "Base (Low Gas $0.01)",
            "buyer_agent_id": "REST-BUYER-AGENT",
            "buyer_wallet": "0x3333333333333333333333333333333333333333",
            "seller_agent_id": "REST-SELLER-AGENT",
            "seller_wallet": "0x4444444444444444444444444444444444444444",
            "hs_code": "1801.00.00",
            "commodity_description": "Cocoa Beans",
            "declared_net_mass_kg": 5000.0
        }
    )
    assert resp_create.status_code in (200, 201)
    escrow_id = resp_create.json()["escrow_id"]

    # 2. Fund via REST
    resp_fund = client.post(
        "/api/v1/payment/escrow/fund",
        json={"escrow_id": escrow_id, "tx_hash": "0x" + "44" * 32}
    )
    assert resp_fund.status_code in (200, 201)

    # 3. Issue on-chain attestation via REST
    resp_attest = client.post(
        "/api/v1/payment/escrow/onchain/attestation",
        json={
            "escrow_id": escrow_id,
            "job_id": 77,
            "risk_score": 15,
            "validity_days": 5
        }
    )
    assert resp_attest.status_code in (200, 201)
    attest_data = resp_attest.json()
    assert attest_data["jobId"] == 77
    assert attest_data["verdict"] == "PASSED"
    assert "v" in attest_data and "r" in attest_data and "s" in attest_data

    # 4. Verify on-chain attestation via REST
    resp_verify = client.post(
        "/api/v1/payment/escrow/onchain/verify",
        json={"attestation": attest_data}
    )
    assert resp_verify.status_code in (200, 201)
    verify_data = resp_verify.json()
    assert verify_data["is_valid"] is True
    assert verify_data["is_signer_match"] is True
    assert "COMPLETE_JOB" in verify_data["action_recommendation"]


@pytest.mark.asyncio
async def test_mcp_tools_onchain_attestation():
    """Verify autonomous agent MCP tools for issuing and verifying EIP-712 attestations."""
    # Create escrow
    escrow = AgentEscrowManager.create_escrow(
        EscrowCreateRequest(
            amount_usdc=500.0,
            chain="Polygon (PoS)",
            buyer_agent_id="MCP-BUYER",
            buyer_wallet="0x5555555555555555555555555555555555555555",
            seller_agent_id="MCP-SELLER",
            seller_wallet="0x6666666666666666666666666666666666666666",
            hs_code="4407.11.00",
            commodity_description="Sawn Timber",
            declared_net_mass_kg=20000.0
        )
    )

    # Fund escrow
    AgentEscrowManager.fund_escrow(
        EscrowFundRequest(
            escrow_id=escrow.escrow_id,
            tx_hash="0x" + "55" * 32
        )
    )

    # Execute tool: eudr_issue_eip712_attestation
    res_issue = await AgentToolsRegistry.execute_tool(
        "eudr_issue_eip712_attestation",
        {
            "escrow_id": escrow.escrow_id,
            "job_id": 888,
            "risk_score": 18
        }
    )
    assert res_issue["status"] == "ATTESTATION_ISSUED"
    assert res_issue["jobId"] == 888
    assert "agent_summary" in res_issue

    # Execute tool: eudr_verify_eip712_attestation
    res_verify = await AgentToolsRegistry.execute_tool(
        "eudr_verify_eip712_attestation",
        {"attestation": res_issue}
    )
    assert res_verify["is_valid"] is True
    assert "COMPLETE_JOB" in res_verify["action_recommendation"]
    assert "agent_summary" in res_verify
