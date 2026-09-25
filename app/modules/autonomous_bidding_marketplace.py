"""Autonomous B2B Reverse-Auction Marketplace for Machine-to-Machine (A2A) Trade.
Enables AI buyer agents to broadcast EUDR-compliant RFQs (Request for Quotation)
and autonomous supplier agents to submit competitive bids.
Matches the optimal low-risk/low-cost bid and instantiates smart escrow contracts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from app.modules.agent_security_gate_adapter import AgentSecurityGateAdapter
from app.modules.agent_escrow_manager import AgentEscrowManager
from app.modules.prometheus_metrics import metrics_collector


class AutonomousBiddingMarketplace:
    """In-memory & autonomous clearing house for Agent-to-Agent commodity RFQs."""

    # In-memory storage for RFQs and Bids
    _rfqs: Dict[str, Dict[str, Any]] = {}
    _bids: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create_rfq(
        cls,
        buyer_agent_id: str,
        buyer_agent_wallet: str,
        commodity: str,
        hs_code: str,
        volume_kg: float,
        max_price_usdc_per_kg: float,
        max_acceptable_risk_score: int = 20,
        destination_port: str = "Rotterdam",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        AI Buyer agent broadcasts an EUDR compliance RFQ to the agent network.
        Validates prompt security and agronomic realism via x402 Security Gate.
        """
        # 1. Security Gate Prompt & AST check
        sec_check = AgentSecurityGateAdapter.inspect_text_security(f"{commodity} {notes}")
        if not sec_check["is_safe"]:
            raise ValueError(f"SecurityGate Blocked RFQ: {sec_check['threats']}")

        # 2. Security Gate Fact-check
        fact_check = AgentSecurityGateAdapter.inspect_compliance_fact_check(
            commodity=commodity,
            hs_code=hs_code,
            declared_net_mass_kg=volume_kg,
            total_area_ha=max(volume_kg / 1000.0, 1.0)
        )
        if not fact_check["is_plausible"]:
            raise ValueError(f"SecurityGate NLI Anomaly in RFQ: {fact_check['anomalies']}")

        rfq_id = f"RFQ-{uuid.uuid4().hex[:10].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()

        rfq_data = {
            "rfq_id": rfq_id,
            "buyer_agent_id": buyer_agent_id,
            "buyer_agent_wallet": buyer_agent_wallet,
            "commodity": commodity,
            "hs_code": hs_code,
            "volume_kg": float(volume_kg),
            "max_price_usdc_per_kg": float(max_price_usdc_per_kg),
            "max_budget_usdc": round(float(volume_kg) * float(max_price_usdc_per_kg), 2),
            "max_acceptable_risk_score": max_acceptable_risk_score,
            "destination_port": destination_port,
            "status": "OPEN",
            "created_at": now_str,
            "bids": [],
            "winning_bid_id": None,
            "escrow_id": None
        }

        cls._rfqs[rfq_id] = rfq_data

        # Update metrics
        metrics_collector.inc_counter("eudr_marketplace_rfqs_total", labels={"commodity": commodity})
        cls._update_active_rfq_gauge()

        return rfq_data

    @classmethod
    def submit_bid(
        cls,
        rfq_id: str,
        seller_agent_id: str,
        seller_agent_wallet: str,
        price_usdc_per_kg: float,
        declared_plots: List[Dict[str, Any]],
        estimated_risk_score: int = 5,
        compliance_diligence_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        AI Supplier agent submits a formal compliance bid for an active RFQ.
        """
        if rfq_id not in cls._rfqs:
            raise KeyError(f"RFQ ID '{rfq_id}' not found.")

        rfq = cls._rfqs[rfq_id]
        if rfq["status"] != "OPEN":
            raise ValueError(f"RFQ '{rfq_id}' is already {rfq['status']}; cannot accept new bids.")

        total_price = round(rfq["volume_kg"] * float(price_usdc_per_kg), 2)
        bid_id = f"BID-{uuid.uuid4().hex[:10].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()

        bid_data = {
            "bid_id": bid_id,
            "rfq_id": rfq_id,
            "seller_agent_id": seller_agent_id,
            "seller_agent_wallet": seller_agent_wallet,
            "price_usdc_per_kg": float(price_usdc_per_kg),
            "total_price_usdc": total_price,
            "declared_plots": declared_plots,
            "estimated_risk_score": estimated_risk_score,
            "compliance_diligence_reference": compliance_diligence_reference,
            "created_at": now_str,
            "status": "SUBMITTED"
        }

        cls._bids[bid_id] = bid_data
        rfq["bids"].append(bid_data)

        # Update metrics
        metrics_collector.inc_counter("eudr_marketplace_bids_total", labels={"seller": seller_agent_id})

        return bid_data

    @classmethod
    def auto_match_rfq(cls, rfq_id: str) -> Dict[str, Any]:
        """
        Autonomous clearing engine:
        Evaluates eligible bids, selects the optimal low-risk/low-cost bid,
        and automatically initiates an Agent Escrow contract.
        """
        if rfq_id not in cls._rfqs:
            raise KeyError(f"RFQ ID '{rfq_id}' not found.")

        rfq = cls._rfqs[rfq_id]
        if rfq["status"] != "OPEN":
            return {
                "matched": False,
                "message": f"RFQ '{rfq_id}' is already {rfq['status']}.",
                "rfq": rfq
            }

        candidate_bids = rfq.get("bids", [])
        if not candidate_bids:
            return {
                "matched": False,
                "message": f"No bids submitted for RFQ '{rfq_id}'.",
                "rfq": rfq
            }

        # Filter valid bids: price <= max_price, risk <= max_risk
        valid_bids = [
            b for b in candidate_bids
            if b["price_usdc_per_kg"] <= rfq["max_price_usdc_per_kg"]
            and b["estimated_risk_score"] <= rfq["max_acceptable_risk_score"]
        ]

        if not valid_bids:
            return {
                "matched": False,
                "message": "No submitted bids meet the price ceiling and risk threshold.",
                "rfq": rfq
            }

        # Sort: lowest price first, tiebreak with lowest risk score
        valid_bids.sort(key=lambda b: (b["price_usdc_per_kg"], b["estimated_risk_score"]))
        winning_bid = valid_bids[0]

        # Update bid and RFQ statuses
        for b in candidate_bids:
            if b["bid_id"] == winning_bid["bid_id"]:
                b["status"] = "ACCEPTED"
            else:
                b["status"] = "REJECTED"

        rfq["status"] = "MATCHED"
        rfq["winning_bid_id"] = winning_bid["bid_id"]

        # Instantiate Autonomous Escrow Contract
        escrow_result = AgentEscrowManager.create_escrow(
            buyer_agent_id=rfq["buyer_agent_id"],
            seller_agent_id=winning_bid["seller_agent_id"],
            buyer_wallet=rfq["buyer_agent_wallet"],
            seller_wallet=winning_bid["seller_agent_wallet"],
            amount_usdc=winning_bid["total_price_usdc"],
            currency="USDC",
            plots=winning_bid.get("declared_plots", []),
            commodity=rfq["commodity"],
            hs_code=rfq["hs_code"],
            net_mass_kg=rfq["volume_kg"],
            destination_market="EU",
            chain_id=8453 # Default Base Mainnet
        )

        escrow_id = escrow_result.escrow_id if hasattr(escrow_result, "escrow_id") else escrow_result.get("escrow_id")
        rfq["escrow_id"] = escrow_id

        cls._update_active_rfq_gauge()

        status_str = escrow_result.status.value if hasattr(escrow_result.status, "value") else str(escrow_result.status)
        vault_addr = getattr(escrow_result, "vault_deposit_address", None) or "0x255F9991233f86B29dB847c8d5b8CB9915e80dCf"

        return {
            "matched": True,
            "rfq_id": rfq_id,
            "winning_bid_id": winning_bid["bid_id"],
            "clearing_price_usdc_per_kg": winning_bid["price_usdc_per_kg"],
            "total_settlement_usdc": winning_bid["total_price_usdc"],
            "seller_agent_id": winning_bid["seller_agent_id"],
            "escrow_id": escrow_id,
            "escrow_status": status_str,
            "escrow_contract": vault_addr,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    @classmethod
    def get_rfq(cls, rfq_id: str) -> Optional[Dict[str, Any]]:
        return cls._rfqs.get(rfq_id)

    @classmethod
    def list_rfqs(cls, status: Optional[str] = None) -> List[Dict[str, Any]]:
        rfq_list = list(cls._rfqs.values())
        if status:
            rfq_list = [r for r in rfq_list if r["status"] == status.upper()]
        return rfq_list

    @classmethod
    def _update_active_rfq_gauge(cls):
        open_count = sum(1 for r in cls._rfqs.values() if r["status"] == "OPEN")
        metrics_collector.set_gauge("eudr_active_rfqs_count", float(open_count))
