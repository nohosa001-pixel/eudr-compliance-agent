# eudr-compliance-agent (Thin MCP Client v3.0.0)

Cloud-Native Thin MCP Client for **[EUDRAgent.com](https://eudragent.com)** — Autonomous EU Deforestation Regulation (EU 2023/1115) Compliance, Copernicus Sentinel-2 Verification & TRACES-NT DDS Gateway.

## Quickstart

```bash
pip install eudr-compliance-agent
```

### MCP Server Configuration (Claude Desktop / Cursor / Windsurf)

```json
{
  "mcpServers": {
    "eudr-compliance": {
      "command": "eudr-mcp",
      "env": {
        "EUDR_API_KEY": "eudr_live_your_key_here"
      }
    }
  }
}
```

### Environment Variables
- `EUDR_GATEWAY_URL`: Gateway URL (default: `https://eudragent.com`)
- `EUDR_API_KEY`: Paid API Key from `/api/v1/payment/orders` + `/api/v1/payment/confirm`
- `EUDR_X402_TX_HASH`: Verified on-chain USDC payment transaction hash
- `EUDR_CHAIN`: Settlement chain (e.g. `Polygon (PoS)`, `Base (Low Gas $0.01)`)

## Architecture
This public repository contains **only** the zero-server-dependency Thin MCP Proxy (`eudr_mcp_proxy.py` + `httpx`). All compliance engines, spatial GIS pipelines, satellite verification, and TRACES-NT generators run securely on `https://eudragent.com`.
