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

    # Telegram Alert Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_NOTIFICATIONS_ENABLED: bool = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "true").lower() in ("true", "1", "yes")
    TELEGRAM_ALLOW_TEST_NOTIFICATIONS: bool = os.getenv("TELEGRAM_ALLOW_TEST_NOTIFICATIONS", "false").lower() in ("true", "1", "yes")

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

    # Web3 / MetaMask Multi-Chain Configuration (Polygon, Base, Arbitrum)
    POLYGON_METAMASK_WALLET_ADDRESS: str = os.getenv("POLYGON_METAMASK_WALLET_ADDRESS", "0x255F9991233f86B29dB847c8d5b8CB9915e80dCf")
    POLYGON_CHAIN_ID: int = int(os.getenv("POLYGON_CHAIN_ID", "137"))
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")

    BASE_CHAIN_ID: int = int(os.getenv("BASE_CHAIN_ID", "8453"))
    BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")

    ARBITRUM_CHAIN_ID: int = int(os.getenv("ARBITRUM_CHAIN_ID", "42161"))
    ARBITRUM_RPC_URL: str = os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc")

    # Native USDC Contract Addresses
    POLYGON_USDC_CONTRACT: str = os.getenv("POLYGON_USDC_CONTRACT", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")
    BASE_USDC_CONTRACT: str = os.getenv("BASE_USDC_CONTRACT", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
    ARBITRUM_USDC_CONTRACT: str = os.getenv("ARBITRUM_USDC_CONTRACT", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831")

    # Deployed AgentPaymentVault Smart Contracts
    POLYGON_AGENT_PAYMENT_VAULT: str = os.getenv("POLYGON_AGENT_PAYMENT_VAULT", "0x45ecBfAa2F4B0Bc6ccD3eB2dB9B1Ca49CF121861")
    BASE_AGENT_PAYMENT_VAULT: str = os.getenv("BASE_AGENT_PAYMENT_VAULT", "0x28292D76E07E5539F15F3b97935dE8E0432E76DD")
    ARBITRUM_AGENT_PAYMENT_VAULT: str = os.getenv("ARBITRUM_AGENT_PAYMENT_VAULT", "0x28292D76E07E5539F15F3b97935dE8E0432E76DD")

    # Glama.ai Inter-Agent Mesh MCP Endpoints
    SECURITY_GATE_MCP_URL: str = os.getenv("SECURITY_GATE_MCP_URL", "https://glama.ai/mcp/servers/nohosa001-pixel/security-gate-x402")
    CLEANWEB_MCP_URL: str = os.getenv("CLEANWEB_MCP_URL", "https://glama.ai/mcp/servers/nohosa001-pixel/x402-cleanweb-agent")
    MINERALS_ORACLE_MCP_URL: str = os.getenv("MINERALS_ORACLE_MCP_URL", "https://glama.ai/mcp/servers/nohosa001-pixel/minerals-oracle-x402")


settings = Settings()
