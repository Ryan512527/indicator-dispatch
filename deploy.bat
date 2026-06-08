@echo off
REM ============================================
REM 部署脚本 — 将已验证的代码更新到生产环境
REM 流程: 构建前端 → 停止生产 → 启动生产
REM 中断时间 < 5 秒
REM ============================================

cd /d "%~dp0"

echo.
echo ========================================
echo   部署到生产环境
echo ========================================
echo.

REM 1. 构建前端
echo [1/3] 构建前端...
cd /d "%~dp0frontend"
call npm run build
if %errorlevel% neq 0 (
    echo [错误] 前端构建失败！
    pause
    exit /b 1
)
echo       前端构建完成
cd /d "%~dp0"

REM 2. 停止生产进程
echo.
echo [2/3] 停止生产进程 (8000端口)...

REM 找到端口 8000 的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    set PID=%%a
    goto :found
)
echo       [跳过] 端口 8000 未被占用
goto :start_prod

:found
echo       进程 PID: %PID%
taskkill /F /PID %PID% >nul 2>&1
if %errorlevel% equ 0 (
    echo       已停止
) else (
    echo       [警告] 无法停止进程，请手动处理
    pause
    exit /b 1
)

REM 等一秒确保端口释放
timeout /t 1 /nobreak >nul

:start_prod
REM 3. 启动生产
echo.
echo [3/3] 启动生产环境...
cd /d "%~dp0backend"

REM 激活 venv (如果有)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

start "指标调度系统-生产" /B uvicorn app.main:app --host 0.0.0.0 --port 8000

REM 等待启动
timeout /t 2 /nobreak >nul

REM 验证
curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/v1/health >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   部署成功！
    echo   后端: http://localhost:8000
    echo   API:  http://localhost:8000/api/v1/health
    echo ========================================
) else (
    echo.
    echo [警告] 服务可能未正常启动，请手动检查
)

echo.
pause
