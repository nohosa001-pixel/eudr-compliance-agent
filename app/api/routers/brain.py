"""
ElizaOS Brain & Security Gate x402 Hardened Cognitive Endpoints.
"""
from fastapi import APIRouter, HTTPException, status, Response
from app.core.config import settings
from typing import Dict, Any, Optional
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


@router.post(
    "/swarm-simulate",
    summary="Run Phase 4 Swarm Sandbox multi-agent simulation"
)
async def run_swarm_simulation(num_simulations: int = 10, include_news_disruptions: bool = True):
    """
    Executes a multi-agent simulation across 5 agent roles (Producer, Trader, Operator, Customs, Bank)
    with RWA yield locks and real-time news shocks.
    """
    return ElizaOSBrainSecurityBridge.run_swarm_simulation_batch(
        num_simulations=num_simulations,
        include_news_disruptions=include_news_disruptions
    )


@router.post(
    "/rfi",
    summary="Handle Customs Request for Information (RFI) autonomously"
)
async def handle_customs_rfi(job_id: str, port_code: str = "NLRTM", rfi_type: str = "GEOLOCATION_DISCREPANCY"):
    """
    Autonomously resolves European port customs inquiries and calibrates port heuristics.
    """
    return ElizaOSBrainSecurityBridge.handle_customs_rfi(
        job_id=job_id,
        port_code=port_code,
        rfi_type=rfi_type
    )


@router.get(
    "/metrics",
    summary="Prometheus / OpenTelemetry Metrics Endpoint for Grafana Monitoring",
    response_class=Response
)
async def get_prometheus_metrics():
    """
    Exposes real-time ElizaOS Brain metrics in standard Prometheus exposition text (v0.0.4)
    including readiness score, memory counts, neutralized attacks, and port inspection frequencies.
    """
    content = ElizaOSBrainSecurityBridge.export_prometheus_metrics()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.post(
    "/satellite-verify",
    summary="Ground farm parcel with Live Copernicus Sentinel-2 CDSE satellite telemetry"
)
async def verify_satellite_parcel(
    parcel_id: str = "PRC-BR-MT-001",
    commodity: str = "soya",
    geojson_polygon: Optional[Dict[str, Any]] = None
):
    """
    Queries Copernicus Sentinel-2 L2A time-series trajectory (NDVI/NDMI) and grounds findings
    into ElizaOS Brain spatial reasoning working memory.
    """
    default_geom = {
        "type": "Polygon",
        "coordinates": [[
            [-55.5123, -12.4567],
            [-55.5023, -12.4567],
            [-55.5023, -12.4467],
            [-55.5123, -12.4467],
            [-55.5123, -12.4567]
        ]]
    }
    geom = geojson_polygon or default_geom
    return ElizaOSBrainSecurityBridge.verify_and_learn_satellite_trajectory(
        parcel_id=parcel_id,
        geometry=geom,
        commodity=commodity
    )


@router.post(
    "/checkpoint/save",
    summary="Persist brain checkpoint with timestamped audit snapshot"
)
async def save_brain_checkpoint_with_snapshot(archive_snapshot: bool = True):
    """
    Persists cognitive checkpoint and archives a timestamped regulatory audit trail snapshot.
    """
    return ElizaOSBrainSecurityBridge.save_checkpoint(archive_snapshot=archive_snapshot)


