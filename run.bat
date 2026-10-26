@echo off
echo ============================================
echo   Power BI Modeling Assistant
echo ============================================
echo.

REM Check if venv exists
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Please run setup.bat first!
    pause
    exit /b 1
)

echo Building frontend...
cd "%~dp0frontend"
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
cd "%~dp0"

echo.
echo Starting assistant...
echo Your browser will open at http://localhost:8000
echo Press Ctrl+C in this window to stop.
echo.

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 goto server_already_running

call "%~dp0venv\Scripts\activate.bat"
start http://localhost:8000
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
pause
exit /b 0

:server_already_running
echo An assistant server is already running on port 8000. Reusing it.
start http://localhost:8000
exit /b 0
