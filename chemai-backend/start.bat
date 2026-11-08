@echo off
title ChemAI Server
cd /d "%~dp0"

rem Usage:   start.bat          dev mode  (port 8001, auto-reload; override via CHEMAI_PORT)
rem          start.bat stable   stable mode (port 8000, no reload)

if /i "%~1"=="stable" goto :stable

:dev
if "%CHEMAI_PORT%"=="" set CHEMAI_PORT=8001
set "RELOAD=--reload"
goto :run

:stable
set "CHEMAI_PORT=8000"
set "RELOAD="

:run
echo ========================================
echo    ChemAI Server Starting...
echo    Frontend + Backend: http://localhost:%CHEMAI_PORT%/
echo ========================================
echo.
echo 1. Stopping old services (ports 8000/8001)...
call "%~dp0stop_server.bat" quiet
echo.
echo 2. Starting server (frontend + backend) on http://localhost:%CHEMAI_PORT% ...
start "ChemAI Server" python -m uvicorn app.main:app --host 127.0.0.1 --port %CHEMAI_PORT% %RELOAD%
echo    Waiting for server to be ready...
powershell -NoProfile -Command "for($i=0;$i -lt 90;$i++){try{$r=Invoke-WebRequest -Uri 'http://localhost:%CHEMAI_PORT%/docs' -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200){exit 0}}catch{};Start-Sleep -Seconds 1};exit 1"
if errorlevel 1 (
    echo.
    echo [ERROR] Server did not become ready in 90s. Check the server window for errors.
) else (
    echo    Server is ready. Opening browser...
    start http://localhost:%CHEMAI_PORT%/
)
echo.
pause
