# ========================================================
#   EUDRAgent.com Live Traffic & User Movement Monitor
# ========================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  🔍 EUDRAgent.com Live Traffic & Visitor Monitor" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$projectId = "my-nohosa-87175"

# 1. Fetch Cloud Run Request Logs from GCP
Write-Host "`n[1/3] Fetching latest live visitor requests from Cloud Run..." -ForegroundColor Yellow
$logQuery = 'resource.type="cloud_run_revision" AND resource.labels.service_name="eudr-compliance-agent" AND httpRequest.requestMethod:*'
$rawLogs = gcloud logging read $logQuery --limit=30 --format="json" --project=$projectId 2>$null | ConvertFrom-Json

if ($rawLogs -and $rawLogs.Count -gt 0) {
    Write-Host "`n--- 🌐 Recent Inbound Web Visitors ---" -ForegroundColor Green
    $userRequests = @()
    $botScanners = @()

    foreach ($entry in $rawLogs) {
        $req = $entry.httpRequest
        $time = ([datetime]$entry.timestamp).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss")
        $url = $req.requestUrl
        $ip = $req.remoteIp
        $status = $req.status
        $agent = $req.userAgent

        $item = [PSCustomObject]@{
            Time       = $time
            Method     = $req.requestMethod
            URL        = $url
            Status     = $status
            RemoteIP   = $ip
            UserAgent  = if ($agent.Length -gt 40) { $agent.Substring(0, 37) + "..." } else { $agent }
        }

        if ($url -match "wp-admin|\.json|\.env|install\.php") {
            $botScanners += $item
        } else {
            $userRequests += $item
        }
    }

    if ($userRequests.Count -gt 0) {
        $userRequests | Format-Table -AutoSize Time, Method, Status, RemoteIP, URL, UserAgent
    } else {
        Write-Host "No human visitor requests recorded in recent 30 entries." -ForegroundColor Gray
    }

    if ($botScanners.Count -gt 0) {
        Write-Host "`n--- 🛡️ Blocked Automated Web Scanners ($($botScanners.Count) attempts) ---" -ForegroundColor DarkGray
        $botScanners | Format-Table -AutoSize Time, Method, Status, RemoteIP, URL
    }
} else {
    Write-Host "No recent logs found." -ForegroundColor Yellow
}

# 2. Check Database Inbound Inquiries / Leads
Write-Host "`n[2/3] Checking received enterprise leads & demo inquiries..." -ForegroundColor Yellow
$pythonExe = ".venv\Scripts\python.exe"
if (Test-Path $pythonExe) {
    & $pythonExe -c "
from app.db.session import SessionLocal
from app.db.models import LeadInquiryRecord, AuditExecutionRecord
db = SessionLocal()
leads = db.query(LeadInquiryRecord).order_by(LeadInquiryRecord.id.desc()).limit(5).all()
audits_count = db.query(AuditExecutionRecord).count()
print(f'Total Completed Audits in DB: {audits_count}')
print(f'Total Enterprise Leads Received: {len(leads)}')
for l in leads:
    print(f'  • [{l.status}] {l.company_name} | {l.contact_name} ({l.contact_email}) | Commodity: {l.commodity_type} | Plots: {l.estimated_monthly_plots}')
db.close()
"
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "  ✅ Traffic Check Complete. Run anytime with .\check_traffic.ps1" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
