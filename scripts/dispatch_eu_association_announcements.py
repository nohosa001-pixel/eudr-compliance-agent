"""
EUDR AGENT - European Association Announcement Dispatcher
Dispatches formal, non-solicitation technical briefings to verified European
commodity importer federations and customs bodies.
"""

import os
import sys
import json
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTACTS_PATH = PROJECT_ROOT / "data" / "eu_outreach_targets" / "verified_association_contacts.json"
OUTBOX_DIR = PROJECT_ROOT / "data" / "eu_outreach_targets" / "outbox"
LOG_PATH = PROJECT_ROOT / "data" / "eu_outreach_targets" / "dispatch_log.json"


def load_contacts():
    if not CONTACTS_PATH.exists():
        raise FileNotFoundError(f"Contacts file not found: {CONTACTS_PATH}")
    with open(CONTACTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_english_announcement(contact: dict) -> tuple[str, str, str]:
    subject = f"Technical Advisory: Autonomous EUDR Verification Architecture for {contact['organization']} Operators"
    
    commodities_str = ", ".join(contact.get("commodities", ["Target Commodities"]))
    
    text_content = f"""To the Secretariat and Technical Working Group,
{contact['organization']}
{contact.get('address', 'Brussels, Belgium')}

RE: Technical Infrastructure Notice — Autonomous Satellite Screening, Zero-Knowledge Geodata Protocols, and TRACES-NT XML Synthesis under Regulation (EU) 2023/1115 (EUDR)

Dear Colleagues,

As your member operators and importers prepare their due diligence systems for the enforcement timeline of Regulation (EU) 2023/1115 (30 December 2026), we wish to share an informational technical briefing regarding an autonomous machine-to-machine (M2M) architecture built specifically to solve the operational bottlenecks currently impacting European commodity supply chains.

Over the past year, discussions across European importer networks have highlighted three persistent structural challenges:
1. Upstream Supplier Geodata Friction: Smallholders and cooperatives frequently express apprehension regarding sharing exact cadastral boundaries directly with commercial buyers, risking supply chain disruption.
2. Downstream Multi-Component Linkage: Importers of composite goods (such as furniture, wood panels, and blended derivatives) face substantial friction compiling fragmented Due Diligence Statements (DDS) into unified declarations.
3. Excessive Enterprise Overhead: Legacy satellite auditing software imposes recurring fixed fees of €15,000 to €150,000 annually, disproportionately burdening small and mid-sized European operators.

In response to these technical realities, EUDRAgent (https://eudragent.com) has deployed a public-access autonomous compliance nexus operating 24/7 with the following statutory capabilities:

• Zero-Knowledge Supplier Privacy Portal (/supplier-portal):
  Overseas cooperatives upload plot boundaries through an isolated, encrypted interface. Satellite verification is executed directly against the 31 December 2020 cut-off (Copernicus Sentinel-2 and JRC GFC2020 v4) without exposing confidential farmer locations or commercial margins downstream.

• Multi-Component Downstream DDS Synthesis:
  Automated aggregation of disparate upstream DDS reference numbers into single-pass, validated TRACES-NT B2G XML dossiers ready for customs clearance at Rotterdam, Hamburg, and Antwerp.

• Autonomous 4-Hectare Polygon Self-Healing:
  Real-time topological sanitization of coordinates (self-intersection resolution, vertex simplification, and 6-decimal WGS84 standardization) to ensure 100% acceptance by the European Commission's Information System.

• Open Utility Model:
  Standardized pay-as-you-go micro-settlement ($0.05 per plot verification) eliminating multi-year SaaS lock-in for European traders.

A detailed Technical White Paper and Executive Briefing has been published for your reference:
https://eudragent.com/docs

Member operators seeking to inspect the autonomous verification pipeline, examine the 37 Model Context Protocol (MCP) tool schemas, or run sample coordinate audits may do so directly at:
https://eudragent.com/dashboard

This notice is provided strictly for informational purposes to support European trade federations and customs bodies as you advise your member operators on technological solutions. We welcome any independent inspection by your technical taskforces.

Respectfully submitted,

EUDRAgent Technical Operations & Architecture Desk
Web: https://eudragent.com
Portal: https://eudragent.com/dashboard
API Documentation: https://eudragent.com/docs
Direct Verification Inquiry: contact@eudragent.com
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 680px; margin: 0 auto; padding: 20px;">
  <div style="border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 20px;">
    <h3 style="color: #0f172a; margin: 0;">EUDR.AGENT // TECHNICAL INFRASTRUCTURE ADVISORY</h3>
    <p style="font-size: 0.85rem; color: #64748b; margin: 4px 0 0;">Regulation (EU) 2023/1115 (EUDR) Verification &amp; Traceability Nexus</p>
  </div>

  <p><strong>To the Secretariat and Technical Working Group,</strong><br>
  {contact['organization']}<br>
  <span style="font-size: 0.85rem; color: #64748b;">{contact.get('address', 'Brussels, Belgium')}</span></p>

  <p><strong>RE: Technical Notice — Autonomous Satellite Screening, Zero-Knowledge Geodata Protocols, and TRACES-NT XML Synthesis</strong></p>

  <p>Dear Colleagues,</p>

  <p>As your member operators and importers prepare their compliance frameworks for the <strong>30 December 2026</strong> enforcement deadline under Regulation (EU) 2023/1115, we wish to share an informational technical briefing regarding an autonomous machine-to-machine (M2M) architecture built to resolve key operational bottlenecks currently facing European commodity supply chains.</p>

  <p>Industry feedback across European trade associations has identified three central challenges:</p>
  <ul>
    <li><strong>Upstream Geodata Resistance:</strong> Smallholders and overseas cooperatives are reluctant to surrender precise GPS farm boundaries fearing commercial exposure.</li>
    <li><strong>Composite Product Fragmentation:</strong> Multi-component goods (e.g., wooden furniture under HS 9401/9403, blended cocoa/palm derivatives) face severe hurdles consolidating upstream DDS reference numbers.</li>
    <li><strong>Disproportionate Software Overhead:</strong> Legacy enterprise tools require €15,000 to €150,000 annual commitments.</li>
  </ul>

  <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin: 20px 0;">
    <h4 style="margin-top: 0; color: #0284c7;">Autonomous Statutory Architecture Capabilities:</h4>
    <ul style="margin-bottom: 0; padding-left: 20px;">
      <li><strong>Supplier Privacy Portal (<code>/supplier-portal</code>):</strong> Allows overseas producers to upload farm polygons securely; verifies land legality and 31 Dec 2020 forest cover without exposing proprietary smallholder records to commercial buyers.</li>
      <li><strong>TRACES-NT XML Direct Synthesis:</strong> Resolves topological errors (4ha polygon splits, self-intersections) and compiles 100% schema-compliant B2G XML for customs entry at Rotterdam, Hamburg, and Antwerp.</li>
      <li><strong>Open Utility Model:</strong> Pay-as-you-go micro-settlement at <strong>$0.05 / plot</strong>, ensuring accessibility for operators of all scales.</li>
    </ul>
  </div>

  <p>Your technical committees and member operators may review the live architecture, API schemas, and interactive demonstration at:</p>
  <p style="text-align: center; margin: 24px 0;">
    <a href="https://eudragent.com/dashboard" style="background: #0284c7; color: #ffffff; padding: 10px 22px; text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-block;">Inspect Operator Workbench &amp; Architecture</a>
  </p>

  <p style="font-size: 0.85rem; color: #64748b;">
    This notice is provided strictly for informational purposes to assist European industry associations in evaluating technical compliance capabilities. 
    Platform Documentation: <a href="https://eudragent.com/docs">eudragent.com/docs</a> • General Inquiries: <a href="mailto:contact@eudragent.com">contact@eudragent.com</a>
  </p>

  <p style="margin-top: 24px; font-size: 0.9rem;">
    Respectfully,<br>
    <strong>EUDRAgent Technical Operations Desk</strong><br>
    <a href="https://eudragent.com">https://eudragent.com</a>
  </p>
</body>
</html>
"""
    return subject, text_content, html_content


def build_german_announcement(contact: dict) -> tuple[str, str, str]:
    subject = f"Technische Mitteilung: Autonome EUDR-Prüfarchitektur für Mitgliedsunternehmen des {contact['organization']}"
    
    text_content = f"""An die Geschäftsführung und die Abteilung Außenhandel / Nachhaltigkeit,
{contact['organization']}
{contact.get('address', 'Berlin / Hamburg, Deutschland')}

BETREFF: Information zur technischen Infrastruktur — Autonome Satellitenprüfung, Zero-Knowledge Geodaten-Protokolle und TRACES-NT XML-Erstellung gemäß Verordnung (EU) 2023/1115 (EUDR)

Sehr geehrte Damen und Herren,

mit Blick auf die Umsetzungsfristen der EU-Entwaldungsverordnung (EUDR 2023/1115) bis zum 30. Dezember 2026 möchten wir Ihnen eine technische Information über eine neuartige, autonome Machine-to-Machine (M2M) Architektur zur Verfügung stellen.

Deutsche Importeure von Holzwaren, Möbeln, Kaffee und weiteren Rohstoffen stehen in der Praxis vor drei zentralen Hürden:
1. Vorbehalte bei Zulieferern: Ausländische Kleinbauern und Genossenschaften verweigern häufig die Weitergabe exakter GPS-Polygone aus Sorge um Datenschutz und kommerzielle Ausnutzung.
2. Mehrkomponenten-Rückverfolgbarkeit: Bei verarbeiteten Waren (z. B. Holzwerkstoffe, Möbel) ist die lückenlose Verknüpfung vorgelagerter Sorgfaltspflichtübertragungen (DDS) bisher extrem aufwendig.
3. Hohe Fixkosten: Etablierte Satelliten-Software verlangt oft 15.000 € bis über 100.000 € Jahreslizenz, was insbesondere mittelständische Händler überproportional belastet.

Vor diesem Hintergrund stellt EUDRAgent (https://eudragent.com) eine öffentlich zugängliche, hochautomatisierte Prüfplattform bereit:

• Verschlüsseltes Zulieferer-Portal (/supplier-portal):
  Erzeuger laden Geodaten über eine isolierte Schnittstelle hoch. Die Satellitenprüfung (Sentinel-2, JRC Global Forest Cover 2020) erfolgt direkt gegen den Stichtag 31.12.2020, ohne dass sensible Parzellendaten an Abnehmer offengelegt werden müssen.

• Fehlerfreie TRACES-NT XML-Erstellung:
  Automatische Reparatur geometrischer Fehler (Selbstüberschneidungen, Glättung bei >4 ha Parzellen) und Erzeugung schema-valider XML-Dateien für die behördliche Zollabfertigung (z.B. BLE / Hamburger Hafen / Rotterdam).

• Transparentes Verbrauchsmodell:
  0,05 $ pro überprüfter Parzelle (Pay-as-you-go) ohne Mindestvertragslaufzeiten.

Eine detaillierte Dokumentation und technische White Papers stehen Ihnen und Ihren Mitgliedern unter folgender Adresse zur Verfügung:
https://eudragent.com/docs

Die operative Arbeitsumgebung kann unverbindlich eingesehen werden:
https://eudragent.com/dashboard

Dieses Schreiben dient der reinen Fachinformation zur Unterstützung Ihrer Verbandsarbeit. Gerne stellen wir Ihren technischen Arbeitskreisen weiterführende Spezifikationen bereit.

Mit freundlichen Grüßen,

EUDRAgent Technical Operations & Architecture Desk
Web: https://eudragent.com
Portal: https://eudragent.com/dashboard
Dokumentation: https://eudragent.com/docs
Kontakt: contact@eudragent.com
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 680px; margin: 0 auto; padding: 20px;">
  <div style="border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 20px;">
    <h3 style="color: #0f172a; margin: 0;">EUDR.AGENT // TECHNISCHE FACHINFORMATION</h3>
    <p style="font-size: 0.85rem; color: #64748b; margin: 4px 0 0;">Verordnung (EU) 2023/1115 (EUDR) Prüf- und Rückverfolgbarkeitsarchitektur</p>
  </div>

  <p><strong>An die Geschäftsführung und die Abteilung Außenhandel / Nachhaltigkeit,</strong><br>
  {contact['organization']}<br>
  <span style="font-size: 0.85rem; color: #64748b;">{contact.get('address', 'Deutschland')}</span></p>

  <p><strong>BETREFF: Information zur technischen Infrastruktur — Autonome Satellitenprüfung, Zero-Knowledge Geodaten-Protokolle und TRACES-NT XML-Erstellung</strong></p>

  <p>Sehr geehrte Damen und Herren,</p>

  <p>mit Blick auf die Umsetzungsfristen der EU-Entwaldungsverordnung (EUDR) bis zum <strong>30. Dezember 2026</strong> möchten wir Ihnen eine technische Fachinformation über eine neuartige, autonome Machine-to-Machine (M2M) Architektur zur Verfügung stellen.</p>

  <p>In den Fachdiskussionen deutscher Importeure stehen derzeit drei Hürden im Vordergrund:</p>
  <ul>
    <li><strong>Geodaten-Zurückhaltung bei Zulieferern:</strong> Erzeuger im Ursprung teilen GPS-Daten aus Sorge um Datenschutz und Verhandlungspositionen oft nur zögerlich.</li>
    <li><strong>Mehrkomponenten-Zuordnung:</strong> Zusammengesetzte Holz- und Agrarprodukte erfordern eine komplexe Koppelung vorangehender Sorgfaltserklärungen (DDS).</li>
    <li><strong>Hohe Softwarekosten:</strong> Feste Jahreslizenzen von 15.000 € bis über 100.000 € belasten insbesondere den Mittelstand.</li>
  </ul>

  <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin: 20px 0;">
    <h4 style="margin-top: 0; color: #0284c7;">Funktionsmerkmale der EUDRAgent-Architektur:</h4>
    <ul style="margin-bottom: 0; padding-left: 20px;">
      <li><strong>Supplier Privacy Portal (<code>/supplier-portal</code>):</strong> Zulieferer übermitteln Geodaten verschlüsselt; Prüfung gegen den 31.12.2020 Stichtag erfolgt unabhängig, ohne dass sensible Parzellendaten an Abnehmer offengelegt werden müssen.</li>
      <li><strong>TRACES-NT XML-Direktexport:</strong> Automatische Fehlerbereinigung bei Polygonen über 4 ha und zollkonforme XML-Dateien für die behördliche Abfertigung.</li>
      <li><strong>Pay-as-you-go:</strong> <strong>0,05 $ pro Parzelle</strong> ohne Mindestvertragslaufzeiten.</li>
    </ul>
  </div>

  <p>Ihre Fachgremien und Mitgliedsunternehmen können das System und die Schnittstellen direkt einsehen:</p>
  <p style="text-align: center; margin: 24px 0;">
    <a href="https://eudragent.com/dashboard" style="background: #0284c7; color: #ffffff; padding: 10px 22px; text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-block;">Operator Workbench &amp; Prüfumgebung öffnen</a>
  </p>

  <p style="font-size: 0.85rem; color: #64748b;">
    Dieses Schreiben dient der reinen Fachinformation zur Unterstützung Ihrer Verbandsarbeit.<br>
    Dokumentation: <a href="https://eudragent.com/docs">eudragent.com/docs</a> • Kontakt: <a href="mailto:contact@eudragent.com">contact@eudragent.com</a>
  </p>

  <p style="margin-top: 24px; font-size: 0.9rem;">
    Mit freundlichen Grüßen,<br>
    <strong>EUDRAgent Technical Operations Desk</strong><br>
    <a href="https://eudragent.com">https://eudragent.com</a>
  </p>
</body>
</html>
"""
    return subject, text_content, html_content


def prepare_and_dispatch():
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    contacts_data = load_contacts()
    contacts = contacts_data.get("contacts", [])

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    sender_email = os.environ.get("SENDER_EMAIL", "announcements@eudragent.com")

    dispatch_records = []

    print(f"[*] Processing {len(contacts)} verified European association contacts...")

    server = None
    if smtp_host and smtp_user and smtp_pass:
        try:
            print(f"[*] Connecting to live SMTP host: {smtp_host}:{smtp_port}...")
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            print("[+] SMTP authenticated successfully.")
        except Exception as e:
            print(f"[!] SMTP connection failed: {e}. Falling back to Outbox file staging.")
            server = None
    else:
        print("[i] Live SMTP credentials not configured in environment. Staging full drafts in Outbox for manual review/dispatch.")

    for c in contacts:
        cid = c["id"]
        lang = c.get("language", "EN")
        if lang == "DE":
            subject, text, html = build_german_announcement(c)
        else:
            subject, text, html = build_english_announcement(c)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"EUDRAgent Technical Operations <{sender_email}>"
        msg["To"] = c["email"]
        if c.get("secondary_email"):
            msg["Cc"] = c["secondary_email"]
        msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg["Message-ID"] = f"<eudr-announcement-{cid}-{int(datetime.now(timezone.utc).timestamp())}@eudragent.com>"

        part1 = MIMEText(text, "plain", "utf-8")
        part2 = MIMEText(html, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        # Save to Outbox
        eml_file = OUTBOX_DIR / f"{cid}_{c['organization'].replace(' ', '_').replace('/', '_')}.eml"
        with open(eml_file, "w", encoding="utf-8") as f:
            f.write(msg.as_string())

        status = "STAGED_IN_OUTBOX"
        error_msg = None

        if server:
            recipients = [c["email"]]
            if c.get("secondary_email"):
                recipients.append(c["secondary_email"])
            try:
                server.sendmail(sender_email, recipients, msg.as_string())
                status = "DISPATCHED_LIVE"
                print(f"  [+] Dispatched live email to {c['organization']} ({c['email']})")
            except Exception as ex:
                status = "DISPATCH_FAILED"
                error_msg = str(ex)
                print(f"  [-] Failed to send to {c['email']}: {ex}")
        else:
            print(f"  [STAGED] Announcement in Outbox: {eml_file.name}")

        dispatch_records.append({
            "id": cid,
            "organization": c["organization"],
            "recipient": c["email"],
            "language": lang,
            "eml_path": str(eml_file),
            "status": status,
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        })

    if server:
        server.quit()

    # Save dispatch log
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "run_at": datetime.now(timezone.utc).isoformat() + "Z",
            "total_processed": len(dispatch_records),
            "records": dispatch_records
        }, f, indent=2)

    print(f"\n[OK] Dispatch run completed. Log saved to: {LOG_PATH}")


if __name__ == "__main__":
    prepare_and_dispatch()
