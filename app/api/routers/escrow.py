"""
Agent Escrow, Web3 Settlement, and On-chain EIP-712 Attestation Endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

import importlib
try:
    _sa_orm = importlib.import_module("sqlalchemy.orm")
    Session = getattr(_sa_orm, "Session")
except Exception:
    Session = Any  # type: ignore

from app.core.config import settings
from app.db.session import get_db
from app.modules.agent_escrow_manager import AgentEscrowManager
from app.schemas import (
    EscrowCreateRequest,
    EscrowFundRequest,
    EscrowReleaseByComplianceRequest,
    EscrowDisputeArbitrateRequest,
    EscrowAgreementResponse,
    MilestoneEscrowCreateRequest,
    EscrowMilestoneReleaseRequest,
    EscrowMilestoneReleaseResponse,
    EscrowAutoSlashRequest,
    OnchainAttestationIssueRequest,
    OnchainAttestationResponse,
    OnchainAttestationVerifyRequest,
    OnchainAttestationVerifyResponse,
)

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/payment/escrow",
    tags=["Agent Escrow & Web3 Settlement"]
)


@router.post(
    "/create",
    response_model=EscrowAgreementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new B2B trade Smart Escrow agreement locking USDC in payment vaults"
)
async def create_agent_escrow(
    payload: EscrowCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Creates an immutable Smart Escrow agreement between autonomous trading agents.
    Locks USDC in multi-chain payment vaults until EUDR compliance is proven.
    """
    try:
        return AgentEscrowManager.create_escrow(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/fund",
    response_model=EscrowAgreementResponse,
    summary="Confirm on-chain blockchain funding for a Smart Escrow agreement"
)
async def fund_agent_escrow(
    payload: EscrowFundRequest,
    db: Session = Depends(get_db)
):
    """
    Confirms on-chain USDC transfer to the payment vault and locks the escrow.
    """
    try:
        return AgentEscrowManager.fund_escrow(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/release",
    response_model=EscrowAgreementResponse,
    summary="Conditionally release locked escrow funds to seller upon verified EU customs clearance"
)
@router.post(
    "/release-by-compliance",
    response_model=EscrowAgreementResponse,
    include_in_schema=False
)
async def release_agent_escrow(
    payload: EscrowReleaseByComplianceRequest,
    db: Session = Depends(get_db)
):
    """
    Releases escrow funds to seller agent upon EU Single Window customs clearance
    (EU-SWEC-CLEARED-*) and satellite deforestation verification.
    """
    try:
        return AgentEscrowManager.release_by_compliance(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/arbitrate",
    response_model=EscrowAgreementResponse,
    summary="Execute deterministic autonomous dispute arbitration using Copernicus satellite telemetry"
)
@router.post(
    "/dispute-arbitrate",
    response_model=EscrowAgreementResponse,
    include_in_schema=False
)
async def arbitrate_agent_escrow(
    payload: EscrowDisputeArbitrateRequest,
    db: Session = Depends(get_db)
):
    """
    Deterministically arbitrates commercial disputes using Copernicus Sentinel-1/2 radar:
    - Deforestation confirmed -> 100% refund to Buyer Agent.
    - Deforestation-free -> 100% release to Seller Agent.
    """
    try:
        return AgentEscrowManager.arbitrate_dispute(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get(
    "/{escrow_id}",
    response_model=EscrowAgreementResponse,
    summary="Query status, vault address, and cryptographic proof of an existing escrow agreement"
)
async def get_agent_escrow(
    escrow_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves full details of a Smart Escrow agreement by ID.
    """
    try:
        return AgentEscrowManager.get_escrow(escrow_id, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "/milestone/create",
    response_model=EscrowAgreementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a 3-Stage Milestone Conditional Escrow with First-Mile split payouts"
)
async def create_milestone_agent_escrow(
    payload: MilestoneEscrowCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a 3-stage milestone conditional escrow agreement:
    - Milestone 1: Pre-shipment Polygon & Satellite Verification (Default 30%)
    - Milestone 2: EU TRACES-NT DDS Issuance (Default 40%)
    - Milestone 3: EU Customs Green Lane Clearance (Default 30%)
    Supports First-Mile multi-party split payouts to smallholder cooperatives and mills.
    """
    try:
        return AgentEscrowManager.create_milestone_escrow(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/milestone/release",
    response_model=EscrowMilestoneReleaseResponse,
    summary="Release a specific milestone in a 3-stage conditional escrow"
)
async def release_milestone_agent_escrow(
    payload: EscrowMilestoneReleaseRequest,
    db: Session = Depends(get_db)
):
    """
    Releases a specific milestone (1, 2, or 3) upon compliance verification:
    - Milestone 1: Satellite zero-deforestation check
    - Milestone 2: Compliant DDS Reference check
    - Milestone 3: EU Customs Green Lane code check
    Issues EIP-712 cryptographic attestation and executes First-Mile split transfers.
    """
    try:
        return AgentEscrowManager.release_milestone(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/auto-slash",
    response_model=EscrowAgreementResponse,
    summary="Execute autonomous on-chain slashing & buyer refund for failed/disputed escrows"
)
async def auto_slash_disputed_escrow(
    payload: EscrowAutoSlashRequest,
    db: Session = Depends(get_db)
):
    """
    Executes autonomous on-chain slashing for escrows with verified deforestation violations:
    Issues EIP-712 BLOCKED attestation (compatible with AgentEscrow.sol slashJob),
    confiscates seller stake, and instantly refunds 100% of remaining locked capital to Buyer.
    """
    try:
        return AgentEscrowManager.auto_slash_disputed_escrow(payload, db_session=db)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/onchain/attestation",
    response_model=OnchainAttestationResponse,
    summary="Issue official EIP-712 cryptographic Oracle Attestation for submission to AgentEscrow.sol"
)
async def issue_onchain_attestation(
    payload: OnchainAttestationIssueRequest,
    db: Session = Depends(get_db)
):
    """
    Issues an EIP-712 signed Attestation (jobId, deliverableHash, riskScore, verdict, expiresAt, v, r, s)
    from the EUDR Compliance Agent as the designated on-chain Oracle Signer.
    Can be directly submitted to AgentEscrow.sol (completeJob or slashJob).
    """
    try:
        proof = AgentEscrowManager.issue_onchain_attestation(
            escrow_id=payload.escrow_id,
            job_id=payload.job_id,
            deliverable_hash=payload.deliverable_hash,
            risk_score=payload.risk_score,
            validity_days=payload.validity_days or 7,
            db_session=db
        )
        return OnchainAttestationResponse(
            **proof,
            message="EIP-712 Oracle Attestation successfully signed by EUDR Compliance Oracle."
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/onchain/verify",
    response_model=OnchainAttestationVerifyResponse,
    summary="Verify an on-chain EIP-712 attestation proof against official EUDR Oracle key"
)
async def verify_onchain_attestation(
    payload: OnchainAttestationVerifyRequest
):
    """
    Cryptographically verifies an EIP-712 attestation against the EUDR Oracle public address
    and assesses riskScore and expiration status.
    """
    try:
        res = AgentEscrowManager.verify_onchain_attestation(payload.attestation)
        return OnchainAttestationVerifyResponse(
            **res,
            message=f"Oracle verification complete. Recommended action: {res['action_recommendation']}"
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


# =============================================================================
# Phase 5: Sovereign RWA Treasury Yield Vault & HTTP 402 Merkle Streaming
# =============================================================================

@router.post(
    "/rwa-vault/deposit",
    summary="Deposit transit-locked escrow capital into tokenized US Treasury RWA (USDY/BUIDL)"
)
async def deposit_escrow_to_rwa_vault(payload: dict):
    """
    Deposits locked escrow capital into a yield-bearing US Treasury RWA vault
    during maritime shipping & customs clearance (14~45 days).
    """
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    job_id = payload.get("job_id")
    if not job_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_id is required")
    principal = float(payload.get("principal_amount_usdc", 1000.0))
    rwa_asset = payload.get("rwa_asset", "USDY")
    lock_days = int(payload.get("lock_days_estimated", 30))
    owner = payload.get("owner_wallet")

    res = SovereignYieldVaultManager.deposit_escrow_to_rwa(
        job_id=job_id,
        principal_amount_usdc=principal,
        rwa_asset=rwa_asset,
        lock_days_estimated=lock_days,
        owner_wallet=owner
    )
    return res


@router.post(
    "/rwa-vault/accrue",
    summary="Calculate accrued RWA sovereign yield on active escrow position"
)
async def calculate_rwa_vault_accrual(payload: dict):
    """
    Computes real-time accrued interest on a yield-bearing escrow deposit.
    """
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    job_id = payload.get("job_id")
    if not job_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_id is required")
    elapsed_days = payload.get("elapsed_days")
    res = SovereignYieldVaultManager.calculate_accrued_yield(
        job_id=job_id,
        elapsed_days=float(elapsed_days) if elapsed_days is not None else None
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.get("message"))
    return res


@router.post(
    "/rwa-vault/redeem",
    summary="Redeem RWA principal and claim accumulated sovereign yield upon customs clearance"
)
async def redeem_rwa_vault_position(payload: dict):
    """
    Redeems RWA principal and transfers accumulated sovereign treasury yield upon EU customs green lane clearance.
    """
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    job_id = payload.get("job_id")
    recipient = payload.get("recipient_wallet")
    if not job_id or not recipient:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_id and recipient_wallet are required")
    elapsed_days = payload.get("elapsed_days")

    res = SovereignYieldVaultManager.redeem_and_claim_yield(
        job_id=job_id,
        recipient_wallet=recipient,
        elapsed_days=float(elapsed_days) if elapsed_days is not None else None
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("message"))
    return res


@router.get(
    "/rwa-vault/{job_id}",
    summary="Get active RWA yield vault position for a specific escrow job"
)
async def get_rwa_vault_position(job_id: str):
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    pos = SovereignYieldVaultManager.get_vault_position(job_id)
    if not pos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No RWA vault position found for {job_id}")
    return pos


@router.post(
    "/streaming/open",
    summary="Open gasless HTTP 402 & ERC-7683 Merkle micro-streaming channel"
)
async def open_micro_streaming_channel(payload: dict):
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    sender = payload.get("sender_agent_id", "agent_sender")
    receiver = payload.get("receiver_agent_id", "agent_receiver")
    deposit = float(payload.get("total_deposit_usdc", 10.0))
    ttl = int(payload.get("channel_ttl_seconds", 86400))
    return SovereignYieldVaultManager.open_streaming_channel(
        sender_agent_id=sender,
        receiver_agent_id=receiver,
        total_deposit_usdc=deposit,
        channel_ttl_seconds=ttl
    )


@router.post(
    "/streaming/tick",
    summary="Record high-frequency micro-payment tick against active streaming channel"
)
async def record_streaming_tick(payload: dict):
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    channel_id = payload.get("channel_id")
    if not channel_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="channel_id is required")
    units = int(payload.get("units_consumed", 1))
    price = float(payload.get("unit_price_usdc", 0.005))
    label = payload.get("payload_label", "Satellite tile query")
    res = SovereignYieldVaultManager.record_stream_tick(
        channel_id=channel_id,
        units_consumed=units,
        unit_price_usdc=price,
        payload_label=label
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error"))
    return res


@router.post(
    "/streaming/close",
    summary="Close streaming channel and generate cryptographic settlement summary"
)
async def close_streaming_channel(payload: dict):
    from app.modules.rwa_yield_vault_manager import SovereignYieldVaultManager
    channel_id = payload.get("channel_id")
    if not channel_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="channel_id is required")
    res = SovereignYieldVaultManager.close_streaming_channel(channel_id=channel_id)
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.get("error"))
    return res
