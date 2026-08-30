import os
import importlib

try:
    _sa = importlib.import_module("sqlalchemy")
    _sa_orm = importlib.import_module("sqlalchemy.orm")
    create_engine = getattr(_sa, "create_engine")
    sessionmaker = getattr(_sa_orm, "sessionmaker")
    declarative_base = getattr(_sa_orm, "declarative_base")
    text = getattr(_sa, "text")
except Exception:
    create_engine = lambda *args, **kwargs: None  # type: ignore
    sessionmaker = lambda *args, **kwargs: lambda: None  # type: ignore
    declarative_base = lambda *args, **kwargs: type("Base", (), {"metadata": type("Meta", (), {"create_all": lambda *a, **k: None})()})  # type: ignore
    text = lambda q: q  # type: ignore

from app.core.config import settings

def get_database_url() -> str:
    """Resolves database URL from settings, environment, or default SQLite path."""
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    if os.getenv("USE_POSTGRES", "false").lower() == "true":
        return f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eudr_compliance.db")
    return f"sqlite:///{db_path}"

DATABASE_URL = get_database_url()

def create_db_engine(url: str):
    """Creates an optimized SQLAlchemy engine for PostgreSQL (with pooling) or SQLite."""
    if url.startswith("postgresql"):
        return create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        echo=False
    )

engine = create_db_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes tables and creates PostGIS extension if connected to PostgreSQL."""
    if DATABASE_URL.startswith("postgresql"):
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
        except Exception:
            pass  # Non-fatal if extension already exists or insufficient permissions
    Base.metadata.create_all(bind=engine)
