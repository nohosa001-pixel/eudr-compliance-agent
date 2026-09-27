Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  PyPI Release Packager - EUDRAgent      " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Clean previous build artifacts
if (Test-Path "dist") {
    Remove-Item -Path "dist" -Recurse -Force
}
if (Test-Path "build") {
    Remove-Item -Path "build" -Recurse -Force
}
Get-ChildItem -Path . -Filter "*.egg-info" -Directory | Remove-Item -Recurse -Force

# 2. Build distributions
Write-Host "[1/2] Building source distribution and wheel with build..." -ForegroundColor Yellow
.venv\Scripts\python.exe -m build

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Build failed!" -ForegroundColor Red
    exit 1
}

# 3. Check artifacts
.venv\Scripts\twine.exe check dist/*
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Twine check failed!" -ForegroundColor Red
    exit 1
}

# 4. Upload to PyPI
Write-Host "[2/2] Ready to upload to PyPI." -ForegroundColor Green
$confirm = Read-Host "Proceed with uploading to PyPI? (y/n)"
if ($confirm -eq "y" -or $confirm -eq "Y") {
    if (-not $env:TWINE_PASSWORD) {
        # Check sibling security-gate-x402/.env for token
        $siblingEnv = "..\security-gate-x402\.env"
        if (Test-Path $siblingEnv) {
            $lines = Get-Content $siblingEnv
            foreach ($line in $lines) {
                if ($line.StartsWith("TWINE_PASSWORD=")) {
                    $env:TWINE_PASSWORD = $line.Substring(15).Trim('"').Trim("'")
                    break
                }
            }
        }
    }

    if (-not $env:TWINE_PASSWORD) {
        $token = Read-Host "Enter PyPI API Token (pypi-...)" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
        $tokenPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        $env:TWINE_PASSWORD = $tokenPlain
    }

    $env:TWINE_USERNAME = "__token__"
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"

    .venv\Scripts\twine.exe upload --disable-progress-bar dist/*
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Published successfully to PyPI!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Publish failed. Check your token and version." -ForegroundColor Red
    }
} else {
    Write-Host "[INFO] Upload skipped." -ForegroundColor Yellow
}
