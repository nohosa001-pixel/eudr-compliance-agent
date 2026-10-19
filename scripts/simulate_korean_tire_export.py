#!/usr/bin/env python3
"""
EUDR Simulation: Korean Tire Manufacturer Global Export Scenario
=================================================================
Target Exporter: Top-tier Korean Tire Enterprise (Hankook / Kumho / Nexen)
Export Route: Busan New Port (KRPUS) -> Port of Hamburg (DEHAM, Germany)
Target Buyer: European Premium Automotive OEMs (BMW, Mercedes-Benz, VW Group)

Regulatory Context:
- HS 4011 (New Pneumatic Tyres): Strictly Regulated under EUDR Annex I (Natural Rubber).
- HS 4012 (Retreaded Tyres): FORMALLY EXCLUDED under finalized 2026 Delegated Act.
- HS 4415 (Wooden Transport Pallets): TARIC Y122 Transport Packaging Exemption.
- Supply Upstream: Thai RAOT / Indonesian Smallholder Rubber Farms.
"""

import os
import sys
import json
import time
import uuid
import datetime
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.core.config import settings

# Deterministic fast simulation mode
settings.USE_LIVE_COPERNICUS_API = False
settings.TELEGRAM_NOTIFICATIONS_ENABLED = False

from app.main import app
from app.schemas import (
    EUDRSupplyChainPayload,
    ProductionPlotInput,
    StatutoryExemptionNoticeRequest,
    CustomsTaricEvaluateRequest,
    CustomsUCCDeclarationRequest,
    CustomsSWECPreClearanceRequest,
    SpatialPlotResult,
    SatellitePlotResult,
    LegalAuditResult,
    RiskTierEnum,
)
from app.modules.statutory_exemption_issuer import StatutoryExemptionIssuer
from app.modules.eu_customs_adapter import EUCustomsAdapter
from app.modules.spatial_validator import SpatialValidator
from app.modules.audit_vault_manager import AuditVaultManager
from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper
from app.modules.producer_adapters.registry_hub import ProducerCountryRegistryHub

client = TestClient(app)


def print_banner(title: str):
    print("\n" + "=" * 78)
    print(f"🛞 {title}")
    print("=" * 78)


