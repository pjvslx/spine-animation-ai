@echo off
setlocal

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%reskin-app\app"
set "BACKEND_DIR=%APP_DIR%\backend"
set "FRONTEND_DIR=%APP_DIR%\frontend"

echo ========================================
echo Genie Spine Reskin - Local Dev Startup
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

echo [1/4] Checking backend virtual environment...
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
  echo Creating backend virtual environment...
  cd /d "%BACKEND_DIR%"
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create Python virtual environment.
    pause
    exit /b 1
  )
)

echo [2/4] Installing backend dependencies...
cd /d "%BACKEND_DIR%"
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install backend dependencies.
  pause
  exit /b 1
)

echo [3/4] Installing frontend dependencies...
cd /d "%FRONTEND_DIR%"
if not exist "%FRONTEND_DIR%\node_modules" (
  npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
) else (
  echo Frontend dependencies already installed.
)

echo [4/4] Starting services...

start "Genie Reskin Backend" cmd /k "cd /d "%BACKEND_DIR%" && ".venv\Scripts\python.exe" -m uvicorn app.backend.server:app --host 127.0.0.1 --port 8765 --app-dir ..\.."
start "Genie Reskin Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo.
echo Backend:  http://127.0.0.1:8765
echo API docs: http://127.0.0.1:8765/docs
echo Frontend: http://127.0.0.1:5173
echo.
echo If you want to use AI generation, configure these in Settings or reskin-app\app\.env:
echo   OPENAI_API_KEY=...
echo   FAL_KEY=...
echo.
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5173

endlocal
