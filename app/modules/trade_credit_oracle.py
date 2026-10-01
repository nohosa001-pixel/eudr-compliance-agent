"""
Autonomous Trade Credit & Lending Oracle (The Sheriff of Agent Finance Bridge)
Collaborates with security-gate-x402 and AgentEscrow to underwrite EUDR-cleared trade finance.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field

from app.modules.agent_security_gate_adapter import AgentSecurityGateAdapter
from app.modules.producer_adapters.registry_hub import ProducerCountryRegistryHub
from app.modules.deforestation_simulator import DeforestationSimulator
from app.modules.inter_agent_mesh import PolygonMetaMaskConfig
from app.schemas import EUDRSupplyChainPayload


COMMODITY_BENCHMARK_USD_PER_KG = {
    "0901": 4.50,   # Coffee (Arabica/Robusta)
    "1801": 8.20,   # Cocoa beans
    "1511": 1.15,   # Palm oil
    "4407": 0.90,   # Sawn wood / Timber
    "4403": 0.65,   # Rough wood / Logs
    "0201": 6.80,   # Bovine meat (fresh/chilled)
    "0202": 6.20,   # Bovine meat (frozen)
    "4001": 2.25,   # Natural rubber
    "1201": 0.58,   # Soya beans
}


class CreditScoreBreakdown(BaseModel):
    satellite_purity_score: float = Field(..., description="0-400 points based on zero post-2020 deforestation")
    land_registry_score: float = Field(..., description="0-300 points based on CAR/SIPUHH/MARD validation")
    operator_governance_score: float = Field(..., description="0-200 points based on EORI, VIES, and Segregation")
    escrow_backing_score: float = Field(..., description="0-100 points based on staked guarantee on AgentEscrow.sol")
    total_credit_score: float = Field(..., description="0-1000 points total score")


class AutonomousLoanOffer(BaseModel):
    loan_reference_id: str
    credit_tier: str  # AAA, AA, A, BBB, REJECT
    is_loan_approved: bool
    estimated_cargo_value_usd: float
    max_loan_amount_usdc: float
    loan_to_value_pct: float
    annual_percentage_rate_apr: float
    loan_tenor_days: int = 90
    settlement_network: str = PolygonMetaMaskConfig.NETWORK_NAME
    chain_id: int = PolygonMetaMaskConfig.CHAIN_ID
    disbursement_token: str = "USDC (Polygon PoS)"
    required_staked_escrow_usdc: float
    escrow_contract_address: str = "0x45ecBfAa2F4B0Bc6ccD3eB2dB9B1Ca49CF121861"  # Polygon AgentEscrow
    slashing_risk_flag: bool = False
    slashing_rationale: Optional[str] = None


class TradeCreditAssessmentResult(BaseModel):
    assessment_id: str
    timestamp_utc: str
    operator_name: str
    operator_eori: str
    commodity_code: str
    commodity_description: str
    security_gate_clearance: Dict[str, Any]
    credit_score: CreditScoreBreakdown
    loan_offer: AutonomousLoanOffer
    underwriting_verdict: str
    executive_summary: str


class TradeCreditUnderwriter:
    """
    Evaluates real-time EUDR satellite signals and legal land registries
    to calculate creditworthiness and underwrite autonomous trade loans.
    """

    def __init__(self):
        self.security_adapter = AgentSecurityGateAdapter()
        self.registry_hub = ProducerCountryRegistryHub()
        self.deforestation_sim = DeforestationSimulator()

    def calculate_cargo_value(self, payload: Any) -> float:
        """Estimates total market cargo value in USD."""
        if isinstance(payload, dict):
            payload = EUDRSupplyChainPayload(**payload)
        if not payload.commodity:
            return 50000.0

        net_mass = payload.commodity.net_mass_kg or 10000.0
        hs_clean = payload.commodity.hs_code.replace(".", "").strip()[:4]
        price_per_kg = COMMODITY_BENCHMARK_USD_PER_KG.get(hs_clean, 2.50)
        return round(net_mass * price_per_kg, 2)

    def evaluate_credit_and_underwrite_loan(
        self,
        payload: Any,
        producer_registry_id: Optional[str] = None,
        staked_escrow_usdc: float = 0.0,
        applicant_agent_id: Optional[str] = None
    ) -> TradeCreditAssessmentResult:
        if isinstance(payload, dict):
            payload = EUDRSupplyChainPayload(**payload)

        assessment_id = f"T-CREDIT-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # ----------------------------------------------------------------------
        # Step 1: security-gate-x402 Front-Line Zero-Trust Shielding
        # ----------------------------------------------------------------------
        commodity_desc = payload.commodity.description if payload.commodity else ""
        hs_code_val = payload.commodity.hs_code if payload.commodity else "0901"
        net_mass_val = payload.commodity.net_mass_kg if payload.commodity else 1000.0
        plots_count = len(payload.plots) if payload.plots else 1
        total_area = sum((p.area_hectares or 1.0) for p in payload.plots) if payload.plots else 2.0

        prompt_check = self.security_adapter.inspect_text_security(commodity_desc)
        fact_check = self.security_adapter.inspect_compliance_fact_check(
            commodity=commodity_desc,
            hs_code=hs_code_val,
            declared_net_mass_kg=net_mass_val,
            plots_count=plots_count,
            total_area_ha=total_area
        )

        sec_cleared = (prompt_check.get("is_safe", True) and fact_check.get("is_plausible", fact_check.get("is_factual", True)))
        sec_details = {
            "prompt_security": prompt_check,
            "fact_checking": fact_check,
            "sheriff_status": "CLEARED" if sec_cleared else "BLOCKED_MALICIOUS"
        }

        # ----------------------------------------------------------------------
        # Step 2: Satellite Deforestation Analysis
        # ----------------------------------------------------------------------
        sat_results = []
        if payload.plots:
            from app.modules.traceability_collector import TraceabilityCollector
            _, spatial_res, _ = TraceabilityCollector.collect_and_validate(payload.plots)
            _, sat_results, _ = DeforestationSimulator.analyze_all_plots(payload.plots, spatial_res)

        deforest_detected = any(s.deforestation_detected for s in sat_results)
        sat_conf_avg = (
            sum(s.confidence_score for s in sat_results) / len(sat_results)
            if sat_results else 0.85
        )

        # ----------------------------------------------------------------------
        # Step 3: Producer Country Public Registry Cross-Check
        # ----------------------------------------------------------------------
        reg_id = producer_registry_id
        if not reg_id:
            for d in payload.documents:
                doc_clean = d.doc_id.upper()
                if any(k in doc_clean for k in ["CAR", "CMS", "CCC", "SIPUHH", "ISPO", "MSPO", "BR-", "GH-", "CI-", "ID-", "MY-", "VN-", "VNTLAS", "LURC", "COFFEE"]):
                    reg_id = d.doc_id
                    break

        reg_result = None
        if reg_id:
            reg_result = self.registry_hub.verify(reg_id)

        # ----------------------------------------------------------------------
        # Step 4: Scoring Algorithm (0 - 1000 Points)
        # ----------------------------------------------------------------------
        # 1. Satellite Purity (0 - 400 pts)
        if deforest_detected:
            sat_score = 0.0
        elif sat_conf_avg >= 0.85:
            sat_score = 400.0
        else:
            sat_score = 260.0

        # 2. Land Registry (0 - 300 pts)
        if reg_result and reg_result.is_valid:
            land_score = 250.0
            if reg_result.spatial_coverage_status in ["POLYGON_VALIDATED_IN_SICAR", "LURC_POLYGON_VERIFIED_IN_MARD", "POLYGON_AND_CONCESSION_BOUNDARIES_VERIFIED"]:
                land_score += 50.0
        elif reg_result and not reg_result.is_valid:
            # Embargo / Moratorium / Illegal Encroachment detected
            land_score = 0.0
        else:
            # No registered ID supplied but has base tenure documents
            doc_types = {d.doc_type.value for d in payload.documents}
            land_score = 150.0 if "LAND_USE_TITLE" in doc_types else 80.0

        # 3. Operator Governance (0 - 200 pts)
        gov_score = 0.0
        if payload.operator and payload.operator.eori_number:
            gov_score += 100.0
        if payload.supplier_id:
            gov_score += 50.0
        if len(payload.documents) >= 2:
            gov_score += 50.0

        # 4. Escrow Staking Backing (0 - 100 pts)
        escrow_score = min(100.0, (staked_escrow_usdc / 5000.0) * 100.0) if staked_escrow_usdc > 0 else 50.0

        # Immediate fraud or injection penalties
        slashing_risk = False
        slashing_note = None

        if not sec_cleared:
            sat_score = 0.0
            land_score = 0.0
            gov_score = 0.0
            slashing_risk = True
            slashing_note = "security-gate-x402 flagged critical prompt injection or agronomic yield fabrication. Staked escrow flagged for on-chain forfeiture."

        if reg_result and reg_result.deforestation_infraction_flag:
            land_score = 0.0
            slashing_risk = True
            slashing_note = f"Producer country registry reported illegal infraction ({reg_result.status}). Staked funds subject to slashing."

        total_score = round(sat_score + land_score + gov_score + escrow_score, 1)

        # ----------------------------------------------------------------------
        # Step 5: Loan Terms and Underwriting
        # ----------------------------------------------------------------------
        cargo_value = self.calculate_cargo_value(payload)

        if slashing_risk or deforest_detected or not sec_cleared:
            tier = "REJECT"
            ltv = 0.0
            apr = 0.0
            approved = False
        elif total_score >= 900.0:
            tier = "AAA"
            ltv = 85.0
            apr = 3.2
            approved = True
        elif total_score >= 800.0:
            tier = "AA"
            ltv = 75.0
            apr = 4.5
            approved = True
        elif total_score >= 700.0:
            tier = "A"
            ltv = 60.0
            apr = 6.0
            approved = True
        elif total_score >= 600.0:
            tier = "BBB"
            ltv = 40.0
            apr = 8.5
            approved = True
        else:
            tier = "REJECT"
            ltv = 0.0
            apr = 0.0
            approved = False

        max_loan = round(cargo_value * (ltv / 100.0), 2)
        required_escrow = round(max_loan * 0.10, 2) if approved else 0.0

        loan_offer = AutonomousLoanOffer(
            loan_reference_id=f"LOAN-X402-{uuid.uuid4().hex[:8].upper()}",
            credit_tier=tier,
            is_loan_approved=approved,
            estimated_cargo_value_usd=cargo_value,
            max_loan_amount_usdc=max_loan,
            loan_to_value_pct=ltv,
            annual_percentage_rate_apr=apr,
            required_staked_escrow_usdc=required_escrow,
            slashing_risk_flag=slashing_risk,
            slashing_rationale=slashing_note
        )

        breakdown = CreditScoreBreakdown(
            satellite_purity_score=sat_score,
            land_registry_score=land_score,
            operator_governance_score=gov_score,
            escrow_backing_score=escrow_score,
            total_credit_score=total_score
        )

        verdict = f"APPROVED_TIER_{tier}" if approved else f"REJECTED_TIER_{tier}"
        summary = (
            f"신용점수 {total_score}점(등급: {tier})으로 평가되었습니다. "
            f"화물 추정가치 ${cargo_value:,.2f} 기준 최대 ${max_loan:,.2f} USDC "
            f"(LTV {ltv}%, 연이율 {apr}%) 대출이 즉시 실행 승인되었습니다."
            if approved else
            f"신용점수 {total_score}점(등급: {tier})으로 대출 승인이 거절되었습니다. 사유: "
            f"{slashing_note or '위성 벌채 신호 감지 또는 규정 미달'}"
        )

        return TradeCreditAssessmentResult(
            assessment_id=assessment_id,
            timestamp_utc=now_iso,
            operator_name=payload.operator.operator_name if payload.operator else "Unknown",
            operator_eori=payload.operator.eori_number if payload.operator else "UNKNOWN",
            commodity_code=payload.commodity.hs_code if payload.commodity else "UNKNOWN",
            commodity_description=payload.commodity.description if payload.commodity else "EUDR Commodity",
            security_gate_clearance=sec_details,
            credit_score=breakdown,
            loan_offer=loan_offer,
            underwriting_verdict=verdict,
            executive_summary=summary
        )
