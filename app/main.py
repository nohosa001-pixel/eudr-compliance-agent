from fastapi import FastAPI, HTTPException, status, Response, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import uuid
import json
import asyncio
from pathlib import Path
from typing import List, Optional, Any

import importlib

try:
    _sa_orm = importlib.import_module("sqlalchemy.orm")
    Session = getattr(_sa_orm, "Session")
except Exception:
    Session = Any  # type: ignore

from app.schemas import (
    EUDRSupplyChainPayload, 
    DDSReport, 
    ProductionPlotInput,
    SpatialPlotResult,
    EUDRCommodityCategory,
    ComplianceStatusEnum,
    ReviewStatusEnum,
    ExpertReviewInput,
    ExpertReviewResponse,
    FullComplianceReport,
    BatchJobSubmitResponse,
    BatchJobStatusResponse,
    IntegrityVerificationResult,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyValidationResponse
)
from app.modules.spatial_validator import SpatialValidator, SelfHealingEngine
from app.modules.traceability_collector import TraceabilityCollector
from app.modules.deforestation_simulator import DeforestationSimulator, DeforestationAnalyzer
from app.modules.legal_document_auditor import LegalAuditor
from app.modules.dds_generator import DDSGenerator
from app.modules.dds_prebuilder import DDSPrebuilder
from app.modules.bulk_file_parser import BulkFileParser
from app.modules.traces_b2g_client import TracesNTB2GClient, TRACESB2GSubmissionResponse
from app.modules.batch_job_manager import BatchJobManager
from app.modules.audit_integrity_verifier import AuditIntegrityVerifier
from app.db.session import init_db, get_db
from app.db.repository import AuditRepository, BatchJobRepository, ApiKeyRepository
from app.core.config import settings



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Automated EUDR (EU Deforestation Regulation) Supply Chain Compliance & TRACES-NT DDS Generator API",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files & Dashboard UI
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def serve_landing():
    """Serves the eudragent.com Official SaaS Landing Page."""
    landing_file = STATIC_DIR / "landing.html"
    if landing_file.exists():
        return FileResponse(str(landing_file))
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h2>EUDRAgent SaaS Platform is running. Visit /docs for Swagger UI.</h2>")

@app.get("/dashboard", include_in_schema=False)
@app.get("/app", include_in_schema=False)
async def serve_dashboard():
    """Serves the interactive EUDR Compliance Console & Operator Workbench."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h2>EUDR Compliance Console is running. Visit /docs for Swagger UI.</h2>")

@app.get("/supplier-portal", include_in_schema=False)
@app.get("/supplier", include_in_schema=False)
async def serve_supplier_portal():
    """Serves the Supplier EUDR Pre-Clearance & Onboarding Portal."""
    portal_file = STATIC_DIR / "supplier_portal.html"
    if portal_file.exists():
        return FileResponse(str(portal_file))
    return HTMLResponse("<h2>Supplier Portal is running.</h2>")

@app.get("/robots.txt", include_in_schema=False)
async def serve_robots():
    """Serves robots.txt for search engine crawlers."""
    robots_file = STATIC_DIR / "robots.txt"
    if robots_file.exists():
        return FileResponse(str(robots_file), media_type="text/plain")
    return Response(content="User-agent: *\nAllow: /\nSitemap: https://eudragent.com/sitemap.xml\n", media_type="text/plain")

@app.get("/sitemap.xml", include_in_schema=False)
async def serve_sitemap():
    """Serves sitemap.xml for search engines."""
    sitemap_file = STATIC_DIR / "sitemap.xml"
    if sitemap_file.exists():
        return FileResponse(str(sitemap_file), media_type="application/xml")
    return Response(content="""<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://eudragent.com/</loc></url></urlset>""", media_type="application/xml")

@app.get(f"{settings.API_V1_PREFIX}/eudr/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "eudr_cutoff_date": str(settings.EUDR_CUTOFF_DATE),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/classify-commodity",
    tags=["EUDR Regulations"],
    summary="Classify HS code into EUDR 7 Annex I commodity categories"
)
async def classify_commodity(hs_code: str):
    """Classifies an HS code against EUDR Annex I commodities."""
    category = LegalAuditor.classify_hs_code(hs_code)
    return {
        "hs_code": hs_code,
        "eudr_category": category.value,
        "is_eudr_regulated": category != EUDRCommodityCategory.OTHER
    }

