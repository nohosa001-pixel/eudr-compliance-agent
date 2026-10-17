"""
EUDR Article 31 5-Year Immutable WORM Audit Vault and Forest Degradation Detection Endpoints.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.modules.audit_vault_manager import AuditVaultManager
from app.modules.forest_degradation_detector import ForestDegradationDetector
from app.schemas import ProductionPlotInput

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/compliance",
    tags=["EUDR Article 31 Audit Vault"]
)


class SealVaultRequest(BaseModel):
    dds_reference_id: str
    verification_code: str
    operator_eori: str
    commodity_code: str
    net_mass_kg: float
    evaluation_payload: Dict[str, Any]
    traces_xml_str: Optional[str] = None
    customs_cert_html: Optional[str] = None
    customs_box44_code: Optional[str] = None


class DegradationAssessRequest(BaseModel):
    plots: List[ProductionPlotInput]
    commodity: str = Field("WOOD", description="Regulated commodity (especially timber/wood)")


@router.post(
    "/audit-vault/seal",
    summary="Seal compliance evidence into Article 31 immutable WORM vault with SHA-256 Merkle anchor"
)
async def seal_audit_vault(req: SealVaultRequest):
    record = AuditVaultManager.seal_audit_evidence(
        dds_reference_id=req.dds_reference_id,
        verification_code=req.verification_code,
        operator_eori=req.operator_eori,
        commodity_code=req.commodity_code,
        net_mass_kg=req.net_mass_kg,
        evaluation_payload=req.evaluation_payload,
        traces_xml_str=req.traces_xml_str,
        customs_cert_html=req.customs_cert_html,
        customs_box44_code=req.customs_box44_code
    )
    return record


@router.get(
    "/audit-vault/{dds_reference_id}",
    summary="Query sealed audit vault record and verify cryptographic Merkle integrity"
)
async def get_audit_vault_record(dds_reference_id: str):
    record = AuditVaultManager.get_vault_record(dds_reference_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sealed audit vault record found for reference '{dds_reference_id}'"
        )
    integrity = AuditVaultManager.verify_vault_integrity(dds_reference_id)
    return {
        "record": record,
        "integrity_verification": integrity
    }


@router.get(
    "/audit-vault/{dds_reference_id}/download",
    summary="Download full tamper-evident statutory audit evidence zip bundle for customs authorities"
)
async def download_audit_vault_archive(dds_reference_id: str):
    archive_bytes = AuditVaultManager.retrieve_archive_bytes(dds_reference_id)
    if not archive_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archive file for reference '{dds_reference_id}' not found in vault."
        )
    safe_id = dds_reference_id.replace("/", "_").replace(":", "_")
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=EUDR_ART31_VAULT_{safe_id}.zip"
        }
    )


@router.post(
    "/forest-degradation/assess",
    tags=["Forest Degradation Engine (EUDR Art. 2(5))"],
    summary="Detect post-2020 structural conversion of primary forests into commercial plantations"
)
async def assess_forest_degradation(req: DegradationAssessRequest):
    return ForestDegradationDetector.evaluate_batch_degradation(
        plots=req.plots,
        commodity=req.commodity
    )
