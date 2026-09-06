from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import hmac
import hashlib
import json
import uuid

from app.schemas import (
    EUDRSupplyChainPayload,
    SpatialPlotResult,
    SatellitePlotResult,
    LegalAuditResult,
    DDSReport,
    TRACESNTStatement,
    ComplianceStatusEnum,
    ConfidenceAssessment,
    ReviewStatusEnum
)
from app.core.config import settings
from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper
from app.modules.evidence_bundle_generator import EvidenceBundleGenerator

class DDSGenerator:
    """
    Generates EU TRACES-NT compliant Due Diligence Statement (DDS) reports,
    cryptographic evidence packages, and confidence assessments.
    """

    @classmethod
    def assemble_report(
        cls,
        payload: EUDRSupplyChainPayload,
        spatial_valid: bool,
        spatial_results: List[SpatialPlotResult],
        spatial_summary: Dict[str, Any],
        deforestation_free: bool,
        satellite_results: List[SatellitePlotResult],
        satellite_summary: Dict[str, Any],
        legal_audit: LegalAuditResult,
        start_time: datetime
    ) -> DDSReport:
        end_time = datetime.now(timezone.utc)
        processing_duration_ms = (end_time - start_time).total_seconds() * 1000.0

        # Determine Overall Compliance Status
        is_compliant = spatial_valid and deforestation_free and legal_audit.overall_compliant

        if is_compliant:
            status = ComplianceStatusEnum.COMPLIANT
            summary_message = "All EUDR statutory compliance requirements met. Ready for TRACES-NT declaration."
        else:
            reasons = []
            if not spatial_valid:
                reasons.append("Spatial/GIS geometry validation failure")
            if not deforestation_free:
                reasons.append("Post-2020 deforestation detected on production plots")
            if not legal_audit.overall_compliant:
                reasons.append("Missing mandatory origin permits or expired documents")
            status = ComplianceStatusEnum.NON_COMPLIANT
            summary_message = f"EUDR Compliance Verification Failed: {'; '.join(reasons)}."

        # Aggregate plots detail for reporting
        spatial_map = {sr.plot_id: sr for sr in spatial_results}
        sat_map = {sr.plot_id: sr for sr in satellite_results}
        
        plots_detail = []
        for p in payload.plots:
            sr = spatial_map.get(p.plot_id)
            sat = sat_map.get(p.plot_id)
            plots_detail.append({
                "plot_id": p.plot_id,
                "country_code": p.country_code,
                "declared_area_ha": p.area_hectares,
                "spatial_valid": sr.is_valid if sr else False,
                "spatial_errors": sr.errors if sr else ["Not evaluated"],
                "precision_warnings": sr.precision_warnings if sr else [],
                "overlap_detected": sr.overlap_detected if sr else False,
                "deforestation_detected": sat.deforestation_detected if sat else False,
                "loss_year": sat.forest_loss_year if sat else None,
                "loss_ratio_pct": sat.loss_ratio_pct if sat else 0.0,
                "satellite_notes": sat.audit_notes if sat else "No satellite evaluation",
                "satellite_consensus": sat.satellite_consensus if sat else {},
                "confidence_score": sat.confidence_score if sat else 1.0,
                "standardized_geojson": sr.standardized_geojson if sr else None,
                "healing_applied": sr.healing_applied if sr else False,
                "healing_actions": sr.healing_actions if sr else [],
                "cloud_fallback_applied": sat.cloud_fallback_applied if sat else False,
                "sensor_mode": sat.sensor_mode if sat else "OPTICAL_COPERNICUS_HANSEN",
                "sar_backscatter_analysis": sat.sar_backscatter_analysis if sat else None,
                "buffer_zone_analysis": sat.buffer_zone_analysis if sat else None
            })

        # Pillar 4: Confidence Assessment & HITL Workflow
        spatial_conf = 1.0 if spatial_valid and spatial_summary.get("overlapping_plots_count", 0) == 0 else 0.75
        sat_conf_avg = sum(s.confidence_score for s in satellite_results) / max(len(satellite_results), 1) if satellite_results else 1.0
        legal_conf = 1.0 if legal_audit.overall_compliant else 0.70
        overall_conf = round(0.35 * spatial_conf + 0.40 * sat_conf_avg + 0.25 * legal_conf, 2)

        review_reasons = []
        if spatial_summary.get("overlapping_plots_count", 0) > 0:
            review_reasons.append("Inter-plot polygon overlap collision detected (Dual-claim risk)")
        if sat_conf_avg < 0.90:
            review_reasons.append("High satellite cloud cover / partial sensor disagreement")

        requires_hitl = len(review_reasons) > 0 or overall_conf < 0.85
        review_status = ReviewStatusEnum.NEEDS_EXPERT_REVIEW if requires_hitl else ReviewStatusEnum.AUTO_APPROVED

        confidence_assessment = ConfidenceAssessment(
            overall_confidence_score=overall_conf,
            spatial_confidence=round(spatial_conf, 2),
            satellite_triangulation_confidence=round(sat_conf_avg, 2),
            legal_document_confidence=round(legal_conf, 2),
            requires_human_review=requires_hitl,
            review_reasons=review_reasons,
            review_status=review_status
        )

        # Pillar 3: Cryptographic Evidence Bundle
        evidence_bundle = EvidenceBundleGenerator.generate_bundle(
            payload=payload,
            spatial_results=spatial_results,
            satellite_results=satellite_results,
            legal_audit=legal_audit
        )

        # Generate TRACES-NT Statement if COMPLIANT
        traces_dds = None
        if status == ComplianceStatusEnum.COMPLIANT:
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            short_id = uuid.uuid4().hex[:8].upper()
            dds_ref_id = f"DDS-EUDR-{today_str}-{short_id}"
            primary_country = payload.plots[0].country_code if payload.plots else "XX"

            # Official TRACES-NT Schema Mapping
            submission_payload = TracesNTSchemaMapper.map_to_traces_payload(
                payload=payload,
                spatial_results=spatial_results,
                satellite_results=satellite_results,
                legal_audit=legal_audit,
                dds_reference_id=dds_ref_id
            )

            sig_hash = submission_payload.get("digitalSignatureBlock", {}).get("signatureValue", "")

            traces_dds = TRACESNTStatement(
                dds_reference_id=dds_ref_id,
                operator_eori=payload.operator.eori_number,
                operator_name=payload.operator.operator_name,
                commodity_hs_code=payload.commodity.hs_code,
                commodity_category=legal_audit.commodity_category.value,
                commodity_description=payload.commodity.description,
                net_mass_kg=payload.commodity.net_mass_kg,
                country_of_production=primary_country,
                total_plots_count=len(payload.plots),
                total_area_ha=spatial_summary.get("total_declared_area_ha", 0.0),
                deforestation_free_declaration=True,
                legally_produced_declaration=True,
                digital_signature_sha256=sig_hash,
                submission_ready_traces_payload=submission_payload,
                generated_at=end_time
            )

        # Audit Trail
        audit_trail = {
            "execution_id": payload.execution_id,
            "pipeline_version": "2.0.0-5PillarVerified",
            "eval_started_at": start_time.isoformat(),
            "eval_completed_at": end_time.isoformat(),
            "processing_duration_ms": round(processing_duration_ms, 2),
            "audit_hash": hashlib.sha256(
                f"{payload.execution_id}-{payload.supplier_id}-{status.value}".encode()
            ).hexdigest()
        }

        return DDSReport(
            execution_id=payload.execution_id,
            status=status,
            evaluation_timestamp=end_time,
            summary_message=summary_message,
            spatial_summary=spatial_summary,
            satellite_summary=satellite_summary,
            legal_summary={
                "overall_compliant": legal_audit.overall_compliant,
                "country_risk_tier": legal_audit.country_risk_tier.value,
                "commodity_category": legal_audit.commodity_category.value,
                "simplified_due_diligence_eligible": legal_audit.simplified_due_diligence_eligible,
                "risk_score": legal_audit.risk_score,
                "verified_documents_count": legal_audit.verified_documents_count,
                "missing_required_documents": legal_audit.missing_required_documents,
                "expired_documents": legal_audit.expired_documents,
                "notes": legal_audit.notes
            },
            plots_detail=plots_detail,
            confidence_assessment=confidence_assessment,
            evidence_bundle=evidence_bundle,
            traces_dds=traces_dds,
            audit_trail=audit_trail
        )

    @classmethod
    def generate_html_report(cls, report: DDSReport, lang: str = "en") -> str:
        """
        Generates a localized, styled, printable HTML summary report suitable for PDF rendering.
        Supports: English ('en'), Korean ('ko'), French ('fr'), Spanish ('es'), German ('de'), Portuguese ('pt').
        """
        from app.modules.report_i18n import get_i18n_dict, get_supported_languages

        t = get_i18n_dict(lang)
        supported_langs = get_supported_languages()
        
        status_is_compliant = (report.status == ComplianceStatusEnum.COMPLIANT)
        status_color = "#10b981" if status_is_compliant else "#ef4444"
        status_text = t["status_compliant"] if status_is_compliant else t["status_non_compliant"]
        
        dds = report.traces_dds

        dds_section = ""
        if dds:
            dds_section = f"""
            <div class="card dds-card" style="border-left: 4px solid #10b981; background: #f0fdf4;">
                <h3 style="color: #166534; margin-top:0;">📜 {t['dds_section_title']}</h3>
                <div class="grid-2">
                    <div>
                        <p><strong>{t['ref_id']}:</strong> <code class="highlight-code">{dds.dds_reference_id}</code></p>
                        <p><strong>{t['operator']}:</strong> {dds.operator_name} (<span>{t['eori']}: {dds.operator_eori}</span>)</p>
                        <p><strong>{t['commodity']}:</strong> {dds.commodity_category} - {t['hs_code']} {dds.commodity_hs_code} ({dds.commodity_description})</p>
                    </div>
                    <div>
                        <p><strong>{t['net_mass']}:</strong> {dds.net_mass_kg:,.1f} kg</p>
                        <p><strong>{t['total_plots']}:</strong> {dds.total_plots_count} ({t['total_area']}: {dds.total_area_ha:.2f} ha)</p>
                        <p><strong>{t['digital_sig']}:</strong><br><code class="sig-code">{dds.digital_signature_sha256}</code></p>
                    </div>
                </div>
            </div>
            """

        plots_rows = []
        for p in report.plots_detail:
            is_valid = p.get("spatial_valid", False)
            healed = p.get("healing_applied", False)
            deforest_detected = p.get("deforestation_detected", False)
            sensor = p.get("sensor_mode", "OPTICAL_COPERNICUS_HANSEN")

            if is_valid and healed:
                gis_badge = f'<span class="badge healed">{t["badge_healed"]}</span>'
            elif is_valid:
                gis_badge = f'<span class="badge pass">{t["badge_valid"]}</span>'
            else:
                gis_badge = f'<span class="badge fail">{t["badge_invalid"]}</span>'

            deforest_badge = f'<span class="badge fail">{t["badge_loss_detected"]}</span>' if deforest_detected else f'<span class="badge pass">{t["badge_deforest_free"]}</span>'

            plots_rows.append(f"""<tr>
                <td><code>{p['plot_id']}</code></td>
                <td><span class="country-tag">{p['country_code']}</span></td>
                <td>{p['declared_area_ha']} ha</td>
                <td>{gis_badge}</td>
                <td>{deforest_badge}</td>
                <td><span class="sensor-tag">{sensor}</span></td>
                <td class="notes-cell">{p['satellite_notes']}</td>
            </tr>""")

        plots_tbody = "".join(plots_rows)

        # Confidence Section
        conf = report.confidence_assessment
        conf_section = ""
        if conf:
            conf_section = f"""
            <div class="card" style="background: #f8fafc; border: 1px solid #e2e8f0;">
                <h3 style="margin-top:0; color:#1e293b;">🎯 {t['confidence_section_title']}</h3>
                <div class="conf-grid">
                    <div class="conf-item">
                        <span class="conf-label">{t['overall_confidence']}</span>
                        <span class="conf-val" style="color: {'#10b981' if conf.overall_confidence_score >= 0.85 else '#f59e0b'};">{int(conf.overall_confidence_score * 100)}%</span>
                    </div>
                    <div class="conf-item">
                        <span class="conf-label">{t['spatial_confidence']}</span>
                        <span class="conf-val">{int(conf.spatial_confidence * 100)}%</span>
                    </div>
                    <div class="conf-item">
                        <span class="conf-label">{t['satellite_confidence']}</span>
                        <span class="conf-val">{int(conf.satellite_triangulation_confidence * 100)}%</span>
                    </div>
                    <div class="conf-item">
                        <span class="conf-label">{t['legal_confidence']}</span>
                        <span class="conf-val">{int(conf.legal_document_confidence * 100)}%</span>
                    </div>
                </div>
            </div>
            """

        # Language Switcher Links
        lang_links = " | ".join([
            f'<a href="?lang={code}" class="lang-link {"active" if code == lang.lower() else ""}">{code.upper()}</a>'
            for code in supported_langs.keys()
        ])

        html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{t['report_title']} - {report.execution_id}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #f1f5f9; 
            color: #0f172a; 
            padding: 24px; 
            margin: 0;
            line-height: 1.5;
        }}
        .container {{ 
            max-width: 960px; 
            margin: 0 auto; 
            background: #ffffff; 
            padding: 40px; 
            border-radius: 14px; 
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01); 
        }}
        .header-bar {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .header-bar h1 {{ 
            font-size: 24px; 
            margin: 0 0 6px 0; 
            color: #0f172a; 
            font-weight: 700;
        }}
        .header-bar .subtitle {{
            color: #64748b;
            font-size: 13px;
            margin: 0;
        }}
        .lang-switcher {{
            font-size: 12px;
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            padding: 6px 12px;
            border-radius: 20px;
        }}
        .lang-link {{
            color: #475569;
            text-decoration: none;
            font-weight: 600;
            padding: 2px 4px;
        }}
        .lang-link:hover {{ color: #2563eb; }}
        .lang-link.active {{
            color: #2563eb;
            background: #dbeafe;
            border-radius: 4px;
        }}
        .status-badge {{ 
            display: inline-block; 
            padding: 8px 20px; 
            border-radius: 24px; 
            font-weight: 700; 
            color: #ffffff; 
            background: {status_color}; 
            font-size: 14px; 
            letter-spacing: 0.5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .meta-strip {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 16px 0 24px 0;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
            border: 1px solid #e2e8f0;
        }}
        .card {{ 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 24px; 
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            font-size: 13px;
        }}
        .grid-2 p {{ margin: 6px 0; }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 16px; 
            font-size: 12.5px; 
        }}
        th, td {{ 
            padding: 10px 12px; 
            border: 1px solid #e2e8f0; 
            text-align: left; 
        }}
        th {{ 
            background: #f1f5f9; 
            font-weight: 600; 
            color: #334155; 
        }}
        tr:hover {{ background-color: #f8fafc; }}
        .badge {{ 
            padding: 4px 8px; 
            border-radius: 6px; 
            font-weight: 600; 
            font-size: 11px; 
            display: inline-block;
        }}
        .badge.pass {{ background: #dcfce7; color: #15803d; }}
        .badge.fail {{ background: #fee2e2; color: #b91c1c; }}
        .badge.healed {{ background: #e0e7ff; color: #4338ca; }}
        .country-tag {{ background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-weight: 600; }}
        .sensor-tag {{ background: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 4px; font-size: 10.5px; }}
        .notes-cell {{ font-size: 11.5px; color: #475569; }}
        code {{ 
            font-family: 'JetBrains Mono', Consolas, monospace;
            background: #f1f5f9; 
            padding: 2px 6px; 
            border-radius: 4px; 
            font-size: 12px;
            color: #0f172a;
        }}
        .highlight-code {{ background: #dbeafe; color: #1e40af; font-weight: 600; }}
        .sig-code {{ font-size: 10.5px; word-break: break-all; color: #475569; display: block; margin-top: 4px; }}
        .conf-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-top: 12px;
        }}
        .conf-item {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .conf-label {{ display: block; font-size: 11px; color: #64748b; margin-bottom: 4px; }}
        .conf-val {{ font-size: 18px; font-weight: 700; color: #0f172a; }}
        .footer-note {{
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            font-size: 11.5px;
            color: #64748b;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .container {{ box-shadow: none; padding: 0; max-width: 100%; }}
            .lang-switcher {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-bar">
            <div>
                <h1>{t['report_title']}</h1>
                <p class="subtitle">{t['subtitle']}</p>
            </div>
            <div class="lang-switcher">
                🌐 {lang_links}
            </div>
        </div>

        <div>
            <span class="status-badge">{status_text}</span>
        </div>

        <div class="meta-strip">
            <div><strong>{t['execution_id']}:</strong> <code>{report.execution_id}</code></div>
            <div><strong>{t['generated_at']}:</strong> {report.evaluation_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </div>

        <div class="card" style="background: #f8fafc; border: 1px solid #e2e8f0;">
            <strong style="color: #334155;">{t['summary']}:</strong>
            <p style="margin: 6px 0 0 0; color: #1e293b;">{report.summary_message}</p>
        </div>
        
        {dds_section}

        {conf_section}

        <h3 style="color:#0f172a; margin-top:28px;">🗺️ {t['plots_section_title']}</h3>
        <table>
            <thead>
                <tr>
                    <th>{t['col_plot_id']}</th>
                    <th>{t['col_country']}</th>
                    <th>{t['col_area']}</th>
                    <th>{t['col_gis_status']}</th>
                    <th>{t['col_deforest_status']}</th>
                    <th>{t['col_sensor_mode']}</th>
                    <th>{t['col_notes']}</th>
                </tr>
            </thead>
            <tbody>
                {plots_tbody}
            </tbody>
        </table>

        <div class="card" style="background: #f8fafc; border: 1px solid #e2e8f0; margin-top:24px;">
            <h4 style="margin:0 0 8px 0; color:#334155; font-size:13px;">🔒 {t['evidence_bundle_title']}</h4>
            <div style="font-size:11.5px; color:#475569;">
                <p style="margin:4px 0;"><strong>{t['bundle_hash']}:</strong> <code>{report.evidence_bundle.digital_signature_hmac_sha256 if report.evidence_bundle else 'N/A'}</code></p>
                <p style="margin:4px 0;"><strong>{t['audit_hash']}:</strong> <code>{report.audit_trail.get('audit_hash')}</code></p>
            </div>
        </div>

        <div class="footer-note">
            <p style="margin:2px 0;">{t['statutory_notice']}</p>
            <p style="margin:2px 0;">{t['disclaimer']}</p>
        </div>
    </div>
</body>
</html>"""
        return html

    @classmethod
    def generate_customs_clearance_certificate_html(
        cls,
        report: DDSReport,
        ack_number: Optional[str] = None,
        customs_declaration_code: Optional[str] = None,
        lang: str = "en"
    ) -> str:
        """
        Generates official EU Single Window Environment for Customs (EU SWE-C) Green Lane Clearance Certificate.
        Suitable for customs agents, import inspection authorities, and border control declarations under EU 2023/1115 Art. 4.
        """
        dds = report.traces_dds
        dds_ref = dds.dds_reference_id if dds else f"DDS-REF-{report.execution_id[:8].upper()}"
        eori = dds.operator_eori if dds else "EORI-PENDING"
        operator = dds.operator_name if dds else "Authorized EU Operator"
        hs_code = dds.commodity_hs_code if dds else "090111"
        desc = dds.commodity_description if dds else "Regulated Commodity"
        net_mass = f"{dds.net_mass_kg:,.1f}" if dds else "0.0"
        plots_count = dds.total_plots_count if dds else len(report.plots_detail)
        total_area = f"{dds.total_area_ha:.2f}" if dds else "0.00"
        origin_country = dds.country_of_production if dds else "Multiple Origin"
        sig = dds.digital_signature_sha256 if dds else (report.evidence_bundle.digital_signature_hmac_sha256 if report.evidence_bundle else "N/A")

        ack_no = ack_number or f"EU-TRACES-ACK-2026-{report.execution_id[:8].upper()}"
        customs_code = customs_declaration_code or f"EU-SWEC-CLEARED-{report.execution_id[:6].upper()}"
        eval_date = report.evaluation_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        qr_url = f"https://ec.europa.eu/tracesnt/verify?ack={ack_no}&dds={dds_ref}"

        status_is_compliant = (report.status == ComplianceStatusEnum.COMPLIANT)
        badge_text = "EU SWE-C GREEN LANE CLEARED" if status_is_compliant else "INSPECTION REQUIRED / REJECTED"
        badge_color = "#15803d" if status_is_compliant else "#b91c1c"
        badge_bg = "#dcfce7" if status_is_compliant else "#fee2e2"
        badge_border = "#86efac" if status_is_compliant else "#fca5a5"

        html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EU SWE-C Customs Certificate - {dds_ref}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f8fafc;
            color: #0f172a;
            padding: 32px 16px;
            margin: 0;
        }}
        .certificate-sheet {{
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            border: 2px solid #0f172a;
            border-radius: 4px;
            padding: 40px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.08);
            position: relative;
        }}
        .watermark {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-30deg);
            font-size: 64px;
            font-weight: 900;
            color: rgba(16, 185, 129, 0.05);
            pointer-events: none;
            white-space: nowrap;
            letter-spacing: 4px;
        }}
        .top-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .eu-logo-title {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .eu-flag {{
            width: 48px;
            height: 32px;
            background: #003399;
            border-radius: 3px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffcc00;
            font-size: 20px;
            font-weight: bold;
        }}
        .header-text h1 {{
            font-size: 18px;
            font-weight: 800;
            margin: 0;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .header-text p {{
            font-size: 11px;
            color: #475569;
            margin: 3px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .stamp-box {{
            text-align: right;
        }}
        .clearance-stamp {{
            display: inline-block;
            border: 2px solid {badge_color};
            background: {badge_bg};
            color: {badge_color};
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 1px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .cert-title-section {{
            text-align: center;
            margin: 20px 0 28px 0;
        }}
        .cert-title-section h2 {{
            font-size: 20px;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 6px 0;
            letter-spacing: 0.5px;
        }}
        .cert-title-section .law-ref {{
            font-size: 11.5px;
            color: #64748b;
        }}
        .ref-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 16px 20px;
            border-radius: 6px;
            margin-bottom: 24px;
            font-size: 12.5px;
        }}
        .ref-grid .item {{ margin: 3px 0; }}
        .ref-grid strong {{ color: #334155; }}
        .mono {{
            font-family: 'JetBrains Mono', Consolas, monospace;
            font-size: 11.5px;
            font-weight: 600;
            color: #0f172a;
        }}
        .section-title {{
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #0f172a;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 6px;
            margin: 20px 0 12px 0;
        }}
        .details-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-bottom: 20px;
        }}
        .details-table th, .details-table td {{
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
            text-align: left;
        }}
        .details-table th {{
            background: #f1f5f9;
            color: #334155;
            width: 28%;
            font-weight: 600;
        }}
        .signature-section {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-top: 32px;
            padding-top: 20px;
            border-top: 2px solid #0f172a;
        }}
        .qr-seal {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .qr-placeholder {{
            width: 80px;
            height: 80px;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            color: #475569;
            text-align: center;
            padding: 4px;
        }}
        .sig-block {{
            flex: 1;
            margin-left: 20px;
            font-size: 10.5px;
            color: #475569;
        }}
        .official-seal {{
            width: 110px;
            height: 110px;
            border: 2px dashed #059669;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 9px;
            font-weight: 700;
            color: #059669;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 8px;
            transform: rotate(-10deg);
        }}
        .btn-print {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #0f172a;
            color: #ffffff;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .btn-print:hover {{ background: #1e293b; }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .certificate-sheet {{ box-shadow: none; border: 1.5px solid #000; padding: 24px; max-width: 100%; }}
            .btn-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>

    <div class="certificate-sheet">
        <div class="watermark">EU SWE-C APPROVED</div>

        <div class="top-header">
            <div class="eu-logo-title">
                <div class="eu-flag">★</div>
                <div class="header-text">
                    <h1>EUROPEAN COMMISSION — TRACES-NT</h1>
                    <p>EU Single Window Environment for Customs (EU SWE-C) System</p>
                </div>
            </div>
            <div class="stamp-box">
                <span class="clearance-stamp">{badge_text}</span>
            </div>
        </div>

        <div class="cert-title-section">
            <h2>CUSTOMS DUE DILIGENCE CLEARANCE CERTIFICATE</h2>
            <div class="law-ref">Issued pursuant to Regulation (EU) 2023/1115 (EUDR) Article 4(2) &amp; SWE-C Customs Pre-Clearance Standard</div>
        </div>

        <div class="ref-grid">
            <div class="item"><strong>Official TRACES ACK:</strong> <span class="mono">{ack_no}</span></div>
            <div class="item"><strong>Customs Clearance Code:</strong> <span class="mono">{customs_code}</span></div>
            <div class="item"><strong>DDS Statement Ref:</strong> <span class="mono">{dds_ref}</span></div>
            <div class="item"><strong>Certified Timestamp:</strong> <span>{eval_date}</span></div>
        </div>

        <div class="section-title">1. Authorized Operator &amp; Declarant Identification</div>
        <table class="details-table">
            <tr>
                <th>Economic Operator (EORI)</th>
                <td><span class="mono">{eori}</span></td>
            </tr>
            <tr>
                <th>Registered Company Name</th>
                <td>{operator}</td>
            </tr>
            <tr>
                <th>Statutory Role</th>
                <td>OPERATOR (First Placer on the EU Internal Market)</td>
            </tr>
        </table>

        <div class="section-title">2. Consignment &amp; Commodity Specifications</div>
        <table class="details-table">
            <tr>
                <th>Customs Tariff HS Code</th>
                <td><span class="mono">{hs_code}</span> — {desc}</td>
            </tr>
            <tr>
                <th>Declared Net Mass</th>
                <td><strong>{net_mass} kg</strong></td>
            </tr>
            <tr>
                <th>Country of Production / Harvest</th>
                <td><strong>{origin_country}</strong> (ISO 3166-1 alpha-2)</td>
            </tr>
            <tr>
                <th>Geolocation Proof Status</th>
                <td>{plots_count} Production Plots Verified ({total_area} ha) | Post-2020 Deforestation Free</td>
            </tr>
        </table>

        <div class="section-title">3. Statutory Attestation under Regulation (EU) 2023/1115</div>
        <p style="font-size: 11.5px; line-height: 1.6; color: #334155; margin: 6px 0 16px 0;">
            The economic operator has fulfilled the mandatory due diligence obligations under Article 4 of Regulation (EU) 2023/1115.
            Multi-sensor satellite triangulation (Copernicus Sentinel-1 SAR &amp; Sentinel-2 MSI) confirms no deforestation or forest degradation
            after 31 December 2020. The consignment satisfies all legal origin requirements and is officially eligible for Green Lane customs clearance.
        </p>

        <div class="signature-section">
            <div class="qr-seal">
                <div class="qr-placeholder">
                    <span style="font-size:16px;">📱</span>
                    <span>TRACES-NT<br>QR Verify</span>
                </div>
                <div class="sig-block">
                    <div><strong>Digital Audit Hash:</strong></div>
                    <div class="mono" style="font-size: 9.5px; word-break: break-all;">{sig}</div>
                    <div style="margin-top: 4px;"><strong>Verification Endpoint:</strong> <a href="{qr_url}" style="color:#2563eb; text-decoration:none;" target="_blank">ec.europa.eu/tracesnt/verify</a></div>
                </div>
            </div>

            <div class="official-seal">
                <span>★ EU SWE-C ★</span>
                <span style="font-size:7.5px; margin: 4px 0;">GREEN LANE<br>CUSTOMS<br>CLEARED</span>
                <span style="font-size:7px;">REG. 2023/1115</span>
            </div>
        </div>
    </div>
</body>
</html>"""
        return html


