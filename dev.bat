@echo off
REM ============================================
REM Dev server: port 8001 with hot-reload
REM ============================================

cd /d "%~dp0backend"

echo.
echo ========================================
echo   Dev Server: http://localhost:8001
echo ========================================
echo.

REM Check frontend build
if not exist "..\frontend\dist\index.html" (
    echo Building frontend...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0backend"
    echo.
)

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo Starting dev server on port 8001 (--reload)...
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

echo.
echo Dev server stopped.
pause
