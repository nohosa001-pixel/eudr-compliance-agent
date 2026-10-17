"""
Outbound Webhooks Endpoints for SAP, ERP, and Enterprise Systems Integration.
"""
from typing import Optional, Any
from fastapi import APIRouter, Depends, status

import importlib
try:
    _sa_orm = importlib.import_module("sqlalchemy.orm")
    Session = getattr(_sa_orm, "Session")
except Exception:
    Session = Any  # type: ignore

from app.core.config import settings
from app.db.session import get_db
from app.modules.webhook_dispatcher import WebhookDispatcher
from app.schemas import (
    WebhookSubscribeRequest,
    WebhookSubscribeResponse,
    WebhookTestRequest,
    WebhookTestResponse,
)

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/webhooks",
    tags=["Outbound Webhooks (SAP / ERP Integration)"]
)


@router.post(
    "/subscribe",
    response_model=WebhookSubscribeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe client ERP system to EUDR.agent outbound events"
)
async def subscribe_webhook(
    req: WebhookSubscribeRequest,
    db: Session = Depends(get_db)
):
    """
    Registers an external HTTPS endpoint (e.g. SAP, Oracle SCM, customs ERP) to receive signed events.
    Events include batch.completed, dds.generated, compliance.alert.
    """
    sub = WebhookDispatcher.create_subscription(
        target_url=req.target_url,
        company_name=req.company_name,
        events=req.events,
        secret_token=req.secret_token,
        db_session=db
    )
    return WebhookSubscribeResponse(**sub)


@router.get(
    "",
    summary="List active outbound webhook subscriptions"
)
async def list_webhooks(
    company_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Lists active client webhook subscriptions.
    """
    return WebhookDispatcher.list_subscriptions(company_name=company_name, db_session=db)


@router.post(
    "/test",
    response_model=WebhookTestResponse,
    summary="Send diagnostic test ping to subscriber target URL"
)
async def test_webhook(req: WebhookTestRequest):
    """
    Sends an immediate diagnostic test event (system.ping) signed with HMAC-SHA256.
    """
    res = await WebhookDispatcher.send_test_ping(target_url=req.target_url, secret_token=req.secret_token)
    return WebhookTestResponse(
        success=res.get("success", False),
        status_code=res.get("status_code"),
        message="Test webhook delivered successfully" if res.get("success") else f"Delivery failed: {res.get('response_body')}",
        delivered_payload=res
    )
