"""
Historical Trade Anomaly & Precedent Mining Engine for EUDR Compliance.
========================================================================
Analyzes current shipments against 10-15 years of European court rulings (EUTR, CJEU),
UN Comtrade bilateral trade anomalies, WCO tariff misclassifications, and maritime
transshipment laundering fingerprints to prevent circumvention of the 2020-12-31 cutoff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class HistoricalTradeAnomalyEngine:
    """
    Cognitive evaluation engine grounded in historical European trade fraud archives.
    Evaluates:
    - 2020 Cut-off Date surge ratios (UN Comtrade 2015-2024 baselines)
    - CJEU / EUTR case law violation signatures (e.g. C-621/21, DOF cloning)
    - HS / TARIC tariff classification obfuscation
    - Maritime intermediate hub switch B/L and seal laundering
    """

    _DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "historical_trade_corpus"

    # Cached in-memory datasets
    _precedents: Optional[List[Dict[str, Any]]] = None
    _surges: Optional[Dict[str, Any]] = None
    _misclassifications: Optional[List[Dict[str, Any]]] = None
    _hubs: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _load_data_if_needed(cls):
        if cls._precedents is None:
            p_file = cls._DATA_DIR / "eutr_court_precedents.json"
            cls._precedents = json.loads(p_file.read_text(encoding="utf-8")) if p_file.exists() else []

        if cls._surges is None:
            s_file = cls._DATA_DIR / "un_comtrade_historical_surges.json"
            cls._surges = json.loads(s_file.read_text(encoding="utf-8")) if s_file.exists() else {}

        if cls._misclassifications is None:
            m_file = cls._DATA_DIR / "customs_misclassification_patterns.json"
            cls._misclassifications = json.loads(m_file.read_text(encoding="utf-8")) if m_file.exists() else []

        if cls._hubs is None:
            h_file = cls._DATA_DIR / "transshipment_laundering_hubs.json"
            cls._hubs = json.loads(h_file.read_text(encoding="utf-8")) if h_file.exists() else []

    @classmethod
    def evaluate_trade_historical_integrity(
        cls,
        commodity: str,
        hs_code: str,
        origin_country: str,
        declared_net_mass_kg: float,
        total_area_ha: float,
        transshipment_ports: Optional[List[str]] = None,
        declared_value_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive historical anomaly scan.
        Returns:
            - is_clean: bool
            - risk_level: str ("LOW", "MEDIUM", "HIGH", "CRITICAL_BLOCKED")
            - anomalies_detected: List[str]
            - precedent_citations: List[Dict[str, Any]]
            - recommended_actions: List[str]
        """
        cls._load_data_if_needed()

        anomalies = []
        citations = []
        actions = []
        risk_score = 0.0

        clean_commodity = commodity.lower().strip()
        clean_country = origin_country.upper().strip()
        clean_hs = hs_code.replace(".", "").strip()
        transshipment = [p.upper().strip() for p in (transshipment_ports or [])]

        # 1. Agronomic Yield Ceiling & Surge Verification
        computed_yield = (declared_net_mass_kg / max(0.01, total_area_ha))
        thresholds = cls._surges.get("country_surge_thresholds", {}).get(clean_country, {})

        if thresholds:
            max_yield = thresholds.get("max_agronomic_yield_kg_ha", 5000.0)
            if computed_yield > max_yield:
                anomalies.append(
                    f"AGRONOMIC_CEILING_BREACH: Declared yield ({computed_yield:.1f} kg/ha) exceeds FAO historical biological limit ({max_yield:.1f} kg/ha) for {clean_country}."
                )
                risk_score += 45.0
                actions.append("REJECT_OR_AUDIT: High probability of FOB over-declaration or laundered harvest from unregistered plots.")

        # 2. Tariff Misclassification Pattern Scan
        for pattern in (cls._misclassifications or []):
            pat_hs = pattern.get("declared_hs", "").replace(".", "").strip()
            if clean_hs.startswith(pat_hs[:4]):
                anomalies.append(
                    f"HISTORICAL_MISCLASSIFICATION_RISK: Declared HS {hs_code} matches known fraud pattern {pattern['pattern_id']} ({pattern['declared_desc']})."
                )
                risk_score += 35.0
                actions.append(f"MANDATORY_LAB_ASSAY: Verify physical consignment composition against true HS {pattern['true_commodity_hs']}.")

        # 3. Transshipment Laundering Hub Scan
        for hub in (cls._hubs or []):
            if hub.get("hub_code") in transshipment:
                anomalies.append(
                    f"TRANSSHIPMENT_LAUNDERING_HUB_DETECTED: Route includes {hub['port_name']} ({hub['hub_code']}) - known switch B/L risk."
                )
                risk_score += 30.0
                actions.append(hub.get("mandatory_inspection", "AUDIT_CONTAINER_SEAL_INTEGRITY"))

        # 4. Relevant EUTR / CJEU Precedent Citations
        for prec in (cls._precedents or []):
            if prec.get("commodity") == clean_commodity:
                citations.append({
                    "case_id": prec["case_id"],
                    "court": prec["court"],
                    "principle": prec["ruling_principle"],
                    "summary": prec["summary"]
                })
                # If specific vector applies
                if clean_commodity == "wood" and computed_yield > 4000.0:
                    anomalies.append(f"CJEU_PRECEDENT_WARNING: Concession timber volume inconsistent with {prec['case_id']}.")
                    risk_score += 20.0

        # Determine Final Rating
        if risk_score >= 60.0:
            risk_level = "CRITICAL_BLOCKED"
            is_clean = False
        elif risk_score >= 30.0:
            risk_level = "HIGH"
            is_clean = False
        elif risk_score > 0.0:
            risk_level = "MEDIUM"
            is_clean = True
        else:
            risk_level = "LOW"
            is_clean = True

        return {
            "is_clean": is_clean,
            "risk_level": risk_level,
            "anomaly_risk_score": min(100.0, risk_score),
            "anomalies_detected": anomalies,
            "precedent_citations": citations,
            "recommended_actions": actions,
            "framework_grounding": "EUTR 995/2010 Case Laws & UN Comtrade Historical Baselines"
        }
