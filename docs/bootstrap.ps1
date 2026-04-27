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
#   2. Downloads the PINNED release tarball (default v0.8.0; override with
#      $env:E156_REF = 'main' or any tag/branch before piping to iex)
#   3. Extracts to %TEMP%\e156-ecosystem-starter-<ref>
#   4. install\install.ps1 hashes itself against docs/HASH.txt (download-
#      integrity check) and then chains rules+memory+optional sub-installers
#
# Security note: download-integrity != tamper-proof. A bad actor with push
# access to the upstream repo can ship a malicious tag along with a matching
# HASH.txt; the gate only catches MitM / corrupt-download. For high-trust
# installs, prefer `git clone --branch v0.x.y --depth 1` from a clean shell
# and verify the tag's GPG signature before running install.ps1.

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# Pinned release tag. Bumping this is a deliberate, reviewable commit. Override
# only for testing pre-release branches: $env:E156_REF = 'main'; iex (irm ...)
$pinnedRef = if ($env:E156_REF) { $env:E156_REF } else { 'v0.8.0' }

Write-Host ""
Write-Host "====================================================="
Write-Host "  E156 Ecosystem Starter — PowerShell bootstrap"
Write-Host "  Pinned to: $pinnedRef"
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

# Detect the Microsoft Store python.exe stub. On a fresh Windows 10/11 install,
# 'python' on PATH points to a 0-byte alias under WindowsApps that, when run,
# prints 'Python was not found ... install from the Microsoft Store' and exits
# with a non-zero code. Get-Command finds it (it IS on PATH) but it's not a
# usable Python interpreter — pip install will fail downstream.
$pyVersion = & $python.Source --version 2>&1
if ($LASTEXITCODE -ne 0 -or $pyVersion -match 'not found' -or $python.Source -match 'WindowsApps') {
    # Try one more probe: a real Python prints 'Python X.Y.Z' to stdout.
    if ($pyVersion -notmatch '^Python \d') {
        Write-Host ""
        Write-Host "  ERROR: 'python' on your PATH is the Microsoft Store stub, not a real" -ForegroundColor Red
        Write-Host "  Python install. Found at:" -ForegroundColor Red
        Write-Host "    $($python.Source)"
        Write-Host ""
        Write-Host "  Fix it (1 minute):"
        Write-Host "    1. Download Python 3.11 or newer from https://www.python.org/downloads/"
        Write-Host "    2. Run the installer."
        Write-Host "    3. CRITICAL: tick 'Add python.exe to PATH' on the first screen."
        Write-Host "    4. Click Install."
        Write-Host "    5. Close and reopen PowerShell, then re-run this command."
        Write-Host ""
        Write-Host "  Optional: also disable the Store stub in Windows Settings ->"
        Write-Host "  Apps -> Advanced app settings -> App execution aliases ->"
        Write-Host "  toggle off 'python.exe' and 'python3.exe'."
        Write-Host ""
        return
    }
}
Write-Host "  OK — $pyVersion at $($python.Source)"

# Check for R (recommended but not blocking — used for meta-analysis validation)
$rscript = Get-Command Rscript -ErrorAction SilentlyContinue
if ($rscript) {
    $rVersion = (& $rscript.Source --version 2>&1 | Select-String -Pattern 'R scripting' | Out-String).Trim()
    if (-not $rVersion) { $rVersion = 'R found' }
    Write-Host "  OK — $rVersion"
} else {
    Write-Host "  WARNING: R / Rscript not on PATH (optional but recommended)" -ForegroundColor Yellow
    Write-Host "    Install R 4.5+ from https://cran.r-project.org/bin/windows/base/"
    Write-Host "    Needed for cross-validating meta-analysis pools against the metafor"
    Write-Host "    package. Install can continue without it; you'll just lose the R"
    Write-Host "    validation step in your dashboards."
}

# --- 2. Download pinned release tarball ---------------------------------------
# Tagged release URL: GitHub names the extract dir "<repo>-<tag-without-v>"
# for tags starting with v, and "<repo>-<branch>" for branches.
if ($pinnedRef -match '^v[0-9]') {
    $zipUrl = "https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/tags/$pinnedRef.zip"
    $extractSuffix = $pinnedRef -replace '^v',''
} else {
    $zipUrl = "https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/$pinnedRef.zip"
    $extractSuffix = $pinnedRef
}
$zipPath = Join-Path $env:TEMP "e156-ecosystem-starter-$pinnedRef.zip"
$extract = Join-Path $env:TEMP "e156-ecosystem-starter-$extractSuffix"

if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

Write-Host ""
Write-Host "[2/4] Downloading $pinnedRef.zip..."
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
