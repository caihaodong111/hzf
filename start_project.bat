@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

set "CONDA_ENV_NAME=hzf"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

call :check_required_path "%BACKEND_DIR%\manage.py" "后端入口"
if errorlevel 1 exit /b 1

call :check_required_path "%FRONTEND_DIR%\package.json" "前端入口"
if errorlevel 1 exit /b 1

call :ensure_command powershell
if errorlevel 1 exit /b 1

echo [INFO] 检查端口占用情况...
call :check_port_available %BACKEND_PORT% "Django 后端"
if errorlevel 1 exit /b 1

call :check_port_available %FRONTEND_PORT% "Vite 前端"
if errorlevel 1 exit /b 1

call :check_process_absent "celery -A aquaculture worker -l info" "Celery Worker"
if errorlevel 1 exit /b 1

call :check_process_absent "celery -A aquaculture beat -l info" "Celery Beat"
if errorlevel 1 exit /b 1

call :resolve_conda
if errorlevel 1 exit /b 1

call "%CONDA_BAT%" activate "%CONDA_ENV_NAME%" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到或无法激活 conda 环境 %CONDA_ENV_NAME%。
    exit /b 1
)

if /I not "%CONDA_DEFAULT_ENV%"=="%CONDA_ENV_NAME%" (
    echo [ERROR] conda 环境 %CONDA_ENV_NAME% 激活失败。
    exit /b 1
)

echo [INFO] 已激活 conda 环境 %CONDA_ENV_NAME%。

call :ensure_command python
if errorlevel 1 exit /b 1

call :ensure_command celery
if errorlevel 1 exit /b 1

call :ensure_command npm
if errorlevel 1 exit /b 1

echo [INFO] 启动 Django 后端...
start "Django Backend" cmd /k "call ""%CONDA_BAT%"" activate ""%CONDA_ENV_NAME%"" && cd /d ""%BACKEND_DIR%"" && python manage.py runserver 0.0.0.0:%BACKEND_PORT%"
call :wait_for_port %BACKEND_PORT% "Django 后端"
if errorlevel 1 exit /b 1

echo [INFO] 启动 Vite 前端...
start "Vite Frontend" cmd /k "call ""%CONDA_BAT%"" activate ""%CONDA_ENV_NAME%"" && cd /d ""%FRONTEND_DIR%"" && npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT%"
call :wait_for_port %FRONTEND_PORT% "Vite 前端"
if errorlevel 1 exit /b 1

echo [INFO] 启动 Celery Worker...
start "Celery Worker" cmd /k "call ""%CONDA_BAT%"" activate ""%CONDA_ENV_NAME%"" && cd /d ""%BACKEND_DIR%"" && celery -A aquaculture worker -l info"

echo [INFO] 启动 Celery Beat...
start "Celery Beat" cmd /k "call ""%CONDA_BAT%"" activate ""%CONDA_ENV_NAME%"" && cd /d ""%BACKEND_DIR%"" && celery -A aquaculture beat -l info"

echo.
echo [INFO] 全部服务已发起启动。
echo 后端地址: http://127.0.0.1:%BACKEND_PORT%
echo 前端地址: http://127.0.0.1:%FRONTEND_PORT%
echo 注意: Celery 依赖 backend\.env 中配置的 Redis 服务，请先确认 Redis 已启动。
exit /b 0

:check_required_path
if not exist "%~1" (
    echo [ERROR] 缺少 %~2: %~1
    exit /b 1
)
exit /b 0

:ensure_command
where %~1 >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到命令: %~1
    exit /b 1
)
exit /b 0

:check_port_available
set "CHECK_PORT=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conn = Get-NetTCPConnection -State Listen -LocalPort $env:CHECK_PORT -ErrorAction SilentlyContinue | Select-Object -First 1; if ($conn) { $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue; if ($proc) { Write-Host ('PID=' + $proc.Id + ' NAME=' + $proc.ProcessName) } else { Write-Host ('PID=' + $conn.OwningProcess) }; exit 1 }"
set "CHECK_PORT="
if errorlevel 1 (
    echo [ERROR] %~2 需要的端口 %~1 已被占用，请先释放后再启动。
    exit /b 1
)
exit /b 0

:check_process_absent
set "PROCESS_PATTERN=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$pattern = $env:PROCESS_PATTERN; $proc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like ('*' + $pattern + '*') } | Select-Object -First 1; if ($proc) { Write-Host ('PID=' + $proc.ProcessId + ' CMD=' + $proc.CommandLine); exit 1 }"
set "PROCESS_PATTERN="
if errorlevel 1 (
    echo [ERROR] %~2 已经在运行，请先停止旧进程。
    exit /b 1
)
exit /b 0

:resolve_conda
set "CONDA_BAT="
for /f "usebackq delims=" %%I in (`where conda.bat 2^>nul`) do (
    set "CONDA_BAT=%%I"
    goto :resolve_conda_done
)

if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "C:\ProgramData\anaconda3\condabin\conda.bat" set "CONDA_BAT=C:\ProgramData\anaconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "C:\ProgramData\miniconda3\condabin\conda.bat" set "CONDA_BAT=C:\ProgramData\miniconda3\condabin\conda.bat"

:resolve_conda_done
if not defined CONDA_BAT (
    echo [ERROR] 未找到 conda.bat，请先确认 Anaconda 或 Miniconda 已安装。
    exit /b 1
)
exit /b 0

:wait_for_port
set "WAIT_PORT=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(15); do { if (Get-NetTCPConnection -State Listen -LocalPort $env:WAIT_PORT -ErrorAction SilentlyContinue | Select-Object -First 1) { exit 0 }; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); exit 1"
set "WAIT_PORT="
if errorlevel 1 (
    echo [ERROR] %~2 启动失败，请查看对应窗口输出。
    exit /b 1
)
exit /b 0
