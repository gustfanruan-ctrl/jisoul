@echo off
chcp 65001 >nul
echo ========================================
echo    机魂 MVP 启动脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

:: 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js 20+
    pause
    exit /b 1
)

:: 检查 .env 文件
if not exist "backend\.env" (
    echo [警告] backend\.env 文件不存在，正在创建模板...
    copy backend\.env.template backend\.env >nul 2>&1
    echo [提示] 请编辑 backend\.env 文件，填写你的 LLM API Key
    echo.
    pause
)

:: 启动后端
echo [1/3] 启动后端服务...
cd backend
if not exist "venv" (
    echo [安装依赖] 正在创建虚拟环境并安装依赖...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

start "机魂后端" cmd /k "venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
cd ..
echo [后端] 已在新窗口启动，端口 8000
echo.

:: 等待后端初始化（Embedding 模型加载需要约 15 秒）
echo [等待] 后端正在加载 Embedding 模型，请等待约 15 秒...
timeout /t 15 /nobreak >nul

:: 启动前端
echo [2/3] 启动前端服务...
cd frontend
if not exist "node_modules" (
    echo [安装依赖] 正在安装 npm 依赖...
    call npm install
)
start "机魂前端" cmd /k "npm run dev"
cd ..
echo [前端] 已在新窗口启动，端口 3000
echo.

:: 完成
echo ========================================
echo    启动完成！
echo ========================================
echo.
echo    访问地址: http://localhost:3000
echo    后端 API: http://localhost:8000/docs
echo.
echo    首次启动需要等待 Embedding 模型加载
echo    如果前端无法连接后端，请等待后端窗口显示
echo    "=== 启动完成 ===" 后刷新页面
echo.
echo    关闭此窗口不会停止服务
echo    要停止服务请关闭后端和前端窗口
echo ========================================
pause