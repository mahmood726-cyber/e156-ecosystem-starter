#Requires -Version 5.1
# install-aact-kit.ps1 - install aact-kit (shared local-AACT data-access library).
#
# One API to resolve / load / validate / aggregate AACT (ClinicalTrials.gov)
# across five local backends (Postgres, SQLite, ZIP, pipe-delimited TSV dir,
# CSV dir). Clones the repo at a pinned commit and persists AACT_KIT_PATH.
#
# Footprint note: aact-kit is a small pip package whose only hard dependency is
# pandas (psycopg2 is optional, only for the Postgres backend). The clone is
# free; installing the importable package is OPT-IN via -WithDeps, and the
# LOW-TOKEN / zero-setup path is to read src\aact_kit\ + README.md. This is the
# LIBRARY other CT.gov projects import -- distinct from the aact-cockpit layer.
#
# Usage:
#   .\scripts\install-aact-kit.ps1               # clone to ~\code\aact-kit (no install)
#   .\scripts\install-aact-kit.ps1 -Target C:\code\aact-kit
#   .\scripts\install-aact-kit.ps1 -WithDeps     # also pip-install -e (import aact_kit)
#   .\scripts\install-aact-kit.ps1 -SkipClone    # only set env + verify existing
#   .\scripts\install-aact-kit.ps1 -Import       # dot-source for tests

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$WithDeps,
    [switch]$SkipClone,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-AactKitRepoUrl { return 'https://github.com/mahmood726-cyber/aact-kit.git' }

# Pinned commit (2026-06-04). Override with $env:AACT_KIT_REF=main for latest.
$script:AactKitDefaultRef = 'b1995128747848d1567386266eca95e9230e19b9'
function Get-AactKitDefaultRef {
    if ($env:AACT_KIT_REF) { return $env:AACT_KIT_REF }
    return $script:AactKitDefaultRef
}
function Get-AactKitDefaultTarget { return (Join-Path $env:USERPROFILE 'code\aact-kit') }

function Test-AactKitPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'src\aact_kit\__init__.py')))
}

function Install-AactKitClone {
    [CmdletBinding()]
    param([string]$TargetDir, [string]$Ref)
    $url = Get-AactKitRepoUrl
    if (Test-Path (Join-Path $TargetDir '.git')) {
        Write-Host "  existing checkout: $TargetDir (fetch + checkout $Ref)" -ForegroundColor DarkGray
        & git -C $TargetDir fetch --quiet origin $Ref 2>$null
        if ($LASTEXITCODE -ne 0) { & git -C $TargetDir fetch --quiet origin 2>$null }
        & git -C $TargetDir checkout --quiet $Ref 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    } else {
        Write-Host "  cloning $url" -ForegroundColor DarkGray
        & git clone --quiet $url $TargetDir 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
        if ($LASTEXITCODE -ne 0) { throw "git clone failed (exit $LASTEXITCODE)" }
        & git -C $TargetDir checkout --quiet $Ref 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }
}

function Set-AactKitPathEnv {
    [CmdletBinding()]
    param([string]$TargetDir)
    [Environment]::SetEnvironmentVariable('AACT_KIT_PATH', $TargetDir, 'User')
    $env:AACT_KIT_PATH = $TargetDir
}

function Install-AactKitDeps {
    # Light: pandas (psycopg2 only for the optional Postgres backend). Opt-in.
    [CmdletBinding()]
    param([string]$TargetDir)
    Write-Host "  pip install -e `"$TargetDir`"  (pandas)" -ForegroundColor DarkGray
    & python -m pip install --quiet --disable-pip-version-check -e $TargetDir 2>&1 |
        ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }
}

if ($Import) { return }

# === Real flow =============================================================
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Target) { $Target = Get-AactKitDefaultTarget }
$ref = Get-AactKitDefaultRef

Write-Host ""
Write-Host "aact-kit installer (shared local-AACT data-access library)" -ForegroundColor Cyan
Write-Host ""

if ($SkipClone) {
    Write-Step "Skipping clone (-SkipClone); using existing checkout at $Target"
    if (-not (Test-AactKitPresent -Dir $Target)) {
        Write-Host "ERROR: -SkipClone but no src\aact_kit\__init__.py at $Target." -ForegroundColor Red; exit 1
    }
} else {
    Write-Step "Installing aact-kit into $Target (ref: $($ref.Substring(0,[Math]::Min(12,$ref.Length))))"
    $parent = Split-Path -Parent $Target
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Install-AactKitClone -TargetDir $Target -Ref $ref
    if (-not (Test-AactKitPresent -Dir $Target)) {
        Write-Host "ERROR: clone completed but $Target\src\aact_kit\__init__.py is missing." -ForegroundColor Red; exit 1
    }
    Write-Ok "checkout ready"
}

Write-Step "Persisting AACT_KIT_PATH (User env var)"
Set-AactKitPathEnv -TargetDir $Target
Write-Ok "AACT_KIT_PATH = $Target"

if ($WithDeps) {
    Write-Step "Installing the package (-WithDeps: pip install -e, pulls pandas)"
    try { Install-AactKitDeps -TargetDir $Target; Write-Ok "aact-kit importable (import aact_kit)" }
    catch { Write-Host "    WARNING: install failed; the read-only source path still works." -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  aact-kit installed at $Target"
Write-Host "  AACT_KIT_PATH is set (reopen PowerShell to pick it up)."
Write-Host ""
Write-Host "  Zero-token / zero-setup path (no install needed):"
Write-Host "    dir `"$Target\src\aact_kit`" ; type `"$Target\README.md`"   # read the API"
Write-Host ""
Write-Host "  Full path (after -WithDeps):"
Write-Host "    python -c `"from aact_kit import load_table, resolve_aact_location`""
Write-Host "    # set AACT_TSV_DIR / AACT_CSV_DIR / AACT_DSN / AACT_SQLITE / AACT_ZIP to your snapshot"
if (-not $WithDeps) {
    Write-Host "  To install the package later:  .\scripts\install-aact-kit.ps1 -WithDeps"
}
Write-Host "======================================================" -ForegroundColor Green

exit 0
