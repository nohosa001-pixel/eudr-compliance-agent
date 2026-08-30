@echo off
chcp 65001 >nul
echo ========================================================
echo   EUDRAgent.com Google Cloud Run Deployment
echo ========================================================
powershell -ExecutionPolicy Bypass -File "%~dp0deploy_gcp.ps1"
pause
