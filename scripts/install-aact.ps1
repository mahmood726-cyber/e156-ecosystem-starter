#Requires -Version 5.1
# install-aact.ps1 - install aact-cockpit (ClinicalTrials.gov/AACT -> e156 capsules).
#
# A local DuckDB-backed cockpit for large-scale AACT analysis that emits
# self-auditing e156 capsules. Clones the repo at a pinned commit and persists
# AACT_COCKPIT_PATH.
#
# Footprint note: unlike rapidmeta-kit, RUNNING aact-cockpit needs duckdb + numpy
# AND a local AACT/CT.gov data snapshot. Those deps are OPT-IN via -WithDataDeps,
# and the LOW-TOKEN / zero-setup path is to read the repo's committed example
# analyses + capsules without building a warehouse. Clone is always free.
#
# Usage:
#   .\scripts\install-aact.ps1                  # clone to ~\code\aact-cockpit (no deps)
#   .\scripts\install-aact.ps1 -Target C:\code\aact-cockpit
#   .\scripts\install-aact.ps1 -WithDataDeps    # also pip-install duckdb + numpy (+the pkg)
#   .\scripts\install-aact.ps1 -SkipClone       # only set env + verify existing
#   .\scripts\install-aact.ps1 -Import          # dot-source for tests

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$WithDataDeps,
    [switch]$SkipClone,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-AactRepoUrl { return 'https://github.com/mahmood726-cyber/aact-cockpit.git' }

# Pinned commit (2026-06-04). Override with $env:AACT_REF=master for latest.
$script:AactDefaultRef = '58a970868c9135accbdb11aef130757aa69558d2'
function Get-AactDefaultRef {
    if ($env:AACT_REF) { return $env:AACT_REF }
    return $script:AactDefaultRef
}
function Get-AactDefaultTarget { return (Join-Path $env:USERPROFILE 'code\aact-cockpit') }

function Test-AactPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'scripts\make_capsule.py')))
}

function Install-AactClone {
    [CmdletBinding()]
    param([string]$TargetDir, [string]$Ref)
    $url = Get-AactRepoUrl
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

function Set-AactPathEnv {
    [CmdletBinding()]
    param([string]$TargetDir)
    [Environment]::SetEnvironmentVariable('AACT_COCKPIT_PATH', $TargetDir, 'User')
    $env:AACT_COCKPIT_PATH = $TargetDir
}

function Install-AactDataDeps {
    # Heavy: duckdb + numpy (the cockpit's required runtime). Opt-in only.
    [CmdletBinding()]
    param([string]$TargetDir)
    Write-Host "  pip install -e `"$TargetDir`"  (duckdb + numpy)" -ForegroundColor DarkGray
    & python -m pip install --quiet --disable-pip-version-check -e $TargetDir 2>&1 |
        ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }
}

if ($Import) { return }

# === Real flow =============================================================
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Target) { $Target = Get-AactDefaultTarget }
$ref = Get-AactDefaultRef

Write-Host ""
Write-Host "aact-cockpit installer (ClinicalTrials.gov/AACT -> e156 capsules)" -ForegroundColor Cyan
Write-Host ""

if ($SkipClone) {
    Write-Step "Skipping clone (-SkipClone); using existing checkout at $Target"
    if (-not (Test-AactPresent -Dir $Target)) {
        Write-Host "ERROR: -SkipClone but no scripts\make_capsule.py at $Target." -ForegroundColor Red; exit 1
    }
} else {
    Write-Step "Installing aact-cockpit into $Target (ref: $($ref.Substring(0,[Math]::Min(12,$ref.Length))))"
    $parent = Split-Path -Parent $Target
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Install-AactClone -TargetDir $Target -Ref $ref
    if (-not (Test-AactPresent -Dir $Target)) {
        Write-Host "ERROR: clone completed but $Target\scripts\make_capsule.py is missing." -ForegroundColor Red; exit 1
    }
    Write-Ok "checkout ready"
}

Write-Step "Persisting AACT_COCKPIT_PATH (User env var)"
Set-AactPathEnv -TargetDir $Target
Write-Ok "AACT_COCKPIT_PATH = $Target"

if ($WithDataDeps) {
    Write-Step "Installing data deps (-WithDataDeps: duckdb + numpy)"
    try { Install-AactDataDeps -TargetDir $Target; Write-Ok "data deps installed" }
    catch { Write-Host "    WARNING: data deps failed; the read-only example path still works." -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  aact-cockpit installed at $Target"
Write-Host "  AACT_COCKPIT_PATH is set (reopen PowerShell to pick it up)."
Write-Host ""
Write-Host "  Zero-token / zero-setup path (no deps, no data snapshot needed):"
Write-Host "    dir `"$Target\analyses`" ; dir `"$Target\templates`"   # read committed example capsules"
Write-Host ""
Write-Host "  Full path (after -WithDataDeps AND a local AACT/CT.gov snapshot):"
Write-Host "    python `"$Target\scripts\build_warehouse.py`" --help"
Write-Host "    python `"$Target\scripts\make_capsule.py`" --help"
if (-not $WithDataDeps) {
    Write-Host "  To install the runtime later:  .\scripts\install-aact.ps1 -WithDataDeps"
}
Write-Host "======================================================" -ForegroundColor Green

exit 0
