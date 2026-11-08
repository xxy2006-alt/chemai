@echo off
title ChemAI Server - Stopping...
echo Stopping ChemAI server (ports 8000/8001)...

rem 1) Kill uvicorn master processes. Python processes only -- other binaries
rem    whose command line merely mentions "uvicorn" (editors, shells, tools)
rem    must never be touched.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'uvicorn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul

rem 2) Kill --reload workers. Their command line is "python -c ...spawn_main..." and
rem    contains no "uvicorn", so step 1 misses them. The worker also holds a handle
rem    to its parent, so "is the parent alive" checks misfire after the master died.
rem    Within this script's contract (stopping the ChemAI server) every python
rem    spawn worker left over is ours, so sweep them unconditionally.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'spawn_main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul

rem 3) Final sweep by port, up to 3 rounds, LISTENING state only.
for /L %%r in (1,1,3) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr /C:":8000 " /C:":8001 "') do taskkill /PID %%a /F 2>nul
    timeout /t 1 >nul
)

echo.
echo Done. Server stopped.
if /i not "%~1"=="quiet" pause
