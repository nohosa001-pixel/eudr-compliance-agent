import pytest
import uuid
import base64
import json
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.core.celery_app import celery_app
from app.schemas import (
    EUDRSupplyChainPayload,
    OperatorInfo,
    CommodityInfo,
    ProductionPlotInput,
    LegalDocumentInput,
    DocumentTypeEnum,
    BatchJobStatusEnum
)
from app.modules.batch_job_manager import BatchJobManager
from app.tasks.eudr_tasks import (
    run_pipeline_sync,
    run_file_pipeline_sync,
    evaluate_supply_chain_task,
    parse_and_evaluate_file_task
)
from app.db.session import SessionLocal
from app.db.repository import BatchJobRepository


@pytest.fixture
def sample_payload_dict():
    payload = {
        "execution_id": f"exec-celery-{uuid.uuid4().hex[:6]}",
        "supplier_id": "SUPPLIER-CELERY-789",
        "operator": {
            "operator_name": "EuroWood Importers GmbH",
            "eori_number": "DE123456789012345",
            "vat_number": "DE987654321",
            "country": "DE",
            "address": "Holzweg 10, 20095 Hamburg, Germany"
        },
        "commodity": {
            "hs_code": "440711",
            "description": "Coniferous wood sawn or chipped lengthwise",
            "net_mass_kg": 25000.0,
            "volume_m3": 45.0,
            "scientific_name": "Pinus sylvestris"
        },
        "plots": [
            {
                "plot_id": "PLOT-SE-001",
                "country_code": "SE",
                "area_hectares": 2.8,
                "geometry": {
                    "type": "Point",
                    "coordinates": [18.060000, 59.320000]
                },
                "production_date": "2024-04-15",
                "producer_name": "Nordic Timber Coop"
            }
        ],
        "documents": [
            {
                "doc_id": "DOC-SE-TITLE",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Swedish Forest Agency (Skogsstyrelsen)",
                "issue_date": "2021-01-10",
                "expiry_date": "2031-01-10",
                "file_hash": "a1b2c3d4e5f67890"
            },
            {
                "doc_id": "DOC-SE-LIC",
                "doc_type": "BUSINESS_LICENSE",
                "issuing_authority": "Swedish Companies Registration Office",
                "issue_date": "2020-05-01"
            }
        ]
    }
    return payload


def test_celery_app_initialization():
    """Verify Celery app instance is properly initialized and configured."""
    assert celery_app is not None
    assert celery_app.main == "eudr_compliance_worker"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.enable_utc is True
    assert celery_app.conf.task_acks_late is True


def test_celery_pipeline_sync_execution(sample_payload_dict):
    """Verify synchronous execution logic for Celery tasks updates DB records."""
    job_id = f"JOB-TEST-CELERY-{uuid.uuid4().hex[:6].upper()}"
    
    db = SessionLocal()
    try:
        BatchJobRepository.create_job(db=db, job_id=job_id, total_plots=2)
    finally:
        db.close()

    result = run_pipeline_sync(job_id=job_id, payload_dict=sample_payload_dict)

    assert result["status"] == "COMPLETED"
    assert result["job_id"] == job_id
    assert result["overall_status"] == "COMPLIANT"
    assert "report" in result

    # Check DB state
    db = SessionLocal()
    try:
        record = BatchJobRepository.get_job(db, job_id)
        assert record is not None
        assert record.status == BatchJobStatusEnum.COMPLETED.value
        assert record.progress_pct == 100.0
        assert record.overall_status == "COMPLIANT"
    finally:
        db.close()


def test_celery_file_pipeline_sync_execution():
    """Verify synchronous file pipeline execution logic for Celery."""
    job_id = f"JOB-TEST-FILE-CELERY-{uuid.uuid4().hex[:6].upper()}"

    geojson_content = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"plot_id": "GEO-CELERY-001", "country_code": "SE"},
                "geometry": {"type": "Point", "coordinates": [15.0, 60.0]}
            }
        ]
    }
    raw_bytes = json.dumps(geojson_content).encode("utf-8")
    b64_bytes = base64.b64encode(raw_bytes).decode("utf-8")

    db = SessionLocal()
    try:
        BatchJobRepository.create_job(db=db, job_id=job_id, total_plots=1)
    finally:
        db.close()

    result = run_file_pipeline_sync(
        job_id=job_id,
        filename="test_farms.geojson",
        content_bytes_b64=b64_bytes,
        supplier_id="SUPP-GEO-CELERY",
        operator_name="Nordic Coffee AB",
        hs_code="090111",
        commodity_desc="Arabica Coffee"
    )

    assert result["status"] == "COMPLETED"
    assert result["job_id"] == job_id

    db = SessionLocal()
    try:
        record = BatchJobRepository.get_job(db, job_id)
        assert record is not None
        assert record.status == BatchJobStatusEnum.COMPLETED.value
    finally:
        db.close()


def test_batch_job_manager_hybrid_fallback(sample_payload_dict):
    """Verify BatchJobManager falls back to local thread execution when distributed queue is not active."""
    payload = EUDRSupplyChainPayload.model_validate(sample_payload_dict)
    
    # Force USE_DISTRIBUTED_QUEUE to False
    with patch.object(settings, "USE_DISTRIBUTED_QUEUE", False):
        submit_resp = BatchJobManager.create_and_start_job_from_payload(payload)
        assert submit_resp.status == BatchJobStatusEnum.QUEUED
        assert submit_resp.job_id.startswith("JOB-")

        # Query status
        status_resp = BatchJobManager.get_job_status(submit_resp.job_id)
        assert status_resp is not None
        assert status_resp.job_id == submit_resp.job_id


def test_batch_job_manager_distributed_dispatch_mock(sample_payload_dict):
    """Verify BatchJobManager calls Celery delay when distributed queue is available."""
    payload = EUDRSupplyChainPayload.model_validate(sample_payload_dict)

    with patch.object(BatchJobManager, "is_distributed_queue_available", return_value=True):
        with patch.object(evaluate_supply_chain_task, "delay") as mock_delay:
            submit_resp = BatchJobManager.create_and_start_job_from_payload(payload)
            assert submit_resp.status == BatchJobStatusEnum.QUEUED
            assert "Celery distributed worker" in submit_resp.message
            mock_delay.assert_called_once()
