#!/usr/bin/env python3
"""
EUDR.agent MCP Server (Standard I/O Adapter).
Enables direct native integration with Claude Desktop, Cursor, Antigravity,
and other Model Context Protocol clients via standard input/output streams.

Usage in claude_desktop_config.json:
{
  "mcpServers": {
    "eudr-compliance": {
      "command": "python",
      "args": ["/path/to/eudr-compliance-agent/mcp_server_stdio.py"]
    }
  }
}
"""
import sys
import io
import json
import logging
import asyncio
from app.modules.mcp_server import MCPServer

# Enforce UTF-8 stdio encoding across all platforms (critical for Windows Korean cp949 and BOM)
try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8-sig", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure all logging is routed to stderr so stdout remains purely reserved for JSON-RPC
logging.basicConfig(stream=sys.stderr, level=logging.INFO)

async def async_main():
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        text = line.strip().lstrip("\ufeff")
        if not text:
            continue
        try:
            req = json.loads(text)
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()
            continue

        try:
            resp = await MCPServer.handle_jsonrpc_request(req)
            if resp is not None:  # Notifications return None and must not produce responses
                sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
                sys.stdout.flush()
        except Exception as e:
            # Notifications must not receive error responses
            if isinstance(req, dict) and req.get("id") is None and str(req.get("method", "")).startswith("notifications/"):
                continue
            req_id = req.get("id") if isinstance(req, dict) else None
            err_resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal JSON-RPC error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()

def main():
    try:
        asyncio.run(async_main())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()

