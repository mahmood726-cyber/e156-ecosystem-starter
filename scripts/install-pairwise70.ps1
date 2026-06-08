#Requires -Version 5.1
# install-pairwise70.ps1 - install pairwise70-workbench (offline Pairwise70 gallery).
#
# An offline gallery hub that shows and reproduces every Pairwise70-family
# analysis in one place; it embeds the proven HTML engines verbatim and the
# statistics run offline in the browser (only the embedded charts use a Plotly
# CDN). Clones the repo at a pinned commit and persists PAIRWISE70_PATH.
#
# Low-token by construction: a static HTML workbench -- open index.html and run
# analyses in the browser. No Python deps, no agent, no tokens.
#
# Usage:
#   .\scripts\install-pairwise70.ps1                # clone to ~\code\pairwise70-workbench
#   .\scripts\install-pairwise70.ps1 -Target C:\code\pairwise70-workbench
#   .\scripts\install-pairwise70.ps1 -SkipClone     # only set env + verify existing
#   .\scripts\install-pairwise70.ps1 -Import        # dot-source for tests

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$SkipClone,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-Pairwise70RepoUrl { return 'https://github.com/mahmood726-cyber/pairwise70-workbench.git' }

# Pinned commit (2026-06-04). Override with $env:PAIRWISE70_REF=master for latest.
$script:Pairwise70DefaultRef = '7303776bc84a86b75f06ec28dc6e776528698ed4'
function Get-Pairwise70DefaultRef {
    if ($env:PAIRWISE70_REF) { return $env:PAIRWISE70_REF }
    return $script:Pairwise70DefaultRef
}
function Get-Pairwise70DefaultTarget { return (Join-Path $env:USERPROFILE 'code\pairwise70-workbench') }

function Test-Pairwise70Present {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'index.html')))
}

function Install-Pairwise70Clone {
    [CmdletBinding()]
    param([string]$TargetDir, [string]$Ref)
    $url = Get-Pairwise70RepoUrl
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

function Set-Pairwise70PathEnv {
    [CmdletBinding()]
    param([string]$TargetDir)
    [Environment]::SetEnvironmentVariable('PAIRWISE70_PATH', $TargetDir, 'User')
    $env:PAIRWISE70_PATH = $TargetDir
}

function Test-Pairwise70Smoke {
    # Optional stdlib smoke if the repo ships one (no deps).
    [CmdletBinding()]
    param([string]$TargetDir)
    $smoke = Join-Path $TargetDir 'tests\smoke.py'
    if (-not (Test-Path $smoke)) { return $true }
    & python $smoke 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if ($Import) { return }

# === Real flow =============================================================
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Target) { $Target = Get-Pairwise70DefaultTarget }
$ref = Get-Pairwise70DefaultRef

Write-Host ""
Write-Host "pairwise70-workbench installer (offline Pairwise70 gallery hub)" -ForegroundColor Cyan
Write-Host ""

if ($SkipClone) {
    Write-Step "Skipping clone (-SkipClone); using existing checkout at $Target"
    if (-not (Test-Pairwise70Present -Dir $Target)) {
        Write-Host "ERROR: -SkipClone but no index.html at $Target." -ForegroundColor Red; exit 1
    }
} else {
    Write-Step "Installing pairwise70-workbench into $Target (ref: $($ref.Substring(0,[Math]::Min(12,$ref.Length))))"
    $parent = Split-Path -Parent $Target
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Install-Pairwise70Clone -TargetDir $Target -Ref $ref
    if (-not (Test-Pairwise70Present -Dir $Target)) {
        Write-Host "ERROR: clone completed but $Target\index.html is missing." -ForegroundColor Red; exit 1
    }
    Write-Ok "checkout ready"
}

Write-Step "Persisting PAIRWISE70_PATH (User env var)"
Set-Pairwise70PathEnv -TargetDir $Target
Write-Ok "PAIRWISE70_PATH = $Target"

Write-Step "Running the offline smoke (if present)"
if (Test-Pairwise70Smoke -TargetDir $Target) { Write-Ok "smoke OK (static workbench, no deps)" }
else { Write-Host "    note: smoke not run; the workbench is static HTML regardless." -ForegroundColor Yellow }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  pairwise70-workbench installed at $Target"
Write-Host "  PAIRWISE70_PATH is set (reopen PowerShell to pick it up)."
Write-Host ""
Write-Host "  Zero-token start -- just open the gallery in a browser:"
Write-Host "    start `"$Target\index.html`""
Write-Host "  The stats run offline in the browser."
Write-Host "======================================================" -ForegroundColor Green

exit 0
