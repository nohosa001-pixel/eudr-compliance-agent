"""
Comprehensive End-to-End Payment Integrity & System Error Verification Suite
Tests all payment paths, escrow logic, agent tools, schemas, and math.
"""

import sys
import os
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Suppress Telegram network timeouts in verification
os.environ["TESTING"] = "true"

# Ensure root is first in sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
settings.TELEGRAM_NOTIFICATIONS_ENABLED = False

errors = []
passes = []

def test(name: str):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            try:
                fn(*args, **kwargs)
                passes.append(name)
                print(f"  [PASS] {name}")
            except Exception as e:
                errors.append((name, str(e)))
                print(f"  [FAIL] {name}: {e}")
        return wrapper
    return decorator


print("=" * 70)
print("  EUDR AGENT FULL SYSTEM PAYMENT INTEGRITY VERIFICATION")
print("=" * 70)

# -----------------------------------------------------------------------------
# 1. Configuration & Constants Verification
# -----------------------------------------------------------------------------
print("\n[Phase 1] Pricing Constants & Tier Integrity")

@test("PLAN_PRICING_USDC contains exactly PRO ($700) and ENTERPRISE ($2,500)")
def test_pricing_constants():
    from app.modules.payment_manager import PLAN_PRICING_USDC
    assert "STARTER" not in PLAN_PRICING_USDC, "STARTER must not exist in PLAN_PRICING_USDC"
    assert PLAN_PRICING_USDC.get("PRO") == 700.00, f"Expected PRO to be 700.00, got {PLAN_PRICING_USDC.get('PRO')}"
    assert PLAN_PRICING_USDC.get("ENTERPRISE") == 2500.00, f"Expected ENTERPRISE to be 2500.00, got {PLAN_PRICING_USDC.get('ENTERPRISE')}"

@test("AgentToolsRegistry PLAN_PRICING_USDC matches PaymentManager")
def test_agent_tools_pricing():
    from app.modules.agent_tools import PLAN_PRICING_USDC
    assert "STARTER" not in PLAN_PRICING_USDC
    assert PLAN_PRICING_USDC.get("PRO") == 700.00
    assert PLAN_PRICING_USDC.get("ENTERPRISE") == 2500.00

@test("AgentEscrowManager CLEARING_FEE_RATE is exactly 0.15% (0.0015)")
def test_escrow_clearing_fee_rate():
    from app.modules.agent_escrow_manager import AgentEscrowManager
    assert hasattr(AgentEscrowManager, "CLEARING_FEE_RATE")
    assert AgentEscrowManager.CLEARING_FEE_RATE == 0.0015, f"Expected 0.0015, got {AgentEscrowManager.CLEARING_FEE_RATE}"

@test("Agent Tools Manifest enum contains only PRO and ENTERPRISE")
def test_manifest_enum():
    from app.modules.agent_tools_manifest import AGENT_TOOLS_MANIFEST
    create_tool = next(t for t in AGENT_TOOLS_MANIFEST if t["name"] == "eudr_create_payment_order")
    tier_enum = create_tool["parameters"]["properties"]["plan_tier"]["enum"]
    assert "STARTER" not in tier_enum, f"STARTER found in manifest enum: {tier_enum}"
    assert set(tier_enum) == {"PRO", "ENTERPRISE"}

@test("Agent Tools Manifest micro-pay description states $0.05 USDC / plot")
def test_manifest_micro_pay():
    from app.modules.agent_tools_manifest import AGENT_TOOLS_MANIFEST
    micro_tool = next(t for t in AGENT_TOOLS_MANIFEST if t["name"] == "eudr_agent_micro_pay")
    desc = micro_tool["parameters"]["properties"]["num_plots"]["description"]
    assert "$0.05" in desc, f"Expected $0.05 in description, got: {desc}"

test_pricing_constants()
test_agent_tools_pricing()
test_escrow_clearing_fee_rate()
test_manifest_enum()
test_manifest_micro_pay()

# -----------------------------------------------------------------------------
# 2. B2B Order Creation, Confirmation & Invoicing Lifecycle
# -----------------------------------------------------------------------------
print("\n[Phase 2] B2B Order Creation, Confirmation & Invoicing Lifecycle")

@test("Create PRO Order ($700.00) via PaymentManager")
def test_create_pro_order():
    from app.modules.payment_manager import PaymentManager
    from app.schemas import PaymentOrderCreateRequest, PaymentOrderStatusEnum
    req = PaymentOrderCreateRequest(
        plan_tier="PRO",
        company_name="Antigravity European Trade AG",
        contact_email="audit@antigravity-trade.eu",
        chain="Base (Low Gas $0.01)",
        billing_country="DE",
        vat_number="DE987654321"
    )
    resp = PaymentManager.create_order(req)
    assert resp.order_id.startswith("ORD-")
    assert resp.amount_usdc == 700.00, f"Expected 700.00, got {resp.amount_usdc}"
    assert resp.plan_tier == "PRO"
    assert resp.status == PaymentOrderStatusEnum.PENDING
    assert "INV-EUDR-2026-" in resp.invoice_number
    assert "700.00 USDC" in resp.instructions

