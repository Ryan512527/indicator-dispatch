@echo off
REM ============================================
REM Production start - stable, no hot-reload
REM Port: 8000
REM Usage: double-click or run prod.bat
REM ============================================

cd /d "%~dp0backend"

echo.
echo ========================================
echo   Starting PRODUCTION (port 8000)
echo   NO --reload (stable)
echo ========================================
echo.

REM Check if port 8000 is already in use
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARN] Port 8000 is already in use!
    echo.
    echo Run: prod_stop.bat first
    echo Or: taskkill /F /PID [PID]
    pause
    exit /b 1
)

echo [1/2] Checking frontend build...
if not exist "..\frontend\dist\index.html" (
    echo [BUILD] Frontend not built, building now...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0backend"
)

echo [2/2] Starting uvicorn (NO --reload)...
echo.

REM Activate venv if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Start - NOTE: no --reload for production
uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo Production server stopped.
pause
