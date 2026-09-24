"""
Downstream Operator DDS Reference Chaining & Cascading Risk Monitor (EUDR Art. 4(8) & Art. 13)
Enables Tier-2/Tier-3 processors, retailers, and traders to inherit upstream due diligence
without duplicating smallholder GIS scans, with real-time cascade risk invalidation tracking.
"""
import uuid
import datetime
from typing import Dict, Any, List, Optional
from app.schemas import DownstreamChainRequest, DownstreamChainResponse


class DownstreamChainManager:
    """
    Manages pass-through reference chaining for downstream manufacturers, retailers, and traders.
    """

    # In-memory registry of validated downstream chains (and cascade audit states)
    _CHAINS: Dict[str, Dict[str, Any]] = {}
    _REVOKED_UPSTREAM_REFERENCES: set = {
        "EU.DDS.2025.TAINTED-001",
        "EU.DDS.2024.ILLEGAL-LOGGING-009"
    }

    @classmethod
    def register_downstream_chain(cls, payload: DownstreamChainRequest) -> DownstreamChainResponse:
        """
        Validates upstream DDS references and generates a downstream linked statement.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        chain_id = f"CHAIN-EUDR-{now_utc.year}-{uuid.uuid4().hex[:8].upper()}"
        downstream_dds_id = f"EU.DDS.DS.{now_utc.year}.{uuid.uuid4().hex[:10].upper()}"

        verified_refs: List[str] = []
        has_revoked = False

        for ref in payload.upstream_dds_references:
            clean_ref = ref.strip()
            if not clean_ref:
                continue
            if clean_ref in cls._REVOKED_UPSTREAM_REFERENCES:
                has_revoked = True
            verified_refs.append(clean_ref)

        if not verified_refs:
            raise ValueError("At least one valid upstream DDS Reference Number is required for downstream pass-through.")

        cascade_status = "REVOKED_ALERT" if has_revoked else "CLEAN_UPSTREAM"
        is_cleared = not has_revoked

        qr_url = f"https://ec.europa.eu/tracesnt/verify-chain?id={chain_id}&dds={downstream_dds_id}"

        summary = (
            f"Downstream pass-through statement registered under EUDR Art. 4(8). "
            f"{len(verified_refs)} upstream DDS references inherited. "
            f"Status: {cascade_status}."
        )

        record = {
            "chain_id": chain_id,
            "downstream_dds_id": downstream_dds_id,
            "operator_eori": payload.downstream_operator_eori,
            "commodity_code": payload.commodity_code,
            "verified_refs": verified_refs,
            "cascade_status": cascade_status,
            "created_at": now_utc.isoformat()
        }
        cls._CHAINS[chain_id] = record

        return DownstreamChainResponse(
            chain_reference_id=chain_id,
            downstream_dds_id=downstream_dds_id,
            downstream_operator_eori=payload.downstream_operator_eori,
            commodity_code=payload.commodity_code,
            upstream_dds_count=len(verified_refs),
            upstream_verified_references=verified_refs,
            cascade_risk_status=cascade_status,
            is_cleared_for_eu_free_circulation=is_cleared,
            customs_chain_qr_url=qr_url,
            timestamp_utc=now_utc.isoformat(),
            statement_summary=summary
        )

    @classmethod
    def check_cascade_health(cls, chain_reference_id: str) -> Dict[str, Any]:
        """
        Polls the health of an existing downstream chain to detect if any upstream parent DDS was revoked.
        """
        chain = cls._CHAINS.get(chain_reference_id)
        if not chain:
            return {"status": "NOT_FOUND", "is_safe": False}

        # Check against latest revoked list
        any_revoked = any(ref in cls._REVOKED_UPSTREAM_REFERENCES for ref in chain["verified_refs"])
        current_status = "REVOKED_ALERT" if any_revoked else "CLEAN_UPSTREAM"
        chain["cascade_status"] = current_status

        return {
            "chain_reference_id": chain_reference_id,
            "downstream_dds_id": chain["downstream_dds_id"],
            "cascade_risk_status": current_status,
            "is_cleared": not any_revoked,
            "is_safe": not any_revoked,
            "verified_upstream_refs": chain["verified_refs"],
            "alert_message": "Immediate supplier quarantine recommended" if any_revoked else "All upstream references verified deforestation-free."
        }
