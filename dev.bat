@echo off
REM ============================================
REM 开发环境启动 — 热重载，不影响生产
REM 后端端口: 8001 (开发)，前端端口: 3001 (可选)
REM 用法: 双击运行 或 命令行执行 dev.bat
REM ============================================

cd /d "%~dp0backend"

echo.
echo ========================================
echo   启动开发环境
echo   后端: http://localhost:8001
echo   API文档: http://localhost:8001/api/v1/health
echo ========================================
echo.

REM 检查前端构建
if not exist "..\frontend\dist\index.html" (
    echo [构建] 前端未构建，正在构建...
    cd /d "%~dp0frontend"
    call npm run build
    cd /d "%~dp0backend"
    echo.
)

REM 激活 venv (如果有)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo [启动] 开发后端 (端口 8001, --reload 热重载)
echo [提示] 修改代码后自动重载，不影响生产 8000
echo.

REM 启动 — 注意：有 --reload，文件改动自动重载
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

echo.
echo 开发环境已停止。
pause
