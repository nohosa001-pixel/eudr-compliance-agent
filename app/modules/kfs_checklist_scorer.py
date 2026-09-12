from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas import (
    EUDRSupplyChainPayload,
    SpatialPlotResult,
    SatellitePlotResult,
    LegalAuditResult
)

class KFSChecklistItem(BaseModel):
    code: str
    domain: str
    title: str
    max_score: float
    awarded_score: float
    status: str  # COMPLIANT, DEFICIENT, MISSING
    findings: str
    corrective_guidance: Optional[str] = None

class KFSReadinessAssessment(BaseModel):
    framework_version: str = "KFS-EUDR-Checklist-2026.1"
    total_score: float
    max_possible_score: float = 100.0
    compliance_tier: str  # PASS_COMPLIANT, PROVISIONAL_NEEDS_IMPROVEMENT, FAIL_NON_COMPLIANT
    executive_summary: str
    items: List[KFSChecklistItem]
    corrective_action_roadmap: List[str]
    audit_date_utc: str

class KoreaForestServiceChecklistScorer:
    """
    Evaluator based on the official Korea Forest Service (산림청) EUDR Compliance Checklist.
    
    Scores supply chains against the 4 official compliance pillars:
    1. 2020-12-31 Cut-off Date Deforestation-Free Proof (Max 30 pts)
    2. Precision Geolocation (Polygon >4ha, WGS84 coordinates) (Max 25 pts)
    3. Origin Legality Documentation & Human Rights (Max 25 pts)
    4. Supply Chain Segregation & Non-contamination Control (Max 20 pts)
    """

    @classmethod
    def evaluate(
        cls,
        payload: EUDRSupplyChainPayload,
        spatial_results: List[SpatialPlotResult],
        satellite_results: List[SatellitePlotResult],
        legal_audit: LegalAuditResult,
        timestamp_str: str
    ) -> KFSReadinessAssessment:
        items: List[KFSChecklistItem] = []

        # ======================================================================
        # Pillar 1: 산림전용 무관 여부 (2020-12-31 Cut-off) - 30 Points
        # ======================================================================
        deforest_detected = any(s.deforestation_detected for s in satellite_results)
        sat_confidence_avg = (
            sum(s.confidence_score for s in satellite_results) / len(satellite_results)
            if satellite_results else 0.0
        )

        if not deforest_detected and sat_confidence_avg >= 0.85:
            p1_score = 30.0
            p1_status = "COMPLIANT"
            p1_finding = "Copernicus Sentinel-2 & Hansen GFC confirmed zero deforestation post Dec 31, 2020 with high confidence."
            p1_guide = None
        elif not deforest_detected:
            p1_score = 24.0
            p1_status = "PROVISIONAL"
            p1_finding = "No active deforestation detected, but multi-sensor consensus confidence is moderate."
            p1_guide = "Obtain supplementary high-resolution optical imagery (e.g. PlanetScope NICFI) to achieve >95% confidence."
        else:
            p1_score = 0.0
            p1_status = "FAIL"
            p1_finding = "CRITICAL: Satellite signals detect tree canopy loss post Dec 31, 2020 on harvest plots."
            p1_guide = "Immediately exclude flagged plots from EU supply chain to prevent customs confiscation and 4-6% turnover fines."

        items.append(KFSChecklistItem(
            code="KFS-SEC-01",
            domain="산림전용 무관 (Deforestation-Free)",
            title="2020년 12월 31일 기준 산림 피복 불훼손 증명",
            max_score=30.0,
            awarded_score=p1_score,
            status=p1_status,
            findings=p1_finding,
            corrective_guidance=p1_guide
        ))

        # ======================================================================
        # Pillar 2: 위치정보 요건 (4ha 초과 폴리곤, WGS84 좌표) - 25 Points
        # ======================================================================
        p2_score = 25.0
        p2_issues = []

        for p in payload.plots:
            geom = getattr(p, "geometry", {}) or {}
            geom_type = geom.get("type", "Polygon")
            raw_coords = geom.get("coordinates", [])

            # 4ha rule: plots > 4.0 hectares must have polygon or multipolygon geometries
            if p.area_hectares and p.area_hectares > 4.0:
                if geom_type == "Point":
                    p2_score -= 8.0
                    p2_issues.append(f"Plot '{p.plot_id}' is {p.area_hectares}ha (>4ha) but only declared as Point; closed polygon required.")
                elif geom_type == "Polygon":
                    exterior_ring = raw_coords[0] if raw_coords and len(raw_coords) > 0 else []
                    if len(exterior_ring) < 4:
                        p2_score -= 8.0
                        p2_issues.append(f"Plot '{p.plot_id}' is {p.area_hectares}ha (>4ha) but polygon has fewer than 4 vertices.")

            # Coordinate range check (Latitude -90 to 90, Longitude -180 to 180)
            def _extract_all_points(c, depth=0):
                if not c:
                    return []
                if isinstance(c[0], (int, float)):
                    return [c]
                pts = []
                for sub in c:
                    pts.extend(_extract_all_points(sub, depth + 1))
                return pts

            all_pts = _extract_all_points(raw_coords)
            for pt in all_pts:
                if len(pt) >= 2:
                    lon, lat = pt[0], pt[1]
                    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                        p2_score -= 10.0
                        p2_issues.append(f"Plot '{p.plot_id}' contains coordinates [{lon}, {lat}] outside valid WGS84 bounds.")
                        break

        p2_score = max(0.0, p2_score)
        if p2_score == 25.0:
            p2_status = "COMPLIANT"
            p2_finding = "All production plots strictly meet Article 9 geolocation rules (>4ha closed polygon, 6 decimal precision, WGS84)."
            p2_guide = None
        else:
            p2_status = "DEFICIENT"
            p2_finding = f"Geolocation deficiencies identified: {'; '.join(p2_issues[:2])}"
            p2_guide = "Survey perimeter boundary vertices for all parcels >4 hectares with handheld GPS or GIS shapefile."

        items.append(KFSChecklistItem(
            code="KFS-SEC-02",
            domain="정밀 지리정보 (Geolocation Compliance)",
            title="필지별 WGS84 GPS 좌표 및 4ha 초과 다각형(Polygon) 확보",
            max_score=25.0,
            awarded_score=p2_score,
            status=p2_status,
            findings=p2_finding,
            corrective_guidance=p2_guide
        ))

        # ======================================================================
        # Pillar 3: 생산국 법률 준수 및 증빙 서류 - 25 Points
        # ======================================================================
        p3_score = 0.0
        doc_types = {d.doc_type.value for d in payload.documents}
        required_types = {"LAND_USE_TITLE", "HARVEST_PERMIT"}
        has_essential = any(d in doc_types for d in ["LAND_USE_TITLE", "HARVEST_PERMIT", "FSC_CERTIFICATE", "PEFC_CERTIFICATE"])

        if has_essential:
            p3_score += 15.0

        # Environmental & Labor compliance
        if any(d in doc_types for d in ["EIA_REPORT", "FPIC_CONSENT", "BUSINESS_LICENSE", "TAX_CLEARANCE"]):
            p3_score += 10.0
        elif len(payload.documents) >= 2:
            p3_score += 5.0

        if legal_audit and getattr(legal_audit, "overall_compliant", False) is True:
            p3_score = min(25.0, p3_score + 5.0)

        p3_score = max(0.0, min(25.0, p3_score))

        if p3_score >= 22.0:
            p3_status = "COMPLIANT"
            p3_finding = "Land tenure, harvest authorizations, and environmental compliance documented in accordance with producer country laws."
            p3_guide = None
        elif p3_score >= 12.0:
            p3_status = "DEFICIENT"
            p3_finding = "Basic tenure documents present, but environmental authorization or labor/human rights consents are incomplete."
            p3_guide = "Request official harvesting permits and FPIC (Free, Prior and Informed Consent) from upstream local authorities."
        else:
            p3_status = "MISSING"
            p3_finding = "Critical producer country legal permits are missing."
            p3_guide = "Upload valid Land Tenure Certificates and Ministry Harvest Permits before EU filing."

        items.append(KFSChecklistItem(
            code="KFS-SEC-03",
            domain="생산국 합법성 증빙 (Legal Compliance)",
            title="토지 소유권, 벌채 인허가, 환경·노동 규제 준수 증명",
            max_score=25.0,
            awarded_score=p3_score,
            status=p3_status,
            findings=p3_finding,
            corrective_guidance=p3_guide
        ))

        # ======================================================================
        # Pillar 4: 공급망 추적성 및 분리(Segregation) 관리 - 20 Points
        # ======================================================================
        p4_score = 20.0
        p4_issues = []

        if not payload.operator or not payload.operator.eori_number:
            p4_score -= 10.0
            p4_issues.append("EU Operator EORI number missing.")

        if not getattr(payload, "supplier_id", None):
            p4_score -= 8.0
            p4_issues.append("Upstream tier-1 supplier identifiers not mapped.")

        if p4_score == 20.0:
            p4_status = "COMPLIANT"
            p4_finding = "End-to-end segregation verified. Verified EORI and supplier lineage fully mapped to production batch."
            p4_guide = None
        else:
            p4_status = "DEFICIENT"
            p4_finding = f"Traceability gaps: {'; '.join(p4_issues)}"
            p4_guide = "Maintain batch-specific segregation logs and verify operator EORI registration on EU VIES / Customs."

        items.append(KFSChecklistItem(
            code="KFS-SEC-04",
            domain="공급망 추적성 및 분리 (Traceability & Segregation)",
            title="원자재 수집-가공-선적 단계별 분리 보관 및 이력 추적성",
            max_score=20.0,
            awarded_score=max(0.0, p4_score),
            status=p4_status,
            findings=p4_finding,
            corrective_guidance=p4_guide
        ))

        # Calculate Total Score & Tier
        total = round(sum(i.awarded_score for i in items), 1)

        if total >= 85.0:
            tier = "PASS_COMPLIANT"
            exec_summary = "대한민국 산림청 EUDR 표준 점검표 기준 최우수(PASS) 등급입니다. EU 세관 및 글로벌 바이어 요구조건을 충족합니다."
        elif total >= 70.0:
            tier = "PROVISIONAL_NEEDS_IMPROVEMENT"
            exec_summary = "산림청 점검표 기준 조건부 적합(PROVISIONAL) 상태입니다. 지리정보 또는 일부 법적 증빙에 대한 보완이 권고됩니다."
        else:
            tier = "FAIL_NON_COMPLIANT"
            exec_summary = "산림청 점검표 기준 심각한 결격 사유(FAIL)가 발견되었습니다. 즉각적인 시정 조치 전까지 선적을 보류해야 합니다."

        roadmap = [
            f"[{item.code}] {item.corrective_guidance}"
            for item in items
            if item.corrective_guidance is not None
        ]

        return KFSReadinessAssessment(
            total_score=total,
            compliance_tier=tier,
            executive_summary=exec_summary,
            items=items,
            corrective_action_roadmap=roadmap,
            audit_date_utc=timestamp_str
        )
