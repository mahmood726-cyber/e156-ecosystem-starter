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
    # A directory named replay_offline.py is not an executable replay entry point.
    return [bool]($Dir -and (Test-Path -LiteralPath (Join-Path $Dir 'scripts\replay_offline.py') -PathType Leaf))
}

# Accept precisely one well-formed record for the requested asset.  Do not
# silently take the first when a release SHA256SUMS has duplicate or malformed
# entries: the Bash installer deliberately refuses the same ambiguity.
# GNU binary-mode lines ("*filename") are accepted.
function Get-MetaHarnessExpectedSha {
    param([string]$SumsPath, [string]$Name)
    $matchingLines = 0
    $digest = $null
    foreach ($line in (Get-Content -LiteralPath $SumsPath)) {
        $parts = @($line.Trim() -split '\s+')
        if ($parts.Count -lt 2 -or
            ($parts[1] -cne $Name -and $parts[1] -cne "*$Name")) {
            continue
        }
        $matchingLines++
        if ($matchingLines -gt 1) {
            throw "REFUSED: SHA256SUMS has multiple entries for $Name"
        }
        if ($parts.Count -ne 2 -or $parts[0] -cnotmatch '^[0-9a-f]{64}$') {
            throw "REFUSED: SHA256SUMS has malformed entry for $Name"
        }
        $digest = $parts[0]
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

# Reject unsafe ZIP member names before Expand-Archive touches the filesystem.
# A matching SHA256SUMS digest alone does not make archive paths safe.
function Assert-MetaHarnessArchiveSafe {
    param([string]$ZipPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        # Windows paths are case-insensitive. Refuse multiple ZIP records that
        # would name the same destination before any files are extracted.
        $seen = @{}
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName
            if ([string]::IsNullOrEmpty($name) -or
                $name.StartsWith('/') -or $name.StartsWith([string][char]92) -or
                $name.Contains([string][char]92) -or $name.Contains(':') -or
                $name -match '[\x00-\x1f]') {
                throw "REFUSED: unsafe archive entry path"
            }
            foreach ($part in $name.TrimEnd('/').Split('/')) {
                if (-not $part -or $part -eq '.' -or $part -eq '..' -or
                    $part -match '[. ]$') {
                    throw "REFUSED: unsafe archive entry path"
                }
                # Device names remain reserved in every Windows directory.
                if ($part -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])([.].*)?$') {
                    throw "REFUSED: Windows reserved device name in archive"
                }
            }
            $key = $name.TrimEnd('/').ToUpperInvariant()
            if ($seen.ContainsKey($key)) {
                throw "REFUSED: duplicate or case-colliding archive entry"
            }
            $seen[$key] = $true
            # ZIP creator's POSIX file type is stored in the high 16 bits.
            $type = (($entry.ExternalAttributes -shr 16) -band 0xF000)
            if ($type -eq 0xA000) {
                throw "REFUSED: symlink entry in archive"
            }
        }
    } finally {
        $archive.Dispose()
    }
}

function Expand-MetaHarness {
    param([string]$ZipPath, [string]$TargetDir)
    $targetFull = [IO.Path]::GetFullPath($TargetDir)
    if ((Test-Path -LiteralPath $targetFull) -and
        (Get-ChildItem -LiteralPath $targetFull -Force | Select-Object -First 1)) {
        throw "REFUSED: $TargetDir exists and is not empty"
    }
    # Preserve the existing archive-path refusal before any extraction.
    Assert-MetaHarnessArchiveSafe -ZipPath $ZipPath
    $parent = Split-Path -Path $targetFull -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    # Stage beside the destination so the final move stays on the same volume.
    $tmp = Join-Path $parent (".mh-stage-" + [guid]::NewGuid().ToString('N'))
    try {
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $tmp
        $tops = @(Get-ChildItem -LiteralPath $tmp -Force)
        $src = if ($tops.Count -eq 1 -and $tops[0].PSIsContainer) { $tops[0].FullName } else { $tmp }
        # Never publish an archive missing the actual replay *file*.
        if (-not (Test-MetaHarnessPresent $src)) {
            throw "REFUSED: scripts/replay_offline.py is missing from staged archive"
        }
        if (Test-Path -LiteralPath $targetFull) { Remove-Item -LiteralPath $targetFull }
        Move-Item -LiteralPath $src -Destination $targetFull -ErrorAction Stop
    } finally {
        if (Test-Path -LiteralPath $tmp) {
            Remove-Item -Recurse -Force -LiteralPath $tmp
        }
    }
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
