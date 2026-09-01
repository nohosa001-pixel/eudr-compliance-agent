# ========================================================
#   eudr-compliance-agent Google Cloud Run PowerShell Script
#   Domain Target: eudragent.com
# ========================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  EUDRAgent.com Cloud Run Production Deployment" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Check gcloud CLI
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] gcloud CLI is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Get current GCP Project
$currentProject = (gcloud config get-value project 2>$null).Trim()
if ([string]::IsNullOrEmpty($currentProject)) {
    $currentProject = "my-nohosa-87175"
    gcloud config set project $currentProject
}

Write-Host "Project ID: $currentProject" -ForegroundColor Green
Write-Host "Regions: us-central1 (Custom Domain: eudragent.com) & asia-northeast3 (Seoul)" -ForegroundColor Green

# 3. Enable Required APIs
Write-Host "`n[1/3] Enabling required GCP APIs (run, cloudbuild, artifactregistry)..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet

# 4. Read Environment Variables from .env
$tgToken = ""
$tgChatId = ""
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^TELEGRAM_BOT_TOKEN=(.+)$") { $tgToken = $matches[1].Trim() }
        if ($_ -match "^TELEGRAM_CHAT_ID=(.+)$") { $tgChatId = $matches[1].Trim() }
    }
}

$envVars = "PROJECT_NAME=EUDRAgent.com Enterprise Platform,SECRET_KEY_FOR_SIGNING=eudr-traces-nt-secret-key-2026,USE_DISTRIBUTED_QUEUE=false,TELEGRAM_BOT_TOKEN=$tgToken,TELEGRAM_CHAT_ID=$tgChatId"

# 4. Deploy to Cloud Run (us-central1 - Domain Mapping Target)
Write-Host "`n[2/3] Deploying to Cloud Run [us-central1] (Custom Domain eudragent.com target)..." -ForegroundColor Yellow
gcloud run deploy eudr-compliance-agent `
    --source . `
    --region us-central1 `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --set-env-vars="$envVars" `
    --quiet

# 5. Deploy to Cloud Run (asia-northeast3 - Seoul Secondary)
Write-Host "`n[3/3] Deploying to Cloud Run [asia-northeast3] (Seoul)..." -ForegroundColor Yellow
gcloud run deploy eudr-compliance-agent `
    --source . `
    --region asia-northeast3 `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --set-env-vars="$envVars" `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] Multi-region Cloud Run deployment successful!" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "Custom Domain: https://eudragent.com" -ForegroundColor Cyan
    Write-Host "Console Dashboard: https://eudragent.com/dashboard" -ForegroundColor Cyan
    Write-Host "Supplier Portal: https://eudragent.com/supplier-portal" -ForegroundColor Cyan
    Write-Host "Swagger Docs: https://eudragent.com/docs" -ForegroundColor Cyan
} else {
    Write-Host "`n[ERROR] Deployment failed. Check the logs above." -ForegroundColor Red
}
