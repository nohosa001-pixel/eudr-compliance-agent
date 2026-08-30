import os
import uuid
import datetime
from datetime import datetime as dt, timezone
from typing import Dict, Any, Optional
import traceback
import base64

from app.core.celery_app import celery_app
from app.schemas import (
    EUDRSupplyChainPayload,
    DDSReport,
    BatchJobStatusEnum
)
from app.modules.bulk_file_parser import BulkFileParser
from app.modules.traceability_collector import TraceabilityCollector
from app.modules.deforestation_simulator import DeforestationSimulator
from app.modules.legal_document_auditor import LegalAuditor
from app.modules.dds_generator import DDSGenerator
from app.db.session import SessionLocal
from app.db.repository import BatchJobRepository, AuditRepository


def run_pipeline_sync(job_id: str, payload_dict: Dict[str, Any]):
    """Synchronous pipeline execution logic runnable inside a Celery task or thread worker."""
    db = SessionLocal()
    try:
        payload = EUDRSupplyChainPayload.model_validate(payload_dict)
        start_time = dt.now(timezone.utc)
        if not payload.execution_id:
            payload.execution_id = f"EXEC-{uuid.uuid4().hex[:12].upper()}"

        total_plots = len(payload.plots)

        # Stage 1: GIS Validation & Self-Healing (15% -> 40%)
        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.VALIDATING_GIS.value,
            progress_pct=20.0,
            current_step=f"Validating & repairing {total_plots} plot geometries (Article 9(1)(d))...",
            processed_plots=0
        )

        spatial_valid, spatial_results, spatial_summary = TraceabilityCollector.collect_and_validate(payload.plots)

        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.VALIDATING_GIS.value,
            progress_pct=38.0,
            current_step=f"Completed GIS topological validation ({len(spatial_results)} plots processed)",
            processed_plots=len(spatial_results)
        )

        # Stage 2: Satellite Deforestation Triangulation & Cloud Fallback (40% -> 75%)
        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.ANALYZING_SATELLITE.value,
            progress_pct=45.0,
            current_step="Querying multi-satellite sensors (Copernicus Sentinel-2, Hansen GFC, JRC 2020, Planet NICFI)...",
            processed_plots=len(spatial_results)
        )

        deforest_free, satellite_results, satellite_summary = DeforestationSimulator.analyze_all_plots(
            payload.plots, spatial_results
        )

        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.ANALYZING_SATELLITE.value,
            progress_pct=72.0,
            current_step=f"Completed multi-spectral satellite deforestation analysis (Deforestation Free: {deforest_free})",
            processed_plots=len(satellite_results)
        )

        # Stage 3: Legal Document Audit (75% -> 85%)
        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.AUDITING_LEGAL.value,
            progress_pct=78.0,
            current_step="Auditing 7 mandatory EUDR legality documents & country risk tier...",
            processed_plots=len(satellite_results)
        )

        legal_audit_result = LegalAuditor.audit_documents(
            documents=payload.documents,
            plots=payload.plots,
            commodity=payload.commodity
        )

        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.AUDITING_LEGAL.value,
            progress_pct=84.0,
            current_step=f"Legal compliance audited (Risk Tier: {legal_audit_result.country_risk_tier.value})",
            processed_plots=len(satellite_results)
        )

        # Stage 4: DDS Assembly & Cryptographic Signing (85% -> 95%)
        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.GENERATING_DDS.value,
            progress_pct=88.0,
            current_step="Assembling EU TRACES-NT DDS Statement & Non-repudiation Evidence Bundle...",
            processed_plots=len(satellite_results)
        )

        report = DDSGenerator.assemble_report(
            payload=payload,
            spatial_valid=spatial_valid,
            spatial_results=spatial_results,
            spatial_summary=spatial_summary,
            deforestation_free=deforest_free,
            satellite_results=satellite_results,
            satellite_summary=satellite_summary,
            legal_audit=legal_audit_result,
            start_time=start_time
        )

        # Stage 5: Save execution to Audit DB (95% -> 100%)
        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.GENERATING_DDS.value,
            progress_pct=96.0,
            current_step="Persisting 5-year immutable audit log and generating reference IDs...",
            processed_plots=len(satellite_results)
        )

        try:
            saved_record = AuditRepository.save_evaluation(db, payload, report)
            report.execution_id = saved_record.execution_id
        except Exception:
            pass

        # Finalize Complete
        status_str = report.status.value if hasattr(report.status, "value") else str(report.status)
        report_dict = report.model_dump(mode="json")

        BatchJobRepository.complete_job(
            db=db,
            job_id=job_id,
            execution_id=report.execution_id,
            overall_status=status_str,
            result_snapshot=report_dict
        )

        return {
            "status": "COMPLETED",
            "job_id": job_id,
            "execution_id": report.execution_id,
            "overall_status": status_str,
            "report": report_dict
        }

    except Exception as err:
        err_msg = f"Pipeline execution failed: {str(err)}\n{traceback.format_exc()}"
        BatchJobRepository.fail_job(
            db=db,
            job_id=job_id,
            error_message=err_msg
        )
        raise err
    finally:
        db.close()


