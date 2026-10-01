"""
Universal Escrow Client for EUDRAgent & Security Gate x402 Interoperability.
=============================================================================
Enables EUDRAgent to trigger physical-truth-conditioned on-chain escrow disbursements
via security-gate-x402 UniversalEscrowCore (Domain 3: EUDR_FOREST).

1. request_eudr_truth_attestation(): Obtains EIP-712 EudrTruthAttestation from security-gate-x402.
2. settle_eudr_escrow_direct_split(): Disburses funds directly to smallholders, cooperatives, and mills.
"""

import os
import httpx
from typing import Dict, Any, List, Optional


class UniversalEscrowClient:
    """Client for interoperating with security-gate-x402 Universal Escrow & Truth Adapters."""

    DEFAULT_SECURITY_GATE_URL = "https://agent-security-gate-x402-212942243360.asia-northeast3.run.app"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("SECURITY_GATE_URL") or self.DEFAULT_SECURITY_GATE_URL).rstrip("/")

    def request_eudr_truth_attestation(
        self,
        job_id: str,
        commodity: str,
        country_code: str,
        polygon_coordinates: List[List[float]],
        dds_reference_id: str,
        deforestation_detected: bool,
        legal_harvest_verified: bool,
        satellite_cutoff_date: str = "2020-12-31",
        chain_id: int = 137,
        verifying_contract: str = "0x5555555555555555555555555555555555555555",
        timeout: float = 10.0
    ) -> Dict[str, Any]:
        """Requests cryptographic EIP-712 EudrTruthAttestation from security-gate-x402."""
        payload = {
            "job_id": job_id,
            "commodity": commodity,
            "country_code": country_code,
            "polygon_coordinates": polygon_coordinates,
            "dds_reference_id": dds_reference_id,
            "deforestation_detected": deforestation_detected,
            "legal_harvest_verified": legal_harvest_verified,
            "satellite_cutoff_date": satellite_cutoff_date,
            "chain_id": chain_id,
            "verifying_contract": verifying_contract
        }
        url = f"{self.base_url}/api/v1/truth/eudr"
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    def settle_eudr_escrow_direct_split(
        self,
        job_id: str,
        recipients: List[Dict[str, Any]],
        attestation: Dict[str, Any],
        truth_payload: str = "EUDR Deforestation-Free Satellite Truth Verified",
        chain_id: int = 137,
        verifying_contract: str = "0x5555555555555555555555555555555555555555",
        timeout: float = 10.0
    ) -> Dict[str, Any]:
        """Executes Universal Escrow Direct Split disbursement on security-gate-x402."""
        payload = {
            "job_id": job_id,
            "domain": 3,  # EUDR_FOREST
            "recipients": recipients,
            "truth_payload": truth_payload,
            "attestation": attestation,
            "chain_id": chain_id,
            "verifying_contract": verifying_contract
        }
        url = f"{self.base_url}/api/v1/escrow/universal/settle"
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    def request_solana_eudr_truth_attestation(
        self,
        job_id: str,
        commodity: str,
        country_code: str,
        polygon_coordinates: List[Any],
        dds_reference_id: str,
        deforestation_detected: bool,
        legal_harvest_verified: bool,
        risk_tier: str = "LOW"
    ) -> Dict[str, Any]:
        """Obtains Ed25519 EUDR Truth Attestation for Solana Mainnet."""
        from app.modules.solana_escrow_adapter import solana_escrow_adapter
        return solana_escrow_adapter.sign_eudr_truth_attestation(
            job_id=job_id,
            commodity=commodity,
            country_code=country_code,
            polygon_coordinates=polygon_coordinates,
            dds_reference_id=dds_reference_id,
            deforestation_detected=deforestation_detected,
            legal_harvest_verified=legal_harvest_verified,
            risk_tier=risk_tier
        )

    def settle_solana_eudr_direct_split(
        self,
        job_id: str,
        buyer_wallet: str,
        recipients: List[Dict[str, Any]],
        attestation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes instant SPL-USDC Direct Split on Solana Mainnet."""
        from app.modules.solana_escrow_adapter import solana_escrow_adapter
        return solana_escrow_adapter.execute_solana_direct_split(
            job_id=job_id,
            buyer_wallet=buyer_wallet,
            recipients=recipients,
            attestation=attestation
        )


universal_escrow_client = UniversalEscrowClient()
