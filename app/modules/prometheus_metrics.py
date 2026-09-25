"""Prometheus APM Telemetry & Metrics Exporter for EUDRAgent.
Implements zero-dependency standard Prometheus / OpenMetrics 0.0.4 text format
for 24/7 continuous APM monitoring, agent transaction volume, and threat tracking.
Inspired by security-gate-x402 metrics architecture.
"""

import time
from typing import Dict, Any, List
from collections import defaultdict


class PrometheusMetricsCollector:
    """Singleton in-memory collector for EUDRAgent system metrics."""

    def __init__(self):
        self.start_time = time.time()
        
        # Counters: metric_name -> {label_tuple: count}
        self._counters: Dict[str, Dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        
        # Gauges: metric_name -> {label_tuple: value}
        self._gauges: Dict[str, Dict[tuple, float]] = defaultdict(lambda: defaultdict(float))

        # Initialize base metrics
        self.inc_counter("eudr_agent_requests_total", labels={"endpoint": "/health", "status": "200"})
        self.set_gauge("eudr_escrow_locked_usdc", 0.0, labels={"chain": "base"})
        self.set_gauge("eudr_escrow_locked_usdc", 0.0, labels={"chain": "polygon"})
        self.set_gauge("eudr_escrow_locked_usdc", 0.0, labels={"chain": "arbitrum"})

    def inc_counter(self, name: str, amount: float = 1.0, labels: Dict[str, str] = None):
        label_tuple = tuple(sorted((labels or {}).items()))
        self._counters[name][label_tuple] += amount

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        label_tuple = tuple(sorted((labels or {}).items()))
        self._gauges[name][label_tuple] = float(value)

    def render_prometheus_text(self) -> str:
        """Render all counters and gauges into official Prometheus 0.0.4 text lines."""
        lines: List[str] = []
        uptime = round(time.time() - self.start_time, 2)

        # 1. Uptime gauge
        lines.append("# HELP eudr_uptime_seconds Total runtime in seconds since agent boot.")
        lines.append("# TYPE eudr_uptime_seconds gauge")
        lines.append(f"eudr_uptime_seconds {uptime}")

        # 2. Gauges
        gauge_docs = {
            "eudr_escrow_locked_usdc": "Total USDC capital currently locked in Smart Escrow payment vaults.",
            "eudr_active_rfqs_count": "Active RFQs pending autonomous bid matching in A2A marketplace."
        }
        for name, values in self._gauges.items():
            doc = gauge_docs.get(name, f"Gauge metric for {name}")
            lines.append(f"# HELP {name} {doc}")
            lines.append(f"# TYPE {name} gauge")
            for label_tuple, val in values.items():
                label_str = ""
                if label_tuple:
                    pairs = [f'{k}="{v}"' for k, v in label_tuple]
                    label_str = "{" + ",".join(pairs) + "}"
                lines.append(f"{name}{label_str} {val}")

        # 3. Counters
        counter_docs = {
            "eudr_agent_requests_total": "Total API and MCP requests handled by EUDRAgent.",
            "eudr_escrow_settled_usdc_total": "Total volume of USDC successfully released to compliant sellers.",
            "eudr_escrow_slashed_usdc_total": "Total volume of USDC forfeited/slashed due to deforestation or fraud.",
            "eudr_satellite_inspections_total": "Count of Copernicus Sentinel SAR/NDVI radar inspections executed.",
            "eudr_security_gate_threats_blocked_total": "Count of malicious prompt injections or data falsifications blocked by x402.",
            "eudr_marketplace_rfqs_total": "Total volume of autonomous compliance RFQs created.",
            "eudr_marketplace_bids_total": "Total volume of bids submitted by supplier agents."
        }
        for name, values in self._counters.items():
            doc = counter_docs.get(name, f"Counter metric for {name}")
            lines.append(f"# HELP {name} {doc}")
            lines.append(f"# TYPE {name} counter")
            for label_tuple, val in values.items():
                label_str = ""
                if label_tuple:
                    pairs = [f'{k}="{v}"' for k, v in label_tuple]
                    label_str = "{" + ",".join(pairs) + "}"
                lines.append(f"{name}{label_str} {val}")

        return "\n".join(lines) + "\n"


# Global singleton instance
metrics_collector = PrometheusMetricsCollector()
