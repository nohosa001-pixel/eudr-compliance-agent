"""Unit tests for eudr-compliance-agent v3.0.0 Thin MCP Proxy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eudr_mcp_proxy import build_gateway_headers, forward_jsonrpc_to_gateway


def test_build_gateway_headers_with_key_and_tx(monkeypatch):
    monkeypatch.setenv("EUDR_API_KEY", "eudr_live_test_123")
    monkeypatch.setenv("EUDR_X402_TX_HASH", "0x" + "a" * 64)
    monkeypatch.setenv("EUDR_CHAIN", "polygon")
    headers = build_gateway_headers()
    assert headers["X-API-Key"] == "eudr_live_test_123"
    assert headers["X-402-Tx-Hash"] == "0x" + "a" * 64
    assert headers["X-Chain"] == "polygon"
    assert headers["User-Agent"] == "eudr-compliance-agent-thin/3.0.0"


@pytest.mark.asyncio
async def test_forward_ping_and_notification():
    ping_res = await forward_jsonrpc_to_gateway({"jsonrpc": "2.0", "id": 7, "method": "ping"})
    assert ping_res == {"jsonrpc": "2.0", "id": 7, "result": {}}

    notif_res = await forward_jsonrpc_to_gateway({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert notif_res is None


@pytest.mark.asyncio
async def test_forward_tools_list_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "eudr_evaluate_compact"}]}}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("eudr_mcp_proxy.httpx.AsyncClient", return_value=mock_client):
        res = await forward_jsonrpc_to_gateway({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        assert res["result"]["tools"][0]["name"] == "eudr_evaluate_compact"


@pytest.mark.asyncio
async def test_forward_402_payment_required():
    mock_resp = MagicMock()
    mock_resp.status_code = 402

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("eudr_mcp_proxy.httpx.AsyncClient", return_value=mock_client):
        res = await forward_jsonrpc_to_gateway({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {}})
        assert res["error"]["code"] == -32002
        assert "EUDR_API_KEY" in res["error"]["message"]
