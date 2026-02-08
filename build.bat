@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "CONDA_ENV=lifeprism_dev"

:: 解析参数
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=all"

if "%TARGET%"=="backend" goto :backend
if "%TARGET%"=="frontend" goto :frontend
if "%TARGET%"=="all" goto :all

echo [错误] 未知参数: %TARGET%
echo 用法: build.bat [backend^|frontend]
echo   无参数  - 完整打包（后端 + 前端）
echo   backend  - 仅打包后端
echo   frontend - 仅打包前端
exit /b 1

:all
call :backend
if errorlevel 1 exit /b 1
call :frontend
if errorlevel 1 exit /b 1
echo.
echo [完成] 全部打包完成！
echo   后端: %PROJECT_ROOT%pyinstaller-dist\lifeprism-backend\
echo   安装包: %FRONTEND_DIR%\release\
goto :eof

:backend
echo ============================================
echo  打包后端 (PyInstaller)
echo ============================================
echo.

:: 清理旧产物
if exist "%PROJECT_ROOT%pyinstaller-dist" (
    echo [清理] 删除旧的 pyinstaller-dist...
    rmdir /s /q "%PROJECT_ROOT%pyinstaller-dist"
)
if exist "%PROJECT_ROOT%build" (
    echo [清理] 删除旧的 build 缓存...
    rmdir /s /q "%PROJECT_ROOT%build"
)

echo [执行] conda activate %CONDA_ENV% ^&^& pyinstaller lifeprism.spec --distpath pyinstaller-dist --noconfirm
call conda activate %CONDA_ENV% && pyinstaller lifeprism.spec --distpath pyinstaller-dist --noconfirm
if errorlevel 1 (
    echo [错误] 后端打包失败！
    exit /b 1
)

echo.
echo [完成] 后端打包成功: %PROJECT_ROOT%pyinstaller-dist\lifeprism-backend\
goto :eof

:frontend
echo ============================================
echo  打包前端 (Vite + Electron Builder)
echo ============================================
echo.

:: 检查后端产物是否存在
if not exist "%PROJECT_ROOT%pyinstaller-dist\lifeprism-backend\lifeprism-backend.exe" (
    echo [警告] 未找到后端产物，请先运行 build.bat backend
    exit /b 1
)

:: 清理旧的前端构建
if exist "%FRONTEND_DIR%\dist" (
    echo [清理] 删除旧的 dist...
    rmdir /s /q "%FRONTEND_DIR%\dist"
)

echo [执行] cd frontend ^&^& npm run electron:build
cd /d "%FRONTEND_DIR%" && call npm run electron:build
if errorlevel 1 (
    echo [错误] 前端打包失败！
    exit /b 1
)

echo.
echo [完成] 前端打包成功: %FRONTEND_DIR%\release\
goto :eof
