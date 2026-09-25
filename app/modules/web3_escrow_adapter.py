"""Web3 Escrow Adapter for AgentEscrow.sol smart contract.
Implements EIP-712 cryptographic oracle attestation signing and verification
for Autonomous Agent-to-Agent (M2M) settlements on Base, Polygon, and Arbitrum.
"""

from typing import Dict, Any, Optional
import time
from eth_account import Account
from eth_account.messages import encode_typed_data
from app.core.config import settings


class Web3EscrowAdapter:
    """Adapter for interacting with and signing for AgentEscrow.sol smart contracts."""

    EIP712_DOMAIN_NAME = "AgentEscrowOracle"
    EIP712_DOMAIN_VERSION = "1.0.0"

    MESSAGE_TYPES = {
        "EscrowAttestation": [
            {"name": "jobId", "type": "uint256"},
            {"name": "deliverableHash", "type": "bytes32"},
            {"name": "riskScore", "type": "uint8"},
            {"name": "verdict", "type": "string"},
            {"name": "expiresAt", "type": "uint256"}
        ]
    }

    def __init__(
        self,
        contract_address: Optional[str] = None,
        chain_id: Optional[int] = None,
        oracle_private_key: Optional[str] = None
    ):
        self.contract_address = contract_address or settings.AGENT_ESCROW_CONTRACT_ADDRESS
        self.chain_id = chain_id or settings.AGENT_ESCROW_CHAIN_ID
        self.private_key = oracle_private_key or settings.ORACLE_SIGNER_PRIVATE_KEY
        
        # Derive oracle public address
        self.oracle_account = Account.from_key(self.private_key)
        self.oracle_address = self.oracle_account.address

    def get_domain_data(self) -> Dict[str, Any]:
        """Generate EIP-712 Domain Data matching AgentEscrow.sol."""
        return {
            "name": self.EIP712_DOMAIN_NAME,
            "version": self.EIP712_DOMAIN_VERSION,
            "chainId": self.chain_id,
            "verifyingContract": self.contract_address
        }

    def _normalize_deliverable_hash(self, raw_hash: Any) -> bytes:
        """Ensure deliverable hash is a 32-byte bytes object."""
        if isinstance(raw_hash, bytes):
            if len(raw_hash) == 32:
                return raw_hash
            raise ValueError(f"deliverableHash must be exactly 32 bytes, got {len(raw_hash)}")
        
        if isinstance(raw_hash, str):
            clean_hex = raw_hash[2:] if raw_hash.startswith("0x") else raw_hash
            if len(clean_hex) != 64:
                raise ValueError(f"deliverableHash hex string must be 64 characters (32 bytes), got {len(clean_hex)}")
            return bytes.fromhex(clean_hex)
        
        raise TypeError(f"Unsupported deliverableHash type: {type(raw_hash)}")

    def sign_attestation(
        self,
        job_id: int,
        deliverable_hash: Any,
        risk_score: int,
        verdict: str,
        validity_duration_seconds: int = 86400 * 7 # 7 days
    ) -> Dict[str, Any]:
        """Sign an EIP-712 EscrowAttestation struct for AgentEscrow.sol.
        
        Args:
            job_id: On-chain jobId in AgentEscrow contract
            deliverable_hash: 32-byte hash of EUDR report/DDS payload
            risk_score: Deforestation & compliance risk (0-100)
            verdict: 'PASSED' (for release) or 'BLOCKED' (for slashing)
            validity_duration_seconds: Time window before signature expires
            
        Returns:
            Dictionary formatted to directly pass into completeJob or slashJob
        """
        norm_hash = self._normalize_deliverable_hash(deliverable_hash)
        expires_at = int(time.time()) + validity_duration_seconds
        
        message_data = {
            "jobId": int(job_id),
            "deliverableHash": norm_hash,
            "riskScore": int(risk_score),
            "verdict": str(verdict),
            "expiresAt": int(expires_at)
        }

        signable_data = encode_typed_data(
            domain_data=self.get_domain_data(),
            message_types=self.MESSAGE_TYPES,
            message_data=message_data
        )

        signed_msg = self.oracle_account.sign_message(signable_data)

        return {
            "jobId": int(job_id),
            "deliverableHash": "0x" + norm_hash.hex(),
            "riskScore": int(risk_score),
            "verdict": str(verdict),
            "expiresAt": int(expires_at),
            "v": int(signed_msg.v),
            "r": "0x" + hex(signed_msg.r)[2:].zfill(64),
            "s": "0x" + hex(signed_msg.s)[2:].zfill(64),
            "oracleSigner": self.oracle_address,
            "chainId": self.chain_id,
            "verifyingContract": self.contract_address
        }

    def verify_attestation(self, attestation: Dict[str, Any]) -> Dict[str, Any]:
        """Verify an EIP-712 EscrowAttestation cryptographically.
        
        Returns validation status, recovered signer, and expiration status.
        """
        norm_hash = self._normalize_deliverable_hash(attestation["deliverableHash"])
        
        message_data = {
            "jobId": int(attestation["jobId"]),
            "deliverableHash": norm_hash,
            "riskScore": int(attestation["riskScore"]),
            "verdict": str(attestation["verdict"]),
            "expiresAt": int(attestation["expiresAt"])
        }

        domain_data = {
            "name": self.EIP712_DOMAIN_NAME,
            "version": self.EIP712_DOMAIN_VERSION,
            "chainId": int(attestation.get("chainId", self.chain_id)),
            "verifyingContract": attestation.get("verifyingContract", self.contract_address)
        }

        signable_data = encode_typed_data(
            domain_data=domain_data,
            message_types=self.MESSAGE_TYPES,
            message_data=message_data
        )

        v = int(attestation["v"])
        r = int(attestation["r"], 16) if isinstance(attestation["r"], str) else int(attestation["r"])
        s = int(attestation["s"], 16) if isinstance(attestation["s"], str) else int(attestation["s"])

        recovered_address = Account.recover_message(signable_data, vrs=(v, r, s))
        
        is_signer_valid = (recovered_address.lower() == self.oracle_address.lower())
        is_expired = time.time() > int(attestation["expiresAt"])
        is_acceptable_risk = int(attestation["riskScore"]) <= settings.ORACLE_MAX_ACCEPTABLE_RISK_SCORE
        is_passed = (attestation["verdict"] == "PASSED")

        valid = is_signer_valid and (not is_expired)

        action_recommendation = "UNKNOWN"
        if valid and is_passed and is_acceptable_risk:
            action_recommendation = "COMPLETE_JOB (Release Payout & Stake to Worker)"
        elif valid and ((not is_passed) or (not is_acceptable_risk)):
            action_recommendation = "SLASH_JOB (Forfeit Worker Stake & Refund Client)"
        elif is_expired:
            action_recommendation = "EXPIRED (Signature timeout, re-verification required)"
        else:
            action_recommendation = "REJECT (Invalid Oracle Signature)"

        return {
            "is_valid": valid,
            "recovered_signer": recovered_address,
            "expected_oracle": self.oracle_address,
            "is_signer_match": is_signer_valid,
            "is_expired": is_expired,
            "is_acceptable_risk": is_acceptable_risk,
            "action_recommendation": action_recommendation
        }

    def format_solidity_calldata(self, attestation: Dict[str, Any]) -> tuple:
        """Format the proof dict into a Solidity tuple for web3.py / eth_abi calls."""
        return (
            int(attestation["jobId"]),
            bytes.fromhex(attestation["deliverableHash"][2:]),
            int(attestation["riskScore"]),
            str(attestation["verdict"]),
            int(attestation["expiresAt"]),
            int(attestation["v"]),
            bytes.fromhex(attestation["r"][2:]),
            bytes.fromhex(attestation["s"][2:])
        )


# Global singleton instance
web3_escrow_adapter = Web3EscrowAdapter()
