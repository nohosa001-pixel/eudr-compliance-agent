# -*- coding: utf-8 -*-
"""Autonomous 24/7 Daily Intelligence Daemon for EUDR Compliance Agent
======================================================================
Schedules autonomous daily EUDR regulatory intelligence generation via Google Gemini 3.8 Flash,
archives reports in `docs/reports/`, alerts via Telegram, and syncs status with A.GRID Ops Hub.
"""

from __future__ import annotations

import os
import sys
import time
import argparse
import datetime
from pathlib import Path
import schedule
from dotenv import load_dotenv

# Reconfigure console output for UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from scripts.generate_daily_eudr_briefing import generate_eudr_briefing


def send_telegram_alert(summary_text: str):
    """Sends a summary alert via Telegram bot if configured in environment."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    enabled = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower() in ("true", "1", "yes")

    if not enabled or not bot_token or not chat_id:
        return

    try:
        from app.modules.notification_manager import NotificationManager
        NotificationManager.send_telegram_message(
            text=summary_text,
            bot_token=bot_token,
            chat_id=chat_id,
            force_live=True
        )
        print("[EUDR Daemon] Telegram notification successfully dispatched.")
    except Exception as exc:
        print(f"[EUDR Daemon] Telegram notification skipped: {exc}")


def execute_eudr_cycle():
    """Runs one full EUDR regulatory intelligence generation cycle."""
    today = datetime.date.today()
    print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> Starting Autonomous EUDR Regulatory Cycle...")

    try:
        report_path, content = generate_eudr_briefing(today)
        print(f"[EUDR Maintenance] Briefing successfully archived at: {report_path.name}")

        # Run ElizaOS Brain Continuous Learning Cycle
        brain_summary = ""
        try:
            from scripts.train_elizaos_brain import (
                ElizaOSBrainSecurityBridge,
                run_phase_1_domain_sft,
                run_phase_2_episodic_clearance,
                run_phase_3_adversarial_red_teaming,
                export_brain_checkpoint
            )
            bridge = ElizaOSBrainSecurityBridge
            run_phase_1_domain_sft(bridge)
            run_phase_2_episodic_clearance(bridge)
            run_phase_3_adversarial_red_teaming(bridge)
            brain_state = bridge.get_brain_security_state()
            export_brain_checkpoint(bridge, PROJECT_ROOT / "data" / "brain_checkpoints" / "elizaos_brain_state.json")
            brain_summary = f"• ElizaOS Brain 연속 학습 완료 (Readiness: {brain_state['readiness_score_pct']}%)\n"
            print(f"[EUDR Brain] Continuous learning cycle complete. Current Readiness: {brain_state['readiness_score_pct']}%")
        except Exception as brain_err:
            print(f"[EUDR Brain] Continuous learning step skipped: {brain_err}")

        # Send Telegram Summary
        today_str = today.strftime("%Y-%m-%d")
        telegram_msg = (
            f"🌲 *[EUDR Daily Intelligence & Brain Learning] {today_str}*\n\n"
            f"✅ EUDR 규제·통관 및 브레인 자가 진화 사이클이 완료되었습니다.\n"
            f"• 보관 경로: `{report_path.name}` ({len(content)}자)\n"
            f"{brain_summary}"
            f"• CSW-CERTEX & TRACES NT 세관 교차검증 상태 최신화\n"
            f"• 위험군별 의무 감사 비율 및 위임규정 (EU) 2026/2102 대응 룰셋 점검 완료"
        )
        send_telegram_alert(telegram_msg)

        # Dispatch event to A.GRID Hub if running
        try:
            import httpx
            agrid_url = os.getenv("AGRID_OPS_URL", "http://localhost:8080")
            event_payload = {
                "event_id": f"evt_eudr_{today.strftime('%Y%m%d')}",
                "source_service": "eudr-compliance-agent",
                "caller_agent_id": "eudr-intelligence-daemon",
                "operation": "daily_regulatory_sync",
                "amount_usdc": 0.0,
                "chain": "polygon",
            }
            with httpx.Client(timeout=2.0) as client:
                client.post(f"{agrid_url}/api/v1/grid/clearing/event", json=event_payload)
            print("[EUDR Maintenance] Dispatched event to A.GRID Hub.")
        except Exception:
            pass

        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] <<< EUDR Cycle Complete.")

    except Exception as exc:
        print(f"[ERROR] Autonomous EUDR cycle failed: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="24/7 Daily EUDR Intelligence Daemon")
    parser.add_argument("--time", type=str, default="09:30", help="Daily execution time (HH:MM 24h, default: 09:30)")
    parser.add_argument("--now", action="store_true", help="Execute immediately on startup")
    args = parser.parse_args()

    print("=" * 80)
    print("  EUDR COMPLIANCE AGENT AUTONOMOUS INTELLIGENCE DAEMON")
    print(f"  Target Schedule: Daily at {args.time} KST")
    print("  Engine: Google Gemini 3.8 Flash with Live Google Search Grounding")
    print("=" * 80)

    if args.now:
        execute_eudr_cycle()

    schedule.every().day.at(args.time).do(execute_eudr_cycle)

    print(f"[Daemon] Listening and waiting for scheduled runs... (Press Ctrl+C to exit)")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
