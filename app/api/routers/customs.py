"""
European Customs, EU SWE-C Gateway, and TARIC Evaluation Endpoints.
Regulation (EU) 2023/1115 Articles 26, 27, 28 & UCC Data Element 12 03.
"""
from fastapi import APIRouter
from app.core.config import settings
from app.schemas import (
    CustomsTaricEvaluateRequest,
    CustomsTaricEvaluateResponse,
    CustomsUCCDeclarationRequest,
    CustomsUCCDeclarationResponse,
    CustomsSWECPreClearanceRequest,
    CustomsSWECPreClearanceResponse,
    CustomsRiskRatesResponse,
)
from app.modules.eu_customs_adapter import EUCustomsAdapter

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/customs",
    tags=["European Customs & EU SWE-C Gateway"]
)


@router.post(
    "/taric-evaluate",
    response_model=CustomsTaricEvaluateResponse,
    summary="Evaluate EUDR TARIC Document Code (C081, C082, Y120, Y121, Y122) for Box 44"
)
async def evaluate_customs_taric_code(req: CustomsTaricEvaluateRequest):
    """
    Evaluates commodity HS code and regulatory status to determine the statutory EU TARIC Document Code:
    - **C081**: Standard/Simplified EUDR DDS Reference Number and Verification Code.
    - **C082**: Downstream Operator Reference to Upstream Declaration (Article 4(8)).
    - **Y120**: Goods outside the substantive scope of EUDR Annex I (Article 1(2)).
    - **Y121**: 100% Post-Consumer Recycled Waste Exemption (Annex I Footnote 1).
    - **Y122**: Protective Transport Packaging Exemption.
    """
    return EUCustomsAdapter.evaluate_taric_document_code(req)


@router.post(
    "/ucc-declaration",
    response_model=CustomsUCCDeclarationResponse,
    summary="Generate Union Customs Code (UCC) Data Element 12 03 000 000 Declaration"
)
async def generate_ucc_customs_declaration(req: CustomsUCCDeclarationRequest):
    """
    Generates standard Union Customs Code (UCC) Data Element 12 03 000 000 payload and XML snippet
    compatible with European national customs clearance engines (ATLAS, DELTA-IE, DMS, AGS).
    """
    return EUCustomsAdapter.generate_ucc_declaration(req)


@router.post(
    "/swe-c/pre-clearance",
    response_model=CustomsSWECPreClearanceResponse,
    summary="Simulate Pre-Arrival Automated Customs Clearance via EU SWE-C System"
)
async def simulate_swe_c_pre_clearance(req: CustomsSWECPreClearanceRequest):
    """
    Simulates automated port clearance under Article 26 & 27:
    - Validates EORI declarant credentials and TRACES-NT DDS reference format.
    - Applies Article 16 statutory inspection quota (High 9%, Standard 3%, Low 1%).
    - Returns Green Lane clearance certificate ACK or inspection hold advisory.
    """
    return EUCustomsAdapter.simulate_swe_c_pre_clearance(req)


@router.get(
    "/risk-rates",
    response_model=CustomsRiskRatesResponse,
    summary="Get Statutory Article 16 Customs Inspection Rates & European Entry Port Profiles"
)
async def get_customs_risk_rates_and_ports():
    """
    Returns statutory customs inspection percentages under Regulation (EU) 2023/1115 Article 16
    and electronic port profiles for major entry hubs (Rotterdam, Antwerp, Hamburg, Valencia, etc.).
    """
    return EUCustomsAdapter.get_risk_rates_and_ports()
