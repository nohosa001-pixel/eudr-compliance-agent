from typing import Dict, Any, Optional
from app.modules.producer_adapters.base_adapter import (
    BaseProducerAdapter,
    ProducerRegistryVerificationResult,
)
from app.modules.producer_adapters.brazil_car_adapter import BrazilCarAdapter
from app.modules.producer_adapters.ghana_cocoa_adapter import GhanaCocoaAdapter
from app.modules.producer_adapters.cote_divoire_cocoa_adapter import CoteDIvoireCocoaAdapter
from app.modules.producer_adapters.indonesia_timber_palm_adapter import IndonesiaTimberPalmAdapter
from app.modules.producer_adapters.vietnam_coffee_timber_adapter import VietnamCoffeeTimberAdapter
from app.modules.producer_adapters.colombia_coffee_cocoa_adapter import ColombiaCoffeeCocoaAdapter

class ProducerCountryRegistryHub:
    """
    Central router for producer country official registries.
    Auto-detects or routes queries to Brazil CAR, Ghana Cocoa CMS, Côte d'Ivoire CCC,
    Indonesia SIPUHH/ISPO, Malaysia MSPO, Vietnam MARD/VNTLAS, and Colombia FNC SICA/FEDECACAO.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseProducerAdapter] = {
            "BR": BrazilCarAdapter(),
            "GH": GhanaCocoaAdapter(),
            "CI": CoteDIvoireCocoaAdapter(),
            "ID": IndonesiaTimberPalmAdapter(),
            "MY": IndonesiaTimberPalmAdapter(),
            "VN": VietnamCoffeeTimberAdapter(),
            "CO": ColombiaCoffeeCocoaAdapter(),
        }

    def detect_country_code(self, identifier: str) -> Optional[str]:
        clean = identifier.strip().upper()
        if clean.startswith("BR-") or any(clean.startswith(f"{uf}-") for uf in BrazilCarAdapter.BRAZILIAN_STATES.keys()):
            return "BR"
        if clean.startswith("GH-") or "CMS" in clean:
            return "GH"
        if clean.startswith("CI-") or "CCC" in clean or "SODEFOR" in clean:
            return "CI"
        if clean.startswith("ID-") or "SIPUHH" in clean or "ISPO" in clean:
            return "ID"
        if clean.startswith("MY-") or "MSPO" in clean:
            return "MY"
        if clean.startswith("VN-") or "VNTLAS" in clean or "LURC" in clean or "COFFEE" in clean:
            return "VN"
        if clean.startswith("CO-") or "SICA" in clean or "FEDECACAO" in clean:
            return "CO"
        return None

    def verify(self, identifier: str, country_code: Optional[str] = None) -> ProducerRegistryVerificationResult:
        detected = self.detect_country_code(identifier)
        if country_code and country_code.upper() in self._adapters:
            code = country_code.upper()
        elif detected and detected in self._adapters:
            code = detected
        else:
            code = (country_code or detected or "UNKNOWN").upper()

        adapter = self._adapters.get(code)

        if not adapter:
            return ProducerRegistryVerificationResult(
                country_code=code,
                registry_name="Unknown / Generic Registry",
                identifier=identifier,
                is_valid=False,
                status="UNSUPPORTED_PRODUCER_REGISTRY",
                spatial_coverage_status="UNSUPPORTED",
                deforestation_infraction_flag=True,
                details={
                    "error": f"Producer country code '{code}' has no integrated public registry adapter.",
                    "supported_countries": list(self._adapters.keys())
                }
            )

        return adapter.verify_registration(identifier)
