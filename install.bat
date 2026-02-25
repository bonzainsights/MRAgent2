@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo         MRAgent Installer
echo ============================================
echo.

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>&1') do set PYTHON_VER=%%v
echo [OK] Found Python %PYTHON_VER%

:: ─────────────────────────────────────────────────────
:: Choose install method
:: ─────────────────────────────────────────────────────
echo.
echo How would you like to install MRAgent?
echo   1. pip install (from PyPI) — recommended
echo   2. Local install (from this cloned repo)
echo.
set /p CHOICE="Enter 1 or 2 [default: 1]: "
if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="1" goto :pip_install
goto :local_install

:: ─────────────────────────────────────────────────────
:pip_install
:: ─────────────────────────────────────────────────────
echo.
echo [INFO] Installing bonza-mragent from PyPI...
pip install --user bonza-mragent
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo [OK] bonza-mragent installed!

:: Find the Scripts directory pip used
for /f "delims=" %%d in ('python -c "import site; print(site.getusersitepackages())"') do set SITE_PKG=%%d
:: Scripts is sibling to site-packages
set "PIP_SCRIPTS=%SITE_PKG%\..\Scripts"
for /f "delims=" %%f in ('python -c "import os, site; print(os.path.normpath(os.path.join(site.getusersitepackages(), '..', 'Scripts')))"') do set "PIP_SCRIPTS=%%f"

echo [INFO] pip Scripts folder: %PIP_SCRIPTS%

:: Add to user PATH if not already present
echo %PATH% | find /i "%PIP_SCRIPTS%" >nul
if %errorlevel% neq 0 (
    echo [INFO] Adding pip Scripts folder to user PATH...
    setx PATH "%PIP_SCRIPTS%;%PATH%"
    echo [OK] PATH updated. Please RESTART your terminal, then type 'mragent'.
) else (
    echo [OK] Scripts folder already in PATH.
    echo [OK] You can now type 'mragent' in any terminal.
)
goto :done

:: ─────────────────────────────────────────────────────
:local_install
:: ─────────────────────────────────────────────────────
echo.
echo [INFO] Setting up virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo    Created .venv
) else (
    echo    Found existing .venv
)

echo [INFO] Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed!

:: Create Launcher Script
set "LAUNCHER_DIR=%USERPROFILE%\bin"
if not exist "%LAUNCHER_DIR%" mkdir "%LAUNCHER_DIR%"

set "LAUNCHER_PATH=%LAUNCHER_DIR%\mragent.cmd"
echo @echo off > "%LAUNCHER_PATH%"
echo cd /d "%CD%" >> "%LAUNCHER_PATH%"
echo call .venv\Scripts\activate.bat >> "%LAUNCHER_PATH%"
echo python main.py %%* >> "%LAUNCHER_PATH%"

:: Add launcher dir to PATH
echo %PATH% | find /i "%LAUNCHER_DIR%" >nul
if %errorlevel% neq 0 (
    setx PATH "%LAUNCHER_DIR%;%PATH%"
    echo [OK] Added to PATH. Please RESTART your terminal, then type 'mragent'.
) else (
    echo [OK] Already in PATH. Type 'mragent' to start.
)

:done
echo.
echo ============================================
echo  Installation Complete!
echo  Type 'mragent' to start your assistant.
echo  (You may need to restart your terminal first)
echo ============================================
pause
