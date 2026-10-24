#Requires -Version 5.1
# install-meta-harness.ps1 - OPTIONAL: fetch a published meta-harness release and
# verify it against the release's SHA256SUMS before unpacking anything.
#
# The meta-harness is NOT vendored into this starter. This downloads the release
# asset named by a tag from github.com/mahmood726-cyber/meta-harness, checks its
# sha256 against the SHA256SUMS published beside it, and only then unpacks it.
# Fail-closed: a missing asset, a missing SHA256SUMS line or a digest mismatch
# stops before anything is unpacked. See docs\meta-harness.md.
#
# Usage:
#   .\scripts\install-meta-harness.ps1                  # fetch v1.0.0 into ~\code\meta-harness-v1.0.0
#   .\scripts\install-meta-harness.ps1 -Target C:\code\meta-harness
#   .\scripts\install-meta-harness.ps1 -Ref v1.0.0
#   .\scripts\install-meta-harness.ps1 -Import          # dot-source for tests
#
# Env overrides: META_HARNESS_REF (tag), META_HARNESS_BASE_URL (release download base).

[CmdletBinding()]
param(
    [string]$Target,
    [string]$Ref,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

$script:MetaHarnessDefaultRef = 'v1.0.0'
function Get-MetaHarnessDefaultRef {
    if ($env:META_HARNESS_REF) { return $env:META_HARNESS_REF }
    return $script:MetaHarnessDefaultRef
}
function Get-MetaHarnessAssetName { param([string]$Tag) return "meta-harness-$Tag.zip" }
function Get-MetaHarnessBaseUrl {
    param([string]$Tag)
    if ($env:META_HARNESS_BASE_URL) { return $env:META_HARNESS_BASE_URL }
    return "https://github.com/mahmood726-cyber/meta-harness/releases/download/$Tag"
}
function Get-MetaHarnessDefaultTarget { param([string]$Tag) return (Join-Path $env:USERPROFILE "code\meta-harness-$Tag") }

function Test-MetaHarnessPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path (Join-Path $Dir 'scripts\replay_offline.py')))
}

# Return the SHA only when exactly one canonical SHA256SUMS record names this
# asset. Duplicate or malformed matching records are REFUSALS, not fallbacks to
# the first digest (including when the second line uses the GNU '*' marker).
function Get-MetaHarnessExpectedSha {
    param([string]$SumsPath, [string]$Name)
    $matches = 0
    $malformed = $false
    $digest = $null
    foreach ($line in (Get-Content -LiteralPath $SumsPath)) {
        $parts = ($line.TrimEnd("`r")) -split '\s+', 2
        if ($parts.Count -ne 2) { continue }
        if ($parts[1] -cne $Name -and $parts[1] -cne "*$Name") { continue }
        $matches++
        if ($parts[0] -cnotmatch '^[0-9a-f]{64}$') {
            $malformed = $true
        } else {
            $digest = $parts[0]
        }
    }
    if ($matches -eq 0) { return $null }
    if ($matches -ne 1 -or $malformed) {
        throw "REFUSED: SHA256SUMS has duplicate or malformed entries for $Name"
    }
    return $digest
}

function Test-MetaHarnessAsset {
    param([string]$ZipPath, [string]$SumsPath)
    $name = Split-Path $ZipPath -Leaf
    $expected = Get-MetaHarnessExpectedSha -SumsPath $SumsPath -Name $name
    if (-not $expected) { throw "REFUSED: SHA256SUMS has no line for $name" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "REFUSED: sha256 mismatch for $name (expected $expected, got $actual)" }
    Write-Host "  sha256 OK: $actual  $name" -ForegroundColor DarkGray
}

function Expand-MetaHarness {
    param([string]$ZipPath, [string]$TargetDir)
    if ((Test-Path $TargetDir) -and (Get-ChildItem -Force $TargetDir | Select-Object -First 1)) {
        throw "REFUSED: $TargetDir exists and is not empty"
    }
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("mh-" + [guid]::NewGuid())
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $tmp
    $tops = @(Get-ChildItem -Force $tmp)
    $src = if ($tops.Count -eq 1 -and $tops[0].PSIsContainer) { $tops[0].FullName } else { $tmp }
    New-Item -ItemType Directory -Force (Split-Path $TargetDir -Parent) | Out-Null
    if (Test-Path $TargetDir) { Remove-Item -LiteralPath $TargetDir }
    Move-Item -LiteralPath $src -Destination $TargetDir
    if (Test-Path $tmp) { Remove-Item -Recurse -Force -LiteralPath $tmp }
}

if ($Import) { return }

# === Real flow =============================================================
if (-not $Ref) { $Ref = Get-MetaHarnessDefaultRef }
$asset = Get-MetaHarnessAssetName -Tag $Ref
$base = Get-MetaHarnessBaseUrl -Tag $Ref
if (-not $Target) { $Target = Get-MetaHarnessDefaultTarget -Tag $Ref }

Write-Host ''
Write-Host 'meta-harness release fetch (optional layer; nothing is vendored into the starter)'
Write-Host "==> release ${Ref}: $base/$asset"

$work = Join-Path ([IO.Path]::GetTempPath()) ("mh-dl-" + [guid]::NewGuid())
New-Item -ItemType Directory $work | Out-Null
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -UseBasicParsing -Uri "$base/SHA256SUMS" -OutFile (Join-Path $work 'SHA256SUMS')
    Invoke-WebRequest -UseBasicParsing -Uri "$base/$asset" -OutFile (Join-Path $work $asset)
    Write-Host "==> verifying against the release's SHA256SUMS"
    Test-MetaHarnessAsset -ZipPath (Join-Path $work $asset) -SumsPath (Join-Path $work 'SHA256SUMS')
    Write-Host "==> unpacking into $Target"
    Expand-MetaHarness -ZipPath (Join-Path $work $asset) -TargetDir $Target
} finally {
    Remove-Item -Recurse -Force -LiteralPath $work -ErrorAction SilentlyContinue
}
if (-not (Test-MetaHarnessPresent $Target)) {
    Write-Host "REFUSED: unpacked, but $Target\scripts\replay_offline.py is missing." -ForegroundColor Red; exit 1
}

Write-Host ''
Write-Host '====================================================='
Write-Host "  meta-harness $Ref unpacked at $Target (sha256 verified)"
Write-Host '  This is a download without git history: replay a review OFFLINE with'
Write-Host "    cd `"$Target`""
Write-Host '    python -m pip install --require-hashes -r docs/offline/requirements.lock'
Write-Host '    python scripts/replay_offline.py dpp4-mace-t2d'
Write-Host '  (scripts/reproduce_review.py needs a git clone -- see docs\meta-harness.md.)'
Write-Host '====================================================='
exit 0
