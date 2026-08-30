import asyncio
import uuid
import datetime
from datetime import datetime as dt, timezone
from typing import Optional, Dict, Any, Tuple
import traceback


from app.schemas import (
    EUDRSupplyChainPayload,
    DDSReport,
    BatchJobStatusEnum,
    BatchJobStatusResponse,
    BatchJobSubmitResponse
)
from app.modules.bulk_file_parser import BulkFileParser
from app.modules.traceability_collector import TraceabilityCollector
from app.modules.deforestation_simulator import DeforestationSimulator
from app.modules.legal_document_auditor import LegalAuditor
from app.modules.dds_generator import DDSGenerator
from app.db.session import SessionLocal
from app.db.repository import BatchJobRepository, AuditRepository
from app.core.config import settings
import base64

try:
    from app.tasks.eudr_tasks import evaluate_supply_chain_task, parse_and_evaluate_file_task
except Exception:
    evaluate_supply_chain_task = None
    parse_and_evaluate_file_task = None


class BatchJobManager:
    """
    Hybrid Batch Processing & Job Progress Engine for High-Volume EUDR Workloads.
    - Dispatches to distributed Celery + Redis workers when configured/available.
    - Gracefully falls back to robust local background thread pool if distributed queue is unavailable.
    - Tracks granular real-time progress across all compliance modules.
    """

    # In-memory fast cache for active job status polling
    _job_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def is_distributed_queue_available(cls) -> bool:
        """Checks if Celery and Redis distributed task queue is configured and operational."""
        if not settings.USE_DISTRIBUTED_QUEUE or evaluate_supply_chain_task is None:
            return False
        try:
            # Ping Redis / Celery broker with 0.5s timeout
            import redis
            r = redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=0.5)
            r.ping()
            return True
        except Exception:
            return False

    @classmethod
    def create_and_start_job_from_payload(
        cls,
        payload: EUDRSupplyChainPayload
    ) -> BatchJobSubmitResponse:
        """Submits an in-memory JSON payload for asynchronous batch execution (Celery or Local)."""
        job_id = f"JOB-{uuid.uuid4().hex[:12].upper()}"
        total_plots = len(payload.plots)
        created_at_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Initialize cache
        cls._job_cache[job_id] = {
            "job_id": job_id,
            "status": BatchJobStatusEnum.QUEUED,
            "progress_pct": 5.0,
            "current_step": "Job queued in processing pipeline",
            "total_plots": total_plots,
            "processed_plots": 0,
            "start_time": datetime.datetime.now(datetime.timezone.utc),
            "execution_id": None,
            "overall_status": None,
            "error_message": None,
            "result_report": None,
            "completed_at": None,
            "engine": "distributed" if cls.is_distributed_queue_available() else "local"
        }

        # Persist Initial Record to Database
        db = SessionLocal()
        try:
            BatchJobRepository.create_job(
                db=db,
                job_id=job_id,
                total_plots=total_plots,
                supplier_id=payload.supplier_id,
                operator_name=payload.operator.operator_name if payload.operator else None,
                commodity_hs_code=payload.commodity.hs_code if payload.commodity else None
            )
        finally:
            db.close()

        # Dispatch strategy: Celery distributed task or Local thread fallback
        use_distributed = cls.is_distributed_queue_available()
        if use_distributed and evaluate_supply_chain_task is not None:
            try:
                evaluate_supply_chain_task.delay(
                    job_id=job_id,
                    payload_dict=payload.model_dump(mode="json")
                )
                msg = "Batch compliance evaluation job successfully dispatched to Celery distributed worker."
            except Exception:
                # Fallback to local thread if dispatch failed
                cls._run_in_background(cls._execute_evaluation_pipeline, job_id=job_id, payload=payload)
                msg = "Batch compliance evaluation job successfully queued (local fallback)."
        else:
            cls._run_in_background(cls._execute_evaluation_pipeline, job_id=job_id, payload=payload)
            msg = "Batch compliance evaluation job successfully queued."

        return BatchJobSubmitResponse(
            job_id=job_id,
            status=BatchJobStatusEnum.QUEUED,
            message=msg,
            created_at=created_at_str
        )

    @classmethod
    def _run_in_background(cls, coro_fn, *args, **kwargs):
        """Runs an async pipeline reliably in background regardless of event loop context."""
        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(coro_fn(*args, **kwargs))
            except Exception as e:
                pass
            finally:
                loop.close()

        import threading
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()

    @classmethod
    def create_and_start_job_from_file(
        cls,
        filename: str,
        content_bytes: bytes,
        supplier_id: str = "SUPP-BATCH-FILE",
        operator_name: str = "Global Import Logistics SA",
        hs_code: str = "090111",
        commodity_desc: str = "Bulk Ingested Commodity"
    ) -> BatchJobSubmitResponse:
        """Submits a bulk file (GeoJSON, KML, CSV, XLSX) for background parsing and batch execution."""
        job_id = f"JOB-{uuid.uuid4().hex[:12].upper()}"
        created_at_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cls._job_cache[job_id] = {
            "job_id": job_id,
            "status": BatchJobStatusEnum.QUEUED,
            "progress_pct": 2.0,
            "current_step": f"Queued file ingestion ({filename})",
            "total_plots": 0,
            "processed_plots": 0,
            "start_time": datetime.datetime.now(datetime.timezone.utc),
            "execution_id": None,
            "overall_status": None,
            "error_message": None,
            "result_report": None,
            "completed_at": None
        }

        db = SessionLocal()
        try:
            BatchJobRepository.create_job(
                db=db,
                job_id=job_id,
                total_plots=0,
                supplier_id=supplier_id,
                operator_name=operator_name,
                commodity_hs_code=hs_code
            )
        finally:
            db.close()

        # Dispatch strategy: Celery distributed task or Local thread fallback
        use_distributed = cls.is_distributed_queue_available()
        if use_distributed and parse_and_evaluate_file_task is not None:
            try:
                content_b64 = base64.b64encode(content_bytes).decode("utf-8")
                parse_and_evaluate_file_task.delay(
                    job_id=job_id,
                    filename=filename,
                    content_bytes_b64=content_b64,
                    supplier_id=supplier_id,
                    operator_name=operator_name,
                    hs_code=hs_code,
                    commodity_desc=commodity_desc
                )
                msg = f"File '{filename}' successfully dispatched to Celery distributed worker."
            except Exception:
                cls._run_in_background(
                    cls._execute_file_and_evaluation_pipeline,
                    job_id=job_id,
                    filename=filename,
                    content_bytes=content_bytes,
                    supplier_id=supplier_id,
                    operator_name=operator_name,
                    hs_code=hs_code,
                    commodity_desc=commodity_desc
                )
                msg = f"File '{filename}' queued for background compliance analysis (local fallback)."
        else:
            cls._run_in_background(
                cls._execute_file_and_evaluation_pipeline,
                job_id=job_id,
                filename=filename,
                content_bytes=content_bytes,
                supplier_id=supplier_id,
                operator_name=operator_name,
                hs_code=hs_code,
                commodity_desc=commodity_desc
            )
            msg = f"File '{filename}' successfully queued for background parsing and compliance analysis."

        return BatchJobSubmitResponse(
            job_id=job_id,
            status=BatchJobStatusEnum.QUEUED,
            message=msg,
            created_at=created_at_str
        )


    @classmethod
    def get_job_status(cls, job_id: str) -> Optional[BatchJobStatusResponse]:
        """Retrieves real-time status and progress percentage of a batch job."""
        cache_item = cls._job_cache.get(job_id)
        if cache_item:
            now = datetime.datetime.now(datetime.timezone.utc)
            start_t = cache_item["start_time"]
            elapsed = (now - start_t).total_seconds() if start_t else 0.0

            return BatchJobStatusResponse(
                job_id=job_id,
                status=cache_item["status"],
                progress_pct=round(cache_item["progress_pct"], 1),
                current_step=cache_item["current_step"],
                total_plots=cache_item["total_plots"],
                processed_plots=cache_item["processed_plots"],
                elapsed_seconds=round(elapsed, 2),
                error_message=cache_item["error_message"],
                overall_status=cache_item["overall_status"],
                execution_id=cache_item["execution_id"],
                created_at=start_t.isoformat() if start_t else "",
                completed_at=cache_item["completed_at"].isoformat() if cache_item["completed_at"] else None
            )

        # Fallback to Database
        db = SessionLocal()
        try:
            record = BatchJobRepository.get_job(db, job_id)
            if not record:
                return None
            
            elapsed = 0.0
            if record.created_at:
                end_time = record.completed_at or datetime.datetime.now(datetime.timezone.utc)
                elapsed = (end_time - record.created_at).total_seconds()

            return BatchJobStatusResponse(
                job_id=record.job_id,
                status=BatchJobStatusEnum(record.status) if record.status in BatchJobStatusEnum.__members__ else BatchJobStatusEnum.FAILED,
                progress_pct=record.progress_pct or 0.0,
                current_step=record.current_step or "",
                total_plots=record.total_plots or 0,
                processed_plots=record.processed_plots or 0,
                elapsed_seconds=round(max(0.0, elapsed), 2),
                error_message=record.error_message,
                overall_status=record.overall_status,
                execution_id=record.execution_id,
                created_at=record.created_at.isoformat() if record.created_at else "",
                completed_at=record.completed_at.isoformat() if record.completed_at else None
            )
        finally:
            db.close()

    @classmethod
    def get_job_result(cls, job_id: str) -> Optional[DDSReport]:
        """Retrieves full DDS compliance report of a completed batch job."""
        cache_item = cls._job_cache.get(job_id)
        if cache_item and cache_item.get("result_report"):
            return cache_item["result_report"]

        db = SessionLocal()
        try:
            record = BatchJobRepository.get_job(db, job_id)
            if record and record.result_snapshot:
                return DDSReport.model_validate(record.result_snapshot)
            return None
        finally:
            db.close()

    # --- Internal Pipeline Execution Helpers ---

    @classmethod
    async def _execute_file_and_evaluation_pipeline(
        cls,
        job_id: str,
        filename: str,
        content_bytes: bytes,
        supplier_id: str,
        operator_name: str,
        hs_code: str,
        commodity_desc: str
    ):
        """Asynchronously parses file and runs the full pipeline."""
        db = SessionLocal()
        try:
            # 1. Parsing File (0% -> 15%)
            cls._update_stage(db, job_id, BatchJobStatusEnum.PARSING, 10.0, f"Parsing file '{filename}'...")
            await asyncio.sleep(0.05)  # Yield loop

            payload = BulkFileParser.parse_file(
                filename=filename,
                content_bytes=content_bytes,
                supplier_id=supplier_id,
                operator_name=operator_name,
                hs_code=hs_code,
                commodity_desc=commodity_desc
            )

            # Update total plots count
            total_plots = len(payload.plots)
            cls._update_total_plots(db, job_id, total_plots)

            # Hand off to evaluation pipeline
            await cls._execute_evaluation_pipeline(job_id=job_id, payload=payload, db=db)

        except Exception as err:
            err_msg = f"File parsing or batch processing failed: {str(err)}"
            cls._update_failure(db, job_id, err_msg)
        finally:
            db.close()

    @classmethod
    async def _execute_evaluation_pipeline(
        cls,
        job_id: str,
        payload: EUDRSupplyChainPayload,
        db: Optional[Any] = None
    ):
        """Runs the 5-step EUDR compliance pipeline with fine-grained progress updates."""
        close_db_at_end = False
        if db is None:
            db = SessionLocal()
            close_db_at_end = True

        try:
            start_time = dt.now(timezone.utc)
            if not payload.execution_id:

                payload.execution_id = f"EXEC-{uuid.uuid4().hex[:12].upper()}"

            total_plots = len(payload.plots)

            # Stage 1: GIS Validation & Self-Healing (15% -> 40%)
            cls._update_stage(
                db, job_id, BatchJobStatusEnum.VALIDATING_GIS, 20.0, 
                f"Validating & repairing {total_plots} plot geometries (Article 9(1)(d))..."
            )
            await asyncio.sleep(0.05)

            spatial_valid, spatial_results, spatial_summary = TraceabilityCollector.collect_and_validate(payload.plots)
            
            cls._update_stage(
                db, job_id, BatchJobStatusEnum.VALIDATING_GIS, 38.0, 
                f"Completed GIS topological validation ({len(spatial_results)} plots processed)",
                processed_plots=len(spatial_results)
            )
            await asyncio.sleep(0.05)

            # Stage 2: Satellite Deforestation Triangulation & Cloud Fallback (40% -> 75%)
            cls._update_stage(
                db, job_id, BatchJobStatusEnum.ANALYZING_SATELLITE, 45.0, 
                "Querying multi-satellite sensors (Copernicus Sentinel-2, Hansen GFC, JRC 2020, Planet NICFI)..."
            )
            await asyncio.sleep(0.05)

            deforest_free, satellite_results, satellite_summary = DeforestationSimulator.analyze_all_plots(
                payload.plots, spatial_results
            )

            cls._update_stage(
                db, job_id, BatchJobStatusEnum.ANALYZING_SATELLITE, 72.0, 
                f"Completed multi-spectral satellite deforestation analysis (Deforestation Free: {deforest_free})",
                processed_plots=len(satellite_results)
            )
            await asyncio.sleep(0.05)

            # Stage 3: Legal Document Audit (75% -> 85%)
            cls._update_stage(
                db, job_id, BatchJobStatusEnum.AUDITING_LEGAL, 78.0, 
                "Auditing 7 mandatory EUDR legality documents & country risk tier..."
            )
            await asyncio.sleep(0.05)

            legal_audit_result = LegalAuditor.audit_documents(
                documents=payload.documents,
                plots=payload.plots,
                commodity=payload.commodity
            )

            cls._update_stage(
                db, job_id, BatchJobStatusEnum.AUDITING_LEGAL, 84.0, 
                f"Legal compliance audited (Risk Tier: {legal_audit_result.country_risk_tier.value})"
            )
            await asyncio.sleep(0.05)

            # Stage 4: DDS Assembly & Cryptographic Signing (85% -> 95%)
            cls._update_stage(
                db, job_id, BatchJobStatusEnum.GENERATING_DDS, 88.0, 
                "Assembling EU TRACES-NT DDS Statement & Non-repudiation Evidence Bundle..."
            )
            await asyncio.sleep(0.05)

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
            cls._update_stage(
                db, job_id, BatchJobStatusEnum.GENERATING_DDS, 96.0, 
                "Persisting 5-year immutable audit log and generating reference IDs..."
            )

            try:
                saved_record = AuditRepository.save_evaluation(db, payload, report)
                report.execution_id = saved_record.execution_id
            except Exception as db_err:
                pass

            # Finalize Complete
            status_str = report.status.value if hasattr(report.status, "value") else str(report.status)
            report_dict = report.model_dump(mode="json")

            cls._update_complete(
                db=db,
                job_id=job_id,
                execution_id=report.execution_id,
                overall_status=status_str,
                report=report,
                report_dict=report_dict,
                processed_plots=total_plots
            )

        except Exception as err:
            err_msg = f"Pipeline execution failed: {str(err)}\n{traceback.format_exc()}"
            cls._update_failure(db, job_id, err_msg)
        finally:
            if close_db_at_end:
                db.close()

    # --- Helper Update Methods ---

    @classmethod
    def _update_stage(
        cls,
        db: Any,
        job_id: str,
        status: BatchJobStatusEnum,
        progress_pct: float,
        step_msg: str,
        processed_plots: Optional[int] = None
    ):
        if job_id in cls._job_cache:
            cls._job_cache[job_id]["status"] = status
            cls._job_cache[job_id]["progress_pct"] = progress_pct
            cls._job_cache[job_id]["current_step"] = step_msg
            if processed_plots is not None:
                cls._job_cache[job_id]["processed_plots"] = processed_plots

        try:
            BatchJobRepository.update_progress(
                db=db,
                job_id=job_id,
                status=status.value,
                progress_pct=progress_pct,
                current_step=step_msg,
                processed_plots=processed_plots
            )
        except Exception:
            pass

    @classmethod
    def _update_total_plots(cls, db: Any, job_id: str, total_plots: int):
        if job_id in cls._job_cache:
            cls._job_cache[job_id]["total_plots"] = total_plots
        try:
            record = BatchJobRepository.get_job(db, job_id)
            if record:
                record.total_plots = total_plots
                db.commit()
        except Exception:
            pass

    @classmethod
    def _update_complete(
        cls,
        db: Any,
        job_id: str,
        execution_id: str,
        overall_status: str,
        report: DDSReport,
        report_dict: Dict[str, Any],
        processed_plots: int
    ):
        now = datetime.datetime.now(datetime.timezone.utc)
        if job_id in cls._job_cache:
            cls._job_cache[job_id]["status"] = BatchJobStatusEnum.COMPLETED
            cls._job_cache[job_id]["progress_pct"] = 100.0
            cls._job_cache[job_id]["current_step"] = "Compliance evaluation completed successfully"
            cls._job_cache[job_id]["execution_id"] = execution_id
            cls._job_cache[job_id]["overall_status"] = overall_status
            cls._job_cache[job_id]["result_report"] = report
            cls._job_cache[job_id]["processed_plots"] = processed_plots
            cls._job_cache[job_id]["completed_at"] = now

        try:
            BatchJobRepository.complete_job(
                db=db,
                job_id=job_id,
                execution_id=execution_id,
                overall_status=overall_status,
                result_snapshot=report_dict
            )
        except Exception:
            pass

    @classmethod
    def _update_failure(cls, db: Any, job_id: str, error_msg: str):
        now = datetime.datetime.now(datetime.timezone.utc)
        if job_id in cls._job_cache:
            cls._job_cache[job_id]["status"] = BatchJobStatusEnum.FAILED
            cls._job_cache[job_id]["error_message"] = error_msg
            cls._job_cache[job_id]["current_step"] = f"Evaluation failed: {error_msg}"
            cls._job_cache[job_id]["completed_at"] = now

        try:
            BatchJobRepository.fail_job(
                db=db,
                job_id=job_id,
                error_message=error_msg
            )
        except Exception:
            pass
