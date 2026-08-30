from typing import Any, Dict, Optional

class EUDRComplianceException(Exception):
    """Base exception for EUDR compliance pipeline."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class SpatialValidationError(EUDRComplianceException):
    """Raised when coordinates or polygon geometry violates EUDR GIS standards."""
    pass

class DeforestationDetectedError(EUDRComplianceException):
    """Raised when deforestation post-2020 is detected and non-compliant."""
    pass

class LegalAuditError(EUDRComplianceException):
    """Raised when essential origin permits or legal docs are missing/invalid."""
    pass
