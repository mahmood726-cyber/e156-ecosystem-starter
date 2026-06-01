#Requires -Version 5.1
# install-extractor.ps1 - install the rct-extractor-v2 RCT data extractor
#
# The extractor (cardiology + malaria + HIV) turns trial PDFs / abstract text
# into the meta-starter-kit config the rest of the ecosystem consumes. This
# clones it at a pinned commit and persists RCT_EXTRACTOR_PATH so the
# meta-system bridges (extractor_bridge\extract_meta.py) auto-find it.
#
# The student's core path -- trial text in, config out -- is STDLIB-ONLY.
# Heavy PDF + scientific deps (numpy/scipy/pdfplumber/pymupdf, ~150 MB) are
# OPT-IN via -WithPdfDeps.
#
# Usage:
#   .\scripts\install-extractor.ps1                       # clone to ~\code\rct-extractor-v2 (core only)
#   .\scripts\install-extractor.ps1 -Target C:\code\rct-extractor-v2
#   .\scripts\install-extractor.ps1 -WithPdfDeps          # also pip-install the PDF/scientific stack
#   .\scripts\install-extractor.ps1 -SkipClone            # only set env + verify an existing clone
#   .\scripts\install-extractor.ps1 -Import               # dot-source for tests

[CmdletBinding()]
param(
    [string]$Target,
    [switch]$WithPdfDeps,
    [switch]$SkipClone,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Assert-RealPython {
    # Defends against the Microsoft Store python.exe stub on Windows 10/11
    # (on PATH but a 0-byte alias). Same guard as install-sentinel.ps1.
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        throw @"
Python is not on PATH.

Install Python 3.11+ from https://www.python.org/downloads/
(tick 'Add python.exe to PATH' on the first installer screen),
then close and reopen PowerShell.
"@
    }
    $version = & $py.Source --version 2>&1
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^Python \d' -or $py.Source -match 'WindowsApps') {
        throw @"
Python on your PATH is the Microsoft Store stub, not a real Python install.

Found at: $($py.Source)

Fix it: install Python 3.11+ from https://www.python.org/downloads/,
tick 'Add python.exe to PATH', then reopen PowerShell and re-run.
"@
    }
}

function Get-ExtractorDefaultTarget {
    return (Join-Path $env:USERPROFILE 'code\rct-extractor-v2')
}

function Get-ExtractorRepoUrl {
    return 'https://github.com/mahmood726-cyber/rct-extractor-v2.git'
}

# Known-good extractor commit (cardiology + malaria + HIV; HIV MA agreement
# 97.9%, malaria 99.4%). Pinned for reproducible installs -- same supply-chain
# approach as Sentinel / Overmind. Override with $env:RCT_EXTRACTOR_REF.
$script:ExtractorDefaultRef = 'dd299165a6cc1e637fe5a261e9a2f5f64ae90ff3'

function Get-ExtractorDefaultRef {
    if ($env:RCT_EXTRACTOR_REF) { return $env:RCT_EXTRACTOR_REF }
    return $script:ExtractorDefaultRef
}

function Test-ExtractorPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'scripts\build_metakit_config.py')))
}

function Install-ExtractorClone {
    [CmdletBinding()]
    param([string]$TargetDir, [string]$Ref)
    $url = Get-ExtractorRepoUrl
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

function Set-ExtractorPathEnv {
    # Persist RCT_EXTRACTOR_PATH as a User env var so the meta-system bridges
    # find the extractor in future shells, and set it for the current session.
    [CmdletBinding()]
    param([string]$TargetDir)
    [Environment]::SetEnvironmentVariable('RCT_EXTRACTOR_PATH', $TargetDir, 'User')
    $env:RCT_EXTRACTOR_PATH = $TargetDir
}

function Test-ExtractorImport {
    # Verify the stdlib-only student path imports (text -> config).
    [CmdletBinding()]
    param([string]$TargetDir)
    $py = @"
import sys
sys.path.insert(0, r'$TargetDir')
import scripts.build_metakit_config
from src.specialties.registry import detect_specialty
assert detect_specialty('viral suppression with dolutegravir')[0] == 'hiv'
print('ok')
"@
    $out = & python -c $py 2>&1
    return ($LASTEXITCODE -eq 0 -and ($out -match 'ok'))
}

function Install-ExtractorPdfDeps {
    # Heavy: numpy/scipy/pdfplumber/pymupdf for real-PDF parsing. ~150 MB.
    [CmdletBinding()]
    param([string]$TargetDir)
    $req = Join-Path $TargetDir 'requirements.txt'
    if (-not (Test-Path $req)) { throw "no requirements.txt at $req" }
    Write-Host "  pip install -r $req  (PDF + scientific stack, ~150 MB)" -ForegroundColor DarkGray
    & python -m pip install --quiet --disable-pip-version-check -r $req 2>&1 |
        ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }
}

if ($Import) { return }   # dot-sourced by tests

# === Real flow =============================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Target) { $Target = Get-ExtractorDefaultTarget }
$ref = Get-ExtractorDefaultRef

Write-Host ""
Write-Host "rct-extractor-v2 installer (cardiology + malaria + HIV)" -ForegroundColor Cyan
Write-Host ""

if ($SkipClone) {
    Write-Step "Skipping clone (-SkipClone); using existing checkout at $Target"
    if (-not (Test-ExtractorPresent -Dir $Target)) {
        Write-Host "ERROR: -SkipClone but no extractor at $Target (missing scripts\build_metakit_config.py)." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Step "Installing extractor into $Target (ref: $($ref.Substring(0,[Math]::Min(12,$ref.Length))))"
    $parent = Split-Path -Parent $Target
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Install-ExtractorClone -TargetDir $Target -Ref $ref
    if (-not (Test-ExtractorPresent -Dir $Target)) {
        Write-Host "ERROR: clone completed but $Target\scripts\build_metakit_config.py is missing." -ForegroundColor Red
        exit 1
    }
    Write-Ok "checkout ready"
}

Write-Step "Persisting RCT_EXTRACTOR_PATH (User env var)"
Set-ExtractorPathEnv -TargetDir $Target
Write-Ok "RCT_EXTRACTOR_PATH = $Target"

Write-Step "Verifying the core (text -> config) path imports"
try { Assert-RealPython } catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
if (Test-ExtractorImport -TargetDir $Target) {
    Write-Ok "core import OK (stdlib-only path verified)"
} else {
    Write-Host "    WARNING: core import check did not return ok." -ForegroundColor Yellow
}

if ($WithPdfDeps) {
    Write-Step "Installing PDF + scientific deps (-WithPdfDeps)"
    try { Install-ExtractorPdfDeps -TargetDir $Target; Write-Ok "PDF deps installed" }
    catch { Write-Host "    WARNING: PDF deps failed; the core text->config path still works." -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  rct-extractor-v2 installed at $Target"
Write-Host "  RCT_EXTRACTOR_PATH is set (reopen PowerShell to pick it up)."
Write-Host ""
Write-Host "  Use it from a meta-system repo (bridge auto-finds it):"
Write-Host "    python extractor_bridge\extract_meta.py records.json --out config.json"
Write-Host "  Or directly:"
Write-Host "    python `"$Target\scripts\build_metakit_config.py`" records.json --out config.json"
Write-Host ""
Write-Host "  Topics auto-detected: cardiology, malaria, hiv."
if (-not $WithPdfDeps) {
    Write-Host "  For local PDF parsing later:  .\scripts\install-extractor.ps1 -WithPdfDeps"
}
Write-Host "======================================================" -ForegroundColor Green

exit 0
