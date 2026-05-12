@echo off
REM e156-setup.bat -- one-click installer for the E156 ecosystem starter.
REM
REM Double-click this file. It will:
REM   1. Check Python is installed
REM   2. Download the latest ecosystem-starter release
REM   3. Extract to %TEMP%
REM   4. Run install.ps1 (which chains Sentinel/Overmind/ProjectIndex)
REM
REM No admin rights needed.

setlocal enabledelayedexpansion

echo.
echo =====================================================
echo   E156 Ecosystem Starter - one-click installer
echo =====================================================
echo.
echo This will install:
echo   - AI agent rules (Claude Code / Gemini CLI / Codex)
echo   - Memory scaffold (cross-session learning)
echo   - Sentinel pre-push hook (optional, 28 quality rules)
echo   - Overmind + TruthCert (optional, verifier + signed bundles)
echo   - ProjectIndex portfolio tracker (optional)
echo   - long-term-plan weekly backlog reranker (optional)
echo.
echo Takes about 2 minutes. No admin rights needed.
echo.
echo Press any key to start, or close this window to cancel.
pause >nul

echo.
echo [1/4] Checking prerequisites...

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Python is not installed or not on your PATH.
    echo.
    echo   Install Python 3.11 or newer from:
    echo     https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: During install, tick "Add Python to PATH" on the first screen.
    echo.
    echo   After installing Python, re-run this file.
    echo.
    pause
    exit /b 1
)
REM Detect Microsoft Store python.exe stub. The stub is on PATH but emits
REM "Python was not found; run without arguments to install from the Microsoft
REM Store..." and exits non-zero. Real Python prints "Python X.Y.Z" and exits 0.
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Python on your PATH is the Microsoft Store stub, not a real Python install.
    echo.
    echo   Fix it:
    echo     1. Download Python 3.11+ from https://www.python.org/downloads/
    echo     2. Run the installer.
    echo     3. CRITICAL: tick "Add python.exe to PATH" on the first screen.
    echo     4. Close this window and re-run this file.
    echo.
    echo   Optional: also disable the Store alias in
    echo     Settings ^> Apps ^> Advanced app settings ^> App execution aliases
    echo.
    pause
    exit /b 1
)
echo   OK - Python found:
python --version

echo.
echo [2/4] Downloading ecosystem-starter...
set "DOWNLOAD_URL=https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/main.zip"
set "ZIP_PATH=%TEMP%\e156-ecosystem-starter.zip"
set "EXTRACT_PARENT=%TEMP%"
set "EXTRACT_PATH=%TEMP%\e156-ecosystem-starter-main"

REM Remove any stale extract from a previous attempt
if exist "%EXTRACT_PATH%" rmdir /S /Q "%EXTRACT_PATH%"
if exist "%ZIP_PATH%" del /Q "%ZIP_PATH%"

powershell -NoProfile -Command "$ProgressPreference = 'SilentlyContinue'; try { Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%ZIP_PATH%' -UseBasicParsing -ErrorAction Stop; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo.
    echo   ERROR: Download failed. Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo   OK - Downloaded to %ZIP_PATH%

echo.
echo [3/4] Extracting...
powershell -NoProfile -Command "try { Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_PARENT%' -Force -ErrorAction Stop; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo.
    echo   ERROR: Extract failed. The zip may be corrupted. Try again.
    echo.
    pause
    exit /b 1
)
if not exist "%EXTRACT_PATH%\install\install.ps1" (
    echo.
    echo   ERROR: Extracted contents do not match expected layout.
    echo   Expected: %EXTRACT_PATH%\install\install.ps1
    echo.
    pause
    exit /b 1
)
echo   OK - Extracted to %EXTRACT_PATH%

echo.
echo [4/4] Running installer (this is where the real work happens)...
echo.
cd /d "%EXTRACT_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\install\install.ps1"
set EXIT_CODE=%ERRORLEVEL%

echo.
echo =====================================================
if %EXIT_CODE% equ 0 (
    echo   INSTALL COMPLETE
    echo.
    echo   You can close this window. Next steps:
    echo     1. Run 'claude' or 'gemini' in any project folder
    echo     2. The rules + memory from this install are loaded automatically
    echo     3. If you answered Yes to Sentinel, every git push is now gated
) else (
    echo   INSTALL FAILED (exit code %EXIT_CODE%)
    echo   Scroll up to see what went wrong.
    echo.
    echo   Common causes:
    echo     - Python too old (need 3.11+)
    echo     - No internet mid-install (pip failed)
    echo     - Ran from a network drive with restricted permissions
)
echo =====================================================
echo.
pause
exit /b %EXIT_CODE%
