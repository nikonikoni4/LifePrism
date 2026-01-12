@echo off
echo ==========================================
echo       LifeWatch-AI 启动脚本
echo ==========================================

:: 启动后端 (Python)
echo [1/2] 正在启动后端服务器 (lifeprism\server\main.py)...
start "LifePrism 后端" cmd /k "python lifeprism\server\main.py"

:: 启动前端 (NPM)
echo [2/2] 正在启动前端开发服务器 (frontend)...
start "LifePrism 前端" cmd /k "cd /d frontend && npm run dev"

echo.
echo 所有服务启动指令已发送。
echo 请检查新打开的两个命令行窗口以查看运行日志。
pause
