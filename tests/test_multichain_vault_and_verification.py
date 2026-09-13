import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.payment_manager import PaymentManager, AGENT_PAYMENT_VAULTS, USDC_CONTRACT_ADDRESSES, CHAIN_RPC_NODES

client = TestClient(app)


def test_multichain_vaults_directory_endpoint():
    """Verify GET /api/v1/payment/vaults returns full multi-chain contract directory."""
    response = client.get("/api/v1/payment/vaults")
    assert response.status_code == 200
    data = response.json()
    
    # Check AgentPaymentVault addresses for 3 major chains
    assert "agent_payment_vaults" in data
    vaults = data["agent_payment_vaults"]
    assert vaults["Polygon (PoS)"] == "0x45ecBfAa2F4B0Bc6ccD3eB2dB9B1Ca49CF121861"
    assert vaults["Base (Low Gas $0.01)"] == "0x28292D76E07E5539F15F3b97935dE8E0432E76DD"
    assert vaults["Arbitrum One"] == "0x28292D76E07E5539F15F3b97935dE8E0432E76DD"

    # Check Native USDC token contract addresses
    assert "usdc_token_contracts" in data
    usdc = data["usdc_token_contracts"]
    assert usdc["Polygon (PoS)"] == "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
    assert usdc["Base (Low Gas $0.01)"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert usdc["Arbitrum One"] == "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"

    # Check RPC nodes
    assert "rpc_endpoints" in data
    assert "Base (Low Gas $0.01)" in data["rpc_endpoints"]
    assert "Arbitrum One" in data["rpc_endpoints"]
    assert "Polygon (PoS)" in data["rpc_endpoints"]


def test_x402_challenge_contains_multichain_vaults():
    """Verify RFC 9110 / x402 challenge response includes deployed vault contracts for AI agents."""
    response = client.get("/api/v1/payment/x402/challenge?resource=satellite_radar_scan&plots=50")
    assert response.status_code == 402
    data = response.json()

    assert "agent_payment_vaults" in data
    assert data["agent_payment_vaults"]["Polygon (PoS)"] == "0x45ecBfAa2F4B0Bc6ccD3eB2dB9B1Ca49CF121861"
    assert data["agent_payment_vaults"]["Base (Low Gas $0.01)"] == "0x28292D76E07E5539F15F3b97935dE8E0432E76DD"

    assert "usdc_contracts" in data
    assert data["usdc_contracts"]["Arbitrum One"] == "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"


def test_onchain_verification_in_confirm_order():
    """Verify that confirming an order populates on-chain verification telemetry."""
    # 1. Create order on Arbitrum One
    order_res = client.post("/api/v1/payment/orders", json={
        "plan_tier": "PRO",
        "company_name": "Arbitrum Timber Import Corp",
        "contact_email": "finance@arbtimber.eu",
        "chain": "Arbitrum One"
    })
    assert order_res.status_code == 200
    order_data = order_res.json()
    order_id = order_data["order_id"]

    # 2. Confirm order with tx_hash
    conf_res = client.post("/api/v1/payment/confirm", json={
        "order_id": order_id,
        "tx_hash": "0x4444555566667777888899990000111122223333444455556666777788889999"
    })
    assert conf_res.status_code == 200
    conf_data = conf_res.json()
    assert conf_data["status"] == "CONFIRMED"
    assert "onchain_verification" in conf_data
    assert conf_data["onchain_verification"]["verified"] is True
    assert conf_data["onchain_verification"]["chain"] == "Arbitrum One"


def test_agent_micro_payment_with_vault_and_verification():
    """Verify autonomous agent micro-settlement returns vault and on-chain verification."""
    payload = {
        "agent_id": "multichain-audit-agent-99",
        "num_plots": 20,
        "chain": "Base (Low Gas $0.01)",
        "tx_hash": "0x888877776666555544443333222211110000ffff888877776666555544443333",
        "sender_wallet": "0x1111222233334444555566667777888899990000"
    }
    res = client.post("/api/v1/payment/agent/micro-settle", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SETTLED"
    assert data["agent_payment_vault"] == "0x28292D76E07E5539F15F3b97935dE8E0432E76DD"
    assert "onchain_verification" in data
    assert data["onchain_verification"]["verified"] is True
    assert data["onchain_verification"]["chain"] == "Base (Low Gas $0.01)"


def test_verify_onchain_transaction_direct():
    """Direct test of PaymentManager.verify_onchain_transaction for simulation & fallback."""
    # Simulated short hash
    sim_res = PaymentManager.verify_onchain_transaction("Polygon (PoS)", "simulated-tx-123")
    assert sim_res["verified"] is True
    assert sim_res["mode"] == "SYNTHETIC_OR_SIMULATED"

    # 66-character EVM hash format with resilient fallback
    evm_res = PaymentManager.verify_onchain_transaction(
        "Base (Low Gas $0.01)",
        "0xabcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    )
    assert evm_res["verified"] is True
    assert "mode" in evm_res
