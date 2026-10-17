param(
    [switch]$Force
)

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
Get-ChildItem -Path . -Filter "*.egg-info" -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# 2. Build distributions with uv (or fallback to python -m build)
Write-Host "[1/2] Building source distribution and wheel with uv build..." -ForegroundColor Yellow
$built = $false
try {
    uv.exe build --link-mode copy
    if ($LASTEXITCODE -eq 0) { $built = $true }
} catch {
    Write-Host "[WARN] uv build not available, falling back to python -m build" -ForegroundColor Yellow
}

if (-not $built) {
    if (Test-Path ".\.venv312\Scripts\python.exe") {
        & ".\.venv312\Scripts\python.exe" -m build
    } elseif (Test-Path ".\.venv\Scripts\python.exe") {
        & ".\.venv\Scripts\python.exe" -m build
    } else {
        python -m build
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Build failed!" -ForegroundColor Red
        exit 1
    }
}

# 3. Check artifacts
Write-Host "[CHECK] Artifacts in dist:" -ForegroundColor Green
Get-ChildItem dist

# 4. Upload to PyPI
Write-Host "[2/2] Ready to upload to PyPI." -ForegroundColor Green
$confirm = if ($Force) { "y" } else { Read-Host "Proceed with uploading to PyPI? (y/n)" }
if ($confirm -eq "y" -or $confirm -eq "Y") {
    $token = $env:UV_PUBLISH_TOKEN
    if (-not $token) { $token = $env:TWINE_PASSWORD }

    # Check local .env first
    if (-not $token -and (Test-Path ".env")) {
        $lines = Get-Content ".env"
        foreach ($line in $lines) {
            if ($line.StartsWith("UV_PUBLISH_TOKEN=") -or $line.StartsWith("TWINE_PASSWORD=")) {
                $token = $line.Split("=", 2)[1].Trim('"').Trim("'")
                break
            }
        }
    }
    # Check sibling security-gate-x402/.env for token
    if (-not $token) {
        $siblingEnv = "..\security-gate-x402\.env"
        if (Test-Path $siblingEnv) {
            $lines = Get-Content $siblingEnv
            foreach ($line in $lines) {
                if ($line.StartsWith("UV_PUBLISH_TOKEN=") -or $line.StartsWith("TWINE_PASSWORD=")) {
                    $token = $line.Split("=", 2)[1].Trim('"').Trim("'")
                    break
                }
            }
        }
    }
    # Check sibling x402-micro-agent/.env
    if (-not $token) {
        $siblingEnv2 = "..\x402-micro-agent\.env"
        if (Test-Path $siblingEnv2) {
            $lines = Get-Content $siblingEnv2
            foreach ($line in $lines) {
                if ($line.StartsWith("UV_PUBLISH_TOKEN=") -or $line.StartsWith("TWINE_PASSWORD=")) {
                    $token = $line.Split("=", 2)[1].Trim('"').Trim("'")
                    break
                }
            }
        }
    }

    if (-not $token) {
        $secToken = Read-Host "Enter PyPI API Token (pypi-...)" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secToken)
        $token = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }

    $env:UV_PUBLISH_TOKEN = $token
    $env:TWINE_PASSWORD = $token
    $env:TWINE_USERNAME = "__token__"
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"

    # Try uv publish first
    Write-Host "[UPLOAD] Uploading to PyPI via uv publish..." -ForegroundColor Cyan
    uv.exe publish --token $token dist/*

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Published v1.9.0 successfully to PyPI!" -ForegroundColor Green
    } else {
        Write-Host "[WARN] uv publish exited with code $LASTEXITCODE. Trying twine fallback..." -ForegroundColor Yellow
        if (Test-Path ".\.venv312\Scripts\twine.exe") {
            & ".\.venv312\Scripts\twine.exe" upload --disable-progress-bar dist/*
        } elseif (Test-Path ".\.venv\Scripts\twine.exe") {
            & ".\.venv\Scripts\twine.exe" upload --disable-progress-bar dist/*
        } else {
            twine upload --disable-progress-bar dist/*
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Published successfully to PyPI via twine!" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Publish failed. Check your token and version." -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "[INFO] Upload skipped." -ForegroundColor Yellow
}
