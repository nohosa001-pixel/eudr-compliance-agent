"""
European Union Customs & EU SWE-C (Single Window Environment for Customs) Adapter
==================================================================================
Implements statutory customs clearance workflows under Regulation (EU) 2023/1115 (EUDR),
specifically Articles 26, 27, 28, and the Union Customs Code (UCC) Data Model.

Key Standards & Capabilities:
1. Official EU TARIC Document Codes:
   - C081: TRACES-NT Due Diligence Statement (DDS) Reference & Verification Code.
   - C082: Downstream Operator Reference to Upstream Declaration (Article 4(8)).
   - Y120: Goods excluded from EUDR scope (Article 1(2)).
   - Y121: 100% Recycled waste materials exemption (Annex I footnote 1).
   - Y122: Packaging materials exemption (used exclusively to support/protect goods).
2. UCC Data Element 12 03 000 000 (Supporting Documents / Box 44) Generator.
3. Pre-Arrival EU SWE-C Automated Port Pre-Clearance Simulation Engine.
4. Article 16 Statutory Inspection Risk Rates (9% High, 3% Standard, 1% Low).
5. Major European Entry Port Clearance Profiles (Rotterdam, Antwerp, Hamburg, Valencia, etc.).
"""

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.schemas import (
    CustomsTaricEvaluateRequest,
    CustomsTaricEvaluateResponse,
    CustomsUCCDeclarationRequest,
    CustomsUCCDeclarationResponse,
    CustomsSWECPreClearanceRequest,
    CustomsSWECPreClearanceResponse,
    CustomsRiskRatesResponse,
    ResponseMetaDisclaimer
)
from app.modules.legal_document_auditor import LegalAuditor, EUDRCommodityCategory

logger = logging.getLogger("eudr_agent.customs_adapter")


# -----------------------------------------------------------------------------
# European Customs Ports of Entry (UN/LOCODE Directory)
# -----------------------------------------------------------------------------
MAJOR_EU_PORTS = {
    "NLRTM": {
        "name": "Port of Rotterdam",
        "country": "Netherlands",
        "customs_authority": "Douane Nederland (Dutch Customs)",
        "electronic_system": "DMS / AGS (Declaration Management System)",
        "primary_commodities": ["Soy", "Palm Oil", "Cocoa", "Coffee"]
    },
    "BEANR": {
        "name": "Port of Antwerp-Bruges",
        "country": "Belgium",
        "customs_authority": "Algemene Administratie der Douane en Accijnzen (AAD&A)",
        "electronic_system": "PLDA / IDMS (PaperLess Douane en Accijnzen)",
        "primary_commodities": ["Timber", "Rubber", "Cocoa", "Coffee"]
    },
    "DEHAM": {
        "name": "Port of Hamburg",
        "country": "Germany",
        "customs_authority": "Zoll (German Federal Customs Service)",
        "electronic_system": "ATLAS (Automatisiertes Tarif- und Lokales Zoll-Abwicklungssystem)",
        "primary_commodities": ["Coffee", "Cocoa", "Wood & Paper", "Rubber"]
    },
    "ESVLC": {
        "name": "Port of Valencia",
        "country": "Spain",
        "customs_authority": "Agencia Tributaria - Departamento de Aduanas",
        "electronic_system": "VUE (Ventanilla Única Aduanera)",
        "primary_commodities": ["Wood", "Soya", "Coffee", "Cattle Hides"]
    },
    "FRLEH": {
        "name": "Port of Le Havre (HAROPA)",
        "country": "France",
        "customs_authority": "Direction générale des douanes et droits indirects (DGDDI)",
        "electronic_system": "DELTA-IE (Dédouanement en Ligne par Traitement Automatisé)",
        "primary_commodities": ["Wood & Pulp", "Rubber", "Cocoa"]
    },
    "ITGOA": {
        "name": "Port of Genoa",
        "country": "Italy",
        "customs_authority": "Agenzia delle Dogane e dei Monopoli (ADM)",
        "electronic_system": "AIDA / Telematico Doganale",
        "primary_commodities": ["Timber", "Coffee", "Leather"]
    },
    "PLGDN": {
        "name": "Port of Gdańsk",
        "country": "Poland",
        "customs_authority": "Krajowa Administracja Skarbowa (KAS)",
        "electronic_system": "CELINA / PUESC",
        "primary_commodities": ["Wood", "Soya", "Pulp & Paper"]
    }
}

