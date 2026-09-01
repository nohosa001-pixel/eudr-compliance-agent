import logging
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger("eudr_lead_notifications")

class NotificationManager:
    """
    Manages instant enterprise notifications for inbound customer leads,
    demo requests, and high-value compliance audit inquiries.
    """

    @classmethod
    def send_telegram_message(
        cls,
        text: str,
        parse_mode: str = "Markdown",
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Dispatches any message text directly to Telegram.
        """
        token = bot_token or settings.TELEGRAM_BOT_TOKEN
        cid = chat_id or settings.TELEGRAM_CHAT_ID

        if not token or not cid:
            logger.info(f"[TELEGRAM SIMULATED / NO CREDS] {text}")
            return False

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({
                "chat_id": cid,
                "text": text,
                "parse_mode": parse_mode
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Failed to dispatch Telegram message: {e}")
            return False

    @classmethod
    def notify_lead_received(
        cls,
        company_name: str,
        contact_name: str,
        contact_email: str,
        phone: Optional[str] = None,
        commodity_type: str = "Timber",
        estimated_monthly_plots: str = "500 - 5,000",
        message: Optional[str] = None,
        inquiry_id: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> bool:
        """
        Dispatches notification across available channels (Telegram, Webhook, and Logger).
        """
        token = telegram_bot_token or settings.TELEGRAM_BOT_TOKEN
        cid = telegram_chat_id or settings.TELEGRAM_CHAT_ID

        # 1. Structured Console / Log Notification
        lead_summary = (
            f"🔔 [NEW ENTERPRISE LEAD] ID: {inquiry_id}\n"
            f"  - Company: {company_name}\n"
            f"  - Contact: {contact_name} ({contact_email})\n"
            f"  - Phone: {phone or 'N/A'}\n"
            f"  - Commodity: {commodity_type}\n"
            f"  - Monthly Volume: {estimated_monthly_plots}\n"
            f"  - Message: {message or 'None'}"
        )
        logger.info(lead_summary)

        success = True

        # 2. Telegram Alert Dispatch (if configured)
        if token and cid:
            tg_text = (
                f"🌿 *[EUDRAgent.com] 신규 엔터프라이즈 데모/도입 문의*\n\n"
                f"🏢 *회사명*: `{company_name}`\n"
                f"👤 *담당자*: {contact_name}\n"
                f"📧 *이메일*: `{contact_email}`\n"
                f"📞 *연락처*: `{phone or '미입력'}`\n"
                f"📦 *품목*: {commodity_type}\n"
                f"📊 *예상 필지 규모*: {estimated_monthly_plots}\n"
                f"💬 *문의 내용*: {message or '내용 없음'}\n"
                f"🆔 *Inquiry ID*: `{inquiry_id}`"
            )
            success = cls.send_telegram_message(tg_text, parse_mode="Markdown", bot_token=token, chat_id=cid)

        # 3. Webhook Alert Dispatch (Slack / Discord / CRM if configured)
        if webhook_url:
            try:
                payload = json.dumps({
                    "event": "eudr.lead.created",
                    "inquiry_id": inquiry_id,
                    "company_name": company_name,
                    "contact_name": contact_name,
                    "contact_email": contact_email,
                    "phone": phone,
                    "commodity_type": commodity_type,
                    "estimated_monthly_plots": estimated_monthly_plots,
                    "message": message
                }).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    pass
            except Exception as e:
                logger.error(f"Failed to dispatch Webhook lead alert: {e}")
                success = False

        return success
