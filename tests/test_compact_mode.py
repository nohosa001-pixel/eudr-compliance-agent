import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.agent_tools import AgentToolsRegistry

client = TestClient(app)

@pytest.fixture
def compliant_sample_payload():
    return {
        "execution_id": "TEST-COMPACT-001",
        "supplier_id": "SUPP-PT-COMPACT",
        "operator": {
            "operator_name": "AgriTrade Global B.V.",
            "eori_number": "NL882910394",
            "vat_number": "NL882910394B01",
            "country": "NL",
            "address": "Keizersgracht 421, Amsterdam"
        },
        "commodity": {
            "hs_code": "151110",
            "description": "Crude Palm Oil",
            "net_mass_kg": 25000.0
        },
        "plots": [
            {
                "plot_id": "PLOT-COMPACT-OK-1",
                "country_code": "ID",
                "area_hectares": 1.8,
                "geometry": {
                    "type": "Point",
                    "coordinates": [101.45, 0.52]
                },
                "production_date": "2026-03-01"
            },
            {
                "plot_id": "PLOT-COMPACT-OK-2",
                "country_code": "ID",
                "area_hectares": 2.2,
                "geometry": {
                    "type": "Point",
                    "coordinates": [101.46, 0.53]
                },
                "production_date": "2026-03-02"
            }
        ],
        "documents": [
            {
                "doc_id": "HGU-ID-99210",
                "doc_type": "LAND_USE_TITLE",
                "issuing_authority": "Badan Pertanahan Nasional",
                "issue_date": "2019-05-10"
            },
            {
                "doc_id": "LIC-ID-4412",
                "doc_type": "BUSINESS_LICENSE",
                "issuing_authority": "Kementerian Investasi",
                "issue_date": "2020-01-15"
            },
            {
                "doc_id": "HARV-ID-8821",
                "doc_type": "HARVEST_PERMIT",
                "issuing_authority": "Kementerian Pertanian",
                "issue_date": "2021-06-01"
            },
            {
                "doc_id": "FPIC-ID-1109",
                "doc_type": "FPIC_CONSENT",
                "issuing_authority": "Masyarakat Adat Council",
                "issue_date": "2020-03-20"
            }
        ],
        "destination_country": "NL"
    }

@pytest.fixture
def non_compliant_sample_payload():
    return {
        "execution_id": "TEST-COMPACT-FAIL-001",
        "supplier_id": "SUPP-DEFOREST-COMPACT",
        "operator": {
            "operator_name": "AgriTrade Global B.V.",
            "eori_number": "NL882910394",
            "country": "NL",
            "address": "Keizersgracht 421, Amsterdam"
        },
        "commodity": {
            "hs_code": "151110",
            "description": "Crude Palm Oil",
            "net_mass_kg": 10000.0
        },
        "plots": [
            {
                # ID with DEFOREST in ID triggers simulated deforestation in DeforestationSimulator
                "plot_id": "PLOT-DEFOREST-2022-X",
                "country_code": "ID",
                "area_hectares": 1.5,
                "geometry": {
                    "type": "Point",
                    "coordinates": [101.50, 0.60]
                },
                "production_date": "2026-01-15"
            }
        ],
        "documents": [],
        "destination_country": "NL"
    }

def test_evaluate_endpoint_standard_mode(compliant_sample_payload):
    """Ensure default compact=false returns the full, exhaustive DDSReport."""
    resp = client.post("/api/v1/eudr/evaluate", json=compliant_sample_payload)
    assert resp.status_code == 200
    data = resp.json()

    # Full report has heavyweight plot details and evidence bundles
    assert "plots_detail" in data
    assert len(data["plots_detail"]) == 2
    assert "evidence_bundle" in data
    assert "spatial_summary" in data
    assert "satellite_summary" in data
    assert data["status"] == "COMPLIANT"

