import pytest
from unittest.mock import patch
from app.modules.notification_manager import NotificationManager

def test_telegram_lead_notification_formatting():
    with patch.object(NotificationManager, "send_telegram_message", return_value=True) as mock_send:
        res = NotificationManager.notify_lead_received(
            company_name="Hamburg Coffee Traders GmbH",
            contact_name="Hans Schmidt",
            contact_email="schmidt@hamburgcoffee.de",
            phone="+49 40 123456",
            commodity_type="Coffee",
            estimated_monthly_plots="1,000 - 5,000",
            message="Need EUDR compliance integration for green coffee imports",
            inquiry_id="INQ-TEST-001",
            telegram_bot_token="fake_bot_token",
            telegram_chat_id="fake_chat_id"
        )

        assert res is True
        mock_send.assert_called_once()
        msg_text = mock_send.call_args[0][0]
        assert "Hamburg Coffee Traders GmbH" in msg_text
        assert "schmidt@hamburgcoffee.de" in msg_text
        assert "Coffee" in msg_text

def test_telegram_deforestation_alert():
    with patch.object(NotificationManager, "send_telegram_message", return_value=True) as mock_send:
        res = NotificationManager.notify_deforestation_alert(
            execution_id="EXEC-DEF-999",
            supplier_id="SUPP-AMAZON-01",
            plot_id="PLOT-BRAZIL-PARA-44",
            country_code="BR",
            loss_year=2023,
            loss_ratio_pct=14.5,
            sensor_mode="SENTINEL_1_SAR_RADAR",
            bot_token="fake_token",
            chat_id="fake_chat"
        )

        assert res is True
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "산림 벌채(Deforestation) 감지" in msg
        assert "PLOT-BRAZIL-PARA-44" in msg
        assert "2023" in msg
        assert "14.5%" in msg
        assert "SENTINEL_1_SAR_RADAR" in msg

def test_telegram_dds_approved_notification():
    with patch.object(NotificationManager, "send_telegram_message", return_value=True) as mock_send:
        res = NotificationManager.notify_dds_approved(
            dds_reference_id="DDS-EUDR-2026-X99",
            ack_number="EU-TRACES-ACK-2026-8888",
            operator_name="Rotterdam Timber Group",
            commodity_desc="Teak Logs",
            net_mass_kg=45000.0,
            plots_count=12,
            bot_token="fake_token",
            chat_id="fake_chat"
        )

        assert res is True
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "DDS-EUDR-2026-X99" in msg
        assert "EU-TRACES-ACK-2026-8888" in msg
        assert "Rotterdam Timber Group" in msg
        assert "GREEN LANE CLEARED" in msg

def test_telegram_supplier_portal_submission():
    with patch.object(NotificationManager, "send_telegram_message", return_value=True) as mock_send:
        res = NotificationManager.notify_supplier_submission(
            supplier_name="Nguyen Van Nam",
            country_code="VN",
            commodity_name="Robusta Coffee",
            area_ha=3.2,
            has_gps=True,
            is_compliant=True,
            bot_token="fake_token",
            chat_id="fake_chat"
        )

        assert res is True
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "Nguyen Van Nam" in msg
        assert "Robusta Coffee" in msg
        assert "3.20 ha" in msg
        assert "위치 확인됨" in msg
        assert "적합 (Green)" in msg

def test_telegram_stripe_subscription_notification():
    with patch.object(NotificationManager, "send_telegram_message", return_value=True) as mock_send:
        res = NotificationManager.notify_stripe_subscription(
            customer_email="compliance@eurosupply.eu",
            plan_name="Enterprise Scale Tier",
            amount_usd=499.0,
            session_id="cs_test_a1b2c3d4e5f6g7h8",
            bot_token="fake_token",
            chat_id="fake_chat"
        )

        assert res is True
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "compliance@eurosupply.eu" in msg
        assert "Enterprise Scale Tier" in msg
        assert "$499.00 USD" in msg
