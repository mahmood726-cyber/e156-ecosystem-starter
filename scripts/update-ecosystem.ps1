#Requires -Version 5.1
# update-ecosystem.ps1 -- pull the latest ecosystem-starter and re-run install.
#
# Scoop has `scoop update`; Chocolatey has `choco upgrade`; this is the
# ecosystem equivalent. Downloads the current main.zip to %TEMP%, extracts,
# runs install.ps1 with -Force -NonInteractive. Existing memory is preserved
# by design (Copy-MemoryScaffold short-circuits on non-empty dirs); rules and
# context files are re-copied with .user backups of any local edits.
#
# Usage:
#   .\scripts\update-ecosystem.ps1
#   .\scripts\update-ecosystem.ps1 -Ref v0.7.0          # pin to a tag instead of main
#   .\scripts\update-ecosystem.ps1 -Ref main -Full       # also re-chain Sentinel/Overmind/ProjectIndex
#   .\scripts\update-ecosystem.ps1 -Import               # dot-source for tests

[CmdletBinding()]
param(
    [string]$Ref = 'main',
    [switch]$Full,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Resolve-DownloadUrl {
    [CmdletBinding()]
    param([string]$RefName)
    # GitHub serves any branch or tag under .../archive/refs/heads/<branch>.zip
    # or .../archive/refs/tags/<tag>.zip. Tag-refs start with 'v'.
    if ($RefName -match '^v\d') {
        return "https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/tags/$RefName.zip"
    }
    return "https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/$RefName.zip"
}

function Get-UpdateWorkspace {
    [CmdletBinding()]
    param()
    return Join-Path $env:TEMP ("e156-update-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}

function Get-ExpectedExtractRoot {
    [CmdletBinding()]
    param([string]$RefName, [string]$Workspace)
    # github.com's archive strips the leading 'v' on tags when naming the
    # extract dir: e156-ecosystem-starter-0.7.0 (not e156-...-v0.7.0).
    $suffix = if ($RefName -match '^v(\d.*)$') { $Matches[1] } else { $RefName }
    return Join-Path $Workspace ("e156-ecosystem-starter-" + $suffix)
}

if ($Import) { return }

# === Real flow =============================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

Write-Host ""
Write-Host "e156-ecosystem-starter update" -ForegroundColor Cyan
Write-Host "  Ref: $Ref"
Write-Host ""

$workspace = Get-UpdateWorkspace
New-Item -ItemType Directory -Force -Path $workspace | Out-Null

Write-Step "Downloading $Ref..."
$url = Resolve-DownloadUrl -RefName $Ref
$zip = Join-Path $workspace 'update.zip'
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -ErrorAction Stop
} catch {
    Write-Host "ERROR: download failed ($($_.Exception.Message))" -ForegroundColor Red
    Remove-Item -Recurse -Force $workspace -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "downloaded to $zip"

Write-Step "Extracting..."
try {
    Expand-Archive -Path $zip -DestinationPath $workspace -Force -ErrorAction Stop
} catch {
    Write-Host "ERROR: extract failed ($($_.Exception.Message))" -ForegroundColor Red
    Remove-Item -Recurse -Force $workspace -ErrorAction SilentlyContinue
    exit 1
}

$extractRoot = Get-ExpectedExtractRoot -RefName $Ref -Workspace $workspace
if (-not (Test-Path (Join-Path $extractRoot 'install\install.ps1'))) {
    Write-Host "ERROR: extracted layout unexpected. Looking for $extractRoot\install\install.ps1" -ForegroundColor Red
    Remove-Item -Recurse -Force $workspace -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "extracted to $extractRoot"

Write-Step "Re-running install.ps1 -Force -NonInteractive"
$installArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-File', (Join-Path $extractRoot 'install\install.ps1'),
                 '-Force', '-NonInteractive')
if ($Full) { $installArgs += '-Full' }

& powershell @installArgs
$installExit = $LASTEXITCODE

# Keep the workspace if install failed so the student can inspect
if ($installExit -eq 0) {
    Remove-Item -Recurse -Force $workspace -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "Update complete." -ForegroundColor Green
    Write-Host "  Your memory was preserved. Rules and context files were refreshed."
    Write-Host "  Any local edits to rules/*.md are backed up as *.user."
    exit 0
} else {
    Write-Host ""
    Write-Host "Install re-run exited $installExit." -ForegroundColor Yellow
    Write-Host "  Workspace kept at: $workspace"
    Write-Host "  (install.ps1's own rollback should have restored prior state;"
    Write-Host "   this workspace is just the downloaded zip, safe to delete.)"
    exit $installExit
}
