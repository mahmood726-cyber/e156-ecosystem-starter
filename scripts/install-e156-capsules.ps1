#Requires -Version 5.1
# install-e156-capsules.ps1 - install the BUNDLED E156 capsule + chart-kit template.
#
# Copies templates\e156-capsule\ (capsule contract + stdlib-only SVG chart-kit +
# a pre-baked sample) into a target dir and persists E156_CAPSULES_PATH. This
# layer makes NO network call and clones NOTHING -- the lowest-footprint layer in
# the ecosystem, fully offline, zero tokens.
#
# Usage:
#   .\scripts\install-e156-capsules.ps1                # copy to ~\code\e156-capsules
#   .\scripts\install-e156-capsules.ps1 -Target C:\code\e156-capsules
#   .\scripts\install-e156-capsules.ps1 -SkipCopy      # only set env + verify existing
#   .\scripts\install-e156-capsules.ps1 -Import        # dot-source for tests

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$SkipCopy,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-E156TemplateDir {
    # templates\e156-capsule\ relative to this script's repo root.
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Join-Path (Split-Path -Parent $scriptDir) 'templates\e156-capsule')
}
function Get-E156DefaultTarget { return (Join-Path $env:USERPROFILE 'code\e156-capsules') }

function Test-E156CapsulesPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'chartkit.py')))
}

function Copy-E156Template {
    [CmdletBinding()]
    param([string]$Src, [string]$Dst)
    if (-not (Test-Path $Src)) { throw "bundled template not found at $Src" }
    if (-not (Test-Path $Dst)) { New-Item -ItemType Directory -Force -Path $Dst | Out-Null }
    Copy-Item -Path (Join-Path $Src '*') -Destination $Dst -Recurse -Force
}

function Set-E156PathEnv {
    [CmdletBinding()]
    param([string]$TargetDir)
    [Environment]::SetEnvironmentVariable('E156_CAPSULES_PATH', $TargetDir, 'User')
    $env:E156_CAPSULES_PATH = $TargetDir
}

function Test-E156Chartkit {
    # Verify the offline chart-kit renders the bundled sample (token-free).
    [CmdletBinding()]
    param([string]$TargetDir)
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { return $true }   # python missing: skip, not fail
    $out = Join-Path $env:TEMP ("e156_" + [System.Guid]::NewGuid().ToString('N') + '.svg')
    & python (Join-Path $TargetDir 'chartkit.py') (Join-Path $TargetDir 'sample.capsule.json') --out $out 2>&1 | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    if (Test-Path $out) { Remove-Item $out -Force }
    return $ok
}

if ($Import) { return }

# === Real flow =============================================================
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Target) { $Target = Get-E156DefaultTarget }

Write-Host ""
Write-Host "e156-capsules installer (offline capsule + chart-kit template; zero network)" -ForegroundColor Cyan
Write-Host ""

if ($SkipCopy) {
    Write-Step "Skipping copy (-SkipCopy); using existing template at $Target"
    if (-not (Test-E156CapsulesPresent -Dir $Target)) {
        Write-Host "ERROR: -SkipCopy but no chartkit.py at $Target." -ForegroundColor Red; exit 1
    }
} else {
    $src = Get-E156TemplateDir
    Write-Step "Copying bundled template -> $Target"
    Copy-E156Template -Src $src -Dst $Target
    if (-not (Test-E156CapsulesPresent -Dir $Target)) {
        Write-Host "ERROR: copy completed but $Target\chartkit.py is missing." -ForegroundColor Red; exit 1
    }
    Write-Ok "template copied"
}

Write-Step "Persisting E156_CAPSULES_PATH (User env var)"
Set-E156PathEnv -TargetDir $Target
Write-Ok "E156_CAPSULES_PATH = $Target"

Write-Step "Verifying the offline chart-kit renders the sample"
if (Test-E156Chartkit -TargetDir $Target) { Write-Ok "chartkit OK (stdlib-only SVG render verified, no network)" }
else { Write-Host "    WARNING: chartkit render check did not pass (python missing?)." -ForegroundColor Yellow }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  e156-capsules installed at $Target"
Write-Host "  E156_CAPSULES_PATH is set (reopen PowerShell to pick it up)."
Write-Host ""
Write-Host "  Zero-token starts:"
Write-Host "    type `"$Target\sample.capsule.md`"          # see a finished capsule"
Write-Host "    start `"$Target\sample.forest.svg`"          # see the chart"
Write-Host "  Author your own (chart step is always token-free):"
Write-Host "    copy `"$Target\capsule.template.md`" my.capsule.md"
Write-Host "    python `"$Target\chartkit.py`" my.capsule.json --out my.svg"
Write-Host "======================================================" -ForegroundColor Green

exit 0
