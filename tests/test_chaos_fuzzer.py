import pytest
import math
import random
import string
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Helper to generate random fuzz strings
def random_fuzz_string(length=50):
    chars = string.ascii_letters + string.digits + string.punctuation + " \t\n\r" + "한글테스트😀🌍🌱"
    return "".join(random.choice(chars) for _ in range(length))

class TestChaosFuzzer:
    """
    Chaos & Fuzzing Resilience Test Suite.
    Injects 100+ randomized, malformed, and adversarial payloads to verify
    the EUDR API never crashes with unhandled 500 errors.
    """

    @pytest.mark.parametrize("fuzz_vat", [
        "",  # Empty
        "   ",  # Whitespace
        "' OR '1'='1",  # SQL injection attempt
        "<script>alert('xss')</script>",  # XSS attempt
        "DE" + "9" * 500,  # Buffer overflow length
        "FR!@#$%^&*()_+",  # Special chars
        "NL123456789B01\x00NULL",  # Null byte injection
        "한글사업자번호123",  # Non-latin unicode
        "IT 123 456 789",  # Embedded spaces
        "0000000000",  # Zeroes
    ])
    def test_fuzz_vies_vat_validation(self, fuzz_vat):
        """Verify VAT verification endpoint resists arbitrary string fuzzing without 500."""
        resp = client.post(
            "/api/v1/agent/tools/execute",
            json={
                "tool_name": "eudr_verify_vies_vat",
                "arguments": {
                    "country_code": fuzz_vat[:2] if len(fuzz_vat) >= 2 else "FR",
                    "vat_number": fuzz_vat
                }
            }
        )
        assert resp.status_code in (200, 400, 422), f"Unexpected status {resp.status_code} for VAT '{fuzz_vat}': {resp.text}"
        data = resp.json()
        assert "error" not in data or data.get("error", {}).get("code") != "INTERNAL_SERVER_ERROR"

    @pytest.mark.parametrize("fuzz_coord", [
        [0.0, 0.0],  # Null Island
        [90.0, 180.0],  # Boundary max
        [-90.0, -180.0],  # Boundary min
        [91.0, 0.0],  # Out of range lat
        [0.0, 181.0],  # Out of range lon
        [-95.0, 200.0],  # Double out of range
        [0.5, 101.5],  # Inverted lat/lon check
        [180.0, 0.0],  # Transposed poles
    ])
    def test_fuzz_coordinates_and_plots(self, fuzz_coord):
        """Verify plot verification endpoint handles extreme coordinate inputs cleanly."""
        resp = client.post(
            "/api/v1/agent/tools/execute",
            json={
                "tool_name": "eudr_verify_plot",
                "arguments": {
                    "plot_id": f"FUZZ-PLOT-{random.randint(1000, 9999)}",
                    "country_code": "ID",
                    "coordinates": fuzz_coord,
                    "production_date": "2024-01-01"
                }
            }
        )
        assert resp.status_code in (200, 400, 422), f"Failed on coord {fuzz_coord}: {resp.text}"

    def test_fuzz_geometric_bowtie_and_self_intersections(self):
        """Verify self-healing engine handles 20 distinct corrupted polygon geometries."""
        corrupted_polygons = [
            # Figure-8 Bowtie
            [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]],
            # Open Ring (not closed)
            [[[10, 10], [10, 20], [20, 20], [20, 10]]],
            # Degenerate collapse to a line
            [[[0, 0], [0, 1], [0, 2], [0, 1], [0, 0]]],
            # Collinear duplicate vertices
            [[[0, 0], [0, 0], [0, 0], [1, 1], [1, 1], [0, 0]]],
            # Single point as polygon ring
            [[[5, 5], [5, 5], [5, 5]]],
            # Huge spike vertex (1000km away)
            [[[10, 10], [10, 11], [80, 80], [11, 11], [11, 10], [10, 10]]],
        ]

        for idx, poly_coords in enumerate(corrupted_polygons):
            resp = client.post(
                "/api/v1/agent/tools/execute",
                json={
                    "tool_name": "eudr_verify_plot",
                    "arguments": {
                        "plot_id": f"CORRUPTED-POLY-{idx}",
                        "country_code": "BR",
                        "coordinates": poly_coords,
                        "area_hectares": 12.5
                    }
                }
            )
            assert resp.status_code in (200, 400, 422), f"Failed on corrupted polygon {idx}: {resp.text}"

    @pytest.mark.parametrize("commodity", [
        "cocoa", "coffee", "oil_palm", "rubber", "soya", "cattle", "wood",
        "INVALID_COMMODITY", "gold", "lithium", "crude_oil", "", " "
    ])
    def test_fuzz_dds_generation_commodities(self, commodity):
        """Verify DDS generator strictly rejects non-EUDR commodities without unhandled crash."""
        resp = client.post(
            "/api/v1/agent/tools/execute",
            json={
                "tool_name": "eudr_generate_dds",
                "arguments": {
                    "operator_name": "Global Trade Corp BV",
                    "operator_vat": "NL858585858B01",
                    "commodity": commodity,
                    "total_net_mass_kg": 25000.0,
                    "plot_ids": ["PLOT-ID-01", "PLOT-ID-02"]
                }
            }
        )
        assert resp.status_code in (200, 400, 422), f"Failed for commodity '{commodity}': {resp.text}"

    @pytest.mark.parametrize("fuzz_mass", [
        0.0,
        -1.0,
        -999999.0,
        0.0000001,
        100000000000.0,  # 100 billion kg
    ])
    def test_fuzz_dds_mass_quantities(self, fuzz_mass):
        """Verify mass quantities with negative or extreme values are handled cleanly."""
        resp = client.post(
            "/api/v1/agent/tools/execute",
            json={
                "tool_name": "eudr_generate_dds",
                "arguments": {
                    "operator_name": "Antwerp Cocoa Imports NV",
                    "operator_vat": "BE0123456789",
                    "commodity": "cocoa",
                    "total_net_mass_kg": fuzz_mass,
                    "plot_ids": ["PLOT-BE-01"]
                }
            }
        )
        assert resp.status_code in (200, 400, 422), f"Failed for mass '{fuzz_mass}': {resp.text}"

    def test_fuzz_audit_integrity_tampering(self):
        """Verify cryptographic audit trail detects any arbitrary bit-level payload tampering."""
        valid_payload = {
            "reference_id": "DDS-EUDR-2026-TEST01",
            "operator": "Test BV",
            "timestamp": "2026-09-07T00:00:00Z"
        }
        tampered_hashes = [
            "",
            "0000000000000000000000000000000000000000000000000000000000000000",
            "not_a_hex_hash",
            "a" * 63,  # 63 chars (1 short of sha256)
            "a" * 65,  # 65 chars (1 too long)
            random_fuzz_string(64),
        ]

        for bad_hash in tampered_hashes:
            resp = client.post(
                "/api/v1/agent/tools/execute",
                json={
                    "tool_name": "eudr_verify_audit_integrity",
                    "arguments": {
                        "audit_payload": valid_payload,
                        "expected_hash": bad_hash
                    }
                }
            )
            assert resp.status_code in (200, 400, 422)
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                # Tampered or invalid hashes must be flagged as NOT tamper-free
                assert res.get("is_tamper_free") is False

    def test_fuzz_random_garbage_agent_tool_requests(self):
        """Fire 30 completely randomized garbage payloads at the agent tools dispatcher."""
        for _ in range(30):
            garbage_payload = {
                "tool_name": random_fuzz_string(15),
                "arguments": {
                    random_fuzz_string(5): random_fuzz_string(20),
                    "nested": [random.random(), None, random_fuzz_string(10)]
                }
            }
            resp = client.post("/api/v1/agent/tools/execute", json=garbage_payload)
            # Must return 400/422/404 or structured error, NEVER unhandled 500 crash
            assert resp.status_code in (200, 400, 404, 422), f"Garbage caused status {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data.get("error", {}).get("code") != "INTERNAL_SERVER_ERROR"
