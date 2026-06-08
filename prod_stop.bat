@echo off
REM ============================================
REM 停止生产环境
REM ============================================
echo 正在停止生产环境 (端口 8000)...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo 找到进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if %errorlevel% equ 0 (
        echo 已停止
    ) else (
        echo 停止失败，请手动处理
    )
    goto :end
)

echo 端口 8000 未被占用，无需停止

:end
pause
