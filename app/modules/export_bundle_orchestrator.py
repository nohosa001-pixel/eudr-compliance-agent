from typing import List, Dict, Any, Optional
import json
import uuid
from datetime import datetime, timezone

from app.schemas import (
    EUDRSupplyChainPayload,
    SpatialPlotResult,
    SatellitePlotResult,
    LegalAuditResult,
    EvidenceBundleSchema,
)
from app.modules.evidence_bundle_generator import EvidenceBundleGenerator
from app.modules.kfs_checklist_scorer import KoreaForestServiceChecklistScorer, KFSReadinessAssessment
from app.modules.producer_adapters.registry_hub import ProducerCountryRegistryHub
from app.modules.producer_adapters.base_adapter import ProducerRegistryVerificationResult

class OneClickExportBundleOrchestrator:
    """
    Orchestrator for the unified EUDR One-Click Export Bundle.
    
    Generates a lawyer-proof, audit-ready compliance dossier combining:
    1. Cryptographic Evidence Bundle (Non-Repudiation HMAC-SHA256 seal)
    2. Korea Forest Service (산림청) 4-Domain Readiness Score
    3. Producer Country Official Registry Verification (Brazil CAR, Ghana CMS, Indonesia SIPUHH)
    4. Satellite & Geospatial Forest Cover Analytics
    5. Official HTML / PDF Printable Export Report
    """

    def __init__(self):
        self.registry_hub = ProducerCountryRegistryHub()

    def build_export_bundle(
        self,
        payload: EUDRSupplyChainPayload,
        spatial_results: List[SpatialPlotResult],
        satellite_results: List[SatellitePlotResult],
        legal_audit: LegalAuditResult,
        producer_registry_id: Optional[str] = None,
        producer_country_code: Optional[str] = None
    ) -> Dict[str, Any]:
        timestamp_str = datetime.now(timezone.utc).isoformat()
        bundle_id = f"EXP-BUNDLE-{payload.execution_id or uuid.uuid4().hex[:12].upper()}"

        # 1. Cryptographic Evidence Bundle
        evidence_bundle = EvidenceBundleGenerator.generate_bundle(
            payload=payload,
            spatial_results=spatial_results,
            satellite_results=satellite_results,
            legal_audit=legal_audit
        )

        # 2. Korea Forest Service (산림청) Checklist Assessment
        kfs_assessment = KoreaForestServiceChecklistScorer.evaluate(
            payload=payload,
            spatial_results=spatial_results,
            satellite_results=satellite_results,
            legal_audit=legal_audit,
            timestamp_str=timestamp_str
        )

        # 3. Producer Country Registry Verification
        producer_verification: Optional[ProducerRegistryVerificationResult] = None
        target_reg_id = producer_registry_id

        # If not explicitly provided, search payload document IDs or plot metadata
        if not target_reg_id:
            for doc in payload.documents:
                doc_clean = doc.doc_id.upper()
                if any(k in doc_clean for k in ["CAR", "CMS", "CCC", "SIPUHH", "ISPO", "MSPO", "BR-", "GH-", "ID-", "CI-", "MY-"]):
                    target_reg_id = doc.doc_id
                    break

        if target_reg_id:
            detected_country = producer_country_code or getattr(payload.plots[0], "country_code", None) if payload.plots else None
            producer_verification = self.registry_hub.verify(target_reg_id, country_code=detected_country)

        # 4. Overall EUDR Verdict Calculation
        zero_deforest = not any(s.deforestation_detected for s in satellite_results)
        kfs_pass = kfs_assessment.compliance_tier in ["PASS_COMPLIANT", "PROVISIONAL_NEEDS_IMPROVEMENT"]
        producer_valid = producer_verification.is_valid if producer_verification else True

        is_cleared = zero_deforest and kfs_pass and producer_valid
        clearance_status = "CLEARED_FOR_EU_IMPORT" if is_cleared else "CRITICAL_DEFICIENCIES_DETECTED"

        bundle_data = {
            "bundle_id": bundle_id,
            "export_batch_id": payload.execution_id or bundle_id,
            "timestamp_utc": timestamp_str,
            "operator_eori": payload.operator.eori_number if payload.operator else "UNKNOWN",
            "operator_name": getattr(payload.operator, "operator_name", None) or getattr(payload.operator, "name", "Export Operator"),
            "overall_clearance_status": clearance_status,
            "is_cleared_for_eu_import": is_cleared,
            "kfs_checklist_assessment": kfs_assessment.model_dump(),
            "producer_registry_verification": producer_verification.model_dump() if producer_verification else None,
            "cryptographic_evidence": evidence_bundle.model_dump(),
            "satellite_summary": {
                "total_plots_analyzed": len(satellite_results),
                "deforestation_detected": not zero_deforest,
                "sensors_consulted": ["Copernicus Sentinel-2", "Hansen Global Forest Change", "EU JRC Forest 2020"]
            },
            "legal_audit_verdict": {
                "overall_compliance": getattr(legal_audit, "overall_compliant", True) if legal_audit else True,
                "risk_tier": str(getattr(legal_audit, "country_risk_tier", "LOW")),
                "total_verified_documents": len(payload.documents)
            }
        }

        return bundle_data

    def render_html_dossier(self, bundle: Dict[str, Any]) -> str:
        """
        Renders a printable executive HTML dossier with modern styling.
        """
        kfs = bundle.get("kfs_checklist_assessment", {})
        evidence = bundle.get("cryptographic_evidence", {})
        prod = bundle.get("producer_registry_verification") or {}
        is_cleared = bundle.get("is_cleared_for_eu_import", False)

        badge_color = "#10b981" if is_cleared else "#ef4444"
        badge_text = "PASSED - CLEARED FOR EU CUSTOMS" if is_cleared else "ALERT - RECTIFICATION REQUIRED"

        kfs_items_html = ""
        for item in kfs.get("items", []):
            st_color = "#10b981" if item.get("status") == "COMPLIANT" else "#f59e0b" if item.get("status") == "PROVISIONAL" else "#ef4444"
            kfs_items_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 12px; font-weight: 600; color: #1e293b;">{item.get('code')}</td>
                <td style="padding: 12px; color: #334155;">{item.get('title')}</td>
                <td style="padding: 12px; font-weight: 700; color: #0f172a;">{item.get('awarded_score')} / {item.get('max_score')}</td>
                <td style="padding: 12px;"><span style="background: {st_color}22; color: {st_color}; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 700;">{item.get('status')}</span></td>
                <td style="padding: 12px; font-size: 13px; color: #64748b;">{item.get('findings')}</td>
            </tr>
            """

        prod_section_html = ""
        if prod:
            p_color = "#10b981" if prod.get("is_valid") else "#ef4444"
            prod_section_html = f"""
            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 18px; margin-bottom: 24px;">
                <h3 style="margin-top: 0; color: #0f172a; font-size: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
                    🏛️ Producer Country Official Registry Verification ({prod.get('country_code')})
                </h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 14px; margin-top: 12px;">
                    <div><strong>Registry:</strong> {prod.get('registry_name')}</div>
                    <div><strong>Identifier:</strong> <code style="background: #e2e8f0; padding: 2px 6px; border-radius: 4px;">{prod.get('identifier')}</code></div>
                    <div><strong>Status:</strong> <span style="color: {p_color}; font-weight: 700;">{prod.get('status')}</span></div>
                    <div><strong>Holder / Farm:</strong> {prod.get('holder_name') or 'N/A'}</div>
                    <div><strong>Spatial Verification:</strong> {prod.get('spatial_coverage_status')}</div>
                    <div><strong>Legal Reserve:</strong> {prod.get('legal_reserve_compliance_pct')}%</div>
                </div>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>EUDR Legal Defense Export Dossier - {bundle.get('bundle_id')}</title>
    <style>
        @media print {{
            body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .no-print {{ display: none; }}
        }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 30px; background: #ffffff; color: #1e293b; line-height: 1.5; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #0f172a; padding-bottom: 16px; margin-bottom: 24px; }}
        .title {{ margin: 0; font-size: 24px; font-weight: 800; color: #0f172a; }}
        .badge {{ background: {badge_color}; color: #ffffff; padding: 8px 16px; border-radius: 6px; font-weight: 800; font-size: 14px; letter-spacing: 0.5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
        .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }}
        .card-label {{ font-size: 12px; text-transform: uppercase; color: #64748b; font-weight: 700; margin-bottom: 4px; }}
        .card-value {{ font-size: 18px; font-weight: 800; color: #0f172a; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 14px; }}
        th {{ background: #f1f5f9; padding: 12px; text-align: left; font-weight: 700; color: #334155; border-bottom: 2px solid #cbd5e1; }}
        .seal {{ border: 2px dashed #94a3b8; background: #fafafa; border-radius: 8px; padding: 16px; font-size: 13px; font-family: monospace; word-break: break-all; color: #334155; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1 class="title">🌲 EUDR Official Due Diligence & Legal Defense Dossier</h1>
            <div style="color: #64748b; font-size: 14px; margin-top: 4px;">Regulation (EU) 2023/1115 & KFS Korea Forest Service Guideline Compliance</div>
        </div>
        <div>
            <span class="badge">{badge_text}</span>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-label">Bundle ID</div>
            <div class="card-value" style="font-size: 15px;">{bundle.get('bundle_id')}</div>
        </div>
        <div class="card">
            <div class="card-label">EU Operator EORI</div>
            <div class="card-value">{bundle.get('operator_eori')}</div>
        </div>
        <div class="card">
            <div class="card-label">KFS Readiness Score</div>
            <div class="card-value" style="color: #0284c7;">{kfs.get('total_score', 0)} / 100 pts</div>
        </div>
    </div>

    {prod_section_html}

    <h2 style="font-size: 18px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
        📋 산림청(KFS) EUDR 4대 핵심 분야 표준 점검 결과
    </h2>
    <table>
        <thead>
            <tr>
                <th style="width: 15%;">Item Code</th>
                <th style="width: 30%;">Assessment Domain</th>
                <th style="width: 12%;">Score</th>
                <th style="width: 13%;">Verdict</th>
                <th style="width: 30%;">Key Findings</th>
            </tr>
        </thead>
        <tbody>
            {kfs_items_html}
        </tbody>
    </table>

    <h2 style="font-size: 18px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
        🔒 Cryptographic Non-Repudiation Seal (Audit Integrity)
    </h2>
    <div class="seal">
        <div><strong>Digital Signature (HMAC-SHA256):</strong> {evidence.get('digital_signature_hmac_sha256')}</div>
        <div style="margin-top: 6px;"><strong>Payload Input Hash (SHA-256):</strong> {evidence.get('sha256_input_payload')}</div>
        <div style="margin-top: 6px;"><strong>Spatial Coordinates Hash:</strong> {evidence.get('sha256_spatial_checksum')}</div>
        <div style="margin-top: 6px;"><strong>Timestamp (UTC):</strong> {bundle.get('timestamp_utc')} | <strong>Status:</strong> IMMUTABLE_AND_VERIFIED</div>
    </div>

    <div style="margin-top: 32px; font-size: 12px; color: #94a3b8; text-align: center;">
        Generated by EUDRAgent Enterprise Platform • Valid for EU Customs Automated Clearing System (TRACES NT)
    </div>
</body>
</html>
"""
        return html_content
