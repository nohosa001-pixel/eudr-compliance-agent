import pytest
from datetime import date
from app.modules.satellite_providers.hansen_gfc_provider import HansenGFCProvider
from app.modules.satellite_providers.copernicus_sentinel_client import CopernicusSentinelClient
from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper
from app.schemas import (
    EUDRSupplyChainPayload,
    OperatorInfo,
    CommodityInfo,
    ProductionPlotInput,
    LegalDocumentInput,
    DocumentTypeEnum,
    SpatialPlotResult,
    SatellitePlotResult,
    LegalAuditResult,
    RiskTierEnum,
    EUDRCommodityCategory
)

def test_hansen_gfc_tile_resolution():
    """Validates Hansen 10x10 degree tile calculation from lat/lon."""
    # Southeast Asia (Indonesia: Lon 101.5, Lat 0.5) -> '10N_100E'
    tile_id = HansenGFCProvider.get_granule_tile_id(lon=101.5, lat=0.5)
    assert tile_id == "10N_100E"

    urls = HansenGFCProvider.get_tile_download_urls(tile_id)
    assert "lossyear_10N_100E.tif" in urls["lossyear"]
    assert "treecover2000_10N_100E.tif" in urls["treecover2000"]

    # South America (Brazil: Lon -55.0, Lat -12.0) -> '10S_060W'
    tile_br = HansenGFCProvider.get_granule_tile_id(lon=-55.0, lat=-12.0)
    assert tile_br == "10S_060W"

def test_hansen_gfc_lossyear_parsing():
    """Checks lossyear band values: index 20 (2020: compliant), index 22 (2022: violation)."""
    # 2020 loss (value 20) -> Not post-2020 violation
    parsed_2020 = HansenGFCProvider.parse_hansen_loss(lon=101.5, lat=0.5, loss_year_val=20, treecover_val=90)
    assert parsed_2020["loss_year_actual"] == 2020
    assert parsed_2020["post_2020_deforestation"] is False

    # 2022 loss (value 22) -> Post-2020 deforestation violation!
    parsed_2022 = HansenGFCProvider.parse_hansen_loss(lon=101.5, lat=0.5, loss_year_val=22, treecover_val=90)
    assert parsed_2022["loss_year_actual"] == 2022
    assert parsed_2022["post_2020_deforestation"] is True

def test_copernicus_sentinel_stat_payload():
    """Validates Copernicus Sentinel Hub Statistical API evalscript and payload construction."""
    geom = {"type": "Point", "coordinates": [101.5, 0.5]}
    payload = CopernicusSentinelClient.build_stat_request_payload(geom)
    assert payload["input"]["bounds"]["geometry"] == geom
    assert "evalscript" in payload["aggregation"]
    assert "B08" in payload["aggregation"]["evalscript"]  # NIR band
    assert "B04" in payload["aggregation"]["evalscript"]  # Red band

def test_traces_nt_schema_mapper_full():
    """Validates full EU TRACES-NT Annex II schema compliance."""
    payload = EUDRSupplyChainPayload(
        supplier_id="SUPP-01",
        operator=OperatorInfo(
            operator_name="Global Timber S.A.",
            eori_number="FR12345678901234",
            vat_number="FR123456789",
            country="FR",
            address="12 Rue de Paris, France"
        ),
        commodity=CommodityInfo(
            hs_code="440711",
            description="Wood sawn lengthwise",
            net_mass_kg=10000.0,
            scientific_name="Pinus sylvestris"
        ),
        plots=[
            ProductionPlotInput(
                plot_id="PLOT-01",
                country_code="SE",
                area_hectares=2.5,
                geometry={"type": "Point", "coordinates": [18.06, 59.32]},
                production_date=date(2024, 5, 1)
            )
        ]
    )

    spatial_results = [
        SpatialPlotResult(
            plot_id="PLOT-01",
            is_valid=True,
            geometry_type="Point",
            declared_area_ha=2.5,
            is_polygon_required=False
        )
    ]
    sat_results = [
        SatellitePlotResult(
            plot_id="PLOT-01",
            deforestation_detected=False,
            compliance_passed=True,
            audit_notes="Verified clean"
        )
    ]
    legal_audit = LegalAuditResult(
        overall_compliant=True,
        country_risk_tier=RiskTierEnum.LOW,
        simplified_due_diligence_eligible=True,
        commodity_category=EUDRCommodityCategory.WOOD,
        verified_documents_count=2,
        risk_score=0.05
    )

    traces_json = TracesNTSchemaMapper.map_to_traces_payload(
        payload=payload,
        spatial_results=spatial_results,
        satellite_results=sat_results,
        legal_audit=legal_audit,
        dds_reference_id="DDS-EUDR-20260825-TEST01"
    )

    assert traces_json["schemaVersion"] == "1.0.0-EUDR"
    assert traces_json["header"]["statementReferenceNumber"] == "DDS-EUDR-20260825-TEST01"
    assert traces_json["header"]["statementType"] == "DDS_SIMPLIFIED"
    assert traces_json["declarant"]["operatorEori"] == "FR12345678901234"
    assert traces_json["goodsDeclaration"]["hsCode"] == "440711"
    assert traces_json["dueDiligenceAttestation"]["deforestationFreeArticle3a"] is True
    assert "digitalSignatureBlock" in traces_json
    assert traces_json["digitalSignatureBlock"]["signatureAlgorithm"] == "HMAC-SHA256"
