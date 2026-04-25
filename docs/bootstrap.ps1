# bootstrap.ps1 — e156-ecosystem-starter, fetched-and-executed.
#
# Designed to be run via:
#     irm https://mahmood726-cyber.github.io/e156-ecosystem-starter/bootstrap.ps1 | iex
#
# This is the Smart-App-Control-friendly equivalent of double-clicking
# e156-setup.bat. PowerShell's iex pipeline runs this script in memory
# without writing an unsigned binary to disk first, which avoids most
# SAC-style block dialogs.
#
# What it does (same as e156-setup.bat):
#   1. Checks Python is installed
#   2. Downloads the latest main.zip
#   3. Extracts to %TEMP%\e156-ecosystem-starter-main
#   4. Runs install\install.ps1 (which copies rules + memory + chains
#      Sentinel/Overmind/ProjectIndex per your prompts)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

Write-Host ""
Write-Host "====================================================="
Write-Host "  E156 Ecosystem Starter — PowerShell bootstrap"
Write-Host "====================================================="
Write-Host ""

# --- 1. Python check ----------------------------------------------------------
Write-Host "[1/4] Checking prerequisites..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host ""
    Write-Host "  ERROR: Python is not on PATH." -ForegroundColor Red
    Write-Host "  Install Python 3.11+ from https://www.python.org/downloads/"
    Write-Host "  (tick 'Add Python to PATH' during install)."
    Write-Host ""
    return
}
Write-Host "  OK — found $($python.Source)"

# --- 2. Download main.zip -----------------------------------------------------
$zipUrl  = 'https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/main.zip'
$zipPath = Join-Path $env:TEMP 'e156-ecosystem-starter.zip'
$extract = Join-Path $env:TEMP 'e156-ecosystem-starter-main'

if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

Write-Host ""
Write-Host "[2/4] Downloading main.zip..."
try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Write-Host "  OK — $((Get-Item $zipPath).Length / 1KB -as [int]) KB to $zipPath"
} catch {
    Write-Host "  ERROR: download failed — $_" -ForegroundColor Red
    return
}

# --- 3. Extract ---------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Extracting..."
try {
    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
    if (-not (Test-Path "$extract\install\install.ps1")) {
        Write-Host "  ERROR: extracted layout unexpected (no install\install.ps1)" -ForegroundColor Red
        return
    }
    Write-Host "  OK — $extract"
} catch {
    Write-Host "  ERROR: extract failed — $_" -ForegroundColor Red
    return
}

# --- 4. Run install.ps1 -------------------------------------------------------
Write-Host ""
Write-Host "[4/4] Running install.ps1..."
Write-Host ""
& "$extract\install\install.ps1"
