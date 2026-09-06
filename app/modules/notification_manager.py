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

    @classmethod
    def notify_deforestation_alert(
        cls,
        execution_id: str,
        supplier_id: str,
        plot_id: str,
        country_code: str,
        loss_year: Optional[int] = None,
        loss_ratio_pct: float = 0.0,
        sensor_mode: str = "OPTICAL_COPERNICUS_HANSEN",
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Urgent Telegram alert when post-2020 deforestation is detected on production plots.
        """
        year_str = str(loss_year) if loss_year else "Post-2020 (Unspecified)"
        tg_text = (
            f"🚨 *[EUDR 긴급 경보] 산림 벌채(Deforestation) 감지!*\n\n"
            f"⚠️ *규정 위반 위험*: `Regulation (EU) 2023/1115 Art. 3(a)`\n"
            f"📍 *필지 ID*: `{plot_id}` ({country_code})\n"
            f"🏢 *공급업체*: `{supplier_id}`\n"
            f"🌲 *벌채 추정 연도*: *{year_str}*\n"
            f"📉 *산림 손실율*: *{loss_ratio_pct:.1f}%*\n"
            f"🛰️ *검증 센서*: `{sensor_mode}`\n"
            f"🆔 *Execution ID*: `{execution_id}`\n\n"
            f"🛑 *권고 조치*: 즉시 선적 보류 및 공급자 이의신청(HITL) 검토 요망."
        )
        logger.warning(f"[DEFORESTATION ALERT] Plot {plot_id} post-2020 loss in {country_code}")
        return cls.send_telegram_message(tg_text, parse_mode="Markdown", bot_token=bot_token, chat_id=chat_id)

    @classmethod
    def notify_dds_approved(
        cls,
        dds_reference_id: str,
        ack_number: str,
        operator_name: str,
        commodity_desc: str,
        net_mass_kg: float,
        plots_count: int,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Telegram alert when EU TRACES-NT DDS is registered and cleared for customs.
        """
        tg_text = (
            f"✅ *[EU TRACES-NT] 세관 녹색 통관(Green Lane) 승인!*\n\n"
            f"📜 *DDS 번호*: `{dds_reference_id}`\n"
            f"🏛️ *TRACES ACK*: `{ack_number}`\n"
            f"🏢 *수입 사업자*: {operator_name}\n"
            f"📦 *품목*: {commodity_desc} ({net_mass_kg:,.1f} kg)\n"
            f"🗺️ *검증 필지*: {plots_count}개 필지 100% 적합\n"
            f"🟢 *상태*: `EU SWE-C GREEN LANE CLEARED`"
        )
        logger.info(f"[TRACES APPROVED] {dds_reference_id} ACK: {ack_number}")
        return cls.send_telegram_message(tg_text, parse_mode="Markdown", bot_token=bot_token, chat_id=chat_id)

    @classmethod
    def notify_supplier_submission(
        cls,
        supplier_name: str,
        country_code: str,
        commodity_name: str,
        area_ha: float,
        has_gps: bool,
        is_compliant: bool,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Telegram alert when a smallholder or supplier submits pre-clearance documents via portal.
        """
        status_tag = "🟢 적합 (Green)" if is_compliant else "🟡 검토 요망 (Review)"
        gps_tag = "위치 확인됨 (WGS84)" if has_gps else "위치 정보 없음"
        tg_text = (
            f"🚜 *[소농/공급자 포털] 신규 사전 통관 서류 접수*\n\n"
            f"🧑‍🌾 *농가/공급자*: `{supplier_name}` ({country_code})\n"
            f"🌱 *품목*: {commodity_name}\n"
            f"📐 *경작 면적*: {area_ha:.2f} ha\n"
            f"📡 *GPS 좌표*: {gps_tag}\n"
            f"📊 *사전 진단*: {status_tag}"
        )
        logger.info(f"[SUPPLIER PORTAL SUBMISSION] {supplier_name} ({country_code})")
        return cls.send_telegram_message(tg_text, parse_mode="Markdown", bot_token=bot_token, chat_id=chat_id)

    @classmethod
    def notify_stripe_subscription(
        cls,
        customer_email: str,
        plan_name: str,
        amount_usd: float,
        session_id: str,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Telegram alert when a new enterprise subscription or payment is completed.
        """
        tg_text = (
            f"💳 *[EUDRAgent.com] 신규 유료 구독 결제 체결!*\n\n"
            f"📧 *고객*: `{customer_email}`\n"
            f"⭐ *구독 플랜*: *{plan_name}*\n"
            f"💵 *결제 금액*: `${amount_usd:,.2f} USD`\n"
            f"🧾 *세션 ID*: `{session_id[:16]}...`"
        )
        logger.info(f"[STRIPE PAYMENT SUCCESS] {customer_email} - {plan_name}")
        return cls.send_telegram_message(tg_text, parse_mode="Markdown", bot_token=bot_token, chat_id=chat_id)

