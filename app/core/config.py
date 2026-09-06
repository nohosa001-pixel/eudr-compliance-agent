import os
from pydantic import BaseModel
from datetime import date
from pathlib import Path

# Load local .env if present
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass


class Settings(BaseModel):
    PROJECT_NAME: str = "EUDR Compliance Automation Agent"
    API_V1_PREFIX: str = "/api/v1"
    EUDR_CUTOFF_DATE: date = date(2020, 12, 31)
    DEFAULT_DEFORESTATION_TOLERANCE_PCT: float = 0.05  # 0.05% margin for satellite noise
    SECRET_KEY_FOR_SIGNING: str = os.getenv("SECRET_KEY_FOR_SIGNING", "eudr-traces-nt-secret-key-2026")
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    USE_DISTRIBUTED_QUEUE: bool = False

    # Telegram Alert Configuration (synced with minerals-oracle)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # PostgreSQL / PostGIS Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "eudr_compliance"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Copernicus CDSE / Sentinel Hub Live Account Settings
    COPERNICUS_CLIENT_ID: str = os.getenv("COPERNICUS_CLIENT_ID", "")
    COPERNICUS_CLIENT_SECRET: str = os.getenv("COPERNICUS_CLIENT_SECRET", "")
    USE_LIVE_COPERNICUS_API: bool = os.getenv("USE_LIVE_COPERNICUS_API", "false").lower() in ("true", "1", "yes")

    # Stripe Payments Configuration (EUR / Cards / SEPA)
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Web3 / MetaMask Polygon (PoS) Configuration
    POLYGON_METAMASK_WALLET_ADDRESS: str = os.getenv("POLYGON_METAMASK_WALLET_ADDRESS", "0x255F9991233f86B29dB847c8d5b8CB9915e80dCf")
    POLYGON_CHAIN_ID: int = int(os.getenv("POLYGON_CHAIN_ID", "137"))
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")

    # Glama.ai Inter-Agent Mesh MCP Endpoints
    SECURITY_GATE_MCP_URL: str = os.getenv("SECURITY_GATE_MCP_URL", "https://glama.ai/mcp/servers/nohosa001-pixel/security-gate-x402")
    CLEANWEB_MCP_URL: str = os.getenv("CLEANWEB_MCP_URL", "https://glama.ai/mcp/servers/nohosa001-pixel/x402-cleanweb-agent")
    MINERALS_ORACLE_MCP_URL: str = os.getenv("MINERALS_ORACLE_MCP_URL", "https://glama.ai/mcp/servers/nohosa001-pixel/minerals-oracle-x402")


settings = Settings()