@app.post(
    f"{settings.API_V1_PREFIX}/eudr/validate-spatial",
    response_model=SpatialPlotResult,
    tags=["Spatial GIS Validation"],
    summary="Validate individual production plot geometry (4ha rule, WGS84, polygon closure, self-healing)"
)
async def validate_single_plot(plot: ProductionPlotInput):
    """
    Validates a single plot geometry against EUDR Article 9(1)(d) standards with Self-Healing:
    - Automatically repairs inverted coordinates ([lat, lon] -> [lon, lat]).
    - Repairs topological defects (self-intersection bowties, unclosed rings, duplicate vertices <0.1m).
    - Checks 4ha polygon rule and computes WGS84 geodesic area.
    """
    return SpatialValidator.validate_plot(plot, auto_heal=True)

@app.post(
    f"{settings.API_V1_PREFIX}/eudr/simulate",
    response_model=DDSReport,
    tags=["EUDR Pipeline Evaluation"],
    summary="Pre-simulate EUDR compliance with Self-Healing GIS, SAR radar fallback, and 10m buffer analysis"
)
@app.post(
    f"{settings.API_V1_PREFIX}/eudr/evaluate",
    response_model=DDSReport,
    tags=["EUDR Pipeline Evaluation"],
    summary="End-to-end EUDR compliance evaluation and TRACES-NT DDS generation"
)
async def evaluate_supply_chain(
    payload: EUDRSupplyChainPayload,
    db: Session = Depends(get_db)
):
    """
    Executes the full EUDR automated compliance workflow:
    1. **Module 1 (Traceability Collector & Self-Healing)**: Validates and repairs plot geometries, 4ha rules, and calculates ellipsoid area.
    2. **Module 2 (Satellite Deforestation Simulator)**: Evaluates 2020-12-31 baseline with optical-to-SAR radar cloud fallback and 10m buffer zone.
    3. **Module 3 (Legal Document Auditor)**: Audits country risk benchmarking, permit expiration, and mandatory documents.
    4. **Module 4 (DDS Prebuilder & Generator)**: Synthesizes TRACES-NT statement, generates digital signature, AS-IS disclaimer, and attaches audit trail.
    5. **Database Persistence**: Persists execution snapshot in SQLite/PostgreSQL audit database.
    """
    start_time = datetime.now(timezone.utc)
    if not payload.execution_id:
        payload.execution_id = str(uuid.uuid4())

    # Step 1: Spatial & Traceability Validation with Self-Healing
    spatial_valid, spatial_results, spatial_summary = TraceabilityCollector.collect_and_validate(payload.plots)

    # Step 2: Satellite Deforestation Analysis with SAR Cloud Fallback & 10m Buffer Zone
    deforest_free, satellite_results, satellite_summary = DeforestationSimulator.analyze_all_plots(
        payload.plots, spatial_results
    )

    # Step 3: Legal Document Audit
    legal_audit_result = LegalAuditor.audit_documents(
        documents=payload.documents,
        plots=payload.plots,
        commodity=payload.commodity
    )

    # Step 4: DDS Assembly & Report Generation
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

    # Step 5: Save execution to Database
    try:
        saved_record = AuditRepository.save_evaluation(db, payload, report)
        report.execution_id = saved_record.execution_id
    except Exception:
        # DB save non-fatal for evaluation response
        pass

    return report

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/report/languages",
    tags=["EUDR Regulations"],
    summary="Get list of supported languages for audit reports (EN, KO, FR, ES, DE, PT)"
)
async def get_supported_report_languages():
    """Returns supported languages for multi-language audit report generation."""
    from app.modules.report_i18n import get_supported_languages
    return get_supported_languages()

@app.post(
    f"{settings.API_V1_PREFIX}/eudr/evaluate/html-report",
    response_class=HTMLResponse,
    tags=["EUDR Pipeline Evaluation"],
    summary="Evaluate supply chain and return formatted printable HTML audit report in chosen language"
)
async def evaluate_supply_chain_html(
    payload: EUDRSupplyChainPayload,
    lang: str = "en",
    db: Session = Depends(get_db)
):
    """Runs evaluation and outputs a printable styled HTML report (Supports: 'en', 'ko', 'fr', 'es', 'de', 'pt')."""
    report = await evaluate_supply_chain(payload, db=db)
    html_content = DDSGenerator.generate_html_report(report, lang=lang)
    return HTMLResponse(content=html_content, status_code=200)

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/history/{{execution_id}}/html-report",
    response_class=HTMLResponse,
    tags=["Commercial Operations"],
    summary="Get formatted printable HTML audit report for a past execution in chosen language"
)
async def get_audit_html_report(
    execution_id: str,
    lang: str = "en",
    db: Session = Depends(get_db)
):
    """Retrieves previous execution record and generates localized printable HTML report."""
    record = AuditRepository.get_by_execution_id(db, execution_id)
    if not record or not record.full_report_snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Execution ID '{execution_id}' not found.")
    
    try:
        report = DDSReport.model_validate(record.full_report_snapshot)
        html_content = DDSGenerator.generate_html_report(report, lang=lang)
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate HTML report: {str(err)}")

