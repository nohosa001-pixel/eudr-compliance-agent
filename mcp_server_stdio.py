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
import json
import asyncio
from app.modules.mcp_server import MCPServer

async def main():
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        text = line.decode("utf-8").strip()
        if not text:
            continue
        try:
            req = json.loads(text)
            resp = await MCPServer.handle_jsonrpc_request(req)
            if resp:  # Notifications might not produce responses
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