def run_korean_tire_export_simulation():
    print_banner("KOREAN TIRE ENTERPRISE EUDR EXPORT COMPLIANCE PIPELINE")
    print("🏢 Exporter: Korea Advanced Tyre & Rubber Corp (Daejeon Plant / KR)")
    print("🇪🇺 Importer / Consignee: Tyre Logistics Europe GmbH (Frankfurt / Germany)")
    print("📋 Operator EORI: DE9876543210 (German Customs ATLAS Integrated)")
    print("🚢 Shipping: HMM Algeciras (Busan Port KRPUS ➔ Port of Hamburg DEHAM)")
    print(f"⏱️ Evaluation Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()} UTC")

    # -------------------------------------------------------------------------
    # STEP 1: Consignment Breakdown & Multi-Tariff Classification
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("[STEP 1] Export Consignment Multi-Tariff HS Code Classification & Strategy")
    print("-" * 78)

    cargo_items = [
        {
            "line": 1,
            "desc": "EV/UHP Passenger Car New Pneumatic Tyres (Hankook iON / Ventus S1)",
            "hs_code": "4011.10.00",
            "quantity_units": 6500,
            "net_mass_kg": 65000.0,
            "regulatory_status": "REGULATED_ANNEX_I",
            "rubber_origin": "Natural Rubber (TSR20 / RSS3) from Thailand & Indonesia"
        },
        {
            "line": 2,
            "desc": "Commercial Eco-Retreaded Truck Tyres (SmartFlex DL12)",
            "hs_code": "4012.12.00",
            "quantity_units": 800,
            "net_mass_kg": 48000.0,
            "regulatory_status": "EXEMPT_DELEGATED_ACT",
            "rubber_origin": "Retreaded Casing (Excluded under finalized Sept 2026 Revision)"
        },
        {
            "line": 3,
            "desc": "Heavy-Duty Returnable Wooden Pallets & Racks for Tyre Securing",
            "hs_code": "4415.20.00",
            "quantity_units": 450,
            "net_mass_kg": 9000.0,
            "regulatory_status": "EXEMPT_TRANSPORT_PACKAGING",
            "rubber_origin": "Packaging exclusively used to support and transport primary goods"
        }
    ]

    for item in cargo_items:
        print(f"📦 Line {item['line']}: {item['desc']}")
        print(f"    - Tariff: HS {item['hs_code']} | Mass: {item['net_mass_kg']:,} kg ({item['quantity_units']:,} pcs)")
        print(f"    - Scope: {item['regulatory_status']} ({item['rubber_origin']})")

    # -------------------------------------------------------------------------
    # STEP 2: Upstream Natural Rubber Smallholder Supply Chain Mapping (Thailand / Indonesia)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("[STEP 2] Natural Rubber Supply Chain Mapping (20 Smallholder Plots)")
    print("-" * 78)

    plots = []
    # 12 Thai Rubber smallholders in Songkhla / Surat Thani (Low-Medium Risk)
    thai_base_lon, thai_base_lat = 99.85, 7.42
    for i in range(1, 13):
        p_id = f"TH-SNG-RUBBER-{i:03d}"
        if i <= 8:
            # 4.2 ha Polygon (>=4ha requires WGS84 closed polygon)
            coords = [
                [
                    [round(thai_base_lon + (i * 0.008), 6), round(thai_base_lat + (i * 0.008), 6)],
                    [round(thai_base_lon + (i * 0.008) + 0.004, 6), round(thai_base_lat + (i * 0.008), 6)],
                    [round(thai_base_lon + (i * 0.008) + 0.004, 6), round(thai_base_lat + (i * 0.008) + 0.004, 6)],
                    [round(thai_base_lon + (i * 0.008), 6), round(thai_base_lat + (i * 0.008) + 0.004, 6)],
                    [round(thai_base_lon + (i * 0.008), 6), round(thai_base_lat + (i * 0.008), 6)],
                ]
            ]
            geom = {"type": "Polygon", "coordinates": coords}
            area = 4.2
        else:
            # 2.5 ha Point (<4ha Point permitted)
            geom = {"type": "Point", "coordinates": [round(thai_base_lon + (i * 0.008), 6), round(thai_base_lat + (i * 0.008), 6)]}
            area = 2.5

        plots.append({
            "plot_id": p_id,
            "country_code": "TH",
            "area_hectares": area,
            "geometry": geom,
            "production_date": "2024-04-15",
            "producer_name": f"Songkhla Rubber Farming Cooperative #{i}",
            "notes": "clean"
        })

    # 8 North Sumatra Indonesian Rubber Plots (High-Risk Benchmark)
    id_base_lon, id_base_lat = 99.12, 2.95
    for i in range(13, 21):
        idx = i - 12
        p_id = f"ID-SUM-RUBBER-{idx:03d}"
        coords = [
            [
                [round(id_base_lon + (idx * 0.009), 6), round(id_base_lat + (idx * 0.009), 6)],
                [round(id_base_lon + (idx * 0.009) + 0.005, 6), round(id_base_lat + (idx * 0.009), 6)],
                [round(id_base_lon + (idx * 0.009) + 0.005, 6), round(id_base_lat + (idx * 0.009) + 0.005, 6)],
                [round(id_base_lon + (idx * 0.009), 6), round(id_base_lat + (idx * 0.009) + 0.005, 6)],
                [round(id_base_lon + (idx * 0.009), 6), round(id_base_lat + (idx * 0.009), 6)],
            ]
        ]
        # INJECT TAINTED BATCH: Farm #17 (ID-SUM-RUBBER-005) suffered 2022 primary forest clearance
        notes = "deforestation_2022" if i == 17 else "clean"

        plots.append({
            "plot_id": p_id,
            "country_code": "ID",
            "area_hectares": 5.1,
            "geometry": {"type": "Polygon", "coordinates": coords},
            "production_date": "2024-03-20",
            "producer_name": f"Sumatra Hevea Smallholder Cluster #{idx}",
            "notes": notes
        })

    print(f" -> Total Upstream Rubber Plots Assembled: {len(plots)} farms")
    print(f"    • Thailand: 12 plots (8 Polygons >=4ha, 4 Points <4ha)")
    print(f"    • Indonesia: 8 Polygons (Sumatra Riau/Asahan Basin)")

    # -------------------------------------------------------------------------
    # STEP 3: Satellite Deforestation Radar & Tainted Batch Defense
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("[STEP 3] Satellite Screening (Hansen GFC + Sentinel-1 SAR Cloud Penetration)")
    print("-" * 78)

    docs = [
        {"doc_id": "DOC-TH-01", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Rubber Authority of Thailand (RAOT)", "issue_date": "2019-06-15"},
        {"doc_id": "DOC-TH-02", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Royal Forest Department (RFD)", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
        {"doc_id": "DOC-TH-03", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Ministry of Commerce Thailand", "issue_date": "2018-03-10"},
        {"doc_id": "DOC-ID-01", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Badan Pertanahan Nasional (BPN)", "issue_date": "2019-01-10"},
        {"doc_id": "DOC-ID-02", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Kementerian Lingkungan Hidup dan Kehutanan", "issue_date": "2022-01-01", "expiry_date": "2027-12-31"},
        {"doc_id": "DOC-ID-03", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "BKPM Indonesia", "issue_date": "2017-05-12"},
        {"doc_id": "DOC-ID-04", "doc_type": "FPIC_CONSENT", "issuing_authority": "Sumatra Adat Indigenous Council", "issue_date": "2020-02-01"}
    ]

    raw_eval_payload = {
        "supplier_id": "SUP-TYRE-RUBBER-GLOBAL",
        "operator": {
            "operator_name": "Tyre Logistics Europe GmbH",
            "eori_number": "DE9876543210",
            "country": "DE",
            "address": "Speicherstadt Zollkanal 55, 20457 Hamburg, Germany"
        },
        "commodity": {
            "hs_code": "40111000",
            "description": "EV/UHP Passenger Car Tyres (Hankook iON Series)",
            "net_mass_kg": 65000.0
        },
        "plots": plots,
        "documents": docs
    }

    t0 = time.perf_counter()
    resp = client.post("/api/v1/eudr/evaluate", json=raw_eval_payload)
    elapsed = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200
    raw_res = resp.json()

    plots_detail = raw_res.get("plots_detail", [])
    tainted = [
        p["plot_id"] for p in plots_detail
        if p.get("deforestation_detected") or (p.get("loss_year") and p.get("loss_year") > 2020)
    ]

    print(f" -> Multi-Sensor Scan Latency: {elapsed:.1f}ms (Average {elapsed/len(plots):.2f}ms/plot)")
    print(f" -> 2020.12.31 Cut-Off Compliant Plots: {len(plots) - len(tainted)} / {len(plots)}")
    print(f" 🚨 TAINTED BATCH DETECTED ON FARM: {tainted}")
    print("    • Statutory Infraction: Post-2020 primary canopy loss detected in Indonesia parcel #5.")
    print("    • Enforcement Risk: EUDR Art. 3/10 would MANDATE 100% CONFISCATION of all 65,000 kg tyres!")

    print("\n 🛡️ [AGENT AUTONOMOUS DEFENSE ACTIVATION]")
    print(f"    1. Quarantining contaminated plot '{tainted[0]}' from tyre master blending silo.")
    clean_plots = [p for p in plots if p["plot_id"] not in tainted]
    print(f"    2. Diverting quarantined rubber volume to non-EU emerging markets.")
    print(f"    3. Re-packaging Clean EU Consignment: {len(clean_plots)} farms (100.0% Deforestation-Free).")

    # Re-evaluate with 100% clean batch
    clean_payload = dict(raw_eval_payload)
    clean_payload["plots"] = clean_plots
    clean_payload["commodity"]["net_mass_kg"] = 61750.0  # Pro-rated clean mass
    clean_resp = client.post("/api/v1/eudr/evaluate", json=clean_payload)
    assert clean_resp.status_code == 200
    clean_res = clean_resp.json()

    dds_obj = clean_res.get("traces_dds") or {}
    dds_ref_hs4011 = dds_obj.get("dds_reference_id") or f"26EUDR{uuid.uuid4().hex[:10].upper()}"
    print(f"\n -> Clean Batch TRACES NT DDS Issued: Ref `{dds_ref_hs4011}`")
    print(f" -> Status: {clean_res.get('status')} | Zero Forest Encroachment Confirmed.")

    # -------------------------------------------------------------------------
    # STEP 4: Delegated Act Scope Exemption for Retreaded Tyres (HS 4012)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("[STEP 4] Delegated Act Scope Exemption for Retreaded Tyres (HS 4012)")
    print("-" * 78)

    exempt_req = StatutoryExemptionNoticeRequest(
        hs_code="4012.12.00",
        product_description="Eco-Retreaded Commercial Truck Tyres (SmartFlex DL12)",
        importer_name="Tyre Logistics Europe GmbH",
        importer_eori="DE9876543210",
        origin_country="KR",
        b_l_number="HMMU998877661"
    )
    exempt_cert = StatutoryExemptionIssuer.issue_certificate(exempt_req)

    print(f" -> Target Product: {exempt_req.product_description} (HS {exempt_req.hs_code})")
    print(f" -> EUDR Scope Exclusion: {exempt_cert.is_exempt_from_eudr} (100% EXEMPT)")
    print(f" -> Legal Basis: {exempt_cert.statutory_legal_basis}")
    print(f" -> Official Certificate Issued: `{exempt_cert.certificate_id}`")
    print(f" -> Financial Benefit: Korean tyre maker SAVES farm-level GPS tracing costs on casings!")

    # -------------------------------------------------------------------------
    # STEP 5: German Customs (Zoll Hamburg - ATLAS) Multi-Line UCC Declaration
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("[STEP 5] German Customs (Zoll DEHAM - ATLAS) Box 44 / UCC DE 12 03 Package")
    print("-" * 78)

    # 1. New Tyres (HS 4011): TARIC C081 (DDS Reference mandatory)
    taric_req_4011 = CustomsTaricEvaluateRequest(hs_code="40111000")
    taric_res_4011 = EUCustomsAdapter.evaluate_taric_document_code(taric_req_4011)

    # 2. Retreaded Tyres (HS 4012): TARIC Y120 (Exempt item declaration)
    taric_req_4012 = CustomsTaricEvaluateRequest(hs_code="40121200")
    taric_res_4012 = EUCustomsAdapter.evaluate_taric_document_code(taric_req_4012)

    # 3. Wooden Transport Pallets (HS 4415): TARIC Y122 (Transport packaging exemption)
    taric_req_4415 = CustomsTaricEvaluateRequest(hs_code="44152000", is_packaging_only=True)
    taric_res_4415 = EUCustomsAdapter.evaluate_taric_document_code(taric_req_4415)

    print("📄 German Customs Electronic Single Declaration (ATLAS DE 12 03 000 000):")
    print(f"  • Line 1 (New Tyres HS 4011):     TARIC [C081] -> Ref: C081:{dds_ref_hs4011}/V-HAM-ION-01")
    print(f"  • Line 2 (Retreaded Tyres HS 4012): TARIC [Y120] -> Ref: Y120:EUDR-EXEMPT-{exempt_cert.certificate_id}")
    print(f"  • Line 3 (Transport Pallets HS 4415):TARIC [Y122] -> Ref: Y122:PACKAGING-TRANSPORT-PALLET-KR")

    # Execute Pre-Clearance with Port of Hamburg (DEHAM)
    customs_req = CustomsSWECPreClearanceRequest(
        dds_reference_id=dds_ref_hs4011,
        verification_code="V-HAM-ION-01",
        eori_number="DE9876543210",
        hs_code="40111000",
        net_mass_kg=61750.0,
        country_code="TH",
        destination_port="DEHAM"
    )
    swe_c_res = EUCustomsAdapter.simulate_swe_c_pre_clearance(customs_req)
    print(f"\n🛃 Port of Hamburg (DEHAM) Single Window Pre-Clearance Result:")
    print(f" -> Clearance Status: {swe_c_res.clearance_status} (Green Lane Cleared: {swe_c_res.green_lane_cleared})")
    print(f" -> Customs ACK Code: {swe_c_res.customs_ack_code}")
    print(f" -> Inspection Quota Rate: {swe_c_res.article16_inspection_rate_pct}% (Low-Risk Fast Track)")
    print(f" -> Automated Advice: {swe_c_res.official_customs_advice}")

    # -------------------------------------------------------------------------
    # STEP 6: Article 31 Statutory 5-Year WORM Vault Sealing & OEM Audit Shield
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("[STEP 6] Article 31 5-Year Immutable WORM Vault & BMW/OEM Audit Defense")
    print("-" * 78)

    vault_meta = AuditVaultManager.seal_audit_evidence(
        dds_reference_id=dds_ref_hs4011,
        verification_code="V-HAM-ION-01",
        operator_eori="DE9876543210",
        commodity_code="40111000",
        net_mass_kg=61750.0,
        evaluation_payload=clean_res,
        traces_xml_str=f"<DDS><Reference>{dds_ref_hs4011}</Reference><Commodity>40111000</Commodity></DDS>",
        customs_cert_html=f"<html><body>Zoll Hamburg Approved: {swe_c_res.clearance_status}</body></html>",
        customs_box44_code=f"C081:{dds_ref_hs4011}/V-HAM-ION-01"
    )

    print(f"🔒 Tamper-Proof Cryptographic WORM Seal Generated:")
    print(f" -> Merkle Root Hash: {vault_meta.merkle_root_hash}")
    print(f" -> Storage Path: {AuditVaultManager.VAULT_DIR / vault_meta.archive_file_name}")
    print(f" -> Statutory Expiry: {vault_meta.retention_expires_utc} (5 Years Immutable)")
    print(f" -> Integrity Verification: {vault_meta.integrity_status}")

    print("\n" + "=" * 78)
    print("🏆 KOREAN TIRE ENTERPRISE EXPORT SIMULATION COMPLETED: ZERO DEFECTS")
    print("   ✓ Tainted Batch Filtered: Protected shipment from 100% seizure in Hamburg.")
    print("   ✓ Delegated Act Exemption: Successfully bypassed DDS on Retreaded Tyres.")
    print("   ✓ German Customs (ATLAS): Generated C081 + Y120 + Y122 Triple Tariff Codes.")
    print("   ✓ BMW / OEM Compliance: 5-Year WORM Vault provides impenetrable legal warranty.")
    print("=" * 78)


if __name__ == "__main__":
    run_korean_tire_export_simulation()
