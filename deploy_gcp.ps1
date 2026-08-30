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
Write-Host "Region: asia-northeast3 (Seoul)" -ForegroundColor Green

# 3. Enable Required APIs
Write-Host "`n[1/2] Enabling required GCP APIs (run, cloudbuild, artifactregistry)..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet

# 4. Deploy to Cloud Run
Write-Host "`n[2/2] Deploying container to Cloud Run (eudr-compliance-agent)..." -ForegroundColor Yellow
gcloud run deploy eudr-compliance-agent `
    --source . `
    --region asia-northeast3 `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --set-env-vars="PROJECT_NAME=EUDRAgent.com Enterprise Platform,SECRET_KEY_FOR_SIGNING=eudr-traces-nt-secret-key-2026,USE_DISTRIBUTED_QUEUE=false" `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] Cloud Run deployment successful!" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
    $serviceUrl = (gcloud run services describe eudr-compliance-agent --region asia-northeast3 --format="value(status.url)").Trim()
    Write-Host "Landing Page: $serviceUrl" -ForegroundColor Cyan
    Write-Host "Console Dashboard: $serviceUrl/dashboard" -ForegroundColor Cyan
    Write-Host "Supplier Portal: $serviceUrl/supplier-portal" -ForegroundColor Cyan
    Write-Host "Swagger Docs: $serviceUrl/docs" -ForegroundColor Cyan
    Write-Host "Health Check: $serviceUrl/api/v1/eudr/health" -ForegroundColor Cyan
} else {
    Write-Host "`n[ERROR] Deployment failed. Check the logs above." -ForegroundColor Red
}
