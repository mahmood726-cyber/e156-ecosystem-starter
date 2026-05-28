#Requires -Version 5.1
# install-sentinel.ps1 - install Sentinel pre-push hook in a target repo
#
# Sentinel is the fail-closed rule engine that runs on `git push`. It
# catches the 20 portfolio-defect patterns (hardcoded paths, XSS sinks,
# empty-DataFrame access, placeholder HMAC, committed .claude/ configs,
# SHA-lockfile presence, etc.) BEFORE code leaves the laptop.
#
# Usage:
#   .\scripts\install-sentinel.ps1 -Repo C:\Projects\my-paper
#   .\scripts\install-sentinel.ps1 -Repo . -Mode block   # abort push on BLOCK (default: warn)
#   .\scripts\install-sentinel.ps1 -Repo . -SkipPipInstall
#   .\scripts\install-sentinel.ps1 -Import               # dot-source for tests

[CmdletBinding()]
param(
    [string]$Repo,
    [ValidateSet('warn', 'block')][string]$Mode = 'warn',
    [switch]$SkipPipInstall,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Test-SentinelInstalled {
    $null = Get-Command sentinel -ErrorAction SilentlyContinue
    return $?
}

function Assert-RealPython {
    # Defends against the Microsoft Store python.exe stub on Windows 10/11,
    # which is on PATH but is a 0-byte alias that exits non-zero when called.
    # Without this check pip install fails 6 lines deep with a confusing
    # "Python was not found" RemoteException.
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

Fix it:
  1. Download Python 3.11+ from https://www.python.org/downloads/
  2. Run the installer.
  3. CRITICAL: tick 'Add python.exe to PATH' on the first screen.
  4. Close and reopen PowerShell.
  5. Re-run this script.

Optional: also disable the Store alias in
  Settings > Apps > Advanced app settings > App execution aliases
"@
    }
}

# Known-good Sentinel commit (the 53-rule build: 21 BLOCK / 28 WARN / 4 INFO).
# v0.1.0 is stale (only ~12 rules); pin to this SHA until a newer semver tag
# ships. Same "pin to a known-good commit" approach used for Overmind.
$script:SentinelDefaultRef = 'ebf065ccec049072d1b92b6ed20122581440e959'

function Get-SentinelDefaultSource {
    # Pinned to a known-good commit by default so a fresh install is reproducible.
    # Override with $env:SENTINEL_REF=main (or any branch/tag/SHA) to opt into
    # bleeding-edge or to roll back if a future release breaks something.
    $ref = if ($env:SENTINEL_REF) { $env:SENTINEL_REF } else { $script:SentinelDefaultRef }
    return "git+https://github.com/mahmood726-cyber/Sentinel.git@$ref"
}

function Install-SentinelPackage {
    [CmdletBinding()]
    param(
        [string]$Source
    )
    if (-not $Source) { $Source = Get-SentinelDefaultSource }
    # Non-interactive pip install. Students on shared machines don't need admin
    # if they're in a venv or using --user; we let pip pick.
    #
    # BANDWIDTH TRIPWIRE (set 2026-04-21): measured Sentinel + Overmind fresh
    # install footprint = 4.5 MB total. That's below the threshold where any
    # preflight UX warning helps. IF a future dependency bump pushes Sentinel
    # alone past ~50 MB (e.g. adding numpy / scipy / torch), add an
    # `--estimate-mb` preflight here that runs `pip install --dry-run --report`
    # against $Source first and prompts the student to confirm before
    # downloading. See review-findings.md P0-2 for the original measurement.
    Write-Host "  source: $Source" -ForegroundColor DarkGray
    & python -m pip install --quiet --disable-pip-version-check $Source 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed (exit $LASTEXITCODE). Check your Python/pip setup."
    }
}

