"""
Unit & Integration Tests for Historical Trade Anomaly & Precedent Mining Engine.
Includes dual verification of Fraud Risk Vectors and Golden Success Archetypes.
"""

from app.modules.historical_trade_anomaly_engine import HistoricalTradeAnomalyEngine


def test_clean_trade_evaluation():
    """Verify standard compliant trade receives LOW risk and passes clean."""
    res = HistoricalTradeAnomalyEngine.evaluate_trade_historical_integrity(
        commodity="coffee",
        hs_code="0901.11",
        origin_country="VN",
        declared_net_mass_kg=3000.0,
        total_area_ha=2.0,  # 1500 kg/ha is well within 2500 kg/ha limit
        transshipment_ports=["NLRTM"]
    )
    assert res["is_clean"] is True
    assert res["risk_level"] == "LOW"
    assert len(res["anomalies_detected"]) == 0
    assert len(res["precedent_citations"]) > 0


def test_agronomic_ceiling_breach_detection():
    """Verify fraudulent yield over-declaration is flagged as CRITICAL_BLOCKED."""
    res = HistoricalTradeAnomalyEngine.evaluate_trade_historical_integrity(
        commodity="coffee",
        hs_code="0901.11",
        origin_country="VN",
        declared_net_mass_kg=12000.0,
        total_area_ha=2.0,  # 6000 kg/ha far exceeds 2500 kg/ha limit
        transshipment_ports=[]
    )
    assert res["is_clean"] is False
    assert res["risk_level"] in ["HIGH", "CRITICAL_BLOCKED"]
    assert any("AGRONOMIC_CEILING_BREACH" in a for a in res["anomalies_detected"])


def test_hs_misclassification_detection():
    """Verify declaring roundwood as wood pellets triggers lab assay audit."""
    res = HistoricalTradeAnomalyEngine.evaluate_trade_historical_integrity(
        commodity="wood",
        hs_code="4401.31",  # Wood pellets pattern
        origin_country="BR",
        declared_net_mass_kg=5000.0,
        total_area_ha=5.0
    )
    assert any("HISTORICAL_MISCLASSIFICATION_RISK" in a for a in res["anomalies_detected"])
    assert any("MANDATORY_LAB_ASSAY" in act for act in res["recommended_actions"])


def test_transshipment_laundering_hub_detection():
    """Verify switch B/L risk at Port of Singapore triggers seal verification."""
    res = HistoricalTradeAnomalyEngine.evaluate_trade_historical_integrity(
        commodity="rubber",
        hs_code="4001.10",
        origin_country="TH",
        declared_net_mass_kg=2000.0,
        total_area_ha=2.0,
        transshipment_ports=["SGSIN", "ESVLC"]
    )
    assert any("TRANSSHIPMENT_LAUNDERING_HUB_DETECTED" in a for a in res["anomalies_detected"])
    assert any("STRICT_SEAL_INTEGRITY_CHECK" in act for act in res["recommended_actions"])


def test_success_archetype_matching_ghana_cocoa():
    """Verify compliant Ghana cocoa matches golden Kuapa Kokoo direct-sourcing archetype."""
    res = HistoricalTradeAnomalyEngine.evaluate_trade_historical_integrity(
        commodity="cocoa",
        hs_code="1801.00",
        origin_country="GH",
        declared_net_mass_kg=6000.0,
        total_area_ha=10.0,  # 600 kg/ha perfectly in [400, 850] optimal range
        transshipment_ports=["BEANR"]
    )
    assert res["is_clean"] is True
    assert res["risk_level"] == "LOW"
    assert res["green_lane_eligible"] is True
    assert res["success_alignment_score"] >= 90.0
    assert len(res["success_archetypes_matched"]) > 0

    match = res["success_archetypes_matched"][0]
    assert match["statutory_archetype"] == "GOLDEN_DIRECT_FAIRTRADE"
    assert match["yield_in_optimal_range"] is True
    assert any("ECONOMIC WIN-WIN BLUEPRINT" in hint for hint in res["economic_optimization_hints"])


def test_fast_track_green_customs_vietnam_coffee():
    """Verify compliant Vietnam coffee matches AEO-C Green Customs corridor blueprint."""
    res = HistoricalTradeAnomalyEngine.evaluate_trade_historical_integrity(
        commodity="coffee",
        hs_code="0901.11",
        origin_country="VN",
        declared_net_mass_kg=2000.0,
        total_area_ha=1.5,
        transshipment_ports=["NLRTM"]
    )
    assert res["is_clean"] is True
    assert len(res["fast_track_customs_precedents"]) > 0
    ft = res["fast_track_customs_precedents"][0]
    assert ft["precedent_id"] == "FAST-TRACK-AEO-ROTTERDAM-COFFEE"
    assert "AEO-C" in ft["framework"]
    assert any("CUSTOMS FAST-TRACK AVAILABLE" in hint for hint in res["economic_optimization_hints"])