def test_evaluate_endpoint_compact_mode(compliant_sample_payload):
    """Ensure ?compact=true returns the ultra-compact CompactDDSReport schema (~300 tokens)."""
    resp = client.post("/api/v1/eudr/evaluate?compact=true", json=compliant_sample_payload)
    assert resp.status_code == 200
    data = resp.json()

    # Verify compact schema fields
    assert data["execution_id"] == compliant_sample_payload["execution_id"]
    assert data["status"] == "COMPLIANT"
    assert data["overall_compliant"] is True
    assert data["total_plots_count"] == 2
    assert data["compliant_plots_count"] == 2
    assert data["flagged_plots_count"] == 0
    assert data["flagged_plot_ids"] == []
    assert data["token_savings_pct"] >= 90.0

    # Ensure heavy fields are stripped from top-level response to preserve agent tokens
    assert "plots_detail" not in data
    assert "evidence_bundle" not in data
    assert "spatial_summary" not in data
    assert "satellite_summary" not in data

    # Verify links and agent summary
    assert data["full_report_download_url"].startswith("/api/v1/eudr/history/")
    assert data["traces_xml_download_url"] is not None
    assert data["customs_certificate_url"] is not None
    assert "EUDR Status: COMPLIANT" in data["agent_summary"]
    assert "Plots: 2/2 compliant" in data["agent_summary"]

def test_evaluate_endpoint_compact_mode_with_flagged_plot(non_compliant_sample_payload):
    """Ensure compact mode highlights flagged plots without dumping massive spatial traces."""
    resp = client.post("/api/v1/eudr/evaluate?compact=true", json=non_compliant_sample_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_compliant"] is False
    assert data["status"] == "NON_COMPLIANT"
    assert data["flagged_plots_count"] >= 1
    assert "PLOT-DEFOREST-2022-X" in data["flagged_plot_ids"]
    assert data["deforestation_free"] is False
    assert "DEFORESTATION_DETECTED" in data["agent_summary"]
    # Customs certificate is omitted for non-compliant batches
    assert data["customs_certificate_url"] is None

@pytest.mark.asyncio
async def test_agent_tools_registry_eudr_evaluate_compact():
    """Verify autonomous agents can execute eudr_evaluate_compact directly via AgentToolsRegistry."""
    args = {
        "operator_name": "Autonomous Trade Bot",
        "operator_eori": "DE998877665",
        "commodity": "Coffee",
        "hs_code": "090111",
        "net_mass_kg": 5000.0,
        "plots": [
            {
                "plot_id": "PLOT-BOT-001",
                "country_code": "CO",
                "area_hectares": 2.0,
                "coordinates": [-75.5, 4.8]
            }
        ],
        "documents": [
            {
                "document_type": "LAND_TITLE",
                "document_id": "COL-LT-12345",
                "is_valid": True
            }
        ]
    }

    res = await AgentToolsRegistry.execute_tool("eudr_evaluate_compact", args)

    assert res["status"] in ["COMPLIANT", "NON_COMPLIANT"]
    assert "total_plots_count" in res
    assert res["total_plots_count"] == 1
    assert "token_savings_pct" in res
    assert res["token_savings_pct"] >= 90.0
    assert "full_report_download_url" in res
    assert "agent_summary" in res
    assert "meta" in res
    assert "disclaimer" in res["meta"]

def test_agent_tools_api_execute_compact():
    """Verify POST /api/v1/agent/tools/execute can invoke eudr_evaluate_compact via HTTP."""
    req_body = {
        "tool_name": "eudr_evaluate_compact",
        "arguments": {
            "operator_name": "Autonomous Procurement LLM",
            "operator_eori": "FR112233445",
            "commodity": "Cocoa",
            "hs_code": "180100",
            "net_mass_kg": 15000.0,
            "plots": [
                {
                    "plot_id": "PLOT-GH-COCOA-1",
                    "country_code": "GH",
                    "area_hectares": 1.2,
                    "coordinates": [-1.6, 6.7]
                }
            ]
        }
    }

    resp = client.post("/api/v1/agent/tools/execute", json=req_body)
    assert resp.status_code == 200
    data = resp.json()

    assert data["tool_name"] == "eudr_evaluate_compact"
    assert data["status"].lower() == "success"
    assert "result" in data
    result = data["result"]
    assert "execution_id" in result
    assert "agent_summary" in result
    assert result["token_savings_pct"] == 95.0
    assert "plots_detail" not in result
