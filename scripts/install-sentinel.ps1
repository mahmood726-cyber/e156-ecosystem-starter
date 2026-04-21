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

function Install-SentinelPackage {
    [CmdletBinding()]
    param(
        [string]$Source = 'git+https://github.com/mahmood726-cyber/Sentinel.git'
    )
    # Non-interactive pip install. Students on shared machines don't need admin
    # if they're in a venv or using --user; we let pip pick.
    & python -m pip install --quiet --disable-pip-version-check $Source 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed (exit $LASTEXITCODE). Check your Python/pip setup."
    }
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
        Write-Host "  Install manually: pip install git+https://github.com/mahmood726-cyber/Sentinel.git"
        exit 1
    }
    Write-Step "Installing sentinel from GitHub (first-time setup)"
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
