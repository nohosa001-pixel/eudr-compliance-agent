"""
Historical Trade Reasoning Engine for EUDR Compliance: Dual Risk & Success Mining.
===================================================================================
Analyzes current shipments against:
1. RISK VECTORS: 10-15 years of European court rulings (EUTR, CJEU), UN Comtrade surge
   anomalies, WCO tariff misclassifications, and maritime laundering hubs.
2. SUCCESS ARCHETYPES: Proven historical trade models, AEO-C Green Customs fast-tracks,
   and direct-sourcing / fair-trade smallholder economic inclusion frameworks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class HistoricalTradeAnomalyEngine:
    """
    Cognitive evaluation and reasoning engine grounded in both historical European
    trade fraud archives (violation patterns) and proven success benchmarks (golden archetypes).
    """

    _DATA_DIR_PRIMARY: Path = Path(__file__).resolve().parent.parent.parent / "data" / "historical_trade_corpus"
    _DATA_DIR_PKG: Path = Path(__file__).resolve().parent.parent / "data" / "historical_trade_corpus"

    @classmethod
    def _get_data_dir(cls) -> Path:
        if cls._DATA_DIR_PRIMARY.exists():
            return cls._DATA_DIR_PRIMARY
        return cls._DATA_DIR_PKG

    # Cached in-memory datasets
    _precedents: Optional[List[Dict[str, Any]]] = None
    _surges: Optional[Dict[str, Any]] = None
    _misclassifications: Optional[List[Dict[str, Any]]] = None
    _hubs: Optional[List[Dict[str, Any]]] = None

    # Success & Golden Archetype Datasets
    _success_benchmarks: Optional[List[Dict[str, Any]]] = None
    _fast_tracks: Optional[List[Dict[str, Any]]] = None
    _direct_sourcing: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _load_data_if_needed(cls):
        # 1. Anomaly Datasets
        if cls._precedents is None:
            p_file = cls._get_data_dir() / "eutr_court_precedents.json"
            cls._precedents = json.loads(p_file.read_text(encoding="utf-8")) if p_file.exists() else []

        if cls._surges is None:
            s_file = cls._get_data_dir() / "un_comtrade_historical_surges.json"
            cls._surges = json.loads(s_file.read_text(encoding="utf-8")) if s_file.exists() else {}

        if cls._misclassifications is None:
            m_file = cls._get_data_dir() / "customs_misclassification_patterns.json"
            cls._misclassifications = json.loads(m_file.read_text(encoding="utf-8")) if m_file.exists() else []

        if cls._hubs is None:
            h_file = cls._get_data_dir() / "transshipment_laundering_hubs.json"
            cls._hubs = json.loads(h_file.read_text(encoding="utf-8")) if h_file.exists() else []

        # 2. Success Archetype Datasets
        if cls._success_benchmarks is None:
            b_file = cls._get_data_dir() / "trade_success_benchmarks.json"
            cls._success_benchmarks = json.loads(b_file.read_text(encoding="utf-8")) if b_file.exists() else []

        if cls._fast_tracks is None:
            ft_file = cls._get_data_dir() / "green_customs_fast_track_precedents.json"
            cls._fast_tracks = json.loads(ft_file.read_text(encoding="utf-8")) if ft_file.exists() else []

        if cls._direct_sourcing is None:
            ds_file = cls._get_data_dir() / "fair_trade_direct_sourcing_models.json"
            cls._direct_sourcing = json.loads(ds_file.read_text(encoding="utf-8")) if ds_file.exists() else []

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
        Runs dual-track cognitive historical analysis:
        1. Anomaly & Fraud Risk Vector Detection (Violation Precedents)
        2. Success Archetype Matching & Green Customs Acceleration (Success Precedents)
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

        # ---------------------------------------------------------------------
        # Part A: Anomaly & Risk Detection (Violation Mining)
        # ---------------------------------------------------------------------
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

        for pattern in (cls._misclassifications or []):
            pat_hs = pattern.get("declared_hs", "").replace(".", "").strip()
            if clean_hs.startswith(pat_hs[:4]):
                anomalies.append(
                    f"HISTORICAL_MISCLASSIFICATION_RISK: Declared HS {hs_code} matches known fraud pattern {pattern['pattern_id']} ({pattern['declared_desc']})."
                )
                risk_score += 35.0
                actions.append(f"MANDATORY_LAB_ASSAY: Verify physical consignment composition against true HS {pattern['true_commodity_hs']}.")

        for hub in (cls._hubs or []):
            if hub.get("hub_code") in transshipment:
                anomalies.append(
                    f"TRANSSHIPMENT_LAUNDERING_HUB_DETECTED: Route includes {hub['port_name']} ({hub['hub_code']}) - known switch B/L risk."
                )
                risk_score += 30.0
                actions.append(hub.get("mandatory_inspection", "AUDIT_CONTAINER_SEAL_INTEGRITY"))

        for prec in (cls._precedents or []):
            if prec.get("commodity") == clean_commodity:
                citations.append({
                    "case_id": prec["case_id"],
                    "court": prec["court"],
                    "principle": prec["ruling_principle"],
                    "summary": prec["summary"]
                })
                if clean_commodity == "wood" and computed_yield > 4000.0:
                    anomalies.append(f"CJEU_PRECEDENT_WARNING: Concession timber volume inconsistent with {prec['case_id']}.")
                    risk_score += 20.0

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

        # ---------------------------------------------------------------------
        # Part B: Success Archetype Matching & Green Lane Acceleration (Success Mining)
        # ---------------------------------------------------------------------
        success_matches = []
        green_lane_eligible = False
        fast_track_citations = []
        optimization_hints = []
        success_alignment_score = 0.0

        if is_clean and risk_score == 0.0:
            # 1. Match against Golden Benchmarks
            for b in (cls._success_benchmarks or []):
                if b.get("commodity") == clean_commodity and b.get("origin_country") == clean_country:
                    min_y, max_y = b.get("optimal_yield_range_kg_ha", [0.0, 99999.0])
                    yield_fit = min_y <= computed_yield <= max_y
                    success_matches.append({
                        "benchmark_id": b["benchmark_id"],
                        "model_name": b["model_name"],
                        "statutory_archetype": b["statutory_archetype"],
                        "yield_in_optimal_range": yield_fit,
                        "success_factors": b["success_factors"],
                        "eu_customs_advantage": b["eu_customs_advantage"]
                    })
                    if yield_fit:
                        success_alignment_score = max(success_alignment_score, 95.0)
                        green_lane_eligible = True
                        optimization_hints.append(
                            f"EXCELLENCE MATCH: Declared yield ({computed_yield:.1f} kg/ha) perfectly aligns with the historic golden standard {b['model_name']} ({min_y}-{max_y} kg/ha)."
                        )
                    else:
                        success_alignment_score = max(success_alignment_score, 75.0)

            # 2. Match Fast-Track Green Customs Precedents
            for ft in (cls._fast_tracks or []):
                if ft.get("commodity") == clean_commodity and ft.get("origin_country") == clean_country:
                    fast_track_citations.append({
                        "precedent_id": ft["precedent_id"],
                        "framework": ft["bilateral_framework"],
                        "statutory_mechanism": ft["statutory_mechanism"],
                        "historical_outcome": ft["historical_outcome"],
                        "blueprint": ft["replication_blueprint_for_eudr"]
                    })
                    optimization_hints.append(
                        f"CUSTOMS FAST-TRACK AVAILABLE: Replicate blueprint from {ft['precedent_id']} to qualify for direct clearance without demurrage delay."
                    )

            # 3. Match Direct Sourcing & Fair Trade Models
            for ds in (cls._direct_sourcing or []):
                if ds.get("commodity") == clean_commodity and ds.get("origin_country") == clean_country:
                    optimization_hints.append(
                        f"ECONOMIC WIN-WIN BLUEPRINT: Apply {ds['model_id']} (Direct-Split 0.15% Escrow). Expected benefits: {ds['historical_results']['intermediary_margin_cut']}."
                    )
        elif is_clean and risk_score < 30.0:
            success_alignment_score = 50.0
            optimization_hints.append("REMEDIATION OPPORTUNITY: Address minor risk factors to unlock EUDR Article 13 Simplified Due Diligence status.")

        return {
            "is_clean": is_clean,
            "risk_level": risk_level,
            "anomaly_risk_score": min(100.0, risk_score),
            "anomalies_detected": anomalies,
            "precedent_citations": citations,
            "recommended_actions": actions,
            # Success mining attributes
            "success_alignment_score": round(success_alignment_score, 1),
            "green_lane_eligible": green_lane_eligible,
            "success_archetypes_matched": success_matches,
            "fast_track_customs_precedents": fast_track_citations,
            "economic_optimization_hints": optimization_hints,
            "framework_grounding": "EUTR 995/2010 Case Laws, UN Comtrade Baselines & Proven Sustainable Trade Archetypes"
        }