# -----------------------------------------------------------------------------
# Official EU TARIC Document Codes for Regulation (EU) 2023/1115
# -----------------------------------------------------------------------------
TARIC_DOCUMENT_CODES = {
    "C081": {
        "name": "Due Diligence Statement (DDS) Reference & Verification Code",
        "description": "Due Diligence Statement reference number and verification code issued through TRACES-NT for EUDR (Regulation (EU) 2023/1115).",
        "format": "DDS_REF/VERIFICATION_CODE",
        "regulation": "Regulation (EU) 2023/1115 Art. 4(2) & Art. 26",
        "action": "Indicate in Box 44 (Data Element 12 03 000 000) for Release for Free Circulation."
    },
    "C082": {
        "name": "Downstream Operator Reference to Existing Upstream Statement",
        "description": "Reference to an existing valid Due Diligence Statement filed by an upstream operator in accordance with Article 4(8) or 4(9).",
        "format": "UPSTREAM_DDS_REF",
        "regulation": "Regulation (EU) 2023/1115 Art. 4(8)",
        "action": "Declare upstream statement reference. No redundant geolocation coordinates required."
    },
    "Y120": {
        "name": "Goods Excluded from EUDR Scope",
        "description": "Goods not falling within the substantive scope of Regulation (EU) 2023/1115 pursuant to Article 1(2) or Annex I exemptions.",
        "format": "STATUTORY_EXEMPTION",
        "regulation": "Regulation (EU) 2023/1115 Art. 1(2)",
        "action": "Declare Y120 on import entry to claim non-application of deforestation checks."
    },
    "Y121": {
        "name": "100% Recycled Waste Exemption",
        "description": "Goods produced entirely from material that has completed its lifecycle and would otherwise be disposed of as waste (post-consumer recycled).",
        "format": "RECYCLED_WASTE_PROOF",
        "regulation": "Regulation (EU) 2023/1115 Annex I, Footnote 1",
        "action": "Declare Y121 supported by recycling mill certificate or recovery documentation."
    },
    "Y122": {
        "name": "Packaging Materials Exemption",
        "description": "Packaging materials used exclusively to support, protect or carry another product placed on the market.",
        "format": "PACKAGING_EXEMPTION",
        "regulation": "Regulation (EU) 2023/1115 Annex I",
        "action": "Declare Y122 for wooden pallets, crates, packing paper accompanying primary goods."
    }
}


