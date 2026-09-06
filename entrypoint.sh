#!/bin/sh
set -e

# 1. If explicit arguments are provided (e.g. docker run <image> python mcp_server_stdio.py)
if [ $# -gt 0 ]; then
    exec "$@"
fi

# 2. If PORT is set (Google Cloud Run / Production Web Container)
if [ -n "$PORT" ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

# 3. Default fallback for Glama inspection / Smithery / Docker stdio MCP client
exec python mcp_server_stdio.py
