@echo off
echo ============================================
echo   Budget Manager - Starting Services
echo ============================================
echo.

:: Activate virtual environment if it exists
if exist "%~dp0.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%~dp0.venv\Scripts\activate.bat"
)

:: Install Python dependencies if needed
echo Checking Python dependencies...
python -c "import flask, flask_cors, graphene, sqlalchemy, openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Python dependencies...
    cd /d %~dp0
    python -m pip install flask flask-cors graphene sqlalchemy openpyxl
) else (
    echo Python dependencies OK.
)

:: Install Node dependencies if needed
echo Checking Node dependencies...
if not exist "%~dp0web-ui\node_modules" (
    echo Installing Node dependencies...
    cd /d %~dp0web-ui
    npm install
) else (
    echo Node dependencies OK.
)

echo.

:: Start the API server in a new window (with venv activated)
echo Starting API server on port 4000...
if exist "%~dp0.venv\Scripts\activate.bat" (
    start "Budget API Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && python api_server.py"
) else (
    start "Budget API Server" cmd /k "cd /d %~dp0 && python api_server.py"
)

:: Wait a moment for the API to initialize
timeout /t 3 /nobreak >nul

:: Start the web UI dev server in a new window
echo Starting Web UI on port 3000...
start "Budget Web UI" cmd /k "cd /d %~dp0web-ui && npm run dev"

:: Wait a moment then open the browser
timeout /t 3 /nobreak >nul
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo ============================================
echo   API Server:  http://localhost:4000
echo   Web UI:      http://localhost:3000
echo   GraphQL:     http://localhost:4000/graphql
echo ============================================
echo.
echo Close the two command windows to stop the servers.
pause
