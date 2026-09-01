import uuid
import datetime
import importlib
from typing import List, Optional, Dict, Any

try:
    _sa_orm = importlib.import_module("sqlalchemy.orm")
    Session = getattr(_sa_orm, "Session")
except Exception:
    Session = Any  # type: ignore
from app.db.models import AuditExecutionRecord, BatchJobRecord, ApiKeyRecord, LeadInquiryRecord
from app.schemas import EUDRSupplyChainPayload, FullComplianceReport


class AuditRepository:

    @classmethod
    def save_evaluation(
        cls,
        db: Session,
        payload: EUDRSupplyChainPayload,
        report: FullComplianceReport
    ) -> AuditExecutionRecord:
        execution_id = payload.execution_id or f"EXEC-{uuid.uuid4().hex[:12].upper()}"
        
        status_val = report.status.value if hasattr(report.status, "value") else str(report.status)
        review_status_val = report.confidence_assessment.review_status
        if hasattr(review_status_val, "value"):
            review_status_val = review_status_val.value

        record = AuditExecutionRecord(
            execution_id=execution_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            supplier_id=payload.supplier_id,
            operator_name=payload.operator.operator_name,
            commodity_hs_code=payload.commodity.hs_code,
            commodity_category=payload.commodity.description,
            total_plots=len(payload.plots),
            total_area_ha=sum(p.area_hectares for p in payload.plots),
            overall_status=status_val,
            confidence_score=report.confidence_assessment.overall_confidence_score if report.confidence_assessment else 1.0,
            review_status=str(review_status_val),
            dds_reference_id=report.traces_dds.dds_reference_id if report.traces_dds else None,
            evidence_bundle_hash=report.evidence_bundle.digital_signature_hmac_sha256 if report.evidence_bundle else None,
            traces_submission_status="UNSUBMITTED",
            payload_snapshot=payload.model_dump(mode="json"),
            full_report_snapshot=report.model_dump(mode="json"),
            evidence_bundle_snapshot=report.evidence_bundle.model_dump(mode="json") if report.evidence_bundle else None
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def list_executions(cls, db: Session, limit: int = 50) -> List[AuditExecutionRecord]:
        return db.query(AuditExecutionRecord).order_by(AuditExecutionRecord.id.desc()).limit(limit).all()

    @classmethod
    def get_by_execution_id(cls, db: Session, execution_id: str) -> Optional[AuditExecutionRecord]:
        return db.query(AuditExecutionRecord).filter(AuditExecutionRecord.execution_id == execution_id).first()

    @classmethod
    def update_traces_submission(
        cls,
        db: Session,
        execution_id: str,
        status: str,
        ack_number: str
    ) -> Optional[AuditExecutionRecord]:
        record = cls.get_by_execution_id(db, execution_id)
        if record:
            record.traces_submission_status = status
            record.traces_ack_number = ack_number
            db.commit()
            db.refresh(record)
        return record


class BatchJobRepository:

    @classmethod
    def create_job(
        cls,
        db: Session,
        job_id: str,
        total_plots: int = 0,
        supplier_id: Optional[str] = None,
        operator_name: Optional[str] = None,
        commodity_hs_code: Optional[str] = None
    ) -> BatchJobRecord:
        job = BatchJobRecord(
            job_id=job_id,
            status="QUEUED",
            progress_pct=0.0,
            current_step="Queued for processing",
            total_plots=total_plots,
            processed_plots=0,
            supplier_id=supplier_id,
            operator_name=operator_name,
            commodity_hs_code=commodity_hs_code,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def get_job(cls, db: Session, job_id: str) -> Optional[BatchJobRecord]:
        return db.query(BatchJobRecord).filter(BatchJobRecord.job_id == job_id).first()

    @classmethod
    def update_progress(
        cls,
        db: Session,
        job_id: str,
        status: str,
        progress_pct: float,
        current_step: str,
        processed_plots: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Optional[BatchJobRecord]:
        job = cls.get_job(db, job_id)
        if job:
            job.status = status
            job.progress_pct = progress_pct
            job.current_step = current_step
            if processed_plots is not None:
                job.processed_plots = processed_plots
            if error_message is not None:
                job.error_message = error_message
            db.commit()
            db.refresh(job)
        return job

    @classmethod
    def complete_job(
        cls,
        db: Session,
        job_id: str,
        execution_id: str,
        overall_status: str,
        result_snapshot: Dict[str, Any]
    ) -> Optional[BatchJobRecord]:
        job = cls.get_job(db, job_id)
        if job:
            job.status = "COMPLETED"
            job.progress_pct = 100.0
            job.current_step = "Evaluation complete"
            job.execution_id = execution_id
            job.overall_status = overall_status
            job.result_snapshot = result_snapshot
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            db.refresh(job)
        return job

    @classmethod
    def fail_job(
        cls,
        db: Session,
        job_id: str,
        error_message: str
    ) -> Optional[BatchJobRecord]:
        job = cls.get_job(db, job_id)
        if job:
            job.status = "FAILED"
            job.error_message = error_message
            job.current_step = f"Failed: {error_message}"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            db.refresh(job)
        return job


class ApiKeyRepository:
    """Repository for managing SaaS API Keys."""

    @classmethod
    def create_api_key(
        cls,
        db: Session,
        company_name: str,
        contact_email: str,
        tier: str = "STARTER"
    ) -> tuple[ApiKeyRecord, str]:
        import secrets
        import hashlib
        import uuid

        # Generate secure raw API key: eudr_live_<32 hex chars>
        raw_token = secrets.token_hex(24)
        raw_api_key = f"eudr_live_{raw_token}"
        
        # SHA256 hash for secure DB storage
        api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()
        key_id = f"key_{uuid.uuid4().hex[:12]}"
        
        quota_map = {
            "STARTER": 5000,
            "PRO": 50000,
            "ENTERPRISE": 1000000
        }
        rate_map = {
            "STARTER": 60,
            "PRO": 300,
            "ENTERPRISE": 1200
        }
        
        record = ApiKeyRecord(
            key_id=key_id,
            api_key_hash=api_key_hash,
            company_name=company_name,
            contact_email=contact_email,
            tier=tier.upper(),
            monthly_quota_plots=quota_map.get(tier.upper(), 5000),
            rate_limit_per_min=rate_map.get(tier.upper(), 60),
            is_active=True
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record, raw_api_key

    @classmethod
    def verify_api_key(cls, db: Session, raw_api_key: str) -> Optional[ApiKeyRecord]:
        import hashlib
        if not raw_api_key or not raw_api_key.startswith("eudr_live_"):
            return None
        
        target_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()
        record = db.query(ApiKeyRecord).filter(
            ApiKeyRecord.api_key_hash == target_hash,
            ApiKeyRecord.is_active == True
        ).first()
        return record


class LeadRepository:
    """
    Repository for managing enterprise leads and demo inquiries.
    """

    @classmethod
    def create_inquiry(
        cls,
        db: Session,
        company_name: str,
        contact_name: str,
        contact_email: str,
        phone: Optional[str] = None,
        commodity_type: str = "Timber",
        estimated_monthly_plots: str = "500 - 5,000",
        message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> LeadInquiryRecord:
        inquiry_id = f"lead_{uuid.uuid4().hex[:12]}"
        record = LeadInquiryRecord(
            inquiry_id=inquiry_id,
            company_name=company_name.strip(),
            contact_name=contact_name.strip(),
            contact_email=contact_email.strip().lower(),
            phone=phone.strip() if phone else None,
            commodity_type=commodity_type,
            estimated_monthly_plots=estimated_monthly_plots,
            message=message.strip() if message else None,
            ip_address=ip_address,
            user_agent=user_agent[:250] if user_agent else None,
            status="NEW",
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def list_inquiries(
        cls,
        db: Session,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[LeadInquiryRecord]:
        query = db.query(LeadInquiryRecord)
        if status:
            query = query.filter(LeadInquiryRecord.status == status)
        return query.order_by(LeadInquiryRecord.id.desc()).limit(limit).all()

    @classmethod
    def get_by_inquiry_id(cls, db: Session, inquiry_id: str) -> Optional[LeadInquiryRecord]:
        return db.query(LeadInquiryRecord).filter(LeadInquiryRecord.inquiry_id == inquiry_id).first()

