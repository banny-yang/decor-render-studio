@echo off
title RealVisXL 一键启动
cd /d "%~dp0"

echo ============================================
echo   RealVisXL 装修效果图系统 一键启动
echo ============================================
echo.

rem ---- 前置检查:ComfyUI 是否就位 ----
if not exist "ComfyUI_windows_portable\python_embeded\python.exe" (
    echo [错误] 未找到 ComfyUI_windows_portable,请先运行 scripts\setup_comfyui.ps1
    pause
    exit /b 1
)

rem ---- 首次运行:创建 server\.env ----
if not exist "server\.env" (
    copy /y "server\.env.example" "server\.env" >nul
    echo [初始化] 已从 .env.example 创建 server\.env
)

echo [1/3] 启动 ComfyUI 推理服务(端口 8188,--lowvram)...
start "ComfyUI" /D "%~dp0ComfyUI_windows_portable" cmd /k .\python_embeded\python.exe -s ComfyUI\main.py --lowvram --port 8188

echo [2/3] 启动 FastAPI 后端(端口 8000)...
start "RealVisXL-Server" /D "%~dp0server" cmd /k python -m uvicorn app.main:app --port 8000 --host 0.0.0.0

echo [3/3] 等待后端就绪...
set /a tries=0
:waitloop
if %tries% geq 20 goto ready
curl -s -o NUL -m 2 http://127.0.0.1:8000 >nul 2>&1
if %errorlevel%==0 goto ready
set /a tries+=1
ping -n 3 127.0.0.1 >nul
goto waitloop
:ready

start "" http://127.0.0.1:8000
echo.
echo 启动完成!浏览器已打开 http://127.0.0.1:8000
echo 登录账号:admin / admin123
echo 停止服务:关闭 ComfyUI 和 RealVisXL-Server 两个窗口
echo.
pause