function Backup-ExistingPrePushHook {
    # If the target repo already has a pre-push hook (eg the researcher has
    # their own lint hook), back it up to pre-push.user-<timestamp> before
    # we let upstream `sentinel install-hook` overwrite it. The upstream
    # CLI may or may not preserve user content; this wrapper guarantees a
    # rollback path either way.
    [CmdletBinding()]
    param([string]$RepoPath)
    $hookPath = Join-Path $RepoPath '.git\hooks\pre-push'
    if (-not (Test-Path $hookPath)) { return $null }
    # Detect Sentinel-installed hooks (which carry a known marker) so we
    # don't churn backups on every re-install.
    $existing = Get-Content -Raw -Path $hookPath -ErrorAction SilentlyContinue
    if ($existing -and $existing -match 'sentinel\s+(scan|run-pre-push)') { return $null }
    $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = "$hookPath.user-$ts"
    Copy-Item -Path $hookPath -Destination $backup -Force
    return $backup
}

function Install-SentinelHookInRepo {
    [CmdletBinding()]
    param(
        [string]$RepoPath,
        [string]$HookMode = 'warn'
    )
    $abs = (Resolve-Path $RepoPath -ErrorAction Stop).Path
    if (-not (Test-Path (Join-Path $abs '.git'))) {
        throw "Not a git repo (no .git/): $abs"
    }
    $backup = Backup-ExistingPrePushHook -RepoPath $abs
    if ($backup) {
        Write-Host "  Backed up existing pre-push hook to: $backup" -ForegroundColor Yellow
        Write-Host "  If you want to chain it with Sentinel, see:" -ForegroundColor DarkGray
        Write-Host "    https://github.com/mahmood726-cyber/Sentinel#chaining-with-existing-hooks" -ForegroundColor DarkGray
    }
    $out = & sentinel install-hook --repo $abs --mode $HookMode 2>&1
    $out | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) {
        throw "sentinel install-hook failed (exit $LASTEXITCODE)"
    }
    return $abs
}

function Get-SentinelBypassLogPath {
    $userHome = $env:USERPROFILE
    if (-not $userHome) { $userHome = $HOME }
    return Join-Path $userHome '.sentinel-logs\bypass.log'
}

if ($Import) { return }   # dot-sourced by tests

# === Real flow =============================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Repo) {
    Write-Host "ERROR: -Repo is required. Example:" -ForegroundColor Red
    Write-Host "  .\scripts\install-sentinel.ps1 -Repo ."
    exit 1
}

Write-Host ""
Write-Host "Sentinel pre-push hook installer" -ForegroundColor Cyan
Write-Host ""

# Step 1: is sentinel on PATH?
Write-Step "Checking for sentinel CLI"
if (Test-SentinelInstalled) {
    $ver = (& sentinel --help 2>&1 | Select-String 'usage: sentinel').ToString().Trim()
    Write-Ok "sentinel already installed"
} else {
    if ($SkipPipInstall) {
        Write-Host "ERROR: sentinel not on PATH and -SkipPipInstall passed." -ForegroundColor Red
        Write-Host "  Install manually: pip install $(Get-SentinelDefaultSource)"
        exit 1
    }
    Write-Step "Installing sentinel from GitHub (first-time setup)"
    try { Assert-RealPython } catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
    Install-SentinelPackage
    if (-not (Test-SentinelInstalled)) {
        Write-Host "ERROR: pip install completed but sentinel is still not on PATH." -ForegroundColor Red
        Write-Host "  You may need to restart PowerShell or add Python Scripts to PATH."
        exit 1
    }
    Write-Ok "sentinel installed"
}

# Step 2: install hook
Write-Step "Installing pre-push hook in $Repo (mode: $Mode)"
$installed = Install-SentinelHookInRepo -RepoPath $Repo -HookMode $Mode
Write-Ok "hook installed at $installed\.git\hooks\pre-push"

# Step 3: bypass-log path
$bypassLog = Get-SentinelBypassLogPath
Write-Host ""
Write-Host "Bypass log: $bypassLog" -ForegroundColor DarkGray
Write-Host "  Use only when a BLOCK is a false positive:"
Write-Host "    `$env:SENTINEL_BYPASS = '1'; git push; `$env:SENTINEL_BYPASS = `$null"
Write-Host "  Each bypass is logged (log path cannot be redirected to NUL)."

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Sentinel hook installed. It fires on every git push."
Write-Host "  List rules:   sentinel list-rules"
Write-Host "  Scan ad-hoc:  sentinel scan --repo $installed"
Write-Host "  Uninstall:    sentinel uninstall-hook --repo $installed"
Write-Host "======================================================" -ForegroundColor Green

exit 0
