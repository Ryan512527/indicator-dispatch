@echo off
REM ============================================
REM 生产环境启动 — 稳定运行，不热重载
REM 端口: 8000
REM 用法: 双击运行 或 命令行执行 prod.bat
REM ============================================

cd /d "%~dp0backend"

echo.
echo ========================================
echo   启动生产环境 (端口 8000)
echo ========================================
echo.

REM 检查端口是否已被占用
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [警告] 端口 8000 已被占用，请先停止现有进程
    echo.
    echo 运行: taskkill /F /PID [进程ID]
    echo 或先执行: prod_stop.bat
    pause
    exit /b 1
)

echo [1/2] 检查前端构建...
if not exist "..\frontend\dist\index.html" (
    echo [构建] 前端未构建，正在构建...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0backend"
)

echo [2/2] 启动 uvicorn (无 --reload 模式)...
echo.

REM 激活 venv (如果有)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM 启动 — 注意：没有 --reload，生产稳定运行
uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo 生产环境已停止。
pause
