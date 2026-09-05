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

class AgentSelfCorrectionError(EUDRComplianceException):
    """
    Exception tailored specifically for autonomous AI agents.
    Provides structured diagnostic hints so LLMs can self-heal parameters.
    """
    def __init__(
        self, 
        message: str, 
        code: str = "AGENT_TOOL_CALL_ERROR",
        recoverable: bool = True,
        suggested_fix: Optional[str] = None,
        agent_action_hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.code = code
        self.recoverable = recoverable
        self.suggested_fix = suggested_fix or "Verify input schema and adjust parameter types."
        self.agent_action_hint = agent_action_hint or "Inspect error details and retry with corrected arguments."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "recoverable": self.recoverable,
                "suggested_fix": self.suggested_fix,
                "agent_action_hint": self.agent_action_hint,
                "details": self.details
            }
        }

