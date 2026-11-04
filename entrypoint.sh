#!/bin/sh
set -e

# ========================================================
# EUDRAgent Dual-Mode Container Entrypoint
# ========================================================

# 1. Google Cloud Run dynamically injects $PORT (usually 8080)
# 2. If $PORT is provided, run production FastAPI HTTP / MCP SSE Server
if [ -n "$PORT" ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

# 3. Default fallback for Glama.ai inspection / Docker stdio MCP client
exec python mcp_server_stdio.py
