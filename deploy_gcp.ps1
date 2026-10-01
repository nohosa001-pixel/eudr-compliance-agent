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
$polygonWallet = "0xA185B43fDD19619f99952AAed6eabf1029bF36a1"
$copernicusId = ""
$copernicusSecret = ""
$useLiveCopernicus = "true"
if (Test-Path ".env") {
    foreach ($line in (Get-Content ".env")) {
        if ($line -match "^TELEGRAM_BOT_TOKEN=(.+)$") { $tgToken = $matches[1].Trim() }
        if ($line -match "^TELEGRAM_CHAT_ID=(.+)$") { $tgChatId = $matches[1].Trim() }
        if ($line -match "^POLYGON_METAMASK_WALLET_ADDRESS=(.+)$") { $polygonWallet = $matches[1].Trim() }
        if ($line -match "^COPERNICUS_CLIENT_ID=(.+)$") { $copernicusId = $matches[1].Trim() }
        if ($line -match "^COPERNICUS_CLIENT_SECRET=(.+)$") { $copernicusSecret = $matches[1].Trim() }
        if ($line -match "^USE_LIVE_COPERNICUS_API=(.+)$") { $useLiveCopernicus = $matches[1].Trim() }
        if ($line -match "^SOLANA_RPC_URL=(.+)$") { $solanaRpc = $matches[1].Trim() }
        if ($line -match "^SOLANA_USDC_MINT=(.+)$") { $solanaMint = $matches[1].Trim() }
        if ($line -match "^SOLANA_TREASURY_WALLET=(.+)$") { $solanaTreasury = $matches[1].Trim() }
        if ($line -match "^SOLANA_ESCROW_PROGRAM_ID=(.+)$") { $solanaProgram = $matches[1].Trim() }
    }
}

if ([string]::IsNullOrEmpty($solanaRpc)) { $solanaRpc = "https://api.mainnet-beta.solana.com" }
if ([string]::IsNullOrEmpty($solanaMint)) { $solanaMint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" }
if ([string]::IsNullOrEmpty($solanaTreasury)) { $solanaTreasury = "411ksMz9RHYVtVMe6RUUErzZYtrU9zzvkgzswKbqx9qp" }
if ([string]::IsNullOrEmpty($solanaProgram)) { $solanaProgram = "EUDRScrw11111111111111111111111111111111111" }

$secGateMcp = "https://agent-security-gate-x402-7qxtp3324q-du.a.run.app/api/v1/mcp"
$mineralsMcp = "https://minerals-oracle-x402-7qxtp3324q-du.a.run.app/api/v1/mcp"
$cleanwebMcp = "https://x402-cleanweb-agent-7qxtp3324q-du.a.run.app/api/v1/mcp"
$agentEscrowContract = "0x28292D76E07E5539F15F3b97935dE8E0432E76DD"

$envVars = "PROJECT_NAME=EUDRAgent.com Enterprise Platform,SECRET_KEY_FOR_SIGNING=eudr-traces-nt-secret-key-2026,USE_DISTRIBUTED_QUEUE=false,TELEGRAM_BOT_TOKEN=$tgToken,TELEGRAM_CHAT_ID=$tgChatId,POLYGON_METAMASK_WALLET_ADDRESS=$polygonWallet,POLYGON_CHAIN_ID=137,POLYGON_RPC_URL=https://polygon-bor-rpc.publicnode.com,BASE_CHAIN_ID=8453,BASE_RPC_URL=https://mainnet.base.org,ARBITRUM_CHAIN_ID=42161,ARBITRUM_RPC_URL=https://arb1.arbitrum.io/rpc,POLYGON_AGENT_PAYMENT_VAULT=0x45ecBfAa2F4B0Bc6ccD3eB2dB9B1Ca49CF121861,BASE_AGENT_PAYMENT_VAULT=0x28292D76E07E5539F15F3b97935dE8E0432E76DD,ARBITRUM_AGENT_PAYMENT_VAULT=0x28292D76E07E5539F15F3b97935dE8E0432E76DD,COPERNICUS_CLIENT_ID=$copernicusId,COPERNICUS_CLIENT_SECRET=$copernicusSecret,USE_LIVE_COPERNICUS_API=$useLiveCopernicus,SECURITY_GATE_MCP_URL=$secGateMcp,MINERALS_ORACLE_MCP_URL=$mineralsMcp,CLEANWEB_MCP_URL=$cleanwebMcp,AGENT_ESCROW_CONTRACT_ADDRESS=$agentEscrowContract,SOLANA_RPC_URL=$solanaRpc,SOLANA_NETWORK=mainnet-beta,SOLANA_USDC_MINT=$solanaMint,SOLANA_TREASURY_WALLET=$solanaTreasury,SOLANA_ESCROW_PROGRAM_ID=$solanaProgram"



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
