#Requires -Version 5.1
# install-rapidmeta.ps1 - install rapidmeta-kit (offline, stdlib-only MA dashboards).
#
# rapidmeta-kit's clone.py turns a small JSON config into a self-contained
# RapidMeta HTML dashboard with NO numpy/scipy and NO network. Clones the repo at
# a pinned commit and persists RAPIDMETA_KIT_PATH. Low-token by construction: the
# whole config -> dashboard path is deterministic Python, no LLM in the loop.
#
# Usage:
#   .\scripts\install-rapidmeta.ps1                 # clone to ~\code\rapidmeta-kit
#   .\scripts\install-rapidmeta.ps1 -Target C:\code\rapidmeta-kit
#   .\scripts\install-rapidmeta.ps1 -SkipClone      # only set env + verify existing
#   .\scripts\install-rapidmeta.ps1 -Import         # dot-source for tests

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$SkipClone,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-RapidmetaRepoUrl { return 'https://github.com/mahmood726-cyber/rapidmeta-kit.git' }

# Pinned to the v1.1.0 release tag (includes the anti-fabrication fix). Override
# with $env:RAPIDMETA_REF=main for latest.
$script:RapidmetaDefaultRef = 'v1.1.0'
function Get-RapidmetaDefaultRef {
    if ($env:RAPIDMETA_REF) { return $env:RAPIDMETA_REF }
    return $script:RapidmetaDefaultRef
}
function Get-RapidmetaDefaultTarget { return (Join-Path $env:USERPROFILE 'code\rapidmeta-kit') }

function Test-RapidmetaPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'clone.py')))
}

function Install-RapidmetaClone {
    [CmdletBinding()]
    param([string]$TargetDir, [string]$Ref)
    $url = Get-RapidmetaRepoUrl
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

function Set-RapidmetaPathEnv {
    [CmdletBinding()]
    param([string]$TargetDir)
    [Environment]::SetEnvironmentVariable('RAPIDMETA_KIT_PATH', $TargetDir, 'User')
    $env:RAPIDMETA_KIT_PATH = $TargetDir
}

function Test-RapidmetaParse {
    # Stdlib-only: just confirm clone.py parses (no deps to import).
    [CmdletBinding()]
    param([string]$TargetDir)
    $clone = Join-Path $TargetDir 'clone.py'
    & python -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" $clone 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if ($Import) { return }

# === Real flow =============================================================
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Target) { $Target = Get-RapidmetaDefaultTarget }
$ref = Get-RapidmetaDefaultRef

Write-Host ""
Write-Host "rapidmeta-kit installer (offline, stdlib-only meta-analysis dashboards)" -ForegroundColor Cyan
Write-Host ""

if ($SkipClone) {
    Write-Step "Skipping clone (-SkipClone); using existing checkout at $Target"
    if (-not (Test-RapidmetaPresent -Dir $Target)) {
        Write-Host "ERROR: -SkipClone but no clone.py at $Target." -ForegroundColor Red; exit 1
    }
} else {
    Write-Step "Installing rapidmeta-kit into $Target (ref: $($ref.Substring(0,[Math]::Min(12,$ref.Length))))"
    $parent = Split-Path -Parent $Target
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Install-RapidmetaClone -TargetDir $Target -Ref $ref
    if (-not (Test-RapidmetaPresent -Dir $Target)) {
        Write-Host "ERROR: clone completed but $Target\clone.py is missing." -ForegroundColor Red; exit 1
    }
    Write-Ok "checkout ready"
}

Write-Step "Persisting RAPIDMETA_KIT_PATH (User env var)"
Set-RapidmetaPathEnv -TargetDir $Target
Write-Ok "RAPIDMETA_KIT_PATH = $Target"

Write-Step "Verifying the stdlib generator parses"
if (Test-RapidmetaParse -TargetDir $Target) { Write-Ok "clone.py OK (stdlib-only, no deps to install)" }
else { Write-Host "    WARNING: clone.py parse check did not pass (python missing?)." -ForegroundColor Yellow }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  rapidmeta-kit installed at $Target"
Write-Host "  RAPIDMETA_KIT_PATH is set (reopen PowerShell to pick it up)."
Write-Host ""
Write-Host "  Token-free dashboard from the bundled example:"
Write-Host "    cd `"$Target`"; .\RUN_EXAMPLE.bat"
Write-Host "  Or from your own config (config is positional):"
Write-Host "    python `"$Target\clone.py`" my.json --out dashboard.html"
Write-Host "======================================================" -ForegroundColor Green

exit 0
