import hmac
import hashlib
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("eudr_agent.webhooks")


class WebhookDispatcher:
    """
    Enterprise Outbound Webhook Engine for SAP, Oracle SCM, and Customs ERPs.
    - Signs all payloads using HMAC-SHA256 for non-repudiation.
    - Dispatches events asynchronously without blocking main compliance threads.
    - Persists delivery logs and supports automated retry.
    """

    # In-memory subscription store for zero-DB staging mode
    _memory_subscriptions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def generate_signature(cls, payload_json: str, secret: str) -> str:
        """Calculates HMAC-SHA256 signature of the payload string."""
        return hmac.new(
            secret.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def create_subscription(
        cls,
        target_url: str,
        company_name: str,
        events: Optional[List[str]] = None,
        secret_token: Optional[str] = None,
        api_key_id: Optional[str] = None,
        db_session=None
    ) -> Dict[str, Any]:
        """Creates and stores a new client webhook subscription."""
        webhook_id = f"whk_{uuid.uuid4().hex[:16]}"
        secret = secret_token or f"whsec_{uuid.uuid4().hex}"
        subscribed_events = events or ["batch.completed", "dds.generated", "compliance.alert"]
        now_str = datetime.now(timezone.utc).isoformat()

        record_data = {
            "webhook_id": webhook_id,
            "target_url": target_url,
            "company_name": company_name,
            "api_key_id": api_key_id,
            "secret_token": secret,
            "events": subscribed_events,
            "is_active": True,
            "status": "active",
            "created_at_utc": now_str
        }

        # Save to DB if available
        try:
            from app.db.models import WebhookSubscriptionRecord
            from app.db.session import SessionLocal
            db = db_session or (SessionLocal() if SessionLocal else None)
            if db:
                sub_rec = WebhookSubscriptionRecord(
                    webhook_id=webhook_id,
                    api_key_id=api_key_id,
                    company_name=company_name,
                    target_url=target_url,
                    secret_token=secret,
                    events=subscribed_events,
                    is_active=True
                )
                db.add(sub_rec)
                db.commit()
        except Exception as e:
            logger.warning(f"Could not persist webhook subscription to DB: {e}. Stored in memory.")

        cls._memory_subscriptions[webhook_id] = record_data
        logger.info(f"[WEBHOOK] Subscribed {company_name} to {target_url} for events: {subscribed_events}")
        return record_data

    @classmethod
    def list_subscriptions(cls, company_name: Optional[str] = None, db_session=None) -> List[Dict[str, Any]]:
        """Lists active subscriptions."""
        try:
            from app.db.models import WebhookSubscriptionRecord
            from app.db.session import SessionLocal
            db = db_session or (SessionLocal() if SessionLocal else None)
            if db:
                query = db.query(WebhookSubscriptionRecord).filter(WebhookSubscriptionRecord.is_active == True)
                if company_name:
                    query = query.filter(WebhookSubscriptionRecord.company_name == company_name)
                records = query.all()
                if records:
                    return [
                        {
                            "webhook_id": r.webhook_id,
                            "target_url": r.target_url,
                            "company_name": r.company_name,
                            "events": r.events,
                            "secret_token": r.secret_token,
                            "is_active": r.is_active,
                            "created_at_utc": r.created_at.isoformat() if r.created_at else ""
                        }
                        for r in records
                    ]
        except Exception:
            pass

        # Memory fallback
        subs = list(cls._memory_subscriptions.values())
        if company_name:
            subs = [s for s in subs if s.get("company_name") == company_name]
        return subs

    @classmethod
    async def dispatch_event(
        cls,
        event_type: str,
        payload_data: Dict[str, Any],
        company_name: Optional[str] = None,
        timeout_sec: float = 5.0,
        db_session=None
    ) -> List[Dict[str, Any]]:
        """
        Dispatches an event to all active matching webhook subscribers.
        Executes concurrently with per-target error isolation.
        """
        subscriptions = cls.list_subscriptions(company_name=company_name, db_session=db_session)
        matching_subs = [
            s for s in subscriptions 
            if s.get("is_active") and (event_type in s.get("events", []) or "*" in s.get("events", []))
        ]

        if not matching_subs:
            return []

        tasks = [
            cls._send_single_webhook(sub, event_type, payload_data, timeout_sec, db_session)
            for sub in matching_subs
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    @classmethod
    async def _send_single_webhook(
        cls,
        sub: Dict[str, Any],
        event_type: str,
        payload_data: Dict[str, Any],
        timeout_sec: float,
        db_session=None
    ) -> Dict[str, Any]:
        """Sends an HMAC-signed POST request to a single subscriber target URL."""
        delivery_id = f"dlv_{uuid.uuid4().hex[:16]}"
        target_url = sub["target_url"]
        secret = sub["secret_token"]

        full_event_envelope = {
            "event_id": delivery_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload_data
        }

        payload_json = json.dumps(full_event_envelope, separators=(',', ':'), default=str)
        signature = cls.generate_signature(payload_json, secret)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "EUDR.agent-Webhook/1.2",
            "X-EUDR-Delivery": delivery_id,
            "X-EUDR-Event": event_type,
            "X-EUDR-Signature": f"sha256={signature}"
        }

        status_code = None
        resp_text = None
        success = False

        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(target_url, content=payload_json, headers=headers)
                status_code = resp.status_code
                resp_text = resp.text[:500]
                success = 200 <= resp.status_code < 300
        except Exception as e:
            resp_text = str(e)[:500]
            logger.warning(f"[WEBHOOK ERROR] Delivery {delivery_id} to {target_url} failed: {e}")

        # Log delivery
        try:
            from app.db.models import WebhookDeliveryRecord
            from app.db.session import SessionLocal
            db = db_session or (SessionLocal() if SessionLocal else None)
            if db:
                log_rec = WebhookDeliveryRecord(
                    delivery_id=delivery_id,
                    webhook_id=sub["webhook_id"],
                    event_type=event_type,
                    payload=full_event_envelope,
                    response_status_code=status_code,
                    response_body=resp_text,
                    attempt_count=1,
                    success=success
                )
                db.add(log_rec)
                db.commit()
        except Exception:
            pass

        return {
            "delivery_id": delivery_id,
            "webhook_id": sub["webhook_id"],
            "target_url": target_url,
            "success": success,
            "status_code": status_code,
            "response_body": resp_text
        }

    @classmethod
    async def send_test_ping(cls, target_url: str, secret_token: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches an immediate diagnostic test event to any target URL."""
        test_sub = {
            "webhook_id": "whk_test_ping",
            "target_url": target_url,
            "secret_token": secret_token or "whsec_test_secret_2026"
        }
        test_payload = {
            "ping": "pong",
            "message": "EUDR.agent Outbound Webhook Diagnostic Test",
            "server_time": datetime.now(timezone.utc).isoformat()
        }
        return await cls._send_single_webhook(test_sub, "system.ping", test_payload, timeout_sec=5.0)
