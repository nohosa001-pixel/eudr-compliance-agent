# ========================================================
#   GitHub Push Script for eudr-compliance-agent
# ========================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Pushing to GitHub: nohosa001-pixel/eudr-compliance-agent" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$remoteUrl = "https://github.com/nohosa001-pixel/eudr-compliance-agent.git"

# Check if origin exists
$existingRemote = (git remote get-url origin 2>$null)
if ([string]::IsNullOrEmpty($existingRemote)) {
    Write-Host "Adding remote origin: $remoteUrl" -ForegroundColor Yellow
    git remote add origin $remoteUrl
} else {
    Write-Host "Setting remote origin: $remoteUrl" -ForegroundColor Yellow
    git remote set-url origin $remoteUrl
}

git branch -M main
git add .
git commit -m "feat(gcp): add Google Cloud Run deploy scripts and production config for eudragent.com" 2>$null

Write-Host "`nPushing main branch to GitHub..." -ForegroundColor Yellow
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "Repository URL: https://github.com/nohosa001-pixel/eudr-compliance-agent" -ForegroundColor Cyan
} else {
    Write-Host "`n[NOTE] If the remote repository does not exist yet on GitHub, please create it first at https://github.com/new (Name: eudr-compliance-agent) and re-run this script." -ForegroundColor Yellow
}
