"""Tests for CleanWeb Intelligence & Extraction Adapter Integration.
==================================================================
Validates:
1. Coordinate extraction from unstructured text.
2. Commodity & certification entity recognition.
3. Auto-generation of ProductionPlotInput objects from raw web content.
4. End-to-end integration with spatial checks via FastAPI client.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.cleanweb_intelligence_adapter import cleanweb_intelligence_adapter

client = TestClient(app)


def test_cleanweb_coordinate_extraction_bracketed():
    """Verify coordinate extraction from bracketed coordinates in markdown."""
    sample_text = (
        "# Estate Report\n"
        "Parcels located at [102.152431, -2.451234] and [102.158765, -2.456789] and [102.161122, -2.450123].\n"
        "Certified by FSC and RSPO."
    )
    coords = cleanweb_intelligence_adapter.extract_coordinates_from_text(sample_text)
    assert len(coords) == 3
    assert coords[0] == [102.152431, -2.451234]


def test_cleanweb_parse_supplier_intelligence():
    """Verify extraction of commodity, certifications, and production plots."""
    raw_md = (
        "## Producer: Sumatra Organic Coffee Cooperative\n"
        "High-altitude Arabica harvested with FSC and Rainforest Alliance certification.\n"
        "Farm coordinates: [98.123456, 3.456789], [98.125678, 3.459012], [98.130000, 3.455000].\n"
        "Zero deforestation observed since December 2020."
    )
    parsed = cleanweb_intelligence_adapter.parse_supplier_intelligence(
        url="https://sumatra-coop.demo.org/about",
        cleaned_markdown=raw_md,
        fallback_country="ID"
    )
    assert parsed["detected_commodity"] == "COFFEE"
    assert parsed["suggested_hs_code"] == "0901.11"
    assert "FSC" in parsed["certifications"]
    assert "RAINFOREST ALLIANCE" in parsed["certifications"]
    assert parsed["extracted_coordinates_count"] == 3
    assert len(parsed["generated_plots"]) == 1
    assert parsed["generated_plots"][0].geometry["type"] == "Polygon"


@pytest.mark.asyncio
async def test_cleanweb_end_to_end_audit():
    """Verify end-to-end audit pipeline from URL to spatial verification."""
    audit_res = await cleanweb_intelligence_adapter.audit_supplier_url_end_to_end(
        target_url="https://supplier-plantation-demo.org/parcels",
        country_code="ID"
    )
    assert audit_res["url"] == "https://supplier-plantation-demo.org/parcels"
    assert "supplier_intelligence" in audit_res
    assert len(audit_res["spatial_validation"]) > 0
    assert audit_res["compliance_verdict"] in ["CLEANED_AND_SPATIALLY_CLEARED", "POTENTIAL_CONFLICT_DETECTED"]


def test_api_cleanweb_supplier_audit_endpoint():
    """Integration test for POST /api/v1/cleanweb/supplier-audit."""
    response = client.post(
        "/api/v1/cleanweb/supplier-audit",
        json={
            "target_url": "https://supplier-plantation-demo.org/parcels",
            "country_code": "ID"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://supplier-plantation-demo.org/parcels"
    assert "supplier_intelligence" in data
    assert data["supplier_intelligence"]["cleanweb_token_reduction_pct"] > 90.0
