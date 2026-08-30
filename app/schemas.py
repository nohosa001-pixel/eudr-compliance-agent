from __future__ import annotations
from enum import Enum
from typing import List, Optional, Union, Dict, Any
from datetime import date, datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid

# --- Enumerations ---

class GeometryTypeEnum(str, Enum):
    POINT = "Point"
    POLYGON = "Polygon"
    MULTIPOLYGON = "MultiPolygon"

class RiskTierEnum(str, Enum):
    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"

class ComplianceStatusEnum(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    ACTION_REQUIRED = "ACTION_REQUIRED"

class DocumentTypeEnum(str, Enum):
    LAND_USE_TITLE = "LAND_USE_TITLE"
    HARVEST_PERMIT = "HARVEST_PERMIT"
    BUSINESS_LICENSE = "BUSINESS_LICENSE"
    FPIC_CONSENT = "FPIC_CONSENT"
    TAX_CLEARANCE = "TAX_CLEARANCE"
    EIA_REPORT = "EIA_REPORT"
    CUSTOMS_DECLARATION = "CUSTOMS_DECLARATION"

class EUDRCommodityCategory(str, Enum):
    CATTLE = "Cattle (소)"
    COCOA = "Cocoa (코코아)"
    COFFEE = "Coffee (커피)"
    OIL_PALM = "Oil Palm (팜유)"
    RUBBER = "Rubber (고무)"
    SOYA = "Soya (대두)"
    WOOD = "Wood & Timber (목재/임산물)"
    OTHER = "Other / Unclassified"

# --- GeoJSON Schemas ---

class PointGeometry(BaseModel):
    type: str = Field(default="Point", pattern="^Point$")
    coordinates: List[float] = Field(
        ..., 
        description="[Longitude, Latitude] in WGS84 (EPSG:4326)",
        min_length=2,
        max_length=2
    )

    @field_validator("coordinates")
    @classmethod
    def validate_point_bounds(cls, v: List[float]) -> List[float]:
        lon, lat = v[0], v[1]
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude {lon} is out of bounds [-180, 180]")
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude {lat} is out of bounds [-90, 90]")
        return v

class PolygonGeometry(BaseModel):
    type: str = Field(default="Polygon", pattern="^Polygon$")
    coordinates: List[List[List[float]]] = Field(
        ...,
        description="List of linear rings: exterior ring followed by optional interior rings. Ring is list of [lon, lat]"
    )

    @field_validator("coordinates")
    @classmethod
    def validate_polygon_structure(cls, rings: List[List[List[float]]]) -> List[List[List[float]]]:
        if not rings or len(rings) == 0:
            raise ValueError("Polygon coordinates must contain at least an exterior ring.")
        for ring_idx, ring in enumerate(rings):
            if len(ring) < 4:
                raise ValueError(f"Ring {ring_idx} has {len(ring)} points; minimum 4 points required (closed ring).")
            # Closed ring check
            if ring[0] != ring[-1]:
                raise ValueError(f"Ring {ring_idx} is not closed: first {ring[0]} != last {ring[-1]}.")
            for pt in ring:
                if len(pt) < 2:
                    raise ValueError("Each coordinate in ring must have [lon, lat].")
                lon, lat = pt[0], pt[1]
                if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                    raise ValueError(f"Coordinate [{lon}, {lat}] in ring is out of WGS84 range.")
        return rings

class MultiPolygonGeometry(BaseModel):
    type: str = Field(default="MultiPolygon", pattern="^MultiPolygon$")
    coordinates: List[List[List[List[float]]]] = Field(
        ...,
        description="List of polygons (each polygon is a list of linear rings)"
    )

    @field_validator("coordinates")
    @classmethod
    def validate_multipolygon_structure(cls, polys: List[List[List[List[float]]]]) -> List[List[List[List[float]]]]:
        if not polys or len(polys) == 0:
            raise ValueError("MultiPolygon must contain at least one polygon.")
        for poly_idx, rings in enumerate(polys):
            if not rings:
                raise ValueError(f"Polygon {poly_idx} in MultiPolygon is empty.")
            for ring_idx, ring in enumerate(rings):
                if len(ring) < 4:
                    raise ValueError(f"Poly {poly_idx} Ring {ring_idx} has {len(ring)} points; min 4 required.")
                if ring[0] != ring[-1]:
                    raise ValueError(f"Poly {poly_idx} Ring {ring_idx} is not closed.")
                for pt in ring:
                    lon, lat = pt[0], pt[1]
                    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                        raise ValueError(f"Coordinate [{lon}, {lat}] in MultiPolygon is out of WGS84 range.")
        return polys

GeometryUnion = Union[PointGeometry, PolygonGeometry, MultiPolygonGeometry]

# --- Supply Chain Input Schemas ---

class ProductionPlotInput(BaseModel):
    plot_id: str = Field(..., description="Unique identifier for the production plot")
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 country code (e.g. 'ID', 'BR', 'CI', 'GH')", min_length=2, max_length=2)
    area_hectares: float = Field(..., description="Declared area in hectares (ha)", gt=0)
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Point, Polygon, or MultiPolygon dictionary")
    production_date: date = Field(..., description="Date or end date of production/harvest")
    producer_name: Optional[str] = None
    notes: Optional[str] = None

class LegalDocumentInput(BaseModel):
    doc_id: str = Field(..., description="Unique document reference ID")
    doc_type: DocumentTypeEnum
    issuing_authority: str
    issue_date: date
    expiry_date: Optional[date] = None
    document_url: Optional[str] = None
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of document binary for tamper verification")

class OperatorInfo(BaseModel):
    operator_name: str
    eori_number: str = Field(..., description="EU Economic Operators Registration and Identification number")
    vat_number: Optional[str] = None
    country: str = Field(..., description="ISO 2-letter country code")
    address: str

class CommodityInfo(BaseModel):
    hs_code: str = Field(..., description="Harmonized System Code (e.g., '440711', '151110', '400110')")
    description: str
    net_mass_kg: float = Field(..., gt=0, description="Net mass in kilograms")
    volume_m3: Optional[float] = Field(None, description="Supplementary unit in m3 if applicable")
    scientific_name: Optional[str] = Field(None, description="Botanical/tree species name (mandatory for timber/wood under EUDR Annex I)")

class EUDRSupplyChainPayload(BaseModel):
    execution_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    supplier_id: str
    operator: OperatorInfo
    commodity: CommodityInfo
    plots: List[ProductionPlotInput] = Field(..., min_length=1)
    documents: List[LegalDocumentInput] = Field(default_factory=list)

# --- Analysis & Compliance Output Schemas ---

class ReviewStatusEnum(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    NEEDS_EXPERT_REVIEW = "NEEDS_EXPERT_REVIEW"
    EXPERT_APPROVED = "EXPERT_APPROVED"
    REJECTED = "REJECTED"
    ACTION_REQUIRED = "ACTION_REQUIRED"

class SpatialPlotResult(BaseModel):
    plot_id: str
    is_valid: bool
    area_hectares: float = 0.0
    declared_area_ha: float = 0.0
    calculated_area_ha: Optional[float] = None
    area_discrepancy_pct: float = 0.0
    geometry_type: str
    is_polygon_required: bool = False
    four_ha_polygon_rule_compliant: bool = True
    precision_warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    overlap_detected: bool = False
    overlapping_plot_ids: List[str] = Field(default_factory=list)
    standardized_geojson: Optional[Dict[str, Any]] = None
    # Self-Healing Metadata
    healing_applied: bool = False
    healing_actions: List[str] = Field(default_factory=list)
    original_geometry: Optional[Dict[str, Any]] = None

class SatellitePlotResult(BaseModel):
    plot_id: str
    deforestation_detected: bool
    forest_loss_year: Optional[int] = None
    loss_area_ha: float = 0.0
    loss_ratio_pct: float = 0.0
    baseline_forest_cover_pct: float = 100.0
    ndvi_trend: str = "STABLE"
    compliance_passed: bool
    audit_notes: str
    satellite_consensus: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 1.0
    # Cloud Fallback & Buffer Zone Analysis
    cloud_fallback_applied: bool = False
    sensor_mode: str = "OPTICAL_COPERNICUS_HANSEN"
    optical_cloud_occluded: bool = False
    sar_backscatter_analysis: Optional[Dict[str, Any]] = None
    buffer_zone_analysis: Optional[Dict[str, Any]] = None

class LegalAuditResult(BaseModel):
    overall_compliant: bool
    country_risk_tier: RiskTierEnum
    simplified_due_diligence_eligible: bool = False
    commodity_category: EUDRCommodityCategory = EUDRCommodityCategory.OTHER
    verified_documents_count: int
    missing_required_documents: List[str] = Field(default_factory=list)
    expired_documents: List[str] = Field(default_factory=list)
    risk_score: float = Field(..., description="0.0 (No Risk) to 1.0 (Critical Risk)")
    notes: List[str] = Field(default_factory=list)

class EvidenceBundleSchema(BaseModel):
    bundle_id: str
    execution_id: str
    timestamp_utc: str
    sha256_input_payload: str
    sha256_spatial_checksum: str
    satellite_telemetry_manifest: List[Dict[str, Any]]
    verified_documents_manifest: List[Dict[str, Any]]
    digital_signature_hmac_sha256: str
    non_repudiation_status: str = "IMMUTABLE_AND_VERIFIED"

class ConfidenceAssessment(BaseModel):
    overall_confidence_score: float = Field(..., ge=0.0, le=1.0)
    spatial_confidence: float = 1.0
    satellite_triangulation_confidence: float = 1.0
    legal_document_confidence: float = 1.0
    requires_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    review_status: ReviewStatusEnum = ReviewStatusEnum.AUTO_APPROVED

class TRACESNTStatement(BaseModel):
    dds_reference_id: str
    operator_eori: str
    operator_name: str
    commodity_hs_code: str
    commodity_category: str
    commodity_description: str
    net_mass_kg: float
    country_of_production: str
    total_plots_count: int
    total_area_ha: float
    deforestation_free_declaration: bool
    legally_produced_declaration: bool
    digital_signature_sha256: str
    submission_ready_traces_payload: Dict[str, Any]
    generated_at: datetime

class DDSReport(BaseModel):
    execution_id: str
    status: ComplianceStatusEnum
    evaluation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    summary_message: str
    spatial_summary: Dict[str, Any]
    satellite_summary: Dict[str, Any]
    legal_summary: Dict[str, Any]
    plots_detail: List[Dict[str, Any]]
    confidence_assessment: ConfidenceAssessment
    evidence_bundle: Optional[EvidenceBundleSchema] = None
    traces_dds: Optional[TRACESNTStatement] = None
    audit_trail: Dict[str, Any]

# Aliases for convenience
FullComplianceReport = DDSReport
TRACESDDSStatement = TRACESNTStatement

class ExpertReviewInput(BaseModel):
    execution_id: str
    decision: ReviewStatusEnum
    expert_name: str
    expert_notes: str
    override_reason: Optional[str] = None

class ExpertReviewResponse(BaseModel):
    execution_id: str
    previous_status: ComplianceStatusEnum
    new_status: ComplianceStatusEnum
    review_status: ReviewStatusEnum
    reviewed_by: str
    reviewed_at: str
    message: str

class BenchmarkCaseResult(BaseModel):
    case_id: str
    title: str
    scenario_type: str
    expected_status: ComplianceStatusEnum
    actual_status: ComplianceStatusEnum
    passed: bool
    confidence_score: float
    duration_ms: float

class BenchmarkSuiteReport(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    accuracy_pct: float
    precision_pct: float
    recall_pct: float
    f1_score: float
    false_positive_rate_pct: float
    false_negative_rate_pct: float
    benchmark_timestamp: str
    case_results: List[BenchmarkCaseResult]


# --- Batch Processing Schemas ---

class BatchJobStatusEnum(str, Enum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    VALIDATING_GIS = "VALIDATING_GIS"
    ANALYZING_SATELLITE = "ANALYZING_SATELLITE"
    AUDITING_LEGAL = "AUDITING_LEGAL"
    GENERATING_DDS = "GENERATING_DDS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class BatchJobSubmitResponse(BaseModel):
    job_id: str
    status: BatchJobStatusEnum
    message: str
    created_at: str

class BatchJobStatusResponse(BaseModel):
    job_id: str
    status: BatchJobStatusEnum
    progress_pct: float = Field(0.0, ge=0.0, le=100.0)
    current_step: str = ""
    total_plots: int = 0
    processed_plots: int = 0
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None
    overall_status: Optional[str] = None
    execution_id: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# --- 5-Year Audit Trail & Integrity Verification Schemas ---

class IntegrityCheckDetail(BaseModel):
    check_name: str
    passed: bool
    expected_value: str
    actual_value: str
    message: str

class IntegrityVerificationResult(BaseModel):
    execution_id: str
    is_valid: bool
    verification_status: str  # INTEGRITY_VERIFIED, TAMPER_DETECTED, NOT_FOUND
    timestamp_utc: str
    checks_passed_count: int
    checks_total_count: int
    check_details: List[IntegrityCheckDetail]
    tamper_alerts: List[str] = Field(default_factory=list)
    legal_defense_statement: str
    digital_signature_verified: bool
    evidence_bundle_id: Optional[str] = None

class EvidencePackageResponse(BaseModel):
    execution_id: str
    bundle_id: str
    digital_signature_hmac_sha256: str
    timestamp_utc: str
    evidence_package: Dict[str, Any]
    integrity_status: str


class ApiKeyCreateRequest(BaseModel):
    company_name: str
    contact_email: str
    tier: str = "STARTER"  # STARTER, PRO, ENTERPRISE


class ApiKeyResponse(BaseModel):
    key_id: str
    api_key: str  # Only returned once upon creation (e.g. eudr_live_xxxx)
    company_name: str
    contact_email: str
    tier: str
    monthly_quota_plots: int
    rate_limit_per_min: int
    created_at: str
    message: str


class ApiKeyValidationResponse(BaseModel):
    is_valid: bool
    key_id: Optional[str] = None
    company_name: Optional[str] = None
    tier: Optional[str] = None
    remaining_quota_plots: Optional[int] = None
    message: str

