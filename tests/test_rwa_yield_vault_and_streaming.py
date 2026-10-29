"""Comprehensive Test Suite for Phase 5 Sovereign Yield Vault & Merkle Micro-Streaming
====================================================================================
Validates:
1. Sovereign RWA Treasury Yield Vault deposit, accrual, and redemption (USDY / BUIDL).
2. HTTP 402 & ERC-7683 Merkle micro-streaming channel lifecycle.
3. UniversalEscrowClient Phase 4 & Phase 5 helper methods.
4. FastAPI REST endpoints for RWA vaults and micro-streaming channels.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.rwa_yield_vault_manager import (
    SovereignYieldVaultManager,
    RWAAssetConfig
)
from app.modules.universal_escrow_client import universal_escrow_client

client = TestClient(app)


def test_rwa_vault_deposit_and_accrual():
    """Verify escrow principal earns tokenized US Treasury yield (USDY @ 5.20% APY)."""
    job_id = "JOB-RWA-TEST-001"
    principal = 100000.0  # $100,000 USDC

    dep = SovereignYieldVaultManager.deposit_escrow_to_rwa(
        job_id=job_id,
        principal_amount_usdc=principal,
        rwa_asset="USDY",
        lock_days_estimated=30
    )
    assert dep["success"] is True
    assert dep["principal_usdc"] == principal
    assert dep["annual_apy_percent"] == 5.20
    assert dep["status"] == "ACCRUING"
    assert dep["projected_yield_usdc"] > 400.0  # Approx $427.40 for 30 days

    # Simulate 30 days of maritime transit
    accrual = SovereignYieldVaultManager.calculate_accrued_yield(job_id=job_id, elapsed_days=30.0)
    assert accrual["success"] is True
    assert accrual["days_accrued"] == 30.0
    assert accrual["accrued_yield_usdc"] > 420.0
    assert accrual["total_withdrawable_usdc"] > 100420.0


def test_rwa_vault_redemption_upon_customs_clearance():
    """Verify principal + sovereign yield redemption upon customs green lane clearance."""
    job_id = "JOB-RWA-REDEEM-002"
    principal = 50000.0
    recipient = "0x9999999999999999999999999999999999999999"

    SovereignYieldVaultManager.deposit_escrow_to_rwa(
        job_id=job_id,
        principal_amount_usdc=principal,
        rwa_asset="BUIDL",
        lock_days_estimated=20
    )

    redeem_res = SovereignYieldVaultManager.redeem_and_claim_yield(
        job_id=job_id,
        recipient_wallet=recipient,
        elapsed_days=20.0
    )
    assert redeem_res["success"] is True
    assert redeem_res["status"] == "REDEEMED"
    assert redeem_res["principal_returned_usdc"] == principal
    assert redeem_res["sovereign_yield_remitted_usdc"] > 140.0
    assert redeem_res["redemption_tx_hash"].startswith("0x")

    # Double redemption attempt should fail
    double_res = SovereignYieldVaultManager.redeem_and_claim_yield(
        job_id=job_id,
        recipient_wallet=recipient
    )
    assert double_res["success"] is False
    assert double_res["error"] == "ALREADY_REDEEMED"


def test_merkle_micro_streaming_channel_lifecycle():
    """Verify gasless ERC-7683 micro-streaming channel for high-frequency queries."""
    ch = SovereignYieldVaultManager.open_streaming_channel(
        sender_agent_id="agent_satellite_consumer",
        receiver_agent_id="agent_sentinel_provider",
        total_deposit_usdc=5.0
    )
    assert ch["status"] == "OPEN"
    channel_id = ch["channel_id"]

    # 1. First micro-tick (1 tile query = $0.005)
    tick1 = SovereignYieldVaultManager.record_stream_tick(
        channel_id=channel_id,
        units_consumed=1,
        unit_price_usdc=0.005,
        payload_label="Sentinel-2 10m RGB tile"
    )
    assert tick1["success"] is True
    assert tick1["debited_usdc"] == 0.005
    assert tick1["remaining_usdc"] == 4.995
    assert tick1["ticks_count"] == 1
    assert tick1["merkle_receipt"].startswith("0x")

    # 2. Second batch micro-tick (10 tiles = $0.05)
    tick2 = SovereignYieldVaultManager.record_stream_tick(
        channel_id=channel_id,
        units_consumed=10,
        unit_price_usdc=0.005,
        payload_label="Sentinel-1 SAR Radar batch"
    )
    assert tick2["success"] is True
    assert tick2["debited_usdc"] == 0.05
    assert tick2["remaining_usdc"] == 4.945
    assert tick2["ticks_count"] == 2

    # 3. Close and settle channel
    close_res = SovereignYieldVaultManager.close_streaming_channel(channel_id=channel_id)
    assert close_res["success"] is True
    assert close_res["status"] == "SETTLED_AND_CLOSED"
    assert close_res["total_remitted_to_receiver_usdc"] == 0.055
    assert close_res["refunded_to_sender_usdc"] == 4.945


def test_universal_escrow_client_phase5_integration():
    """Verify UniversalEscrowClient methods for Phase 4 & Phase 5."""
    # Phase 4 Ephemeral Sub-account
    sub = universal_escrow_client.delegate_ephemeral_sub_account(
        parent_agent_id="universal_parent_001",
        budget_cap_usdc=3.50
    )
    assert sub["status"] == "ACTIVE"
    assert sub["budget_cap_usdc"] == 3.50

    charge = universal_escrow_client.charge_ephemeral_sub_account(
        session_id=sub["session_id"],
        amount_usdc=0.75,
        purpose="Customs verification check"
    )
    assert charge["success"] is True
    assert charge["remaining_usdc"] == 2.75

    # Phase 5 Sovereign Yield Vault
    vault_job = "JOB-CLIENT-INTEG-003"
    dep = universal_escrow_client.deposit_sovereign_yield_vault(
        job_id=vault_job,
        principal_amount_usdc=25000.0,
        rwa_asset="USDY",
        lock_days_estimated=15
    )
    assert dep["success"] is True

    calc = universal_escrow_client.calculate_sovereign_yield(job_id=vault_job, elapsed_days=15.0)
    assert calc["success"] is True
    assert calc["accrued_yield_usdc"] > 50.0

    redeem = universal_escrow_client.redeem_sovereign_yield(
        job_id=vault_job,
        recipient_wallet="0x1234567890123456789012345678901234567890",
        elapsed_days=15.0
    )
    assert redeem["success"] is True
    assert redeem["status"] == "REDEEMED"


def test_api_rwa_vault_and_streaming_endpoints():
    """Test REST API endpoints for RWA vaults and micro-streaming."""
    # 1. Deposit
    job_id = "JOB-API-VAULT-004"
    resp_dep = client.post(
        "/api/v1/payment/escrow/rwa-vault/deposit",
        json={
            "job_id": job_id,
            "principal_amount_usdc": 40000.0,
            "rwa_asset": "USDY",
            "lock_days_estimated": 25
        }
    )
    assert resp_dep.status_code == 200
    assert resp_dep.json()["success"] is True

    # 2. Query position
    resp_pos = client.get(f"/api/v1/payment/escrow/rwa-vault/{job_id}")
    assert resp_pos.status_code == 200
    assert resp_pos.json()["status"] == "ACCRUING"

    # 3. Accrue calculation
    resp_acc = client.post(
        "/api/v1/payment/escrow/rwa-vault/accrue",
        json={"job_id": job_id, "elapsed_days": 25.0}
    )
    assert resp_acc.status_code == 200
    assert resp_acc.json()["accrued_yield_usdc"] > 140.0

    # 4. Redeem
    resp_red = client.post(
        "/api/v1/payment/escrow/rwa-vault/redeem",
        json={
            "job_id": job_id,
            "recipient_wallet": "0xABCDEF1234567890ABCDEF1234567890ABCDEF12",
            "elapsed_days": 25.0
        }
    )
    assert resp_red.status_code == 200
    assert resp_red.json()["status"] == "REDEEMED"

    # 5. Streaming channel open, tick, close
    resp_open = client.post(
        "/api/v1/payment/escrow/streaming/open",
        json={
            "sender_agent_id": "buyer_agent_api",
            "receiver_agent_id": "seller_agent_api",
            "total_deposit_usdc": 2.0
        }
    )
    assert resp_open.status_code == 200
    ch_id = resp_open.json()["channel_id"]

    resp_tick = client.post(
        "/api/v1/payment/escrow/streaming/tick",
        json={
            "channel_id": ch_id,
            "units_consumed": 2,
            "unit_price_usdc": 0.005,
            "payload_label": "High-res Sentinel NDVI"
        }
    )
    assert resp_tick.status_code == 200
    assert resp_tick.json()["debited_usdc"] == 0.01

    resp_close = client.post(
        "/api/v1/payment/escrow/streaming/close",
        json={"channel_id": ch_id}
    )
    assert resp_close.status_code == 200
    assert resp_close.json()["status"] == "SETTLED_AND_CLOSED"