@app.post(
    f"{settings.API_V1_PREFIX}/eudr/ingest-file",
    response_model=EUDRSupplyChainPayload,
    tags=["Commercial Operations"],
    summary="Bulk ingest supply chain plots from CSV, Excel (.xlsx), GeoJSON, or KML files"
)
async def ingest_bulk_file(
    file: UploadFile = File(...),
    supplier_id: str = Form("SUPP-FILE-INGEST"),
    operator_name: str = Form("Global Import Logistics SA"),
    hs_code: str = Form("090111"),
    commodity_desc: str = Form("Bulk Ingested Commodity")
):
    """
    Ingests and parses supplier-provided land parcel files:
    - **GeoJSON** (.geojson, .json)
    - **KML** (.kml)
    - **CSV** (.csv)
    - **Excel** (.xlsx)
    Automatically maps coordinates, checks geometry structure, and formats ready-to-evaluate JSON payload.
    """
    content = await file.read()
    try:
        payload = BulkFileParser.parse_file(
            filename=file.filename or "upload.geojson",
            content_bytes=content,
            supplier_id=supplier_id,
            operator_name=operator_name,
            hs_code=hs_code,
            commodity_desc=commodity_desc
        )
        return payload
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file '{file.filename}': {str(err)}"
        )

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/history",
    tags=["Commercial Operations"],
    summary="List past compliance audit executions from database"
)
async def list_audit_history(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieves list of past audit executions from database."""
    records = AuditRepository.list_executions(db, limit=limit)
    return [
        {
            "execution_id": r.execution_id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "supplier_id": r.supplier_id,
            "operator_name": r.operator_name,
            "commodity_hs_code": r.commodity_hs_code,
            "total_plots": r.total_plots,
            "total_area_ha": r.total_area_ha,
            "overall_status": r.overall_status,
            "confidence_score": r.confidence_score,
            "review_status": r.review_status,
            "dds_reference_id": r.dds_reference_id,
            "traces_submission_status": r.traces_submission_status,
            "traces_ack_number": r.traces_ack_number
        }
        for r in records
    ]

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/history/{{execution_id}}",
    tags=["Commercial Operations"],
    summary="Get full audit execution report and snapshot by execution ID"
)
async def get_audit_detail(execution_id: str, db: Session = Depends(get_db)):
    """Retrieves full snapshot and report of a previous execution."""
    record = AuditRepository.get_by_execution_id(db, execution_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Execution ID '{execution_id}' not found.")
    return {
        "execution_id": record.execution_id,
        "timestamp": record.timestamp.isoformat() if record.timestamp else None,
        "overall_status": record.overall_status,
        "confidence_score": record.confidence_score,
        "review_status": record.review_status,
        "traces_submission_status": record.traces_submission_status,
        "traces_ack_number": record.traces_ack_number,
        "payload": record.payload_snapshot,
        "full_report": record.full_report_snapshot,
        "evidence_bundle": record.evidence_bundle_snapshot
    }


@app.post(
    f"{settings.API_V1_PREFIX}/eudr/traces-nt/submit",
    response_model=TRACESB2GSubmissionResponse,
    tags=["Commercial Operations"],
    summary="Direct transmission of Due Diligence Statement to EU TRACES-NT Gateway"
)
async def submit_to_traces_nt(
    report: FullComplianceReport,
    db: Session = Depends(get_db)
):
    """
    Submits a compliant EUDR report directly to EU TRACES-NT Gateway via B2G interface:
    - Generates EU Single Window Customs Clearance code (EU SWE-C).
    - Updates local audit database record with official ACK number.
    """
    if not report.traces_dds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit to TRACES-NT: Report does not contain a valid TRACES-NT DDS Statement."
        )

    submission_resp = TracesNTB2GClient.submit_statement(
        traces_dds=report.traces_dds,
        report_status=report.status
    )

    if report.execution_id:
        AuditRepository.update_traces_submission(
            db=db,
            execution_id=report.execution_id,
            status="SUBMITTED",
            ack_number=submission_resp.traces_ack_number
        )

    return submission_resp

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/benchmark/run",
    tags=["Verification Assurance"],
    summary="Run Golden Benchmark Suite (10 Ground-Truth scenarios) and compute accuracy metrics"
)
async def run_golden_benchmark():
    """
    Executes the 10 Ground-Truth Golden Benchmark cases covering all critical EUDR edge cases:
    - Computes Accuracy, Precision, Recall, F1-Score, and False Positive/Negative rates.
    """
    from app.modules.golden_benchmark import GoldenBenchmarkSuite
    return GoldenBenchmarkSuite.run_suite()

@app.post(
    f"{settings.API_V1_PREFIX}/eudr/hitl/review",
    tags=["Verification Assurance"],
    summary="Submit Human-in-the-Loop expert review decision / sign-off"
)
async def submit_expert_review(review: ExpertReviewInput):
    """
    Applies expert GIS/Compliance officer manual review decision on flagged or boundary cases.
    """
    new_status = ComplianceStatusEnum.COMPLIANT if review.decision == ReviewStatusEnum.EXPERT_APPROVED else ComplianceStatusEnum.NON_COMPLIANT
    return ExpertReviewResponse(
        execution_id=review.execution_id,
        previous_status=ComplianceStatusEnum.ACTION_REQUIRED,
        new_status=new_status,
        review_status=review.decision,
        reviewed_by=review.expert_name,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        message=f"Human-in-the-Loop review completed by {review.expert_name}. Decision: {review.decision.value}."
    )


# -------------------------------------------------------------------
# Asynchronous Batch Processing & Streaming Endpoints
# -------------------------------------------------------------------

@app.post(
    f"{settings.API_V1_PREFIX}/eudr/batch/submit",
    response_model=BatchJobSubmitResponse,
    tags=["Batch Processing Engine"],
    summary="Submit JSON supply chain payload for asynchronous background batch evaluation"
)
async def submit_batch_job(payload: EUDRSupplyChainPayload):
    """Queues a high-volume supply chain payload for background asynchronous evaluation."""
    return BatchJobManager.create_and_start_job_from_payload(payload)


@app.post(
    f"{settings.API_V1_PREFIX}/eudr/batch/upload",
    response_model=BatchJobSubmitResponse,
    tags=["Batch Processing Engine"],
    summary="Upload bulk plot file (CSV, GeoJSON, KML, XLSX) for background batch evaluation"
)
async def upload_bulk_file_batch(
    file: UploadFile = File(...),
    supplier_id: str = Form("SUPP-BATCH-INGEST"),
    operator_name: str = Form("Global Import Logistics SA"),
    hs_code: str = Form("090111"),
    commodity_desc: str = Form("Bulk Batch Evaluated Commodity")
):
    """Accepts large supplier land parcel files and processes compliance asynchronously in background."""
    content = await file.read()
    try:
        return BatchJobManager.create_and_start_job_from_file(
            filename=file.filename or "upload.geojson",
            content_bytes=content,
            supplier_id=supplier_id,
            operator_name=operator_name,
            hs_code=hs_code,
            commodity_desc=commodity_desc
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initiate batch job for '{file.filename}': {str(err)}"
        )


@app.get(
    f"{settings.API_V1_PREFIX}/eudr/batch/{{job_id}}/status",
    response_model=BatchJobStatusResponse,
    tags=["Batch Processing Engine"],
    summary="Query real-time progress and results of a batch job"
)
async def get_batch_job_status(job_id: str):
    """Returns granular progress percentage, current evaluation stage, and result report upon completion."""
    job_status = BatchJobManager.get_job_status(job_id)
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job '{job_id}' not found."
        )
    return job_status


@app.get(
    f"{settings.API_V1_PREFIX}/eudr/batch/{{job_id}}/stream",
    tags=["Batch Processing Engine"],
    summary="Server-Sent Events (SSE) stream for real-time batch job progress updates"
)
async def stream_batch_job_progress(job_id: str):
    """
    Streams live Server-Sent Events (SSE) for frontend progress bars and real-time dashboard updates.
    """
    initial_status = BatchJobManager.get_job_status(job_id)
    if not initial_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job '{job_id}' not found."
        )

    async def event_generator():
        while True:
            current_status = BatchJobManager.get_job_status(job_id)
            if not current_status:
                break
            
            data_json = current_status.model_dump_json()
            yield f"data: {data_json}\n\n"

            if current_status.status in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# -------------------------------------------------------------------
# EUDR Article 31 Cryptographic Audit Integrity Verification Endpoints
# -------------------------------------------------------------------

@app.get(
    f"{settings.API_V1_PREFIX}/eudr/audit/integrity/{{execution_id}}",
    response_model=IntegrityVerificationResult,
    tags=["Audit Integrity Verification"],
    summary="Verify cryptographic integrity & tamper-resistance of an Article 31 audit execution record"
)
async def verify_audit_execution_integrity(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """
    Executes EUDR Article 31 (5-Year Record Retention) Cryptographic Integrity Verification:
    - Verifies SHA-256 snapshots against stored Merkle Tree and HMAC signatures.
    - Validates OGC spatial geometry checksums and satellite telemetry manifest integrity.
    - Provides a court-admissible legal defense statement on record validity.
    """
    record = AuditRepository.get_by_execution_id(db, execution_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit execution ID '{execution_id}' not found in audit database."
        )

    return AuditIntegrityVerifier.verify_execution_record(record)


@app.post(
    f"{settings.API_V1_PREFIX}/eudr/audit/integrity/verify-bundle",
    response_model=IntegrityVerificationResult,
    tags=["Audit Integrity Verification"],
    summary="Directly verify cryptographic integrity of an exported Evidence Bundle JSON package"
)
async def verify_evidence_bundle_integrity(
    payload_snapshot: dict,
    report_snapshot: dict,
    evidence_bundle: dict,
    execution_id: Optional[str] = None
):
    """
    Directly validates independent evidence bundle JSON exports against tampering or post-facto modification.
    """
    exec_id = execution_id or report_snapshot.get("execution_id") or "EXEC-DIRECT-BUNDLE"
    return AuditIntegrityVerifier.verify_bundle_data(
        execution_id=exec_id,
        payload_dict=payload_snapshot,
        report_dict=report_snapshot,
        evidence_dict=evidence_bundle
    )


# ---------------------------------------------------------
# SaaS Tenant & API Key Authentication Endpoints
# ---------------------------------------------------------

@app.post(
    f"{settings.API_V1_PREFIX}/auth/api-keys",
    response_model=ApiKeyResponse,
    tags=["SaaS Auth & API Keys"],
    summary="Generate a new B2B API Key for ERP / SCM programmatic integration"
)
async def create_api_key(
    req: ApiKeyCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a new high-security API key for eudragent.com enterprise clients.
    Note: The raw API key (eudr_live_...) is returned only once at creation time.
    """
    record, raw_key = ApiKeyRepository.create_api_key(
        db=db,
        company_name=req.company_name,
        contact_email=req.contact_email,
        tier=req.tier
    )
    return ApiKeyResponse(
        key_id=record.key_id,
        api_key=raw_key,
        company_name=record.company_name,
        contact_email=record.contact_email,
        tier=record.tier,
        monthly_quota_plots=record.monthly_quota_plots,
        rate_limit_per_min=record.rate_limit_per_min,
        created_at=record.created_at.isoformat() if record.created_at else datetime.now(timezone.utc).isoformat(),
        message="API Key created successfully. Store this key securely; it will not be displayed again."
    )


@app.post(
    f"{settings.API_V1_PREFIX}/auth/verify-key",
    response_model=ApiKeyValidationResponse,
    tags=["SaaS Auth & API Keys"],
    summary="Validate an API Key and inspect tenant quota"
)
async def verify_api_key(
    api_key: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Validates the provided API key and returns the client profile, tier, and remaining quota.
    """
    record = ApiKeyRepository.verify_api_key(db=db, raw_api_key=api_key)
    if not record:
        return ApiKeyValidationResponse(
            is_valid=False,
            message="Invalid or inactive API Key."
        )
    
    remaining = max(0, record.monthly_quota_plots - record.used_plots_this_month)
    return ApiKeyValidationResponse(
        is_valid=True,
        key_id=record.key_id,
        company_name=record.company_name,
        tier=record.tier,
        remaining_quota_plots=remaining,
        message="API Key is valid and active."
    )

