#!/usr/bin/env python3
"""
Synthetic Canary Health Prober for EUDRAgent.com.
Performs end-to-end continuous health probing across all core compliance modules:
1. System Liveness & Health Endpoint
2. GIS Plot Geometry & Boundary Verification
3. Satellite Deforestation Analysis past 2020 baseline
4. EU Commission VIES VAT Number Validation
5. TRACES-NT Due Diligence Statement (DDS) XML Generation
6. SHA-256 Cryptographic Chain of Custody Integrity Check

Usage:
    python scripts/canary_health_prober.py
    python scripts/canary_health_prober.py --url https://eudragent.com
"""

import sys
import time
import json
import argparse
from typing import Dict, Any, List
from datetime import datetime, timezone

# Ensure project root is on sys.path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi.testclient import TestClient
from app.main import app

class CanaryHealthProber:
    def __init__(self, target_url: str = None):
        self.target_url = target_url
        if not target_url:
            self.client = TestClient(app)
        else:
            import requests
            self.client = requests.Session()
            self.base_url = target_url.rstrip("/")

    def _post(self, path: str, json_data: Dict[str, Any]) -> tuple[int, Dict[str, Any], float]:
        start = time.perf_counter()
        if self.target_url:
            resp = self.client.post(f"{self.base_url}{path}", json=json_data, timeout=10)
            latency_ms = (time.perf_counter() - start) * 1000
            try:
                return resp.status_code, resp.json(), latency_ms
            except Exception:
                return resp.status_code, {"raw": resp.text}, latency_ms
        else:
            resp = self.client.post(path, json=json_data)
            latency_ms = (time.perf_counter() - start) * 1000
            try:
                return resp.status_code, resp.json(), latency_ms
            except Exception:
                return resp.status_code, {"raw": resp.text}, latency_ms

    def _get(self, path: str) -> tuple[int, Dict[str, Any], float]:
        start = time.perf_counter()
        if self.target_url:
            resp = self.client.get(f"{self.base_url}{path}", timeout=10)
            latency_ms = (time.perf_counter() - start) * 1000
            try:
                return resp.status_code, resp.json(), latency_ms
            except Exception:
                return resp.status_code, {"raw": resp.text}, latency_ms
        else:
            resp = self.client.get(path)
            latency_ms = (time.perf_counter() - start) * 1000
            try:
                return resp.status_code, resp.json(), latency_ms
            except Exception:
                return resp.status_code, {"raw": resp.text}, latency_ms

    def run_all_probes(self) -> bool:
        print("=" * 70)
        target_name = self.target_url or "In-Process TestClient (Local)"
        print(f"[CANARY] EUDRAgent Synthetic Canary Prober Starting: [{target_name}]")
        print(f"[TIME]   Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}")
        print("=" * 70)

        results = []

        # 1. Liveness & Health Probe
        status_code, data, latency = self._get("/health")
        passed = (status_code == 200 and data.get("status") == "healthy")
        results.append(("1. System Health & Liveness", passed, latency, f"status={data.get('status')}"))

        # 2. GIS Plot Validation Probe (Art. 9)
        status_code, data, latency = self._post("/api/v1/agent/tools/execute", {
            "tool_name": "eudr_verify_plot",
            "arguments": {
                "plot_id": "CANARY-PLOT-BRAZIL-01",
                "country_code": "BR",
                "commodity": "soya",
                "coordinates": [
                    [-55.500000, -12.500000],
                    [-55.490000, -12.500000],
                    [-55.490000, -12.490000],
                    [-55.500000, -12.490000],
                    [-55.500000, -12.500000]
                ],
                "area_hectares": 12.0
            }
        })
        passed = (status_code == 200 and data.get("result", {}).get("is_valid") is True)
        results.append(("2. GIS Plot Polygon Geometry", passed, latency, f"valid={data.get('result', {}).get('is_valid')}"))

        # 3. Satellite Deforestation Radar Probe (Art. 10)
        status_code, data, latency = self._post("/api/v1/agent/tools/execute", {
            "tool_name": "eudr_check_deforestation",
            "arguments": {
                "plot_id": "CANARY-PLOT-BRAZIL-01",
                "country_code": "BR",
                "coordinates": [-55.500000, -12.500000],
                "cutoff_date": "2020-12-31"
            }
        })
        passed = (status_code == 200 and data.get("result", {}).get("status") == "COMPLIANT")
        results.append(("3. Satellite Deforestation Check", passed, latency, f"status={data.get('result', {}).get('status')}"))

        # 4. EU Commission VIES VAT Engine Probe
        status_code, data, latency = self._post("/api/v1/agent/tools/execute", {
            "tool_name": "eudr_verify_vies_vat",
            "arguments": {
                "country_code": "NL",
                "vat_number": "858585858B01"
            }
        })
        passed = (status_code == 200 and "is_valid" in data.get("result", {}))
        results.append(("4. EU Commission VIES VAT Engine", passed, latency, f"consultation={data.get('result', {}).get('consultation_number', 'OK')}"))

        # 5. TRACES-NT DDS XML Generation Probe
        status_code, data, latency = self._post("/api/v1/agent/tools/execute", {
            "tool_name": "eudr_generate_dds",
            "arguments": {
                "operator_name": "Rotterdam Cocoa Trading BV",
                "operator_vat": "NL858585858B01",
                "commodity": "cocoa",
                "total_net_mass_kg": 25000.0,
                "plot_ids": ["CANARY-PLOT-BRAZIL-01"]
            }
        })
        passed = (status_code == 200 and "dds_reference_id" in data.get("result", {}))
        ref_id = data.get("result", {}).get("dds_reference_id", "N/A")
        results.append(("5. TRACES-NT DDS XML Engine", passed, latency, f"ref={ref_id}"))

        # 6. Cryptographic Chain of Custody SHA-256 Probe
        sample_audit = {"ref": ref_id, "ts": datetime.now(timezone.utc).isoformat()}
        from app.modules.audit_integrity_verifier import AuditIntegrityVerifier
        calc_hash = AuditIntegrityVerifier.compute_sha256(sample_audit)

        status_code, data, latency = self._post("/api/v1/agent/tools/execute", {
            "tool_name": "eudr_verify_audit_integrity",
            "arguments": {
                "audit_payload": sample_audit,
                "expected_hash": calc_hash
            }
        })
        passed = (status_code == 200 and data.get("result", {}).get("is_tamper_free") is True)
        results.append(("6. SHA-256 Audit Integrity Check", passed, latency, f"tamper_free={data.get('result', {}).get('is_tamper_free')}"))

        # Print Summary
        all_passed = True
        print(f"\n{'Probe Name':<35} | {'Status':<8} | {'Latency':<10} | {'Detail'}")
        print("-" * 75)
        for name, p, lat, detail in results:
            status_str = "[PASS]" if p else "[FAIL]"
            if not p:
                all_passed = False
            print(f"{name:<35} | {status_str:<8} | {lat:>7.1f} ms | {detail}")

        print("=" * 75)
        if all_passed:
            print("[SUCCESS] ALL CANARY HEALTH PROBES PASSED WITH ZERO ERRORS!")
        else:
            print("[ALERT] CANARY PROBE DETECTED DEGRADATIONS OR FAILURES!")
            # Trigger notification if available
            try:
                from app.modules.notification_manager import NotificationManager
                NotificationManager.send_telegram_message(
                    f"⚠️ *[Canary Alert]* EUDRAgent Health Probe Detected an Issue on `{target_name}`!"
                )
            except Exception:
                pass

        return all_passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EUDRAgent synthetic canary prober.")
    parser.add_argument("--url", help="Target remote URL (e.g. https://eudragent.com)")
    args = parser.parse_args()

    prober = CanaryHealthProber(target_url=args.url)
    success = prober.run_all_probes()
    sys.exit(0 if success else 1)
