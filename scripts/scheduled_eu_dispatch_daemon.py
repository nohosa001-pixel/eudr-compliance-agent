"""
EUDR AGENT - European Business Hours Auto-Dispatcher Daemon
Waits until European Business Hours (Monday, 2026-11-02 09:00:00 CET / 17:00:00 KST / 08:00:00 UTC)
and automatically triggers the association announcement dispatch.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISPATCH_SCRIPT = PROJECT_ROOT / "scripts" / "dispatch_eu_association_announcements.py"

# Target dispatch time: 2026-11-02 08:00:00 UTC (09:00 CET / 17:00 KST)
TARGET_UTC = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)


def send_telegram_alert(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as ex:
        print(f"[!] Telegram alert error: {ex}")


def run_scheduled_daemon():
    print(f"[*] European Business Hours Dispatch Scheduler Armed.")
    print(f"[*] Target Dispatch Time (UTC): {TARGET_UTC.isoformat()}")
    print(f"[*] Target Dispatch Time (CET): Monday 09:00 AM")
    print(f"[*] Target Dispatch Time (KST): Monday 17:00 PM")

    while True:
        now_utc = datetime.now(timezone.utc)
        remaining = (TARGET_UTC - now_utc).total_seconds()

        if remaining <= 0:
            print(f"[!] TARGET TIME REACHED! Initiating European association announcement dispatch...")
            send_telegram_alert(
                "🇪🇺 *[EUDR.AGENT // EU MORNING DISPATCH TRIGGERED]*\n"
                "유럽 비즈니스 아침 09:00 CET에 도달했습니다.\n"
                "유럽 9대 수입 협회(ECF, EFIC, ETTF 등) 공식 기술 공지 메일 발송 파이프라인을 실행합니다."
            )
            
            # Execute dispatch script
            os.system(f"python {DISPATCH_SCRIPT}")
            print(f"[+] European association announcement dispatch completed.")
            break

        # Log heartbeat every hour or wait
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        print(f"[Scheduler Heartbeat] Waiting for European Monday Morning... Remaining: {hours}h {minutes}m")
        
        # Sleep up to 60 seconds between checks
        time.sleep(min(60, max(5, remaining)))


if __name__ == "__main__":
    run_scheduled_daemon()

