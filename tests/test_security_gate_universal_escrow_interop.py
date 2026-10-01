"""
Integration Tests for EUDRAgent & Security Gate x402 Universal Escrow Interoperability.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.modules.universal_escrow_client import universal_escrow_client

client = TestClient(app)


def test_request_eudr_truth_attestation_payload_construction():
    """Verify universal_escrow_client constructs and posts valid EUDR truth verification requests."""
    fake_response_data = {
        "domain": "EUDR_FOREST",
        "domain_id": 3,
        "job_id": "job_eudr_interop_001",
        "is_valid": True,
        "deforestation_free": True,
        "signature": {
            "r": "0x1111",
            "s": "0x2222",
            "v": 27,
            "full_signature": "0x" + "aa" * 65
        }
    }

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_response_data
        mock_post.return_value = mock_resp

        result = universal_escrow_client.request_eudr_truth_attestation(
            job_id="job_eudr_interop_001",
            commodity="coffee",
            country_code="CO",
            polygon_coordinates=[[4.57, -74.29], [4.58, -74.30], [4.59, -74.28]],
            dds_reference_id="EU-DDS-2026-CO-00129",
            deforestation_detected=False,
            legal_harvest_verified=True
        )

        assert result["domain"] == "EUDR_FOREST"
        assert result["is_valid"] is True
        assert mock_post.called
        call_args = mock_post.call_args
        assert "/api/v1/truth/eudr" in call_args[0][0]
        assert call_args[1]["json"]["commodity"] == "coffee"


def test_settle_eudr_escrow_direct_split_payload_construction():
    """Verify universal_escrow_client sends proper Direct Split disbursement payload."""
    fake_settle_response = {
        "status": "SETTLED",
        "job_id": "job_eudr_interop_001",
        "domain": 3,
        "total_disbursed_usdc": 15000.0
    }

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_settle_response
        mock_post.return_value = mock_resp

        result = universal_escrow_client.settle_eudr_escrow_direct_split(
            job_id="job_eudr_interop_001",
            recipients=[{"recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "amount": 15000.0}],
            attestation={"jobId": "job_eudr_interop_001", "isValid": True}
        )

        assert result["status"] == "SETTLED"
        assert result["total_disbursed_usdc"] == 15000.0
        assert mock_post.called
        call_args = mock_post.call_args
        assert "/api/v1/escrow/universal/settle" in call_args[0][0]
        assert call_args[1]["json"]["domain"] == 3


def test_api_settle_eudr_universal_escrow_endpoint():
    """Integration Test for POST /api/v1/escrow/universal/settle-eudr."""
    fake_attestation = {
        "domain": "EUDR_FOREST",
        "domain_id": 3,
        "is_valid": True,
        "signature": {"full_signature": "0x123"}
    }
    fake_settlement = {
        "status": "SETTLED",
        "total_disbursed_usdc": 50000.0
    }

    with patch.object(universal_escrow_client, "request_eudr_truth_attestation", return_value=fake_attestation), \
         patch.object(universal_escrow_client, "settle_eudr_escrow_direct_split", return_value=fake_settlement):

        payload = {
            "job_id": "job_live_eudr_rubber_99",
            "commodity": "rubber",
            "country_code": "ID",
            "polygon_coordinates": [[-0.55, 101.40], [-0.54, 101.41], [-0.55, 101.42]],
            "dds_reference_id": "EU-DDS-2026-ID-88319",
            "deforestation_detected": False,
            "legal_harvest_verified": True,
            "recipients": [{"recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "amount": 50000.0}]
        }
        resp = client.post("/api/v1/escrow/universal/settle-eudr", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["settlement"]["status"] == "SETTLED"
        assert data["settlement"]["total_disbursed_usdc"] == 50000.0
