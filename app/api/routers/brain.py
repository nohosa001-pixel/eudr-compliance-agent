"""
ElizaOS Brain & Security Gate x402 Hardened Cognitive Endpoints.
"""
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.modules.elizaos_brain_security_bridge import (
    ElizaOSBrainSecurityBridge,
    BrainPerceptionRequest,
    BrainExecutionRequest
)

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/brain",
    tags=["ElizaOS Brain & Security Gate Architecture"]
)


@router.post(
    "/perceive",
    summary="Inbound Perception Shield: Verify stimulus and prevent memory poisoning"
)
async def perceive_stimulus(payload: BrainPerceptionRequest):
    """
    Sub-millisecond Security Gate interceptor for all inputs entering the ElizaOS Brain.
    Filters prompt injections, AST vulnerabilities, and financial diversion attacks.
    """
    return ElizaOSBrainSecurityBridge.perceive_and_filter(payload)


@router.post(
    "/reason-and-act",
    summary="Execute hardened compliance decision with episodic memory & capital air-gap"
)
async def reason_and_execute(payload: BrainExecutionRequest):
    """
    Autonomous decision pipeline combining:
    - Episodic port clearance heuristics
    - Agronomic yield ceiling NLI fact-checking
    - EU AI Act Art. 50 watermark provenance
    - Ephemeral sub-account ($1~$5 micro-budget) key isolation
    - EIP-712 truth attestation & RWA yield accrual
    """
    res = ElizaOSBrainSecurityBridge.evaluate_and_execute_action(payload)
    if not res.get("is_executable"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res)
    return res


@router.get(
    "/status",
    summary="Get synchronized cognitive status, episodic depth, and immune defense metrics"
)
async def get_brain_security_state():
    """
    Returns the real-time health, readiness score, episodic records, and neutralized threat counts.
    """
    return ElizaOSBrainSecurityBridge.get_brain_security_state()
