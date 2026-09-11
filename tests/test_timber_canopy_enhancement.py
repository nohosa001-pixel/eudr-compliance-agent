import pytest
from datetime import date
from app.schemas import ProductionPlotInput, SpatialPlotResult
from app.modules.satellite_compliance_checker import DeforestationAnalyzer
from app.modules.satellite_providers.hansen_gfc_provider import HansenGFCProvider

def test_canopy_multi_threshold_clean_plot():
    """Verify that a compliant plot generates valid multi-threshold evaluations for 10%, 20%, and 30%."""
    plot = ProductionPlotInput(
        plot_id="PLOT-TIMBER-CLEAN-01",
        country_code="BR",
        area_hectares=25.0,
        geometry={"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]},
        production_date=date(2024, 5, 10),
        notes="clean certified eucalyptus plantation"
    )
    spatial_res = SpatialPlotResult(
        plot_id=plot.plot_id,
        is_valid=True,
        geometry_type="Polygon",
        declared_area_ha=25.0,
        is_polygon_required=True
    )
    sat_res = DeforestationAnalyzer.analyze_plot(plot, spatial_res)
    
    assert sat_res.compliance_passed is True
    assert sat_res.deforestation_detected is False
    assert sat_res.canopy_multi_threshold is not None
    assert len(sat_res.canopy_multi_threshold) == 3

    # Check 10% FAO baseline
    th_10 = next(t for t in sat_res.canopy_multi_threshold if t.threshold_pct == 10)
    assert th_10.standard_name == "FAO_ARTICLE_2_EUDR"
    assert th_10.baseline_forest_status is True
    assert th_10.compliance_verdict == "COMPLIANT"

    # Check 20% Standard baseline
    th_20 = next(t for t in sat_res.canopy_multi_threshold if t.threshold_pct == 20)
    assert th_20.standard_name == "STANDARD_BASELINE_20"
    assert th_20.compliance_verdict == "COMPLIANT"

    # Check 30% UNEP conservative baseline
    th_30 = next(t for t in sat_res.canopy_multi_threshold if t.threshold_pct == 30)
    assert th_30.standard_name == "UNEP_CONSERVATIVE_30"
    assert th_30.compliance_verdict == "COMPLIANT"

    # Verify audit immunity defense statement
    assert "AUDIT IMMUNITY DEFENSE" in sat_res.regulatory_defense_statement
    assert "10% FAO statutory" in sat_res.regulatory_defense_statement

def test_canopy_multi_threshold_deforestation_flagged():
    """Verify that a plot deforested post-2020 is flagged across applicable canopy thresholds."""
    plot = ProductionPlotInput(
        plot_id="PLOT-TIMBER-FAIL-deforestation_2022",
        country_code="BR",
        area_hectares=50.0,
        geometry={"type": "Polygon", "coordinates": [[[10,10], [11,10], [11,11], [10,11], [10,10]]]},
        production_date=date(2024, 5, 10),
        notes="timber clearing deforestation_2022"
    )
    spatial_res = SpatialPlotResult(
        plot_id=plot.plot_id,
        is_valid=True,
        geometry_type="Polygon",
        declared_area_ha=50.0,
        is_polygon_required=True
    )
    sat_res = DeforestationAnalyzer.analyze_plot(plot, spatial_res)

    assert sat_res.compliance_passed is False
    assert sat_res.deforestation_detected is True
    assert sat_res.forest_loss_year == 2022
    assert sat_res.canopy_multi_threshold is not None

    for th in sat_res.canopy_multi_threshold:
        assert th.loss_detected_post_2020 is True
        assert th.compliance_verdict == "NON_COMPLIANT"

    assert "AUDIT WARNING" in sat_res.regulatory_defense_statement
    assert "2022" in sat_res.regulatory_defense_statement

def test_hansen_multi_threshold_intermediate_canopy():
    """
    Test edge case where canopy cover is 15% (meets FAO 10% but below UNEP 30%).
    Demonstrates defense against auditor misclassification.
    """
    result = HansenGFCProvider.parse_hansen_multi_threshold(
        lon=102.0,
        lat=1.0,
        loss_year_val=0,
        treecover_val=15,
        loss_ratio_pct=0.0
    )
    
    matrix = result["threshold_matrix"]
    m_10 = next(m for m in matrix if m["threshold_pct"] == 10)
    m_30 = next(m for m in matrix if m["threshold_pct"] == 30)

    # 10% is forest and compliant
    assert m_10["baseline_forest_status"] is True
    assert m_10["compliance_verdict"] == "COMPLIANT"

    # 30% is not considered forest under strict UNEP
    assert m_30["baseline_forest_status"] is False
    assert m_30["compliance_verdict"] == "NOT_FOREST_LAND"

    # Both are legally compliant with EUDR
    assert result["fao_10pct_compliant"] is True
    assert result["unep_30pct_compliant"] is True
    assert "CANOPY THRESHOLD DEFENSE" in result["regulatory_defense_statement"]


def test_fsc_hybrid_traces_mapping():
    """Verify that FSC/PEFC certification metadata seamlessly flows into TRACES-NT JSON and XML."""
    from app.schemas import (
        EUDRSupplyChainPayload, OperatorInfo, CommodityInfo, 
        LegalAuditResult, RiskTierEnum, EUDRCommodityCategory
    )
    from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper

    payload = EUDRSupplyChainPayload(
        supplier_id="SUP-SUZANO-01",
        operator=OperatorInfo(
            operator_name="Suzano Pulp Europe B.V.",
            eori_number="NL899999999",
            vat_number="NL899999999B01",
            country="NL",
            address="Zuidplein 100, 1077 XV Amsterdam"
        ),
        commodity=CommodityInfo(
            hs_code="470329",
            description="Bleached Eucalyptus Kraft Pulp (BEKP)",
            net_mass_kg=500000.0,
            scientific_name="Eucalyptus grandis",
            certification_scheme="FSC-100%",
            certificate_id="FSC-C012345",
            chain_of_custody_id="CU-COC-801234"
        ),
        plots=[
            ProductionPlotInput(
                plot_id="PLOT-SUZANO-BAHIA-01",
                country_code="BR",
                area_hectares=100.0,
                geometry={"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]},
                production_date=date(2024, 4, 1),
                notes="clean eucalyptus plantation"
            )
        ]
    )

    spatial_res = [
        SpatialPlotResult(
            plot_id="PLOT-SUZANO-BAHIA-01",
            is_valid=True,
            geometry_type="Polygon",
            declared_area_ha=100.0,
            is_polygon_required=True
        )
    ]

    sat_res = [
        DeforestationAnalyzer.analyze_plot(payload.plots[0], spatial_res[0])
    ]

    legal_audit = LegalAuditResult(
        overall_compliant=True,
        country_risk_tier=RiskTierEnum.STANDARD,
        simplified_due_diligence_eligible=False,
        commodity_category=EUDRCommodityCategory.WOOD,
        verified_documents_count=3,
        risk_score=0.0
    )

    # 1. Test JSON Mapping
    traces_json = TracesNTSchemaMapper.map_to_traces_payload(
        payload=payload,
        spatial_results=spatial_res,
        satellite_results=sat_res,
        legal_audit=legal_audit,
        dds_reference_id="DDS-SUZANO-2026-EUDR-001"
    )

    goods = traces_json["goodsDeclaration"]
    assert "thirdPartyCertification" in goods
    assert goods["thirdPartyCertification"]["scheme"] == "FSC-100%"
    assert goods["thirdPartyCertification"]["certificateId"] == "FSC-C012345"
    assert goods["thirdPartyCertification"]["chainOfCustodyId"] == "CU-COC-801234"
    assert goods["thirdPartyCertification"]["hybridComplianceStatus"] == "HYBRID_FSC_EUDR_VALIDATED"

    # Verify canopy multi-threshold in plot verification
    plot_0 = traces_json["productionPlots"]["placesOfProduction"][0]
    assert plot_0["satelliteVerification"]["canopyMultiThreshold"] is not None
    assert len(plot_0["satelliteVerification"]["canopyMultiThreshold"]) == 3
    assert "AUDIT IMMUNITY DEFENSE" in plot_0["satelliteVerification"]["regulatoryDefenseStatement"]

    # 2. Test XML Mapping
    traces_xml = TracesNTSchemaMapper.map_to_traces_xml(
        payload=payload,
        spatial_results=spatial_res,
        satellite_results=sat_res,
        legal_audit=legal_audit,
        dds_reference_id="DDS-SUZANO-2026-EUDR-001"
    )

    assert "<ThirdPartyCertification>" in traces_xml
    assert "<CertificateID>FSC-C012345</CertificateID>" in traces_xml
    assert "<HybridComplianceStatus>HYBRID_FSC_EUDR_VALIDATED</HybridComplianceStatus>" in traces_xml
    assert "<RegulatoryDefenseStatement>" in traces_xml


def test_biomass_clean_batch_quarantine_partition():
    """
    Verify Tainted Batch prevention:
    Partitions bulk candidate timber/pellet plots into Clean EU Roster vs Quarantined Non-EU Roster.
    """
    from app.modules.spatial_validator import SpatialValidator

    # Candidate plots: 3 clean, 1 deforestation, 1 spatial invalid
    plots = [
        ProductionPlotInput(
            plot_id=f"PLOT-TIMBER-OK-0{i}",
            country_code="BR",
            area_hectares=50.0,
            geometry={"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]},
            production_date=date(2024, 4, 1),
            notes="clean verified"
        )
        for i in range(1, 4)
    ]
    # Deforestation plot
    plots.append(
        ProductionPlotInput(
            plot_id="PLOT-TIMBER-FAIL-deforestation_2022",
            country_code="BR",
            area_hectares=60.0,
            geometry={"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]},
            production_date=date(2024, 4, 1),
            notes="satellite alert: deforestation_2022"
        )
    )
    # Spatial error plot (out of country bbox or invalid)
    plots.append(
        ProductionPlotInput(
            plot_id="PLOT-TIMBER-INVALID-SPATIAL",
            country_code="BR",
            area_hectares=40.0,
            geometry={"type": "Point", "coordinates": [10.0, 10.0]},  # Far outside Brazil bbox
            production_date=date(2024, 4, 1)
        )
    )

    # Validate spatial
    spatial_res = [SpatialValidator.validate_plot(p) for p in plots]
    # Validate satellite
    sat_res = [DeforestationAnalyzer.analyze_plot(p, sr) for p, sr in zip(plots, spatial_res)]

    # Run partition
    partition_res = SpatialValidator.partition_clean_timber_batch(
        plots=plots,
        spatial_results=spatial_res,
        satellite_results=sat_res,
        commodity_type="wood_pellets"
    )

    assert partition_res["total_plots_analyzed"] == 5
    assert partition_res["total_declared_ha"] == 250.0
    assert partition_res["is_entirely_clean"] is False

    # Clean batch check
    clean = partition_res["clean_batch"]
    assert clean["count"] == 3
    assert clean["area_hectares"] == 150.0
    assert clean["plot_ids"] == ["PLOT-TIMBER-OK-01", "PLOT-TIMBER-OK-02", "PLOT-TIMBER-OK-03"]

    # Quarantine batch check
    quarantine = partition_res["quarantine_batch"]
    assert quarantine["count"] == 2
    assert quarantine["area_hectares"] == 100.0
    
    q_ids = [q["plot_id"] for q in quarantine["quarantined_plots"]]
    assert "PLOT-TIMBER-FAIL-deforestation_2022" in q_ids
    assert "PLOT-TIMBER-INVALID-SPATIAL" in q_ids

    # Routing directive check
    assert "BATCH_SEGREGATION_REQUIRED" in partition_res["routing_directive"]
    assert partition_res["tainted_batch_protection_active"] is True


def test_api_evaluate_suzano_hybrid_preset():
    """Verify that the Suzano FSC-Hybrid Timber preset evaluates successfully via FastAPI endpoint."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    payload = {
        "supplier_id": "SUP-SUZANO-01",
        "operator": {
            "operator_name": "Suzano Pulp Europe B.V.",
            "eori_number": "NL899999999",
            "vat_number": "NL899999999B01",
            "country": "NL",
            "address": "Zuidplein 100, 1077 XV Amsterdam"
        },
        "commodity": {
            "hs_code": "470329",
            "description": "Bleached Eucalyptus Kraft Pulp (BEKP)",
            "net_mass_kg": 120000.0,
            "scientific_name": "Eucalyptus grandis",
            "certification_scheme": "FSC-100%",
            "certificate_id": "FSC-C012345",
            "chain_of_custody_id": "CU-COC-801234"
        },
        "plots": [
            {
                "plot_id": "BR-BAHIA-SUZ-01",
                "country_code": "BR",
                "area_hectares": 110.5,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-39.7500, -17.5000],
                            [-39.7400, -17.5000],
                            [-39.7400, -17.4900],
                            [-39.7500, -17.4900],
                            [-39.7500, -17.5000]
                        ]
                    ]
                },
                "production_date": "2024-03-25",
                "producer_name": "Suzano Mucuri Plantation Unit",
                "notes": "clean eucalyptus plantation"
            }
        ],
        "documents": [
            {
                "doc_id": "FSC-C012345-2024",
                "doc_type": "FSC_CERTIFICATE",
                "issuing_authority": "Forest Stewardship Council (FSC)",
                "issue_date": "2021-06-01",
                "expiry_date": "2028-06-01"
            },
            {
                "doc_id": "CAR-BA-291083-2020",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Cadastro Ambiental Rural (CAR Bahia)",
                "issue_date": "2019-11-20",
                "expiry_date": "2029-11-20"
            }
        ]
    }

    res = client.post("/api/v1/eudr/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLIANT"
    assert "traces_dds" in data
    assert data["traces_dds"]["deforestation_free_declaration"] is True

    # Check third party certification in TRACES payload
    goods = data["traces_dds"]["submission_ready_traces_payload"]["goodsDeclaration"]
    assert "thirdPartyCertification" in goods
    assert goods["thirdPartyCertification"]["scheme"] == "FSC-100%"
    assert goods["thirdPartyCertification"]["hybridComplianceStatus"] == "HYBRID_FSC_EUDR_VALIDATED"

    # Check canopy multi-threshold in plot details
    plot_0 = data["plots_detail"][0]
    assert plot_0["canopy_multi_threshold"] is not None
    assert len(plot_0["canopy_multi_threshold"]) == 3
    assert "AUDIT IMMUNITY DEFENSE" in plot_0["regulatory_defense_statement"]


