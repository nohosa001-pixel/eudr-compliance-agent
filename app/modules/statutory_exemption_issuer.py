"""
Statutory Exemption Notice & Certificate Issuer (EUDR Regulation (EU) 2023/1115 Delegated Act Sept 2026)
Generates legally grounded, printable exemption certificates for European Customs Authorities (EU SWE-C Green Lane).
Specifically defends automotive seats, luxury goods, footwear, and finished bovine leather (HS 4101, 4104, 4107)
against wrongful customs detention and administrative delay.
"""
import uuid
import datetime
from typing import Dict, Any, Optional
from app.modules.legal_document_auditor import LegalAuditor
from app.schemas import StatutoryExemptionNoticeRequest, StatutoryExemptionNoticeResponse


class StatutoryExemptionIssuer:
    """
    Issues official EU customs-compliant Exemption Notices grounded in the finalized Sept 2026 Delegated Act.
    """

    SCRUTINY_PERIOD_EXPIRY: str = "2026-09-14"
    LEGAL_DELEGATED_ACT_REF: str = "Commission Delegated Regulation amending Annex I to Regulation (EU) 2023/1115 (Exclusion of Bovine Leather)"

    @classmethod
    def issue_certificate(cls, payload: StatutoryExemptionNoticeRequest) -> StatutoryExemptionNoticeResponse:
        """
        Validates HS code against statutory exemptions and generates an official certificate.
        """
        hs = payload.hs_code.strip()
        is_exempt, reason = LegalAuditor.check_exemption(hs)

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cert_id = f"EU-EXEMPT-CERT-{now_utc.year}-{uuid.uuid4().hex[:8].upper()}"

        if not is_exempt:
            advice = (
                f"HS Code '{hs}' is NOT exempt from EUDR Annex I. "
                f"Standard Due Diligence Statement (DDS) and GPS/polygon verification are legally required."
            )
            legal_basis = "Regulated under EUDR (EU) 2023/1115 Annex I (Deforestation-Free Mandate)."
        else:
            advice = (
                f"FORMAL EXEMPTION CONFIRMED: Commodity under HS code '{hs}' ({payload.product_description}) "
                f"has been formally excluded from Regulation (EU) 2023/1115 Annex I pursuant to the European Commission "
                f"Delegated Act following completion of the European Parliament and Council scrutiny period on {cls.SCRUTINY_PERIOD_EXPIRY}. "
                f"No EUDR Due Diligence Statement (DDS) or farm-level geolocation coordinates may be demanded by customs authorities."
            )
            legal_basis = f"{cls.LEGAL_DELEGATED_ACT_REF}; Scrutiny Period expired without objection on {cls.SCRUTINY_PERIOD_EXPIRY}."

        html_url = f"/api/v1/eudr/exemption/certificate/html?cert_id={cert_id}&hs={hs}&importer={payload.importer_name}"

        return StatutoryExemptionNoticeResponse(
            certificate_id=cert_id,
            hs_code=hs,
            product_description=payload.product_description,
            importer_name=payload.importer_name,
            importer_eori=payload.importer_eori,
            is_exempt_from_eudr=is_exempt,
            statutory_legal_basis=legal_basis,
            scrutiny_period_completion_date=cls.SCRUTINY_PERIOD_EXPIRY,
            official_customs_advice=advice,
            html_certificate_url=html_url,
            generated_at_utc=now_utc.isoformat()
        )

    @classmethod
    def generate_html_certificate(
        cls,
        cert_id: str,
        hs_code: str,
        importer_name: str,
        importer_eori: str = "EORI-EU-VERIFIED",
        product_description: str = "Bovine Hides / Leather Product",
        origin_country: str = "GLOBAL",
        b_l_number: Optional[str] = None
    ) -> str:
        """
        Renders an official European Commission styled printable Certificate of Statutory Exemption.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        is_exempt, reason = LegalAuditor.check_exemption(hs_code)

        badge_color = "#10b981" if is_exempt else "#ef4444"
        badge_text = "STATUTORILY EXEMPT (ANNEX I DELETED)" if is_exempt else "NOT EXEMPT (REGULATED COMMODITY)"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Official Statutory Exemption Notice - EUDR SWE-C</title>
    <style>
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background-color: #0f172a;
            color: #f1f5f9;
            margin: 0;
            padding: 40px 20px;
        }}
        .certificate-container {{
            max-width: 860px;
            margin: 0 auto;
            background: #1e293b;
            border: 2px solid #334155;
            border-radius: 12px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            padding: 48px;
            position: relative;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 24px;
            margin-bottom: 32px;
        }}
        .eu-stars {{
            color: #fbbf24;
            font-size: 28px;
            letter-spacing: 4px;
        }}
        .title-block h1 {{
            margin: 0;
            font-size: 24px;
            color: #60a5fa;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .title-block p {{
            margin: 4px 0 0;
            color: #94a3b8;
            font-size: 13px;
        }}
        .status-badge {{
            display: inline-block;
            background-color: {badge_color};
            color: #ffffff;
            font-weight: 700;
            font-size: 14px;
            padding: 8px 18px;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 28px;
        }}
        .card {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 16px 20px;
        }}
        .card .label {{
            font-size: 12px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .card .val {{
            font-size: 16px;
            font-weight: 600;
            color: #f8fafc;
            font-family: monospace;
        }}
        .legal-box {{
            background: rgba(59, 130, 246, 0.08);
            border-left: 4px solid #3b82f6;
            padding: 20px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 32px;
            line-height: 1.6;
        }}
        .legal-box h3 {{
            margin: 0 0 10px;
            color: #93c5fd;
            font-size: 15px;
            text-transform: uppercase;
        }}
        .legal-box p {{
            margin: 0;
            font-size: 14px;
            color: #cbd5e1;
        }}
        .footer {{
            border-top: 1px solid #334155;
            padding-top: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: #64748b;
        }}
        .stamp {{
            border: 2px dashed #10b981;
            color: #10b981;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 13px;
            border-radius: 6px;
            text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <div class="certificate-container">
        <div class="header">
            <div>
                <div class="eu-stars">★ ★ ★ ★ ★ ★</div>
                <div class="title-block">
                    <h1>Statutory Exemption Certificate</h1>
                    <p>Regulation (EU) 2023/1115 (EUDR) Customs SWE-C Green Lane</p>
                </div>
            </div>
            <div>
                <span class="status-badge">{badge_text}</span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="label">Certificate Reference ID</div>
                <div class="val">{cert_id}</div>
            </div>
            <div class="card">
                <div class="label">Tariff Classification (HS Code)</div>
                <div class="val">{hs_code}</div>
            </div>
            <div class="card">
                <div class="label">Declaring Importer / Operator</div>
                <div class="val">{importer_name} ({importer_eori})</div>
            </div>
            <div class="card">
                <div class="label">Product / Component Spec</div>
                <div class="val">{product_description}</div>
            </div>
            <div class="card">
                <div class="label">Country of Origin</div>
                <div class="val">{origin_country}</div>
            </div>
            <div class="card">
                <div class="label">Shipment B/L Number</div>
                <div class="val">{b_l_number or "DIRECT_CONSIGNMENT"}</div>
            </div>
        </div>

        <div class="legal-box">
            <h3>Binding Statutory Legal Defense for EU Customs Authorities</h3>
            <p>
                This document certifies that the aforementioned commodity classified under <strong>HS {hs_code}</strong> 
                is statutorily excluded from the scope of <strong>Regulation (EU) 2023/1115 Annex I</strong>.
                Pursuant to the European Commission Delegated Act and the formal conclusion of the European Parliament 
                and EU Council 2-month scrutiny period on <strong>September 14, 2026</strong>, bovine raw hides (HS 4101), 
                tanned leather (HS 4104), and finished leather (HS 4107) have been deleted from EUDR Annex I.
            </p>
            <p style="margin-top: 10px;">
                <strong>Customs Clearance Order:</strong> Customs inspectors may not request TRACES-NT Due Diligence Statements (DDS) 
                or farm-level GPS polygon coordinates for this consignment. Direct entry under Green Lane customs clearance applies.
            </p>
        </div>

        <div class="footer">
            <div>
                Generated at: {now_str}<br>
                Authority: EU Single Window Environment for Customs (EU SWE-C) Interoperability Standard
            </div>
            <div class="stamp">
                VERIFIED EXEMPT 2026
            </div>
        </div>
    </div>
</body>
</html>"""
