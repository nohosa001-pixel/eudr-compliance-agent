"""
Unit and Integration Tests for Solana Mainnet-Beta Escrow Rail & Ed25519 Oracle.
=================================================================================
Validates:
1. Pure Python Base58 encoding/decoding accuracy.
2. Ed25519 EUDR Truth Attestation signing and cryptographic verification.
3. Program Derived Address (PDA) escrow vault calculation.
4. SPL-USDC Direct Split execution and non-compliant slashing logic.
5. Solana Pay URI / QR payload formatting.
6. REST API endpoints for Solana settlement on FastAPI.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.solana_escrow_adapter import (
    SolanaEscrowAdapter,
    b58encode,
    b58decode,
    is_valid_solana_pubkey
)

client = TestClient(app)

SAMPLE_SOLANA_BUYER = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
SAMPLE_SOLANA_FARMER_1 = "4Nd1mBQtrMJVYVfKf2PJy9NZmcCcFiSm3bZPwtbPgUJa"
SAMPLE_SOLANA_MILL_2 = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"


# ---------------------------------------------------------------------------
# 1. Base58 Codec Tests
# ---------------------------------------------------------------------------
def test_base58_encode_decode_vectors():
    """Validates Base58 codec with known test vectors."""
    test_cases = [
        (b"", ""),
        (b"\x00", "1"),
        (b"\x00\x00", "11"),
        (b"hello world", "StV1DL6CwTryKyV"),
        (b"Solana Mainnet Escrow", "68aDTNcUjyyReiqmuxNWxcf2qiLpW"),
        (b"\x00\x00\x01\x02\x03", "11Ldp")
    ]
    for raw, expected_b58 in test_cases:
        encoded = b58encode(raw)
        assert encoded == expected_b58
        decoded = b58decode(encoded)
        assert decoded == raw


def test_solana_pubkey_validation():
    """Ensures 32-byte Base58 Solana public keys are validated correctly."""
    assert is_valid_solana_pubkey(SAMPLE_SOLANA_BUYER) is True
    assert is_valid_solana_pubkey(SAMPLE_SOLANA_FARMER_1) is True
    assert is_valid_solana_pubkey(SAMPLE_SOLANA_MILL_2) is True
    assert is_valid_solana_pubkey("Invalid-Key-With-Illegal-Chars-0OIl") is False
    assert is_valid_solana_pubkey("TooShort") is False


# ---------------------------------------------------------------------------
# 2. Ed25519 Cryptographic Attestation Tests
# ---------------------------------------------------------------------------
def test_ed25519_eudr_truth_attestation_signing_and_verification():
    """Signs compliant EUDR physical truth and verifies Ed25519 cryptographic validity."""
    attestation = SolanaEscrowAdapter.sign_eudr_truth_attestation(
        job_id="job_solana_coffee_001",
        commodity="coffee",
        country_code="VN",
        polygon_coordinates=[[108.45, 11.95], [108.46, 11.95], [108.46, 11.96], [108.45, 11.96]],
        dds_reference_id="EUDR-DDS-2026-VN-COFFEE-88",
        deforestation_detected=False,
        legal_harvest_verified=True,
        risk_tier="LOW"
    )

    assert attestation["domain"] == "EUDR_FOREST_SOLANA"
    assert attestation["is_valid"] is True
    assert attestation["deforestation_free"] is True
    assert len(attestation["signature"]) > 40
    assert len(attestation["oracle_pubkey"]) > 30

    # Verify signature
    is_valid = SolanaEscrowAdapter.verify_eudr_truth_attestation(attestation)
    assert is_valid is True

    # Tampering test: Modify payload data and verify signature fails
    tampered_attestation = dict(attestation)
    tampered_attestation["canonical_payload"] = dict(attestation["canonical_payload"])
    tampered_attestation["canonical_payload"]["commodity"] = "cocoa" # Tampered!
    assert SolanaEscrowAdapter.verify_eudr_truth_attestation(tampered_attestation) is False


# ---------------------------------------------------------------------------
# 3. Solana Escrow PDA Derivation Tests
# ---------------------------------------------------------------------------
def test_solana_escrow_pda_derivation():
    """Verifies deterministic PDA vault address derivation."""
    pda = SolanaEscrowAdapter.derive_escrow_pda(
        buyer_pubkey_b58=SAMPLE_SOLANA_BUYER,
        job_id="job_solana_timber_99"
    )
    assert "pda_address" in pda
    assert is_valid_solana_pubkey(pda["pda_address"]) is True
    assert 190 <= pda["bump_seed"] <= 255
    assert pda["buyer_pubkey"] == SAMPLE_SOLANA_BUYER


# ---------------------------------------------------------------------------
# 4. SPL-USDC Direct Split Execution Tests
# ---------------------------------------------------------------------------
def test_solana_direct_split_success():
    """Tests instant Direct Split disbursement across smallholders and cooperatives."""
    attestation = SolanaEscrowAdapter.sign_eudr_truth_attestation(
        job_id="job_solana_rubber_042",
        commodity="rubber",
        country_code="ID",
        polygon_coordinates=[[-0.55, 101.40]],
        dds_reference_id="EU-DDS-2026-ID-RUBBER-042",
        deforestation_detected=False,
        legal_harvest_verified=True
    )

    recipients = [
        {"recipient": SAMPLE_SOLANA_FARMER_1, "amount": 18500.50, "role": "SMALLHOLDER_PRODUCER"},
        {"recipient": SAMPLE_SOLANA_MILL_2, "amount": 4200.00, "role": "PROCESSING_COOPERATIVE"}
    ]

    settlement = SolanaEscrowAdapter.execute_solana_direct_split(
        job_id="job_solana_rubber_042",
        buyer_wallet=SAMPLE_SOLANA_BUYER,
        recipients=recipients,
        attestation=attestation
    )

    assert settlement["status"] == "SETTLED_ON_SOLANA_MAINNET"
    assert settlement["total_disbursed_usdc"] == 22700.5
    assert len(settlement["disbursed_recipients"]) == 2
    assert len(settlement["tx_signature"]) > 60
    assert "explorer.solana.com" in settlement["solana_explorer_url"]
    assert settlement["network_fee_sol"] == 0.000005


def test_solana_direct_split_tampered_attestation_rejected():
    """Ensures tampered Ed25519 attestation is rejected."""
    bad_attestation = {
        "domain": "EUDR_FOREST_SOLANA",
        "signature": "InvalidSignature123456789",
        "oracle_pubkey": SAMPLE_SOLANA_BUYER,
        "canonical_payload": {"job_id": "bad_job"}
    }
    settlement = SolanaEscrowAdapter.execute_solana_direct_split(
        job_id="bad_job",
        buyer_wallet=SAMPLE_SOLANA_BUYER,
        recipients=[{"recipient": SAMPLE_SOLANA_FARMER_1, "amount": 100.0}],
        attestation=bad_attestation
    )
    assert settlement["status"] == "REJECTED_INVALID_ATTESTATION"


def test_solana_direct_split_deforestation_slashed():
    """Ensures plots flagged for deforestation are slashed."""
    slashed_attestation = SolanaEscrowAdapter.sign_eudr_truth_attestation(
        job_id="job_slashed_palm_oil_66",
        commodity="oil_palm",
        country_code="MY",
        polygon_coordinates=[[3.13, 101.68]],
        dds_reference_id="EU-DDS-2026-MY-PALM-ILLEGAL",
        deforestation_detected=True,  # VIOLATION!
        legal_harvest_verified=False
    )

    settlement = SolanaEscrowAdapter.execute_solana_direct_split(
        job_id="job_slashed_palm_oil_66",
        buyer_wallet=SAMPLE_SOLANA_BUYER,
        recipients=[{"recipient": SAMPLE_SOLANA_FARMER_1, "amount": 5000.0}],
        attestation=slashed_attestation
    )
    assert settlement["status"] == "SLASHED_NON_COMPLIANT"
    assert "deforestation" in settlement["error"].lower()


# ---------------------------------------------------------------------------
# 5. Solana Pay & Cluster Inspection Tests
# ---------------------------------------------------------------------------
def test_solana_pay_link_generation():
    """Verifies Solana Pay URI compliance with standard specification."""
    link = SolanaEscrowAdapter.generate_solana_pay_link(
        recipient_pubkey=SAMPLE_SOLANA_FARMER_1,
        amount_usdc=250.75,
        reference_job_id="job_pay_demo_77",
        memo="Smallholder Direct Payout"
    )
    assert link["protocol"] == "Solana Pay (x402 Micropayment)"
    assert link["solana_pay_url"].startswith(f"solana:{SAMPLE_SOLANA_FARMER_1}?")
    assert "amount=250.7500" in link["solana_pay_url"]
    assert "spl-token=" in link["solana_pay_url"]


def test_solana_cluster_status_query():
    """Verifies Solana Mainnet cluster status returns high-performance parameters."""
    status = SolanaEscrowAdapter.get_solana_cluster_status()
    assert status["status"] == "ONLINE"
    assert status["average_block_time_ms"] == 400
    assert "SPL-USDC" in status["settlement_currency"]


# ---------------------------------------------------------------------------
# 6. REST API Endpoints Integration Tests
# ---------------------------------------------------------------------------
def test_api_solana_attest_and_settle_workflow():
    """Tests end-to-end FastAPI endpoints for Solana EUDR attestation and settlement."""
    # 1. Attest Truth
    attest_payload = {
        "job_id": "job_api_solana_001",
        "commodity": "cocoa",
        "country_code": "GH",
        "polygon_coordinates": [[5.60, -0.18]],
        "dds_reference_id": "EU-DDS-2026-GH-COCOA-01",
        "deforestation_detected": False,
        "legal_harvest_verified": True,
        "risk_tier": "LOW"
    }
    attest_resp = client.post("/api/v1/escrow/solana/attest", json=attest_payload)
    assert attest_resp.status_code == 200
    attest_data = attest_resp.json()
    assert attest_data["domain"] == "EUDR_FOREST_SOLANA"
    assert attest_data["is_valid"] is True

    # 2. Settle Direct Split
    settle_payload = {
        "job_id": "job_api_solana_001",
        "buyer_wallet": SAMPLE_SOLANA_BUYER,
        "recipients": [
            {"recipient": SAMPLE_SOLANA_FARMER_1, "amount": 12500.0, "role": "FARMER_UNION"}
        ],
        "attestation": attest_data
    }
    settle_resp = client.post("/api/v1/escrow/solana/settle-eudr", json=settle_payload)
    assert settle_resp.status_code == 200
    settle_data = settle_resp.json()
    assert settle_data["status"] == "SETTLED_ON_SOLANA_MAINNET"
    assert settle_data["total_disbursed_usdc"] == 12500.0

    # 3. Generate Solana Pay URL
    pay_payload = {
        "recipient_pubkey": SAMPLE_SOLANA_FARMER_1,
        "amount_usdc": 12500.0,
        "reference_job_id": "job_api_solana_001",
        "memo": "Ghana Cocoa Payout"
    }
    pay_resp = client.post("/api/v1/escrow/solana/pay-url", json=pay_payload)
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert "solana:" in pay_data["solana_pay_url"]

    # 4. Query Cluster Status
    cluster_resp = client.get("/api/v1/escrow/solana/cluster-status")
    assert cluster_resp.status_code == 200
    assert cluster_resp.json()["status"] == "ONLINE"
