#Requires -Version 5.1
# install-extractor.ps1 - install the rct-extractor-v2 RCT data extractor
#
# The extractor (17 disease specialties: HIV, malaria, typhoid, schistosomiasis,
# sickle cell, cholera, maternal/neonatal, TB, hepatitis, meningitis, pneumonia,
# diarrhoeal, malnutrition, helminths, hypertension, cervical cancer, diabetes)
# turns trial PDFs / abstract text into the meta-starter-kit config the rest of
# the ecosystem consumes. This clones it at a pinned commit and persists
# RCT_EXTRACTOR_PATH so the meta-system bridges (extractor_bridge\extract_meta.py)
# auto-find it. The installed clone also ships the `rct-extract` CLI and the
# `rct_extractor` Python package (see README "Install & use").
#
# The student's core path -- trial text in, config out -- is STDLIB-ONLY.
# Heavy PDF + scientific deps (numpy/scipy/pdfplumber/pymupdf, ~150 MB) are
# OPT-IN via -WithPdfDeps.
#
# Usage:
#   .\scripts\install-extractor.ps1                       # clone to ~\code\rct-extractor-v2 (core only)
#   .\scripts\install-extractor.ps1 -Target "$env:USERPROFILE\code\rct-extractor-v2"
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

# Known-good extractor commit (all 17 disease specialties; packaged as the
# pip-installable `rct_extractor` lib + `rct-extract` CLI; 1343 tests green).
# Pinned to the v1.0.0 release tag (the reviewed/fixed build) for reproducible
# installs -- same supply-chain approach as Sentinel / Overmind. Override with
# $env:RCT_EXTRACTOR_REF.
$script:ExtractorDefaultRef = 'v1.0.0'

function Get-ExtractorDefaultRef {
    if ($env:RCT_EXTRACTOR_REF) { return $env:RCT_EXTRACTOR_REF }
    return $script:ExtractorDefaultRef
}

function Test-ExtractorPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'scripts\build_metakit_config.py')))
}

function Invoke-ExtractorGit {
    param([string[]]$GitArguments)
    $python = Get-Command python -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $transport = Join-Path $PSScriptRoot 'bounded_native.py'
    if (-not (Test-Path -LiteralPath $transport -PathType Leaf)) {
        throw 'REFUSED: required bounded extractor Git transport is missing'
    }
    $output = & $python.Source $transport git -c credential.interactive=false @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'REFUSED: extractor Git operation failed; no successful installation claimed'
    }
    return $output
}

function Install-ExtractorClone {
    [CmdletBinding()]
    param([string]$TargetDir, [string]$Ref)
    # Git ref arguments must never be interpreted as command-line options.
    if ([string]::IsNullOrWhiteSpace($Ref) -or
        $Ref -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$' -or
        $Ref.Contains('..') -or $Ref.Contains('//') -or $Ref.EndsWith('/')) {
        throw "REFUSED: invalid extractor Git ref"
    }

    $url = Get-ExtractorRepoUrl
    $targetFull = [IO.Path]::GetFullPath($TargetDir)
    $hasGit = Test-Path -LiteralPath (Join-Path $targetFull '.git') -PathType Container
    $stage = $null
    if (-not $hasGit -and (Test-Path -LiteralPath $targetFull)) {
        throw "REFUSED: extractor target exists but is not a Git checkout: $targetFull"
    }

    try {
        if ($hasGit) {
            $checkout = $targetFull
            Write-Host "  existing checkout: $checkout (fetch + verify $Ref)" -ForegroundColor DarkGray
        } else {
            # An unavailable ref must not leave an apparently installed clone.
            $parent = Split-Path -Parent $targetFull
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
            $stage = Join-Path $parent ('.extractor-stage-' + [guid]::NewGuid().ToString('N'))
            Write-Host "  preparing requested release in temporary checkout" -ForegroundColor DarkGray
            $null = Invoke-ExtractorGit @('init', '--quiet', $stage)
            $null = Invoke-ExtractorGit @('-C', $stage, 'remote', 'add', 'origin', $url)
            $checkout = $stage
        }

        # The release contains paths longer than Win32's legacy MAX_PATH.
        # Keep this setting local to the extractor, never change global Git.
        $null = Invoke-ExtractorGit @('-C', $checkout, 'config', 'core.longpaths', 'true')
        # FETCH_HEAD refers to the exact newly fetched request, not a
        # potentially stale local tag/branch in an existing installation.
        Write-Host "  fetching requested ref (120-second command deadline)" -ForegroundColor DarkGray
        try {
            $null = Invoke-ExtractorGit @('-C', $checkout, 'fetch', '--quiet', '--depth=1', 'origin', $Ref)
        } catch {
            throw "REFUSED: requested extractor Git ref unavailable: $Ref"
        }

        $resolved = Invoke-ExtractorGit @('-C', $checkout, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}')
        if (-not $resolved -or
            ([string]$resolved).Trim() -cnotmatch '^[0-9a-fA-F]{40}$') {
            throw "REFUSED: requested extractor ref did not resolve to a commit: $Ref"
        }
        $resolved = ([string]$resolved).Trim()
        Write-Host "  checking out verified commit" -ForegroundColor DarkGray
        $null = Invoke-ExtractorGit @('-C', $checkout, 'checkout', '--quiet', '--detach', $resolved)
        $actual = Invoke-ExtractorGit @('-C', $checkout, 'rev-parse', '--verify', 'HEAD')
        if (-not $actual -or
            ([string]$actual).Trim() -ne $resolved) {
            throw "REFUSED: extractor HEAD did not match requested commit $resolved"
        }

        if ($stage) {
            Move-Item -LiteralPath $stage -Destination $targetFull -ErrorAction Stop
            $stage = $null
        }
        Write-Host "  verified extractor commit: $resolved" -ForegroundColor DarkGray
    } finally {
        if ($stage -and (Test-Path -LiteralPath $stage)) {
            $stageFull = [IO.Path]::GetFullPath($stage)
            if (-not $stageFull.StartsWith($parent + [IO.Path]::DirectorySeparatorChar,
                    [StringComparison]::OrdinalIgnoreCase) -or
                (Split-Path -Leaf $stageFull) -notmatch '^\.extractor-stage-[0-9a-f]{32}$') {
                throw 'REFUSED: extractor cleanup path escaped its staging parent'
            }
            Remove-Item -LiteralPath $stageFull -Recurse -Force -ErrorAction Stop
        }
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
# prove this is the 17-specialty build, not the old cardio+malaria+HIV one
assert detect_specialty('empagliflozin in type 2 diabetes lowered HbA1c')[0] == 'diabetes'
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
Write-Host "rct-extractor-v2 installer (17 disease specialties)" -ForegroundColor Cyan
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
Write-Host "  Or the new unified CLI (after `pip install `"$Target`"):"
Write-Host "    rct-extract --list-specialties"
Write-Host "    rct-extract --specialty diabetes --input abstract.txt"
Write-Host "    rct-extract --auto --input ./corpus --json -o results.jsonl"
Write-Host ""
Write-Host "  17 specialties auto-detected: hiv, malaria, typhoid, schistosomiasis,"
Write-Host "    sickle_cell, cholera, maternal_neonatal, tuberculosis, hepatitis,"
Write-Host "    meningitis, pneumonia, diarrhoeal, malnutrition, helminths,"
Write-Host "    hypertension, cervical_cancer, diabetes."
if (-not $WithPdfDeps) {
    Write-Host "  For local PDF parsing later:  .\scripts\install-extractor.ps1 -WithPdfDeps"
}
Write-Host "======================================================" -ForegroundColor Green

exit 0
