"""
Health, Liveness, and Inter-Agent Mesh Diagnostic Endpoints.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Response
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get(f"{settings.API_V1_PREFIX}/health")
@router.get(f"{settings.API_V1_PREFIX}/eudr/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "eudr_cutoff_date": str(settings.EUDR_CUTOFF_DATE),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(f"{settings.API_V1_PREFIX}/eudr/mesh/status", tags=["Inter-Agent Mesh"])
async def get_inter_agent_mesh_status():
    """
    Returns live network discovery and status of the 4 autonomous agent services
    connected via Model Context Protocol (MCP) on MetaMask Polygon Mainnet.
    """
    from app.modules.inter_agent_mesh import InterAgentMeshCoordinator
    return InterAgentMeshCoordinator.get_mesh_status()


@router.get(f"{settings.API_V1_PREFIX}/eudr/mesh/security-gate/diagnostics", tags=["Inter-Agent Mesh"])
async def check_security_gate_integration():
    """
    Performs live end-to-end diagnostic probes against agent-security-gate-x402:
    - Subsystem health heartbeat
    - Sub-5ms cognitive firewall (MCP verify_agent_output)
    - EVM EIP-712 EUDR truth oracle (Domain 3)
    - Solana Ed25519 oracle attestation
    """
    from app.modules.inter_agent_mesh import InterAgentMeshCoordinator
    return await InterAgentMeshCoordinator.check_security_gate_diagnostics()


@router.get(
    "/metrics",
    tags=["Prometheus APM Telemetry"],
    summary="Prometheus APM Telemetry & Metrics (OpenMetrics text/plain)"
)
async def get_prometheus_metrics():
    """
    Exposes real-time agent metrics, escrow TVL, slashing history,
    threat blocks, and satellite inspection counters in standard Prometheus format.
    """
    from app.modules.prometheus_metrics import metrics_collector
    return Response(
        content=metrics_collector.render_prometheus_text(),
        media_type="text/plain; version=0.0.4"
    )

