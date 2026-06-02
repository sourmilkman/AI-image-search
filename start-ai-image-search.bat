@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_PORT=5317"
set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"
set "BACKEND_URL=http://127.0.0.1:8765/api/health"
set "BACKEND_HOST=0.0.0.0"

echo Starting Local AI Image Search...
echo.

call :find_python
if errorlevel 1 (
  echo Could not find Python 3.11, 3.12, or 3.13.
  echo.
  echo Please install Python 3.12 from https://www.python.org/downloads/
  echo Make sure the Python launcher is enabled during install.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo Could not find npm.
  echo.
  echo Please install Node.js LTS from https://nodejs.org/
  pause
  exit /b 1
)

if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
  echo Creating backend virtual environment...
  %PYTHON_CMD% -m venv "%BACKEND_DIR%\.venv"
)

echo Installing backend dependencies...
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
  echo.
  echo Backend dependency install failed.
  pause
  exit /b 1
)

echo Installing local AI model dependencies...
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements-ai.txt"
if errorlevel 1 (
  echo.
  echo Local CLIP dependency install failed.
  echo The app can still run, but search quality will be poor until these install.
  echo You can retry later with:
  echo "%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements-ai.txt"
  echo.
)

if not exist "%ROOT%node_modules" (
  echo Installing frontend dependencies...
  pushd "%ROOT%"
  call npm install
  popd
  if errorlevel 1 (
    echo.
    echo Frontend dependency install failed.
    pause
    exit /b 1
  )
)

echo Launching backend...
start "AI Image Search Backend" /D "%BACKEND_DIR%" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host %BACKEND_HOST% --port 8765"

echo Launching frontend...
start "AI Image Search PWA" /D "%ROOT%" cmd /k "npm run dev -- --port %FRONTEND_PORT% --strictPort"

echo Waiting for the app to start...
timeout /t 5 /nobreak >nul

start "" "%FRONTEND_URL%"

echo.
echo Local AI Image Search is starting.
echo Frontend: %FRONTEND_URL%
echo Backend:  %BACKEND_URL%
echo.
echo For another device on your Wi-Fi, set the app Backend URL to:
echo http://YOUR-PC-LAN-IP:8765
echo.
echo GitHub Pages uses HTTPS, so phones may require an HTTPS tunnel or proxy
echo before the Pages-hosted PWA can talk to this local backend.
echo.
echo You can close this window. Keep the two service windows open while using the app.
pause
exit /b 0

:find_python
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3.12"
  exit /b 0
)

py -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3.13"
  exit /b 0
)

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3.11"
  exit /b 0
)

if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  set "PYTHON_CMD="%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe""
  exit /b 0
)

exit /b 1
