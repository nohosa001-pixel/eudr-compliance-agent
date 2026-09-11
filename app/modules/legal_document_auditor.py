from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import date
import hashlib
from app.schemas import (
    LegalDocumentInput, 
    ProductionPlotInput, 
    CommodityInfo,
    LegalAuditResult, 
    RiskTierEnum, 
    DocumentTypeEnum,
    EUDRCommodityCategory
)

class LegalAuditor:
    """
    Validates origin legality and regulatory documentation compliance under EUDR.
    - Matches country risk tiers (Low, Standard, High) based on EU benchmarking.
    - Supports Simplified Due Diligence (EUDR Art. 13) for Low Risk countries.
    - Classifies Annex I HS Codes (Cattle, Cocoa, Coffee, Oil Palm, Rubber, Soya, Wood).
    - Enforces species scientific name validation for timber products.
    """

    # EUDR Country Benchmarking Matrix
    COUNTRY_RISK_MAP: Dict[str, RiskTierEnum] = {
        # High Risk
        "MM": RiskTierEnum.HIGH,  # Myanmar
        "CD": RiskTierEnum.HIGH,  # DR Congo
        "BR": RiskTierEnum.HIGH,  # Brazil
        "ID": RiskTierEnum.HIGH,  # Indonesia
        # Low Risk
        "SE": RiskTierEnum.LOW,   # Sweden
        "FI": RiskTierEnum.LOW,   # Finland
        "DE": RiskTierEnum.LOW,   # Germany
        "FR": RiskTierEnum.LOW,   # France
        "CA": RiskTierEnum.LOW,   # Canada
        "US": RiskTierEnum.LOW,   # United States
        "KR": RiskTierEnum.LOW,   # South Korea
        "JP": RiskTierEnum.LOW,   # Japan
        "AT": RiskTierEnum.LOW,   # Austria
        "NO": RiskTierEnum.LOW,   # Norway
    }

    # Mandatory Document Requirements per Risk Tier
    TIER_REQUIREMENTS: Dict[RiskTierEnum, Set[DocumentTypeEnum]] = {
        RiskTierEnum.HIGH: {
            DocumentTypeEnum.LAND_USE_TITLE,
            DocumentTypeEnum.HARVEST_PERMIT,
            DocumentTypeEnum.BUSINESS_LICENSE,
            DocumentTypeEnum.FPIC_CONSENT,
        },
        RiskTierEnum.STANDARD: {
            DocumentTypeEnum.LAND_USE_TITLE,
            DocumentTypeEnum.HARVEST_PERMIT,
            DocumentTypeEnum.BUSINESS_LICENSE,
        },
        RiskTierEnum.LOW: {
            DocumentTypeEnum.LAND_USE_TITLE,
            DocumentTypeEnum.BUSINESS_LICENSE,
        },
    }

    EXEMPTED_HS_CODES: Dict[str, str] = {
        "4101": "Raw hides and skins of bovine (cattle) exempted under July 2026 EUDR revision",
        "4104": "Tanned or crust hides and skins of bovine exempted under July 2026 EUDR revision",
        "4107": "Leather further prepared after tanning exempted under July 2026 EUDR revision",
        "4012": "Retreaded pneumatic tyres of rubber exempted under July 2026 EUDR revision",
        "120110": "Soya beans for sowing/seed exempted under July 2026 EUDR revision",
        "4016": "Other articles of vulcanised rubber exempted under July 2026 EUDR revision",
    }

    @classmethod
    def check_exemption(cls, hs_code: str) -> Tuple[bool, Optional[str]]:
        """Checks if an HS code has been formally exempted from EUDR scope under the 2026 revision."""
        clean_hs = hs_code.replace(".", "").strip()
        for prefix, reason in cls.EXEMPTED_HS_CODES.items():
            if clean_hs.startswith(prefix):
                return True, reason
        return False, None

    @classmethod
    def classify_hs_code(cls, hs_code: str) -> EUDRCommodityCategory:
        """Classifies HS Code into one of the 7 EUDR Annex I commodity categories or EXEMPTED."""
        is_exempt, _ = cls.check_exemption(hs_code)
        if is_exempt:
            return EUDRCommodityCategory.EXEMPTED

        clean_hs = hs_code.replace(".", "").strip()
        if clean_hs.startswith(("0102", "0201", "0202")):
            return EUDRCommodityCategory.CATTLE
        elif clean_hs.startswith(("1801", "1802", "1803", "1804", "1805", "1806")):
            return EUDRCommodityCategory.COCOA
        elif clean_hs.startswith("0901"):
            return EUDRCommodityCategory.COFFEE
        elif clean_hs.startswith(("1511", "120710", "151321", "151329", "230660", "382311")):
            return EUDRCommodityCategory.OIL_PALM
        elif clean_hs.startswith(("4001", "4005", "4006", "4007", "4008", "4013", "4015", "4017")):
            return EUDRCommodityCategory.RUBBER
        elif clean_hs.startswith(("1201", "120810", "1507", "2304")):
            return EUDRCommodityCategory.SOYA
        elif clean_hs.startswith(("44", "47", "48", "9403")):
            return EUDRCommodityCategory.WOOD
        return EUDRCommodityCategory.OTHER

    @classmethod
    def determine_country_risk(cls, country_codes: List[str]) -> RiskTierEnum:
        """Determines the aggregate risk tier (highest risk among origin countries)."""
        highest_risk = RiskTierEnum.LOW
        for code in country_codes:
            code_upper = code.upper()
            tier = cls.COUNTRY_RISK_MAP.get(code_upper, RiskTierEnum.STANDARD)
            if tier == RiskTierEnum.HIGH:
                return RiskTierEnum.HIGH
            elif tier == RiskTierEnum.STANDARD and highest_risk == RiskTierEnum.LOW:
                highest_risk = RiskTierEnum.STANDARD
        return highest_risk

    @classmethod
    def audit_documents(
        cls, 
        documents: List[LegalDocumentInput], 
        plots: List[ProductionPlotInput],
        commodity: Optional[CommodityInfo] = None,
        reference_date: Optional[date] = None
    ) -> LegalAuditResult:
        if not reference_date:
            reference_date = date.today()

        country_codes = list({p.country_code for p in plots})
        risk_tier = cls.determine_country_risk(country_codes)
        is_simplified = (risk_tier == RiskTierEnum.LOW)
        required_docs = cls.TIER_REQUIREMENTS.get(risk_tier, set())

        present_doc_types = {d.doc_type for d in documents}
        notes = []

        # FSC / PEFC Voluntary Forest Certification Equivalency Recognition
        has_fsc_or_pefc = (DocumentTypeEnum.FSC_CERTIFICATE in present_doc_types or DocumentTypeEnum.PEFC_CERTIFICATE in present_doc_types)
        if has_fsc_or_pefc:
            # Internationally recognized certification covers forest management legality, harvest permits, and FPIC
            present_doc_types.add(DocumentTypeEnum.HARVEST_PERMIT)
            present_doc_types.add(DocumentTypeEnum.BUSINESS_LICENSE)
            present_doc_types.add(DocumentTypeEnum.FPIC_CONSENT)
            notes.append("FSC/PEFC Forest Certification recognized: Harvest Permit, Business License, and FPIC legal equivalency applied under EUDR Due Diligence.")

        missing_docs = [req.value for req in required_docs if req not in present_doc_types]

        expired_docs = []
        risk_penalties = 0.0

        # Commodity category classification & exemption detection
        category = EUDRCommodityCategory.OTHER
        is_exempt = False
        exemption_reason = None
        if commodity:
            is_exempt, exemption_reason = cls.check_exemption(commodity.hs_code)
            category = cls.classify_hs_code(commodity.hs_code)
            if is_exempt:
                notes.append(f"Statutory Exemption Notice: {exemption_reason}. Full EUDR DDS filing not legally required.")
            elif category == EUDRCommodityCategory.WOOD and not commodity.scientific_name:
                notes.append("Advisory: Wood/timber commodity (Annex I) should specify botanical scientific species name.")
                risk_penalties += 0.1

        if is_simplified:
            notes.append("Simplified Due Diligence (EUDR Article 13) applied: Origin country classified as Low Risk.")

        # Check each document validity
        for doc in documents:
            # Check expiration
            if doc.expiry_date and doc.expiry_date < reference_date:
                expired_docs.append(f"{doc.doc_id} ({doc.doc_type.value}) expired on {doc.expiry_date}")
                risk_penalties += 0.35

            # Issue date cannot be in the future
            if doc.issue_date > reference_date:
                notes.append(f"Suspicious future issue date on doc {doc.doc_id}: {doc.issue_date}")
                risk_penalties += 0.20

            # Hash verification note
            if not doc.file_hash:
                notes.append(f"Document {doc.doc_id} missing SHA-256 binary hash for tamper verification.")

        # Evaluate missing required documents (exempted goods do not fail due to missing docs)
        if not is_exempt:
            for missing in missing_docs:
                risk_penalties += 0.30
                notes.append(f"Mandatory document '{missing}' is missing for {risk_tier.value} risk origin.")

        # Calculate final risk score [0.0 - 1.0]
        base_risk = 0.00 if is_exempt else (0.05 if risk_tier == RiskTierEnum.LOW else (0.25 if risk_tier == RiskTierEnum.STANDARD else 0.50))
        total_risk_score = min(1.0, round(base_risk + risk_penalties, 2))

        # Overall compliance requires no expired docs and no missing mandatory docs (exempt goods auto-comply)
        is_compliant = is_exempt or ((len(missing_docs) == 0) and (len(expired_docs) == 0))

        if is_compliant and not is_exempt:
            notes.append("All statutory origin legality requirements successfully verified.")

        return LegalAuditResult(
            overall_compliant=is_compliant,
            country_risk_tier=risk_tier,
            simplified_due_diligence_eligible=is_simplified,
            commodity_category=category,
            is_exempt_from_eudr=is_exempt,
            exemption_reason=exemption_reason,
            verified_documents_count=len(documents),
            missing_required_documents=[] if is_exempt else missing_docs,
            expired_documents=expired_docs,
            risk_score=0.0 if is_exempt else total_risk_score,
            notes=notes
        )

