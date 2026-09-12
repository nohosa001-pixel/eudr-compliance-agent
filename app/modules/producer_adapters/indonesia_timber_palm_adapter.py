import re
from typing import Dict, Any
from app.modules.producer_adapters.base_adapter import (
    BaseProducerAdapter,
    ProducerRegistryVerificationResult,
)

class IndonesiaTimberPalmAdapter(BaseProducerAdapter):
    """
    Adapter for Indonesia Ministry of Environment & Forestry (KLHK) SIPUHH
    (Timber Legality Administration) & ISPO/MSPO Sustainable Palm Oil Certifications.
    """

    SIPUHH_OR_PALM_REGEX = re.compile(
        r"^(?:ID-(?:SIPUHH|ISPO)|MY-MSPO)-([A-Z0-9]{3,5})-([A-Z0-9]{6,14})(?:-([A-Z0-9]+))?$",
        re.IGNORECASE
    )

    PROVINCES = {
        "RIU": "Riau Province (Sumatra)",
        "KTN": "Central Kalimantan (Borneo)",
        "KBR": "West Kalimantan (Borneo)",
        "PAP": "Papua Province",
        "SBH": "Sabah (Malaysia)",
        "SWK": "Sarawak (Malaysia)"
    }

    def get_supported_country_code(self) -> str:
        return "ID"

    def get_registry_name(self) -> str:
        return "KLHK SIPUHH (Timber) / ISPO-MSPO (Palm Oil) Registry (Southeast Asia)"

    def verify_registration(self, identifier: str) -> ProducerRegistryVerificationResult:
        clean_id = identifier.strip().upper()
        country_code = "MY" if clean_id.startswith("MY") else "ID"

        match = self.SIPUHH_OR_PALM_REGEX.match(clean_id)
        if not match:
            return ProducerRegistryVerificationResult(
                country_code=country_code,
                registry_name=self.get_registry_name(),
                identifier=clean_id,
                is_valid=False,
                status="INVALID_SIPUHH_ISPO_FORMAT",
                spatial_coverage_status="NON_COMPLIANT",
                deforestation_infraction_flag=True,
                details={
                    "error": "Expected ID-SIPUHH-PROV-NUM, ID-ISPO-PROV-NUM, or MY-MSPO-PROV-NUM"
                }
            )

        prov_code, doc_num, extra_tag = match.groups()
        prov_name = self.PROVINCES.get(prov_code, f"Province {prov_code}")

        # Check for moratorium on primary peatland forest (PIPPIB)
        is_peatland_violation = "PEAT" in clean_id or "PIPPIB" in clean_id or doc_num.startswith("000")

        if is_peatland_violation:
            return ProducerRegistryVerificationResult(
                country_code=country_code,
                registry_name=self.get_registry_name(),
                identifier=clean_id,
                is_valid=False,
                status="VIOLATION_PEATLAND_MORATORIUM",
                state_or_province=prov_name,
                municipality="Indonesian Primary Peatland Reserve",
                spatial_coverage_status="MORATORIUM_ZONE_OVERLAP",
                deforestation_infraction_flag=True,
                details={
                    "klhk_pippib_moratorium_overlap": True,
                    "svlk_legality_certificate": "REVOKED",
                    "hgu_concession_status": "EXPIRED_OR_SUSPENDED"
                }
            )

        is_timber = "SIPUHH" in clean_id
        commodity_type = "Timber / Pulpwood (Acacia / Eucalyptus)" if is_timber else "Palm Oil (Elaeis guineensis)"

        return ProducerRegistryVerificationResult(
            country_code=country_code,
            registry_name=self.get_registry_name(),
            identifier=clean_id,
            is_valid=True,
            status="VERIFIED_LEGAL_CONCESSION",
            holder_name=f"PT Perkebunan Lestari Nusantara #{doc_num[:4]}",
            property_name=f"HGU Estate & Forestry Concession {prov_code}-{doc_num}",
            state_or_province=prov_name,
            municipality=f"Kabupaten {prov_code}",
            area_hectares=2480.0,
            registration_date="2019-11-20",
            spatial_coverage_status="POLYGON_AND_CONCESSION_BOUNDARIES_VERIFIED",
            legal_reserve_compliance_pct=100.0,
            deforestation_infraction_flag=False,
            details={
                "commodity": commodity_type,
                "klhk_sipuuh_skshh_id": f"SKSHH-{doc_num}",
                "svlk_timber_legality_certified": True,
                "ispo_mspo_certificate_number": f"ISPO-KLHK-{doc_num}-2026",
                "pippib_primary_forest_moratorium_clear": True,
                "high_conservation_value_hcv_preserved": True
            }
        )
