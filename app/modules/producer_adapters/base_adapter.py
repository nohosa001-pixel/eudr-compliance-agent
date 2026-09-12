from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ProducerRegistryVerificationResult(BaseModel):
    country_code: str
    registry_name: str
    identifier: str
    is_valid: bool
    status: str
    holder_name: Optional[str] = None
    property_name: Optional[str] = None
    state_or_province: Optional[str] = None
    municipality: Optional[str] = None
    area_hectares: Optional[float] = None
    registration_date: Optional[str] = None
    spatial_coverage_status: str = "POLYGON_AVAILABLE"
    legal_reserve_compliance_pct: Optional[float] = 100.0
    deforestation_infraction_flag: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)

class BaseProducerAdapter(ABC):
    """
    Abstract base adapter for producer country official registries.
    """

    @abstractmethod
    def get_supported_country_code(self) -> str:
        """Returns the ISO 3166-1 alpha-2 country code (e.g. 'BR', 'GH', 'ID')."""
        pass

    @abstractmethod
    def get_registry_name(self) -> str:
        """Returns the official government registry name."""
        pass

    @abstractmethod
    def verify_registration(self, identifier: str) -> ProducerRegistryVerificationResult:
        """Verifies legal land/plot registration status against public records."""
        pass
