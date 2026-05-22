@echo off
chcp 65001 >nul
title AI 翻译助手

echo 正在检查 Python 环境...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未检测到 Python，请先安装：https://www.python.org/downloads/
    pause
    exit /b
)

echo 正在检查依赖...
python -c "import flask" 2>nul
if %ERRORLEVEL% neq 0 (
    echo 首次使用，正在安装依赖...
    pip install -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %ERRORLEVEL% neq 0 (
        echo [错误] 依赖安装失败，请尝试手动运行：pip install -r requirements.txt
        pause
        exit /b
    )
    echo 依赖安装完成！
)

echo 正在停止旧服务...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /nh 2^>nul') do taskkill /pid %%i /f >nul 2>&1
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq pythonw.exe" /nh 2^>nul') do taskkill /pid %%i /f >nul 2>&1
timeout /t 1 /nobreak >nul

echo 正在启动服务...
start /min "" pythonw "%~dp0app.py"
if %ERRORLEVEL% neq 0 (
    start "" python "%~dp0app.py"
)
echo 服务启动中，浏览器将自动打开...
exit
