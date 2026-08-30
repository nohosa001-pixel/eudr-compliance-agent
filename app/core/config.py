from pydantic import BaseModel
from datetime import date

class Settings(BaseModel):
    PROJECT_NAME: str = "EUDR Compliance Automation Agent"
    API_V1_PREFIX: str = "/api/v1"
    EUDR_CUTOFF_DATE: date = date(2020, 12, 31)
    DEFAULT_DEFORESTATION_TOLERANCE_PCT: float = 0.05  # 0.05% margin for satellite noise
    SECRET_KEY_FOR_SIGNING: str = "eudr-traces-nt-secret-key-2024"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    USE_DISTRIBUTED_QUEUE: bool = False

    # PostgreSQL / PostGIS Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "eudr_compliance"
    DATABASE_URL: str = ""

    # Copernicus CDSE / Sentinel Hub Live Account Settings
    COPERNICUS_CLIENT_ID: str = ""
    COPERNICUS_CLIENT_SECRET: str = ""
    USE_LIVE_COPERNICUS_API: bool = False

settings = Settings()
