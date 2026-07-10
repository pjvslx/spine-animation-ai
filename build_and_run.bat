@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%reskin-app\app"
set "BACKEND_DIR=%APP_DIR%\backend"
set "FRONTEND_DIR=%APP_DIR%\frontend"
set "BACKEND_PORT=8765"
set "FRONTEND_PORT=5173"

echo ========================================
echo Spine Animation AI - Build and Run
echo ========================================
echo.

if not exist "%BACKEND_DIR%" (
  echo [ERROR] Backend folder not found: %BACKEND_DIR%
  pause
  exit /b 1
)

if not exist "%FRONTEND_DIR%" (
  echo [ERROR] Frontend folder not found: %FRONTEND_DIR%
  pause
  exit /b 1
)

call :kill_port %BACKEND_PORT%
call :kill_port %FRONTEND_PORT%

echo.
echo [1/6] Checking backend virtual environment...
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
  echo Creating backend virtual environment...
  cd /d "%BACKEND_DIR%"
  python -m venv .venv
  if errorlevel 1 goto :backend_venv_failed
)

echo.
echo [2/6] Installing backend dependencies...
cd /d "%BACKEND_DIR%"
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :backend_deps_failed

echo.
echo [3/6] Checking backend Python files...
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m compileall ai spine reskin server.py secrets_store.py settings.py projects_multi.py projects.py logs.py imaging.py __init__.py
if errorlevel 1 goto :backend_build_failed

echo.
echo [4/6] Installing frontend dependencies if needed...
cd /d "%FRONTEND_DIR%"
if not exist "%FRONTEND_DIR%\node_modules" (
  call npm install
  if errorlevel 1 goto :frontend_deps_failed
) else (
  echo Frontend dependencies already installed.
)

echo.
echo [5/6] Building frontend latest code...
cd /d "%FRONTEND_DIR%"
call npm run build
if errorlevel 1 goto :frontend_build_failed

echo.
echo [6/6] Starting backend and frontend...
set "BACKEND_CMD=%TEMP%\spine_ai_backend_%RANDOM%.cmd"
set "FRONTEND_CMD=%TEMP%\spine_ai_frontend_%RANDOM%.cmd"
(
  echo @echo off
  echo cd /d "%BACKEND_DIR%"
  echo "%BACKEND_DIR%\.venv\Scripts\python.exe" -m uvicorn app.backend.server:app --host 127.0.0.1 --port %BACKEND_PORT% --app-dir ..\..
  echo pause
) > "%BACKEND_CMD%"
(
  echo @echo off
  echo cd /d "%FRONTEND_DIR%"
  echo call npm run preview -- --host 127.0.0.1 --port %FRONTEND_PORT% --strictPort
  echo pause
) > "%FRONTEND_CMD%"
start "Spine AI Backend :%BACKEND_PORT%" cmd /k "%BACKEND_CMD%"
start "Spine AI Frontend :%FRONTEND_PORT%" cmd /k "%FRONTEND_CMD%"

echo.
echo ========================================
echo Started successfully
echo ========================================
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo Backend:  http://127.0.0.1:%BACKEND_PORT%
echo API docs: http://127.0.0.1:%BACKEND_PORT%/docs
echo.
echo Opening browser...
timeout /t 3 /nobreak >nul
start http://127.0.0.1:%FRONTEND_PORT%

echo.
echo Backend and frontend were started in separate windows.
echo You can close this window, but keep the Backend and Frontend windows open.
pause

endlocal
exit /b 0

:kill_port
set "PORT=%~1"
echo.
echo Stopping old process on port %PORT% if any...
set "FOUND_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  set "FOUND_PID=%%P"
  echo Killing PID %%P on port %PORT%...
  taskkill /F /PID %%P >nul 2>nul
)
if not defined FOUND_PID echo No process is listening on port %PORT%.
exit /b 0

:backend_venv_failed
echo [ERROR] Failed to create backend virtual environment.
pause
exit /b 1

:backend_deps_failed
echo [ERROR] Failed to install backend dependencies.
pause
exit /b 1

:backend_build_failed
echo [ERROR] Backend compile check failed.
pause
exit /b 1

:frontend_deps_failed
echo [ERROR] Failed to install frontend dependencies.
pause
exit /b 1

:frontend_build_failed
echo [ERROR] Frontend build failed.
pause
exit /b 1
