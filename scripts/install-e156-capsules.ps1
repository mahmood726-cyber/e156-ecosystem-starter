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
    if (-not (Test-Path -LiteralPath $Src -PathType Container)) { throw "bundled template not found at $Src" }
    # Prevent accidental overwrite of existing capsules. Reparse-point
    # destinations can redirect the copy outside the requested directory.
    if (Test-Path -LiteralPath $Dst) {
        $item = Get-Item -LiteralPath $Dst -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "REFUSED: destination $Dst is not a regular directory."
        }
        if (Get-ChildItem -LiteralPath $Dst -Force | Select-Object -First 1) {
            throw "REFUSED: destination $Dst is not empty; use -SkipCopy to verify the existing template."
        }
    } else {
        New-Item -ItemType Directory -Path $Dst -Force | Out-Null
    }
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
    if (-not $py -or $py.Source -match 'WindowsApps') { return $false }
    $out = Join-Path $env:TEMP ("e156_" + [System.Guid]::NewGuid().ToString('N') + '.svg')
    try {
        & $py.Source (Join-Path $TargetDir 'chartkit.py') (Join-Path $TargetDir 'sample.capsule.json') --out $out 2>&1 | Out-Null
        # Exit zero and nonempty bytes alone do not prove a valid SVG artifact.
        if ($LASTEXITCODE -ne 0 -or
            -not (Test-Path -LiteralPath $out -PathType Leaf) -or
            (Get-Item -LiteralPath $out).Length -eq 0) { return $false }
        $xml = New-Object System.Xml.XmlDocument
        $xml.Load($out)
        # LocalName alone accepts impostors such as <SVG/> or an unrelated
        # namespace's <x:svg/>. Match the SVG root exactly, as Bash does.
        $root = $xml.DocumentElement
        return [bool](($root.LocalName -ceq 'svg') -and
            (($root.NamespaceURI -ceq '') -or
             ($root.NamespaceURI -ceq 'http://www.w3.org/2000/svg')))
    } catch {
        return $false
    } finally {
        if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Force }
    }
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

Write-Step "Verifying the offline chart-kit renders the sample"
if (-not (Test-E156Chartkit -TargetDir $Target)) {
    Write-Host "ERROR: chartkit render check failed; refusing a successful installation." -ForegroundColor Red
    exit 1
}
Write-Ok "chartkit OK (stdlib-only SVG render verified, no network)"

# Do not persist a path whose chartkit has not passed its installation canary.
Write-Step "Persisting E156_CAPSULES_PATH (User env var)"
Set-E156PathEnv -TargetDir $Target
Write-Ok "E156_CAPSULES_PATH = $Target"

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
