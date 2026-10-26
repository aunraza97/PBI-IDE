@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo   Power BI Modeling Assistant - SETUP
echo ============================================
echo.

REM ═══════════════════════════════════════════════════════════════
REM  Fully isolated environment:
REM  - Forces Python 3.12
REM  - Downloads portable Python if not found or broken
REM  - Verifies venv/virtualenv works BEFORE proceeding
REM  - Clean venv with exact pinned package versions
REM ═══════════════════════════════════════════════════════════════

set "PYTHON_VERSION=3.12.8"
set "PYTHON_EMBED_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "LOCAL_PYTHON_DIR=%~dp0python312"
set "PYTHON_CMD="
set "USE_VIRTUALENV=0"

REM ── Step 1: Find or Install Python 3.12 (with venv verification) ──
echo [1/4] Checking for Python 3.12...

REM First: check if we already have a working local Python
if exist "%LOCAL_PYTHON_DIR%\python.exe" (
    echo       Found bundled Python in python312\ folder
    set PYTHON_CMD="%LOCAL_PYTHON_DIR%\python.exe"
    goto :verify_venv
)

REM Second: check if py launcher can find 3.12
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    echo       Found Python 3.12 via 'py' launcher
    set "PYTHON_CMD=py -3.12"
    goto :verify_venv
)

REM Third: check PATH for python that is 3.12
python --version 2>nul | findstr /C:"3.12" >nul 2>&1
if not errorlevel 1 (
    echo       Found Python 3.12 via 'python'
    set "PYTHON_CMD=python"
    goto :verify_venv
)

REM Not found at all — go straight to install
echo       Python 3.12 not found on this machine.
goto :install_python

REM ── Verify venv module works ──
:verify_venv
echo       Verifying venv module works...

REM Quick test: try to create a temp venv
%PYTHON_CMD% -m venv "%~dp0_venv_test" >nul 2>&1

if exist "%~dp0_venv_test\Scripts\python.exe" (
    echo       [OK] Python 3.12 with working venv confirmed
    rmdir /s /q "%~dp0_venv_test" 2>nul
    goto :python_ok
)

REM Cleanup failed test
rmdir /s /q "%~dp0_venv_test" 2>nul

echo.
echo       WARNING: Python 3.12 was found but venv module is broken!
echo       Installing a clean local copy instead...
echo.

REM If the broken Python is in our local folder, remove it
if exist "%LOCAL_PYTHON_DIR%" (
    echo       Removing broken local Python...
    rmdir /s /q "%LOCAL_PYTHON_DIR%" 2>nul
    timeout /t 2 /nobreak >nul
)

REM ── Install Python 3.12 locally ──
:install_python
echo.
echo       Installing Python %PYTHON_VERSION% locally...
echo       No admin rights needed.
echo.

REM ── METHOD 1: Embeddable zip (no .exe needed) ──
echo       [Method 1] Downloading portable Python zip...

powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_EMBED_URL%' -OutFile '%~dp0_python_embed.zip'"

if not exist "%~dp0_python_embed.zip" (
    echo       Download failed. Skipping to Method 2...
    goto :try_installer
)

echo       Download OK. Extracting...

REM Create target directory
if not exist "%LOCAL_PYTHON_DIR%" mkdir "%LOCAL_PYTHON_DIR%"

REM Try tar first (built into Windows 10 1803+)
tar -xf "%~dp0_python_embed.zip" -C "%LOCAL_PYTHON_DIR%" 2>nul

if not exist "%LOCAL_PYTHON_DIR%\python.exe" (
    echo       tar failed, trying PowerShell...
    rmdir /s /q "%LOCAL_PYTHON_DIR%" 2>nul
    mkdir "%LOCAL_PYTHON_DIR%"
    powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -LiteralPath '%~dp0_python_embed.zip' -DestinationPath '%LOCAL_PYTHON_DIR%' -Force"
)

del "%~dp0_python_embed.zip" 2>nul

if not exist "%LOCAL_PYTHON_DIR%\python.exe" (
    echo       ERROR: Extraction failed.
    rmdir /s /q "%LOCAL_PYTHON_DIR%" 2>nul
    goto :try_installer
)

echo       Extraction OK. Setting up pip...

REM Enable site-packages in embeddable Python
set "PTH_FILE=%LOCAL_PYTHON_DIR%\python312._pth"
if exist "%PTH_FILE%" (
    powershell -ExecutionPolicy Bypass -Command "(Get-Content '%PTH_FILE%') -replace '#import site','import site' | Set-Content '%PTH_FILE%'"
)

REM Download get-pip.py
powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%~dp0_get_pip.py'"

if not exist "%~dp0_get_pip.py" (
    echo       ERROR: Failed to download get-pip.py
    rmdir /s /q "%LOCAL_PYTHON_DIR%" 2>nul
    goto :try_installer
)

echo       Installing pip...
"%LOCAL_PYTHON_DIR%\python.exe" "%~dp0_get_pip.py" --no-warn-script-location
del "%~dp0_get_pip.py" 2>nul

