@echo off
REM ============================================
REM Stop production server
REM ============================================
echo Stopping production (port 8000)...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo Found PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo Killed.
    ) else (
        echo Failed, please kill manually.
    )
    goto :end
)

echo Port 8000 not in use, nothing to stop.

:end
pause