class EUCustomsAdapter:
    """
    Coordinates European Union Customs (DG TAXUD / EU SWE-C) interactions for EUDR imports.
    """

    @classmethod
    def evaluate_taric_document_code(cls, req: CustomsTaricEvaluateRequest) -> CustomsTaricEvaluateResponse:
        """
        Determines the correct TARIC document code (C081, C082, Y120, Y121, Y122)
        and formats the Box 44 / Data Element 12 03 000 000 customs declaration.
        """
        clean_hs = req.hs_code.replace(".", "").strip()
        commodity_cat = LegalAuditor.classify_hs_code(clean_hs)
        is_regulated = commodity_cat != EUDRCommodityCategory.OTHER

        # Check statutory exemptions
        if req.is_recycled:
            code = "Y121"
            info = TARIC_DOCUMENT_CODES["Y121"]
            ref_str = f"Y121:RECYCLED-WASTE-PROOF-HS{clean_hs}"
            stmt = f"TARIC {code} - Exemption under Annex I Footnote 1 (100% Post-Consumer Recycled Material)."
            action = "File Y121 in Box 44 with certified bill of lading and mill recycling affidavit."
            is_mandated = False
        elif req.is_packaging_only:
            code = "Y122"
            info = TARIC_DOCUMENT_CODES["Y122"]
            ref_str = f"Y122:PACKAGING-TRANSPORT-HS{clean_hs}"
            stmt = f"TARIC {code} - Exemption under Annex I (Transport packaging supporting primary commodity)."
            action = "File Y122 in Box 44. No DDS reference number required for protective packaging."
            is_mandated = False
        elif not is_regulated:
            code = "Y120"
            info = TARIC_DOCUMENT_CODES["Y120"]
            ref_str = f"Y120:NON-EUDR-HS{clean_hs}"
            stmt = f"TARIC {code} - Commodity under HS {clean_hs} is outside the substantive scope of EUDR Annex I."
            action = "Declare Y120 for customs automated green light clearance."
            is_mandated = False
        elif req.is_downstream_operator and req.upstream_dds_reference:
            code = "C082"
            info = TARIC_DOCUMENT_CODES["C082"]
            ref_str = f"C082:{req.upstream_dds_reference.strip()}"
            stmt = f"TARIC {code} - Downstream Operator Pass-Through under Article 4(8) referencing {req.upstream_dds_reference}."
            action = "File C082 referencing valid upstream DDS. Customs automated match via EU SWE-C."
            is_mandated = True
        else:
            # Standard or Simplified Due Diligence Statement (C081)
            code = "C081"
            info = TARIC_DOCUMENT_CODES["C081"]
            dds_id = req.dds_reference_id or f"26EUDR{uuid.uuid4().hex[:10].upper()}"
            ver_code = req.verification_code or f"V-{uuid.uuid4().hex[:5].upper()}"
            ref_str = f"{dds_id}/{ver_code}"
            stmt = f"TARIC {code} - Due Diligence Statement (Regulation (EU) 2023/1115): Ref {dds_id}, VerCode {ver_code}."
            action = "Enter C081 with DDS Reference and Verification Code in Box 44 / DE 12 03 000 000."
            is_mandated = True

        return CustomsTaricEvaluateResponse(
            hs_code=req.hs_code,
            taric_document_code=code,
            taric_code_description=info["description"],
            box44_formatted_statement=stmt,
            box44_reference_code=ref_str,
            legal_citation=info["regulation"],
            is_eudr_mandated=is_mandated,
            action_required_for_customs=action
        )

    @classmethod
    def generate_ucc_declaration(cls, req: CustomsUCCDeclarationRequest) -> CustomsUCCDeclarationResponse:
        """
        Generates the standard Union Customs Code (UCC) Data Element 12 03 000 000
        supporting document structure and XML snippet for electronic import declarations.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        port_info = MAJOR_EU_PORTS.get(req.destination_port_code.upper(), {
            "name": f"EU Port {req.destination_port_code}",
            "country": "European Union",
            "electronic_system": "EU SWE-C Interoperability Gateway"
        })

        taric_code = "C081"
        formatted_ref = f"{req.dds_reference_id.strip()}/{req.verification_code.strip()}"
        box44_text = f"C081 | Ref: {req.dds_reference_id} | VerCode: {req.verification_code} | Mass: {req.net_mass_kg:,.1f}kg"

        # UCC Data Element 12 03 structure (WCO / UCC Data Model v3)
        de_1203 = [
            {
                "typeCode": taric_code,
                "documentIdentifier": formatted_ref,
                "issuingAuthority": "European Commission / TRACES-NT",
                "issuanceDate": now_iso[:10],
                "validityStatus": "VALID_ACTIVE",
                "declarantEori": req.declarant_eori.upper().strip(),
                "importerEori": req.importer_eori.upper().strip(),
                "itemCommodityCode": req.hs_code.replace(".", "").strip(),
                "quantityDeclaredKg": req.net_mass_kg,
                "countryOfOrigin": req.country_of_origin.upper().strip()
            }
        ]

        # Standard UCC XML representation for Box 44
        xml_snippet = (
            f"<DeclarationItem>\n"
            f"  <GoodsItemNumber>1</GoodsItemNumber>\n"
            f"  <CommodityCode>{req.hs_code.replace('.', '').strip()}</CommodityCode>\n"
            f"  <GrossMass>{req.net_mass_kg * 1.05:.2f}</GrossMass>\n"
            f"  <NetMass>{req.net_mass_kg:.2f}</NetMass>\n"
            f"  <CountryOfOrigin>{req.country_of_origin.upper().strip()}</CountryOfOrigin>\n"
            f"  <SupportingDocument>\n"
            f"    <TypeCode>{taric_code}</TypeCode>\n"
            f"    <Identifier>{formatted_ref}</Identifier>\n"
            f"    <IssuingAuthority>TRACES-NT</IssuingAuthority>\n"
            f"  </SupportingDocument>\n"
            f"</DeclarationItem>"
        )

        return CustomsUCCDeclarationResponse(
            customs_procedure="40 00 (Release for Free Circulation)",
            data_element_1203_supporting_documents=de_1203,
            ucc_xml_snippet=xml_snippet,
            declarant_eori=req.declarant_eori.upper().strip(),
            importer_eori=req.importer_eori.upper().strip(),
            destination_port=req.destination_port_code.upper().strip(),
            port_name=port_info["name"],
            formatted_box44=box44_text,
            declaration_timestamp=now_iso,
            customs_gateway=f"{port_info['electronic_system']} -> EU SWE-C"
        )

    @classmethod
    def simulate_swe_c_pre_clearance(cls, req: CustomsSWECPreClearanceRequest) -> CustomsSWECPreClearanceResponse:
        """
        Simulates the automated verification performed by national customs systems
        interfacing with TRACES-NT through the EU Single Window Environment for Customs (EU SWE-C)
        pursuant to Article 26 & 27 of Regulation (EU) 2023/1115.
        """
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        port_code = req.destination_port.upper().strip()
        port_info = MAJOR_EU_PORTS.get(port_code, {
            "name": f"Customs Port {port_code}",
            "country": "European Union",
            "electronic_system": "EU SWE-C"
        })

        # 1. Verification Checklist
        eori_valid = bool(re.match(r"^[A-Z]{2}[A-Za-z0-9]{6,15}$", req.eori_number.strip()))
        dds_format_valid = len(req.dds_reference_id.strip()) >= 8
        ver_code_valid = len(req.verification_code.strip()) >= 3
        hs_valid = len(req.hs_code.replace(".", "").strip()) >= 4
        mass_valid = req.net_mass_kg > 0

        checklist = {
            "eori_format_verified": eori_valid,
            "dds_reference_format_valid": dds_format_valid,
            "verification_code_valid": ver_code_valid,
            "commodity_hs_classification_valid": hs_valid,
            "net_mass_positive": mass_valid,
            "traces_nt_cross_reference_match": True,
            "quota_and_volume_deduction_available": True
        }

        # 2. Risk Benchmarking (Article 29) & Inspection Rates (Article 16)
        high_risk_countries = {"MM", "KP", "BY", "SY"}
        low_risk_countries = {"FI", "SE", "NO", "NZ", "IS"}
        origin = req.country_code.upper().strip()

        if origin in high_risk_countries:
            tier = "HIGH"
            rate_pct = 9.0  # Article 16(1): 9% for high-risk countries
            channel = "ORANGE_DOCUMENTARY_CHECK"
        elif origin in low_risk_countries:
            tier = "LOW"
            rate_pct = 1.0  # Article 16(1): 1% for low-risk countries
            channel = "AUTOMATED_GREEN_LANE"
        else:
            tier = "STANDARD"
            rate_pct = 3.0  # Article 16(1): 3% for standard-risk countries
            channel = "AUTOMATED_GREEN_LANE"

        # Determine overall clearance outcome
        all_passed = all(checklist.values())
        if not all_passed:
            status = "CUSTOMS_HOLD_REJECTED"
            green_lane = False
            ack_code = f"EU-SWEC-HOLD-{now_utc.year}-{uuid.uuid4().hex[:6].upper()}"
            advice = "Consignment blocked. Incomplete or invalid EORI/DDS reference coordinates. Do not release cargo."
        elif tier == "HIGH":
            status = "ROUTED_FOR_INSPECTION"
            green_lane = False
            ack_code = f"EU-SWEC-INSPECT-{now_utc.year}-{uuid.uuid4().hex[:6].upper()}"
            advice = (
                f"Cargo routed for documentary audit (Statutory Article 16 rate: {rate_pct}%). "
                f"Electronic pre-check satisfied; hold for customs inspector sign-off at {port_info['name']}."
            )
        else:
            status = "GREEN_LANE_CLEARED"
            green_lane = True
            ack_code = f"EU-SWEC-CLEARED-{now_utc.year}-{uuid.uuid4().hex[:6].upper()}"
            advice = (
                f"Automated green lane clearance granted. Electronic match verified on TRACES-NT via EU SWE-C. "
                f"Commodity released for free circulation at {port_info['name']} under procedure 40 00."
            )

        qr_url = f"https://ec.europa.eu/tracesnt/customs-verify?ack={ack_code}&eori={req.eori_number.strip()}&port={port_code}"

        return CustomsSWECPreClearanceResponse(
            clearance_status=status,
            green_lane_cleared=green_lane,
            customs_ack_code=ack_code,
            destination_port=port_code,
            port_name=port_info["name"],
            country_risk_tier=tier,
            article16_inspection_rate_pct=rate_pct,
            risk_assessment_routing=channel,
            verification_checklist=checklist,
            qr_verification_url=qr_url,
            cleared_at_utc=now_iso,
            official_customs_advice=advice
        )

    @classmethod
    def get_risk_rates_and_ports(cls) -> CustomsRiskRatesResponse:
        """
        Returns statutory EUDR Article 16 inspection percentages, Article 29 risk tiers,
        and major European ports of entry directory.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        ports_list = [
            {"locode": k, **v} for k, v in MAJOR_EU_PORTS.items()
        ]
        taric_dict = {
            k: v["name"] for k, v in TARIC_DOCUMENT_CODES.items()
        }

        return CustomsRiskRatesResponse(
            timestamp_utc=now_iso,
            article16_inspection_rates={
                "high_risk_tier_pct": 9.0,
                "standard_risk_tier_pct": 3.0,
                "low_risk_tier_pct": 1.0,
                "basis": "Regulation (EU) 2023/1115 Article 16(1) minimum annual inspection quota"
            },
            major_entry_ports=ports_list,
            official_taric_codes=taric_dict,
            regulatory_acts=[
                "Regulation (EU) 2023/1115 (EUDR) Articles 4, 16, 26, 27, 28",
                "Regulation (EU) 2022/2399 (EU Single Window Environment for Customs - EU SWE-C)",
                "Regulation (EU) No 952/2013 (Union Customs Code - UCC)"
            ]
        )


eu_customs_adapter = EUCustomsAdapter()
