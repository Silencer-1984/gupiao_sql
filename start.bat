@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title A-Share Dashboard

REM ============================================================
REM  One-click start:  deps -> frontend build -> serve -> browser
REM  Usage:  start.bat            (production, port 8000+)
REM          start.bat 9000       (custom port)
REM          start.bat dev        (auto-reload, backend dev)
REM ============================================================

set "MODE=prod"
set "PORT="
if /i "%~1"=="dev" (
  set "MODE=dev"
) else (
  if not "%~1"=="" set "PORT=%~1"
)

where uv >nul 2>nul
if errorlevel 1 (
  echo [x] uv not found. Install: powershell -c "irm https://astral.sh/uv/install.ps1 ^| iex"
  goto :end
)

if not exist ".venv\Scripts\python.exe" (
  echo [*] First run: creating venv and installing deps...
  uv sync --python 3.13
  if errorlevel 1 (
    echo [x] uv sync failed
    goto :end
  )
) else (
  echo [*] Syncing dependencies...
  uv sync --quiet
)

if not exist "web\dist\index.html" (
  echo [*] Building frontend...
  pushd web
  if exist "node_modules" (
    call pnpm build
  ) else (
    call pnpm install
    call pnpm build
  )
  popd
)

REM ---- pick a free port ----
if "%PORT%"=="" (
  set "PORT=8000"
  :findport
  netstat -ano | findstr /C:":!PORT! " | findstr /C:"LISTENING" >nul
  if not errorlevel 1 (
    set /a PORT+=1
    if !PORT! gtr 8020 (
      echo [x] no free port in 8000-8020
      goto :end
    )
    goto :findport
  )
)

echo.
echo ============================================================
echo   URL      http://127.0.0.1:%PORT%/
echo   API      http://127.0.0.1:%PORT%/api/overview
echo   MODE     %MODE%
echo   Stop     Ctrl+C
echo ============================================================
echo.

start "" "http://127.0.0.1:%PORT%/"

if /i "%MODE%"=="dev" (
  uv run dash --port %PORT% --reload
) else (
  uv run dash --port %PORT%
)

:end
echo.
pause
