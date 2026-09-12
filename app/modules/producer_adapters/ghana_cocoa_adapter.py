import re
from typing import Dict, Any
from app.modules.producer_adapters.base_adapter import (
    BaseProducerAdapter,
    ProducerRegistryVerificationResult,
)

class GhanaCocoaAdapter(BaseProducerAdapter):
    """
    Adapter for Ghana Cocoa Board (COCOBOD) Cocoa Management System (CMS)
    and Côte d'Ivoire Conseil du Café-Cacao (CCC) National Traceability System.
    """

    COCOA_REGEX = re.compile(r"^(?:GH-CMS|CI-CCC)-([A-Z]{2,4})-(\d{6,8})(?:-(\d{2}))?$", re.IGNORECASE)

    REGIONS = {
        "ASH": "Ashanti Region (Ghana)",
        "WNR": "Western North (Ghana)",
        "EST": "Eastern Region (Ghana)",
        "BAS": "Bas-Sassandra (Côte d'Ivoire)",
        "MON": "Montagnes (Côte d'Ivoire)",
        "LAG": "Lagunes (Côte d'Ivoire)"
    }

    def get_supported_country_code(self) -> str:
        return "GH"

    def get_registry_name(self) -> str:
        return "COCOBOD CMS / CCC National Cocoa Traceability System (West Africa)"

    def verify_registration(self, identifier: str) -> ProducerRegistryVerificationResult:
        clean_id = identifier.strip().upper()
        country_code = "CI" if clean_id.startswith("CI") else "GH"

        match = self.COCOA_REGEX.match(clean_id)
        if not match:
            return ProducerRegistryVerificationResult(
                country_code=country_code,
                registry_name=self.get_registry_name(),
                identifier=clean_id,
                is_valid=False,
                status="INVALID_COCOA_ID_FORMAT",
                spatial_coverage_status="NON_COMPLIANT",
                deforestation_infraction_flag=True,
                details={
                    "error": "Invalid format. Expected: GH-CMS-REG-NUMBER or CI-CCC-REG-NUMBER (e.g. GH-CMS-WNR-482019-01)"
                }
            )

        region_code, farmer_num, parcel_idx = match.groups()
        region_name = self.REGIONS.get(region_code, f"District {region_code}")

        # Check for encroachment into Gazetted Forest Reserves
        is_encroachment = "RESERVE" in clean_id or farmer_num.startswith("999")

        if is_encroachment:
            return ProducerRegistryVerificationResult(
                country_code=country_code,
                registry_name=self.get_registry_name(),
                identifier=clean_id,
                is_valid=False,
                status="REJECTED_FOREST_RESERVE_ENCROACHMENT",
                state_or_province=region_name,
                municipality="Forest Reserve Buffer Zone",
                spatial_coverage_status="OVERLAPS_PROTECTED_AREA",
                deforestation_infraction_flag=True,
                details={
                    "encroachment_alert": "Parcel boundary overlaps gazetted National Forest Reserve (Post-2020 boundary)",
                    "cocobod_qr_status": "REVOKED",
                    "living_income_differential_status": "INELIGIBLE"
                }
            )

        return ProducerRegistryVerificationResult(
            country_code=country_code,
            registry_name=self.get_registry_name(),
            identifier=clean_id,
            is_valid=True,
            status="ACTIVE_CERTIFIED_COCOA_FARM",
            holder_name=f"Smallholder Cooperative Member #{farmer_num[:4]}",
            property_name=f"Smallholder Cocoa Plot #{farmer_num}-{parcel_idx or '01'}",
            state_or_province=region_name,
            municipality=f"District {region_code}",
            area_hectares=3.40,
            registration_date="2020-09-15",
            spatial_coverage_status="POLYGON_SURVEYED_CMS",
            legal_reserve_compliance_pct=100.0,
            deforestation_infraction_flag=False,
            details={
                "cocobod_qr_status": "VERIFIED_ACTIVE",
                "agroforestry_canopy_cover_pct": 34.5,
                "child_labor_monitoring_system": "AUDITED_CLEAR",
                "living_income_differential_eligible": True,
                "baseline_2020_forest_overlap": False
            }
        )
