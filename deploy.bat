@echo off
REM ============================================
REM Deploy: build frontend + restart production
REM ============================================

cd /d "%~dp0"

echo.
echo ========================================
echo   Deploy to Production
echo ========================================
echo.

REM 1. Build frontend
echo [1/3] Building frontend...
cd /d "%~dp0frontend"
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)
echo       Done
cd /d "%~dp0"

REM 2. Stop production on port 8000
echo.
echo [2/3] Stopping production (port 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    set PID=%%a
    goto :found
)
echo       Nothing on port 8000
goto :start_prod

:found
echo       PID: %PID%
taskkill /F /PID %PID% >nul 2>&1
if %errorlevel% equ 0 (
    echo       Stopped
) else (
    echo       [WARN] Cannot stop PID %PID%
)
timeout /t 1 /nobreak >nul

:start_prod
REM 3. Start production
echo.
echo [3/3] Starting production on port 8000...
cd /d "%~dp0backend"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

start "indicator-dispatch-prod" /B uvicorn app.main:app --host 0.0.0.0 --port 8000

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Deploy complete!
echo   http://localhost:8000
echo ========================================
echo.
pause
