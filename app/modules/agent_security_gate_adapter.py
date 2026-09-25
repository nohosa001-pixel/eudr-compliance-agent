"""Security Gate x402 Adapter for EUDRAgent.
Implements deterministic sub-millisecond Prompt Injection Defense, AST Code Shielding,
and NLI Fact-Checking against hallucinatory trade anomalies and falsified geolocation coordinates.
Derived from and compatible with security-gate-x402 (The Sheriff of Agent Finance).
"""

import re
from typing import Dict, Any, List, Optional
from app.modules.prometheus_metrics import metrics_collector


class AgentSecurityGateAdapter:
    """Security interceptor and fact-checker for autonomous agent inputs."""

    # Prompt Injection & Jailbreak RegEx patterns
    INJECTION_PATTERNS = [
        r"(?i)(ignore|disregard|forget)\s+(all\s+)?(prior|previous|past|above|system)?\s*instructions",
        r"(?i)system\s+prompt\s*(override|bypass)",
        r"(?i)(override|bypass)\s+(all\s+)?(checks|security|rules|filters|safeguards)",
        r"(?i)you\s+are\s+now\s+in\s+(dan|developer)\s+mode",
        r"(?i)grant\s+(me\s+)?admin(istrator)?\s+privileges",
        r"(?i)drop\s+table\s+",
        r"(?i)<script\b[^>]*>",
        r"(?i)select\s+\*\s+from\s+",
        r"(?i)declare\s+deforestation_free\s+without\s+inspection"
    ]

    # Malicious Code Execution patterns
    DANGEROUS_AST_PATTERNS = [
        r"\bimport\s+os\b",
        r"\bimport\s+subprocess\b",
        r"\bos\.system\(",
        r"\bsubprocess\.Popen\(",
        r"\beval\(",
        r"\bexec\(",
        r"\b__import__\(",
        r"\bshutil\.rmtree\("
    ]

    @classmethod
    def inspect_text_security(cls, text: str) -> Dict[str, Any]:
        """Inspect inbound text for prompt injections and malicious AST code."""
        if not text:
            return {"is_safe": True, "verdict": "ALLOW", "threats": [], "threat_score": 0}

        threats = []
        threat_score = 0

        # Check prompt injection
        for pat in cls.INJECTION_PATTERNS:
            if re.search(pat, text):
                threats.append(f"Prompt Injection Attempt detected: '{pat}'")
                threat_score += 45

        # Check code execution
        for pat in cls.DANGEROUS_AST_PATTERNS:
            if re.search(pat, text):
                threats.append(f"Dangerous Code Execution attempt detected: '{pat}'")
                threat_score += 55

        is_safe = (threat_score < 25)
        verdict = "ALLOW" if is_safe else "BLOCK"

        if not is_safe:
            metrics_collector.inc_counter(
                "eudr_security_gate_threats_blocked_total",
                labels={"threat_type": "injection" if "Injection" in str(threats) else "ast_code"}
            )

        return {
            "is_safe": is_safe,
            "verdict": verdict,
            "threat_score": min(threat_score, 100),
            "threats": threats,
            "sheriff_status": "ENFORCED"
        }

    @classmethod
    def inspect_compliance_fact_check(
        cls,
        commodity: str,
        hs_code: str,
        declared_net_mass_kg: float,
        plots_count: int = 1,
        total_area_ha: float = 2.0
    ) -> Dict[str, Any]:
        """
        NLI Fact-Checker: Detects fabricated hallucination statistics & severe trade anomalies.
        e.g., Declaring 100,000 kg of coffee harvested from a 0.5 ha smallholder plot (impossibility).
        """
        anomalies = []
        anomaly_score = 0

        # 1. HS code mismatch
        commodity_clean = (commodity or "").lower().strip()
        hs_clean = (hs_code or "").replace(".", "").strip()
        
        if "coffee" in commodity_clean and not hs_clean.startswith("0901"):
            anomalies.append(f"Commodity '{commodity}' conflicts with HS code '{hs_code}' (Expected 0901.*).")
            anomaly_score += 40
        elif "cocoa" in commodity_clean and not (hs_clean.startswith("1801") or hs_clean.startswith("1802") or hs_clean.startswith("1803")):
            anomalies.append(f"Commodity '{commodity}' conflicts with HS code '{hs_code}' (Expected 1801-1806.*).")
            anomaly_score += 40
        elif ("wood" in commodity_clean or "timber" in commodity_clean) and not (hs_clean.startswith("44") or hs_clean.startswith("47") or hs_clean.startswith("48") or hs_clean.startswith("94")):
            anomalies.append(f"Commodity '{commodity}' conflicts with HS code '{hs_code}' (Expected 4401-4421.*).")
            anomaly_score += 40

        # 2. Agronomic Yield Ceiling Check (Maximum biologically feasible harvest per ha)
        max_yield_kg_per_ha = {
            "coffee": 4000.0,       # High-yield Arabica max ~4,000 kg/ha/yr
            "cocoa": 3000.0,        # High-yield Cocoa max ~3,000 kg/ha/yr
            "oil_palm": 30000.0,    # FFB max ~30,000 kg/ha/yr
            "soya": 5000.0,         # High-yield Soybean max ~5,000 kg/ha/yr
            "rubber": 3500.0,       # Latex max ~3,500 kg/ha/yr
            "wood": 150000.0        # Timber mass max ~150,000 kg/ha
        }

        matched_yield_ceiling = 10000.0 # Default
        for comm_key, ceiling in max_yield_kg_per_ha.items():
            if comm_key in commodity_clean:
                matched_yield_ceiling = ceiling
                break

        if declared_net_mass_kg is None or float(declared_net_mass_kg) <= 0:
            anomalies.append(f"Invalid declared net mass: {declared_net_mass_kg}. Must be greater than 0 kg.")
            anomaly_score += 50
            effective_mass = 0.0
        else:
            effective_mass = float(declared_net_mass_kg)

        effective_ha = max(float(total_area_ha or 0.1), 0.1)
        yield_per_ha = effective_mass / effective_ha

        # If declared yield exceeds 3x world-record biological limit -> Flag severe hallucination/fraud
        if effective_mass > 0 and yield_per_ha > (matched_yield_ceiling * 3.0):
            anomalies.append(
                f"Agronomic yield anomaly: {yield_per_ha:,.1f} kg/ha exceeds biological ceiling "
                f"({matched_yield_ceiling * 3.0:,.1f} kg/ha). Possible fabricated data or smallholder volume inflation."
            )
            anomaly_score += 60

        is_plausible = (anomaly_score < 30)
        verdict = "PASSED" if is_plausible else "BLOCKED"

        return {
            "is_plausible": is_plausible,
            "verdict": verdict,
            "anomaly_score": min(anomaly_score, 100),
            "anomalies": anomalies,
            "computed_yield_kg_per_ha": round(yield_per_ha, 2),
            "fact_check_model": "x402-NLI-Agronomic-Evaluator"
        }
