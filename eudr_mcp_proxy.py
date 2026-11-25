"""
eudr-compliance-agent v3.0.0 Cloud-Native Thin MCP Proxy
======================================================
Forwards local stdio MCP JSON-RPC 2.0 requests directly to the live
EUDRAgent.com Cloud Run Gateway over HTTPS, ensuring:
- Zero local server dependencies (no fastapi, uvicorn, sqlalchemy, shapely, pyproj, numpy)
- Transparent X-API-Key / X-402-Tx-Hash header forwarding
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None  # Stdlib urllib.request fallback when container Python lacks httpx

DEFAULT_GATEWAY_URL = os.getenv("EUDR_GATEWAY_URL", "https://eudragent.com").rstrip("/")


def build_gateway_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "eudr-compliance-agent-thin/3.0.0",
        "X-Request-ID": f"eudr_thin_{secrets.token_hex(6)}",
    }
    api_key = os.getenv("EUDR_API_KEY") or os.getenv("X_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key.strip()
    tx_hash = os.getenv("EUDR_X402_TX_HASH") or os.getenv("X_402_TX_HASH")
    if tx_hash:
        headers["X-402-Tx-Hash"] = tx_hash.strip()
    chain = os.getenv("EUDR_CHAIN")
    if chain:
        headers["X-Chain"] = chain.strip()
    return headers


def _post_json_stdlib(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_sec: float) -> tuple[int, Dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body_raw = err.read().decode("utf-8", errors="ignore")
        try:
            body_json = json.loads(body_raw)
        except Exception:
            body_json = {"detail": body_raw}
        return err.code, body_json


async def forward_jsonrpc_to_gateway(
    req_data: Dict[str, Any],
    gateway_url: Optional[str] = None,
    timeout_sec: float = 20.0,
) -> Optional[Dict[str, Any]]:
    """Forwards a JSON-RPC 2.0 MCP request to the EUDRAgent Cloud Gateway /api/v1/mcp endpoint."""
    method = req_data.get("method", "")
    req_id = req_data.get("id")

    if method.startswith("notifications/") or req_id is None:
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    base = (gateway_url or DEFAULT_GATEWAY_URL).rstrip("/")
    mcp_endpoint = f"{base}/api/v1/mcp"

    try:
        headers = build_gateway_headers()
        if httpx is not None:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(mcp_endpoint, json=req_data, headers=headers)
                status_code = resp.status_code
                if status_code != 402:
                    resp.raise_for_status()
                body = resp.json() if status_code != 402 else {}
        else:
            status_code, body = await asyncio.to_thread(_post_json_stdlib, mcp_endpoint, req_data, headers, timeout_sec)
            if status_code >= 400 and status_code != 402:
                raise RuntimeError(f"HTTP {status_code}: {body}")

        if status_code == 402:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32002,
                    "message": (
                        "Payment Required (HTTP 402): Set EUDR_API_KEY or EUDR_X402_TX_HASH "
                        "after settling USDC via https://eudragent.com/api/v1/payment/x402/challenge"
                    ),
                },
            }
        return body
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32603,
                "message": f"EUDRAgent Thin Client gateway error: {exc}",
            },
        }


async def _stdio_loop() -> None:
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        text = line.strip().lstrip("\ufeff")
        if not text:
            continue
        try:
            req = json.loads(text)
        except Exception as exc:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        resp = await forward_jsonrpc_to_gateway(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()


def main() -> None:
    for stream_name, enc in (("stdin", "utf-8-sig"), ("stdout", "utf-8"), ("stderr", "utf-8")):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding=enc, errors="replace")
            except Exception:
                pass
    asyncio.run(_stdio_loop())


if __name__ == "__main__":
    main()