@test("Create ENTERPRISE Order ($2,500.00) via PaymentManager")
def test_create_enterprise_order():
    from app.modules.payment_manager import PaymentManager
    from app.schemas import PaymentOrderCreateRequest, PaymentOrderStatusEnum
    req = PaymentOrderCreateRequest(
        plan_tier="ENTERPRISE",
        company_name="Global Commodity Conglomerate B.V.",
        contact_email="procurement@commodity-giant.nl",
        chain="Polygon (PoS)",
        billing_country="NL",
        vat_number="NL123456789B01"
    )
    resp = PaymentManager.create_order(req)
    assert resp.amount_usdc == 2500.00, f"Expected 2500.00, got {resp.amount_usdc}"
    assert resp.plan_tier == "ENTERPRISE"
    assert "2500.00 USDC" in resp.instructions

@test("Confirm Order and Verify API Key & HMAC Invoice Proof")
def test_confirm_order_and_invoice():
    from app.modules.payment_manager import PaymentManager
    from app.schemas import PaymentOrderCreateRequest, PaymentOrderConfirmRequest, PaymentOrderStatusEnum
    from app.core.config import settings

    req = PaymentOrderCreateRequest(
        plan_tier="PRO",
        company_name="Hamburg Coffee Traders GmbH",
        contact_email="compliance@hamburg-coffee.de",
        chain="Base (Low Gas $0.01)"
    )
    order = PaymentManager.create_order(req)
    
    # Confirm
    tx_hash = "0x" + "ee" * 32
    conf_req = PaymentOrderConfirmRequest(order_id=order.order_id, tx_hash=tx_hash)
    conf_resp = PaymentManager.confirm_order(conf_req)
    assert conf_resp.status == PaymentOrderStatusEnum.CONFIRMED
    assert conf_resp.api_key_issued.startswith("eudr_live_")
    assert conf_resp.monthly_quota_plots == 50000
    assert conf_resp.tx_hash == tx_hash

    # Invoice
    invoice = PaymentManager.get_invoice_receipt(order.order_id)
    assert invoice.amount_usdc == 700.00
    assert invoice.company_name == "Hamburg Coffee Traders GmbH"
    assert invoice.tx_hash == tx_hash
    assert len(invoice.hmac_audit_signature) == 64

    # Verify HMAC
    raw_msg = f"{invoice.invoice_number}|{700.0}|{tx_hash}|Hamburg Coffee Traders GmbH"
    expected_hmac = hmac.new(settings.SECRET_KEY_FOR_SIGNING.encode(), raw_msg.encode(), hashlib.sha256).hexdigest()
    assert invoice.hmac_audit_signature == expected_hmac, "HMAC signature mismatch"

test_create_pro_order()
test_create_enterprise_order()
test_confirm_order_and_invoice()

# -----------------------------------------------------------------------------
# 3. M2M Micro-Settlement (HTTP 402 & EIP-3009)
# -----------------------------------------------------------------------------
print("\n[Phase 3] M2M Micro-Settlement (HTTP 402 & EIP-3009 Gasless)")

@test("RFC 9110 x402 Challenge generates exactly $0.05/plot")
def test_x402_challenge():
    from app.modules.payment_manager import PaymentManager
    ch1 = PaymentManager.generate_x402_challenge(num_plots=1)
    assert ch1["unit_price_per_plot_usdc"] == 0.05
    assert ch1["amount_usdc"] == 0.05

    ch100 = PaymentManager.generate_x402_challenge(num_plots=100)
    assert ch100["amount_usdc"] == 5.00

    ch250 = PaymentManager.generate_x402_challenge(num_plots=250)
    assert ch250["amount_usdc"] == 12.50

@test("Agent Micro-Payment Settlement calculation at $0.05/plot")
def test_agent_micro_settle():
    from app.modules.payment_manager import PaymentManager
    from app.schemas import AgentMicroPaymentRequest
    req = AgentMicroPaymentRequest(
        agent_id="test-agent-alpha-402",
        num_plots=20,
        chain="Base (Low Gas $0.01)",
        tx_hash="0x" + "11" * 32,
        sender_wallet="0x1111222233334444555566667777888899990000"
    )
    res = PaymentManager.process_agent_micro_payment(req)
    assert res["status"] == "SETTLED"
    assert res["amount_paid_usdc"] == 1.00, f"Expected 20 * 0.05 = 1.00, got {res['amount_paid_usdc']}"
    assert res["temporary_auth_token"].startswith("eudr_agent_micro_")

@test("EIP-3009 Gasless Transfer With Authorization calculates quota at $0.05/plot")
def test_eip3009_gasless():
    from app.modules.payment_manager import PaymentManager
    from app.schemas import EIP3009AuthorizationRequest
    now_ts = int(datetime.now(timezone.utc).timestamp())
    req = EIP3009AuthorizationRequest(
        from_address="0x" + "22" * 20,
        value_usdc=5.00,
        valid_after=0,
        valid_before=now_ts + 3600,
        nonce="0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        signature="0x" + "33" * 65,
        chain="Base (Low Gas $0.01)",
        agent_id="eip3009-bot-test"
    )
    res = PaymentManager.process_eip3009_authorization(req)
    assert res["status"] == "AUTHORIZED_AND_REDEEMED"
    assert res["amount_usdc"] == 5.00
    assert res["num_plots_credited"] == 100, f"Expected 5.00 / 0.05 = 100 plots, got {res['num_plots_credited']}"

