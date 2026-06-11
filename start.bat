@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title = Indicator Dispatch - Quick Start

echo ════════════════════════════════════════
echo   Indicator Dispatch - 一键拉起服务
echo   前端3000 + 后端8000 + Cpolar穿透
echo   只映射前端到公网
echo ════════════════════════════════════════
echo.

set "PROJECT_DIR=D:\SHtongbao\indicator-dispatch"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIST=%PROJECT_DIR%\frontend\dist"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "NODE=C:\Users\USER370107\.workbuddy\binaries\node\versions\22.22.2\node.exe"
set "CPOLAR_EXE=C:\Program Files\cpolar\cpolar.exe"
set "CPOLAR_LOGS=C:\Users\USER370107\.cpolar\logs"

:: ── 1. 清理残留进程 ──
echo [1/6] 清理残留端口...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 :3000" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo       已清理

:: ── 2. 检查 venv ──
if not exist "%VENV_PYTHON%" (
    echo [2/6] 创建虚拟环境...
    C:\Users\USER370107\.workbuddy\binaries\python\versions\3.13.12\python.exe -m venv "%BACKEND_DIR%\.venv" >nul 2>&1
    echo [2/6] 安装依赖...
    "%BACKEND_DIR%\.venv\Scripts\pip.exe" install -r "%BACKEND_DIR%\requirements.txt" -q >nul 2>&1
) else (
    echo [2/6] 虚拟环境 OK
)

:: ── 3. 启动后端 8000 ──
echo [3/6] 启动后端 (8000)...
start "Backend-8000" cmd /c "cd /d %BACKEND_DIR% && %VENV_PYTHON% -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 5 /nobreak >nul

:: 验证
for /f "%%a in ('curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/v1/health 2^>nul') do set HTTP_CODE=%%a
if "%HTTP_CODE%"=="200" (
    echo        后端启动成功 (200)
) else (
    echo        后端可能仍在启动中，继续...
)

:: ── 4. 启动前端代理 3000 ──
echo [4/6] 启动前端代理 (3000)...
start "Frontend-3000" cmd /c "cd /d %PROJECT_DIR%\frontend && %NODE% -e "const http=require('http'),fs=require('fs'),path=require('path');const P=3000,B='http://localhost:8000',D=__dirname+'/dist';http.createServer((req,res)=>{if(req.url.startsWith('/api/')||req.url.startsWith('/docs')||req.url.startsWith('/openapi')){const u=new URL(req.url,B);const o={hostname:'localhost',port:8000,path:u.pathname+u.search,method:req.method,headers:{...req.headers,host:'localhost:8000'}};const p=http.request(o,r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res)});p.on('error',()=>{res.writeHead(502);res.end('Backend unavailable')});req.pipe(p)}else{let fp=path.join(D,req.url==='/'?'index.html':req.url);const ext=path.extname(fp);fs.readFile(fp,(err,data)=>{if(err||!ext){fp=path.join(D,'index.html');fs.readFile(fp,(e,d)=>{if(e){res.writeHead(404);res.end('Not found')}else{res.writeHead(200,{'Content-Type':'text/html'});res.end(d)}});return};const T={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.ico':'image/x-icon'};res.writeHead(200,{'Content-Type':T[ext]||'application/octet-stream'});res.end(data)})}}).listen(P,()=>console.log('Frontend proxy running on:'+P))""
timeout /t 3 /nobreak >nul
echo        前端代理已启动

:: ── 5. 重启 Cpolar ──
echo [5/6] 重启 Cpolar 穿透...
net stop cpolar >nul 2>&1
timeout /t 3 /nobreak >nul
net start cpolar >nul 2>&1
if !errorlevel! equ 0 (
    echo        Cpolar 已重启
) else (
    echo        Cpolar 可能已在运行，检查中...
)

:: ── 6. 获取公网地址 ──
echo.
echo [6/6] 获取公网地址...
timeout /t 8 /nobreak >nul

:: 从当天日志提取最新 website 隧道地址
set "TODAY=%date:~0,4%%date:~5,2%%date:~8,2%"
set "LOG_FILE=%CPOLAR_LOGS%\cpolar_service.log.%TODAY%"

if exist "%LOG_FILE%" (
    for /f "tokens=*" %%i in ('findstr /C:"Tunnel established at https://" "%LOG_FILE%"') do set LAST_LINE=%%i
    if defined LAST_LINE (
        for %%a in (%LAST_LINE%) do set CPOLAR_URL=%%a
        echo.
        echo ════════════════════════════════════════
        echo   公网访问地址:
        echo   %CPOLAR_URL%
        echo ════════════════════════════════════════
        echo.
        echo 本地地址: http://localhost:3000
        echo 后端API:  http://localhost:8000/docs
        echo.
        echo 按任意键打开公网地址...
        pause >nul
        start "" "%CPOLAR_URL%"
    ) else (
        echo 无法从日志获取URL，请稍后查看 Cpolar 控制台
    )
) else (
    echo 日志文件不存在，等待 Cpolar 初始化（约10秒）...
    timeout /t 10 /nobreak >nul
    if exist "%LOG_FILE%" (
        for /f "tokens=*" %%i in ('findstr /C:"Tunnel established at https://" "%LOG_FILE%"') do set LAST_LINE=%%i
        for %%a in (%LAST_LINE%) do set CPOLAR_URL=%%a
        echo.
        echo   公网地址: %CPOLAR_URL%
    ) else (
        echo Cpolar 日志尚未生成，请手动检查
    )
)

endlocal
