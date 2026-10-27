@echo off
chcp 65001 > nul
title EUDR Compliance Agent Autonomous Intelligence Daemon

echo =====================================================================
echo  Starting EUDR Compliance Agent 24/7 Autonomous Intelligence Daemon
echo =====================================================================
echo.

python "%~dp0scripts\run_daily_eudr_daemon.py" --time 09:30

pause
