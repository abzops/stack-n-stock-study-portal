@echo off
title Stack n Stock - Pick & Pack Study Portal
cd /d "%~dp0"

echo ======================================================================
echo    STACK N STOCK - PICK & PACK STUDY PORTAL LAUNCHER
echo ======================================================================
echo.
echo Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.8+ or add python to your Windows PATH.
    echo.
    pause
    exit /b 1
)

echo Starting local portal server and opening browser...
echo.
python launch_portal.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Portal server exited with an error code: %ERRORLEVEL%
    pause
)