test_x402_challenge()
test_agent_micro_settle()
test_eip3009_gasless()

# -----------------------------------------------------------------------------
# 4. Agent Tools Registry & Budget Safety Guardrails
# -----------------------------------------------------------------------------
print("\n[Phase 4] Autonomous Agent Tools & Budget Safety Guardrails")

def run_sync(coro):
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    raise RuntimeError("Coroutine did not finish synchronously")

@test("eudr_create_payment_order tool creates PRO ($700.00) order")
def test_agent_tool_order():
    from app.modules.agent_tools import AgentToolsRegistry
    args = {
        "plan_tier": "PRO",
        "company_name": "Autonomous Logistics Mesh",
        "contact_email": "agent@logistics-mesh.org",
        "chain": "Polygon (PoS)",
        "max_budget_usdc": 1000.00
    }
    result = run_sync(AgentToolsRegistry.execute_tool("eudr_create_payment_order", args))
    assert result["amount_usdc"] == 700.00
    assert result["plan_tier"] == "PRO"
    assert result["status"] == "PENDING"

@test("eudr_create_payment_order blocks order when budget cap is exceeded")
def test_agent_tool_budget_rejection():
    from app.modules.agent_tools import AgentToolsRegistry
    from app.core.exceptions import AgentSelfCorrectionError
    args = {
        "plan_tier": "PRO",
        "company_name": "Constrained Bot",
        "contact_email": "bot@budget-constrained.io",
        "chain": "Base (Low Gas $0.01)",
        "max_budget_usdc": 500.00  # PRO is $700.00 > $500.00
    }
    try:
        run_sync(AgentToolsRegistry.execute_tool("eudr_create_payment_order", args))
        assert False, "Should have raised AgentSelfCorrectionError"
    except AgentSelfCorrectionError as exc:
        assert exc.code == "BUDGET_CAP_EXCEEDED"
        assert "exceeds agent budget cap" in exc.message

test_agent_tool_order()
test_agent_tool_budget_rejection()

# -----------------------------------------------------------------------------
# 5. Smart Escrow & Clearing Fee Mechanics
# -----------------------------------------------------------------------------
print("\n[Phase 5] Smart Escrow Lifecycle & Clearing Fee Mechanics")

@test("3-Stage Milestone Escrow creation with 0.15% clearing fee rate")
def test_escrow_milestone():
    from app.modules.agent_escrow_manager import AgentEscrowManager
    from app.schemas import MilestoneEscrowCreateRequest, FirstMileSplitRecipient, EscrowStatusEnum

    req = MilestoneEscrowCreateRequest(
        buyer_agent_id="buyer-bot-eudr",
        buyer_wallet="0x" + "44" * 20,
        seller_agent_id="seller-coop-ghana",
        seller_wallet="0x" + "55" * 20,
        amount_usdc=100000.0,
        chain="Base (Low Gas $0.01)",
        hs_code="18010000",
        commodity_description="Certified Sustainable Raw Cocoa Beans",
        declared_net_mass_kg=50000.0,
        milestone_weights=[30.0, 40.0, 30.0],
        split_recipients=[
            FirstMileSplitRecipient(
                recipient_role="SMALLHOLDER_COOP",
                wallet_address="0x" + "66" * 20,
                share_percentage=80.0
            ),
            FirstMileSplitRecipient(
                recipient_role="LOCAL_MILL",
                wallet_address="0x" + "77" * 20,
                share_percentage=20.0
            )
        ]
    )
    resp = AgentEscrowManager.create_milestone_escrow(req)
    assert resp.status == EscrowStatusEnum.AWAITING_DEPOSIT
    assert resp.amount_usdc == 100000.0
    assert len(resp.milestones) == 3
    assert resp.milestones[0].amount_usdc == 30000.0
    assert resp.milestones[1].amount_usdc == 40000.0
    assert resp.milestones[2].amount_usdc == 30000.0
    
    # Calculate Clearing Fee
    clearing_fee = round(resp.amount_usdc * AgentEscrowManager.CLEARING_FEE_RATE, 2)
    assert clearing_fee == 150.00, f"Expected 0.15% of $100k to be $150.00, got {clearing_fee}"

test_escrow_milestone()

# -----------------------------------------------------------------------------
# Final Summary
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"  VERIFICATION RESULTS: {len(passes)} PASSED, {len(errors)} FAILED")
print("=" * 70)

if errors:
    print("\nFAILED TESTS:")
    for name, err in errors:
        print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print("\nALL PAYMENT SYSTEMS & INTEGRATIONS FUNCTION WITH ZERO ERRORS!")
    sys.exit(0)
