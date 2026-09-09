from datetime import date
from app.modules.legal_document_auditor import LegalAuditor
from app.schemas import CommodityInfo, ProductionPlotInput, EUDRCommodityCategory, RiskTierEnum

def test_eudr_2026_july_exemption():
    """Verify that July 2026 EUDR exempted items (raw hides 4101, retreaded tyres 4012) are correctly flagged."""
    # Test 1: Raw Bovine Hides (HS 4101) - Exempted
    is_exempt, reason = LegalAuditor.check_exemption("4101.20.00")
    assert is_exempt is True
    assert "Raw hides and skins" in reason
    assert LegalAuditor.classify_hs_code("4101.20") == EUDRCommodityCategory.EXEMPTED

    # Test 2: Retreaded tyres (HS 4012) - Exempted
    is_exempt_tyre, reason_tyre = LegalAuditor.check_exemption("4012.11.00")
    assert is_exempt_tyre is True
    assert "Retreaded pneumatic tyres" in reason_tyre

    # Test 3: Regular Coffee (HS 0901) - Regulated (Not Exempted)
    is_exempt_coffee, reason_coffee = LegalAuditor.check_exemption("0901.11.00")
    assert is_exempt_coffee is False
    assert reason_coffee is None
    assert LegalAuditor.classify_hs_code("0901.11") == EUDRCommodityCategory.COFFEE

    # Test 4: Document audit for an exempted commodity does not penalize missing origin documents
    dummy_plot = ProductionPlotInput(
        plot_id="PLOT-EXEMPT-01",
        country_code="BR",
        area_hectares=10.0,
        geometry={"type": "Point", "coordinates": [-47.88, -15.79]},
        production_date=date(2026, 1, 15)
    )
    exempt_commodity = CommodityInfo(
        hs_code="410120",
        description="Bovine Raw Hides",
        net_mass_kg=5000.0
    )
    
    audit_res = LegalAuditor.audit_documents(
        documents=[], # zero documents provided
        plots=[dummy_plot],
        commodity=exempt_commodity
    )

    assert audit_res.overall_compliant is True
    assert audit_res.is_exempt_from_eudr is True
    assert audit_res.risk_score == 0.0
    assert "Statutory Exemption Notice" in audit_res.notes[0]