REM Install virtualenv (embeddable Python doesn't have venv)
echo       Installing virtualenv...
"%LOCAL_PYTHON_DIR%\python.exe" -m pip install virtualenv --no-warn-script-location

REM Verify it works
"%LOCAL_PYTHON_DIR%\python.exe" -m virtualenv "%~dp0_venv_test" >nul 2>&1
if exist "%~dp0_venv_test\Scripts\python.exe" (
    rmdir /s /q "%~dp0_venv_test" 2>nul
    set PYTHON_CMD="%LOCAL_PYTHON_DIR%\python.exe"
    set "USE_VIRTUALENV=1"
    echo       [OK] Portable Python %PYTHON_VERSION% ready
    goto :python_ok
)
rmdir /s /q "%~dp0_venv_test" 2>nul

echo       Portable method failed. Trying installer...
rmdir /s /q "%LOCAL_PYTHON_DIR%" 2>nul

REM ── METHOD 2: Traditional .exe installer ──
:try_installer
echo.
echo       [Method 2] Downloading Python installer...
powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%~dp0_python_installer.exe'"

if not exist "%~dp0_python_installer.exe" (
    echo       ERROR: Download failed. Check internet connection.
    echo       Install Python 3.12 manually from: https://www.python.org/downloads/
    pause
    exit /b 1
)

if exist "%LOCAL_PYTHON_DIR%" (
    rmdir /s /q "%LOCAL_PYTHON_DIR%" 2>nul
    timeout /t 2 /nobreak >nul
)

echo       Running installer...
echo       (If you see a prompt, click Yes)
START /WAIT "" "%~dp0_python_installer.exe" /passive InstallAllUsers=0 PrependPath=0 TargetDir="%LOCAL_PYTHON_DIR%" Include_launcher=0 Include_test=0

timeout /t 3 /nobreak >nul
del "%~dp0_python_installer.exe" 2>nul

if not exist "%LOCAL_PYTHON_DIR%\python.exe" (
    echo.
    echo       ERROR: Installer did not create python.exe in:
    echo         %LOCAL_PYTHON_DIR%
    echo.
    echo       FIX: Install Python 3.12 manually from python.org
    echo       Check "Add Python to PATH" during installation.
    echo       Then re-run this setup.bat.
    pause
    exit /b 1
)

set PYTHON_CMD="%LOCAL_PYTHON_DIR%\python.exe"
"%LOCAL_PYTHON_DIR%\python.exe" -m venv "%~dp0_venv_test" >nul 2>&1
if exist "%~dp0_venv_test\Scripts\python.exe" (
    rmdir /s /q "%~dp0_venv_test" 2>nul
    set "USE_VIRTUALENV=0"
    echo       [OK] Python %PYTHON_VERSION% installed
    goto :python_ok
)
rmdir /s /q "%~dp0_venv_test" 2>nul
echo       ERROR: Installed Python has broken venv module.
pause
exit /b 1

:python_ok
echo.

REM ── Step 2: Verify MCP server is bundled ──
echo [2/4] Checking Power BI MCP server...
if not exist "%~dp0server\powerbi-modeling-mcp.exe" (
    echo       ERROR: server\powerbi-modeling-mcp.exe not found!
    echo.
    echo       Please ensure the server\ folder contains powerbi-modeling-mcp.exe
    pause
    exit /b 1
)
echo       [OK] MCP server found in server\ folder
echo.

REM ── Step 3: Create FRESH venv ──
echo [3/4] Creating clean Python environment...

if exist "%~dp0venv" (
    echo       Removing old venv to ensure clean state...
    rmdir /s /q "%~dp0venv" 2>nul
    timeout /t 2 /nobreak >nul
)

if "%USE_VIRTUALENV%"=="1" (
    echo       Running: python -m virtualenv venv
    %PYTHON_CMD% -m virtualenv "%~dp0venv"
) else (
    echo       Running: python -m venv venv
    %PYTHON_CMD% -m venv "%~dp0venv"
)

if not exist "%~dp0venv\Scripts\activate.bat" (
    echo       ERROR: Failed to create virtual environment.
    echo       Try deleting the python312\ folder and run setup.bat again.
    pause
    exit /b 1
)

call "%~dp0venv\Scripts\activate.bat"
echo       [OK] Virtual environment created
echo.

REM ── Step 4: Install EXACT pinned packages ──
echo [4/4] Installing packages with pinned versions...
echo       This may take 1-2 minutes on first run...
echo.

pip install --no-cache-dir -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo       ERROR: Package installation failed.
    echo       Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [Bonus] Installing frontend (npm) dependencies...
cd "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo.
    echo       WARNING: npm install failed. You can run 'npm install' manually in the frontend\ folder.
    echo       The app will attempt to install dependencies again on next run.
    pause
) else (
    echo       [OK] Frontend dependencies installed.
)
cd "%~dp0"

echo.
echo ============================================
echo   SETUP COMPLETE!
echo ============================================
echo.
echo   Packages installed with exact pinned versions.
echo   Environment is fully isolated from your system.
echo.
echo   NEXT STEPS:
echo     1. Double-click run.bat to start Power BI IDE
echo     2. Click Settings (gear icon) in the app to configure your AI token
echo.
pause
