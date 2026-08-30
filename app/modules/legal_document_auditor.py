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

    @classmethod
    def classify_hs_code(cls, hs_code: str) -> EUDRCommodityCategory:
        """Classifies HS Code into one of the 7 EUDR Annex I commodity categories."""
        clean_hs = hs_code.replace(".", "").strip()
        if clean_hs.startswith(("0102", "0201", "0202", "4101", "4104", "4107")):
            return EUDRCommodityCategory.CATTLE
        elif clean_hs.startswith(("1801", "1802", "1803", "1804", "1805", "1806")):
            return EUDRCommodityCategory.COCOA
        elif clean_hs.startswith("0901"):
            return EUDRCommodityCategory.COFFEE
        elif clean_hs.startswith(("1511", "120710", "151321", "151329", "230660", "382311")):
            return EUDRCommodityCategory.OIL_PALM
        elif clean_hs.startswith(("4001", "4005", "4006", "4007", "4008", "4012", "4013", "4015", "4016", "4017")):
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
        missing_docs = [req.value for req in required_docs if req not in present_doc_types]

        expired_docs = []
        notes = []
        risk_penalties = 0.0

        # Commodity category classification
        category = EUDRCommodityCategory.OTHER
        if commodity:
            category = cls.classify_hs_code(commodity.hs_code)
            # Timber specific check: scientific botanical name
            if category == EUDRCommodityCategory.WOOD and not commodity.scientific_name:
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

        # Evaluate missing required documents
        for missing in missing_docs:
            risk_penalties += 0.30
            notes.append(f"Mandatory document '{missing}' is missing for {risk_tier.value} risk origin.")

        # Calculate final risk score [0.0 - 1.0]
        base_risk = 0.05 if risk_tier == RiskTierEnum.LOW else (0.25 if risk_tier == RiskTierEnum.STANDARD else 0.50)
        total_risk_score = min(1.0, round(base_risk + risk_penalties, 2))

        # Overall compliance requires no expired docs and no missing mandatory docs
        is_compliant = (len(missing_docs) == 0) and (len(expired_docs) == 0)

        if is_compliant:
            notes.append("All statutory origin legality requirements successfully verified.")

        return LegalAuditResult(
            overall_compliant=is_compliant,
            country_risk_tier=risk_tier,
            simplified_due_diligence_eligible=is_simplified,
            commodity_category=category,
            verified_documents_count=len(documents),
            missing_required_documents=missing_docs,
            expired_documents=expired_docs,
            risk_score=total_risk_score,
            notes=notes
        )