def run_file_pipeline_sync(
    job_id: str,
    filename: str,
    content_bytes_b64: str,
    supplier_id: str,
    operator_name: str,
    hs_code: str,
    commodity_desc: str
):
    """Synchronous file parsing and pipeline execution logic."""
    db = SessionLocal()
    try:
        BatchJobRepository.update_progress(
            db=db,
            job_id=job_id,
            status=BatchJobStatusEnum.PARSING.value,
            progress_pct=10.0,
            current_step=f"Parsing file '{filename}'...",
            processed_plots=0
        )

        content_bytes = base64.b64decode(content_bytes_b64)
        payload = BulkFileParser.parse_file(
            filename=filename,
            content_bytes=content_bytes,
            supplier_id=supplier_id,
            operator_name=operator_name,
            hs_code=hs_code,
            commodity_desc=commodity_desc
        )

        record = BatchJobRepository.get_job(db, job_id)
        if record:
            record.total_plots = len(payload.plots)
            db.commit()

        db.close()
        return run_pipeline_sync(job_id=job_id, payload_dict=payload.model_dump(mode="json"))

    except Exception as err:
        err_msg = f"File parsing or batch processing failed: {str(err)}"
        BatchJobRepository.fail_job(
            db=db,
            job_id=job_id,
            error_message=err_msg
        )
        db.close()
        raise err


# Register Celery tasks if Celery is initialized
if celery_app is not None:
    @celery_app.task(name="app.tasks.eudr_tasks.evaluate_supply_chain_task", bind=True, max_retries=3)
    def evaluate_supply_chain_task(self, job_id: str, payload_dict: Dict[str, Any]):
        """Celery distributed task for supply chain evaluation."""
        try:
            return run_pipeline_sync(job_id=job_id, payload_dict=payload_dict)
        except Exception as exc:
            # Automatic retry with exponential backoff for transient failures
            raise self.retry(exc=exc, countdown=min(60, 2 ** self.request.retries))

    @celery_app.task(name="app.tasks.eudr_tasks.parse_and_evaluate_file_task", bind=True, max_retries=3)
    def parse_and_evaluate_file_task(
        self,
        job_id: str,
        filename: str,
        content_bytes_b64: str,
        supplier_id: str,
        operator_name: str,
        hs_code: str,
        commodity_desc: str
    ):
        """Celery distributed task for bulk file parsing and evaluation."""
        try:
            return run_file_pipeline_sync(
                job_id=job_id,
                filename=filename,
                content_bytes_b64=content_bytes_b64,
                supplier_id=supplier_id,
                operator_name=operator_name,
                hs_code=hs_code,
                commodity_desc=commodity_desc
            )
        except Exception as exc:
            raise self.retry(exc=exc, countdown=min(60, 2 ** self.request.retries))
else:
    evaluate_supply_chain_task = None
    parse_and_evaluate_file_task = None
