import datetime
import importlib

try:
    _sa = importlib.import_module("sqlalchemy")
    Column = _sa.Column
    String = _sa.String
    Float = _sa.Float
    Boolean = _sa.Boolean
    DateTime = _sa.DateTime
    Text = _sa.Text
    JSON = _sa.JSON
    Integer = _sa.Integer
except Exception:
    Column = String = Float = Boolean = DateTime = Text = JSON = Integer = lambda *args, **kwargs: None  # type: ignore

from app.db.session import Base


class AuditExecutionRecord(Base):
    __tablename__ = "audit_executions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    execution_id = Column(String(64), unique=True, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    supplier_id = Column(String(64), index=True)
    operator_name = Column(String(128))
    commodity_hs_code = Column(String(16), index=True)
    commodity_category = Column(String(32))
    
    total_plots = Column(Integer, default=0)
    total_area_ha = Column(Float, default=0.0)
    
    overall_status = Column(String(32), index=True) # COMPLIANT, NON_COMPLIANT
    confidence_score = Column(Float, default=0.0)
    review_status = Column(String(32), default="AUTO_APPROVED")
    
    dds_reference_id = Column(String(128), nullable=True, index=True)
    evidence_bundle_hash = Column(String(128), nullable=True)
    
    traces_submission_status = Column(String(32), default="UNSUBMITTED") # UNSUBMITTED, SUBMITTED, REJECTED
    traces_ack_number = Column(String(128), nullable=True)
    
    payload_snapshot = Column(JSON, nullable=True)
    full_report_snapshot = Column(JSON, nullable=True)
    evidence_bundle_snapshot = Column(JSON, nullable=True)


class BatchJobRecord(Base):
    __tablename__ = "batch_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(32), default="QUEUED", index=True)  # QUEUED, PROCESSING, COMPLETED, FAILED
    progress_pct = Column(Float, default=0.0)
    current_step = Column(String(128), default="Initialized")
    total_plots = Column(Integer, default=0)
    processed_plots = Column(Integer, default=0)
    
    supplier_id = Column(String(64), nullable=True)
    operator_name = Column(String(128), nullable=True)
    commodity_hs_code = Column(String(16), nullable=True)
    
    execution_id = Column(String(64), nullable=True, index=True)
    overall_status = Column(String(32), nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    
    result_snapshot = Column(JSON, nullable=True)


try:
    _ga = importlib.import_module("geoalchemy2")
    Geometry = getattr(_ga, "Geometry", None)
    from app.db.session import DATABASE_URL
    GEOALCHEMY_AVAILABLE = True and DATABASE_URL.startswith("postgresql")
except Exception:
    Geometry = None
    GEOALCHEMY_AVAILABLE = False


class SpatialPlotRecord(Base):
    """
    High-Performance Spatial PostGIS Table for Production Plot Geometries.
    - Uses PostGIS GiST Spatial Indexing for fast R-Tree geometric lookups on PostgreSQL.
    - Stores WGS84 (EPSG:4326) Points, Polygons, and MultiPolygons.
    - Gracefully falls back to WKT text storage when running on SQLite without SpatiaLite.
    """
    __tablename__ = "spatial_plots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plot_id = Column(String(64), index=True, nullable=False)
    execution_id = Column(String(64), index=True, nullable=True)
    supplier_id = Column(String(64), index=True, nullable=True)
    country_code = Column(String(8), index=True, nullable=False)
    
    geometry_type = Column(String(32), default="Polygon")  # Point, Polygon, MultiPolygon
    declared_area_ha = Column(Float, default=0.0)
    calculated_geodesic_area_ha = Column(Float, default=0.0)
    
    is_valid_geometry = Column(Boolean, default=True)
    is_self_healed = Column(Boolean, default=False)
    deforestation_free = Column(Boolean, default=True)
    
    # PostGIS Spatial Geometry Column (SRID 4326 = WGS84) on PostgreSQL, WKT Text on SQLite
    if GEOALCHEMY_AVAILABLE and Geometry is not None:
        geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=True)
    else:
        geom = Column(Text, nullable=True)
    
    geojson_raw = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class ApiKeyRecord(Base):
    """
    SaaS Client Tenant & API Key Authentication Record.
    """
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key_id = Column(String(64), unique=True, index=True, nullable=False)
    api_key_hash = Column(String(128), unique=True, index=True, nullable=False)
    
    company_name = Column(String(128), nullable=False)
    contact_email = Column(String(128), index=True, nullable=False)
    tier = Column(String(32), default="STARTER")  # STARTER, PRO, ENTERPRISE
    
    is_active = Column(Boolean, default=True)
    rate_limit_per_min = Column(Integer, default=60)
    monthly_quota_plots = Column(Integer, default=5000)
    used_plots_this_month = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True)


class LeadInquiryRecord(Base):
    """
    Enterprise Lead Capture & Demo Request Record.
    """
    __tablename__ = "lead_inquiries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    inquiry_id = Column(String(64), unique=True, index=True, nullable=False)
    
    company_name = Column(String(128), nullable=False)
    contact_name = Column(String(128), nullable=False)
    contact_email = Column(String(128), index=True, nullable=False)
    phone = Column(String(64), nullable=True)
    
    commodity_type = Column(String(64), default="Timber")
    estimated_monthly_plots = Column(String(64), default="500 - 5,000")
    message = Column(Text, nullable=True)
    
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)
    status = Column(String(32), default="NEW", index=True)  # NEW, CONTACTED, QUALIFIED, CLOSED
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

