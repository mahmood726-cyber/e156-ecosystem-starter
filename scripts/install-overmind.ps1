#Requires -Version 5.1
# install-overmind.ps1 -- install the Overmind verifier (incl. TruthCert engine)
#
# Overmind is the portfolio-wide verifier. It runs test suites + smoke checks
# + numerical baselines + TruthCert (HMAC-signed certification bundle) against
# a repo and emits a verdict: PASS / FAIL / UNVERIFIED / REJECT.
#
# Usage:
#   .\scripts\install-overmind.ps1               # pip install + prompt for HMAC key
#   .\scripts\install-overmind.ps1 -SkipPipInstall
#   .\scripts\install-overmind.ps1 -HmacKey <pre-generated>
#   .\scripts\install-overmind.ps1 -Import       # dot-source for tests

[CmdletBinding()]
param(
    [switch]$SkipPipInstall,
    [string]$HmacKey,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Assert-RealPython {
    # Defends against the Microsoft Store python.exe stub on Windows 10/11.
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
  2. Run the installer, tick 'Add python.exe to PATH'.
  3. Close and reopen PowerShell.
  4. Re-run this script.

Optional: Settings > Apps > Advanced app settings > App execution
aliases > toggle off python.exe and python3.exe
"@
    }
}

function Test-OvermindInstalled {
    $null = Get-Command overmind -ErrorAction SilentlyContinue
    return $?
}

function Install-OvermindPackage {
    [CmdletBinding()]
    param([string]$Source = 'git+https://github.com/mahmood726-cyber/overmind.git')
    # BANDWIDTH TRIPWIRE (set 2026-04-21): Overmind + Sentinel fresh-install
    # measured at 4.5 MB total. If a future Overmind release adds heavy deps
    # (numpy / scipy / torch / pandas) and the footprint passes ~50 MB, add a
    # `--estimate-mb` preflight that runs `pip install --dry-run --report`
    # first and prompts the student to confirm. See review-findings.md P0-2.
    & python -m pip install --quiet --disable-pip-version-check $Source 2>&1 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed (exit $LASTEXITCODE). Check your Python/pip setup."
    }
}

function New-TruthCertHmacKey {
    # 32 bytes of crypto-grade random, hex-encoded -> 64 hex chars.
    # Mirrors what TruthCert expects (any high-entropy string works; hex is
    # copy-paste safe across shells).
    [CmdletBinding()]
    param()
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

function Set-TruthCertHmacKey {
    [CmdletBinding()]
    param(
        [string]$Key,
        [ValidateSet('User', 'Process')][string]$Scope = 'User'
    )
    if ([string]::IsNullOrWhiteSpace($Key)) {
        throw "HMAC key is empty."
    }
    if ($Scope -eq 'User') {
        [Environment]::SetEnvironmentVariable('TRUTHCERT_HMAC_KEY', $Key, 'User')
    }
    # Always also set Process scope so the current shell sees it without restart
    [Environment]::SetEnvironmentVariable('TRUTHCERT_HMAC_KEY', $Key, 'Process')
    $env:TRUTHCERT_HMAC_KEY = $Key
}

if ($Import) { return }

# === Real flow =============================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

Write-Host ""
Write-Host "Overmind + TruthCert installer" -ForegroundColor Cyan
Write-Host ""

# Step 1: ensure overmind is on PATH
Write-Step "Checking for overmind CLI"
if (Test-OvermindInstalled) {
    Write-Ok "overmind already installed"
} else {
    if ($SkipPipInstall) {
        Write-Host "ERROR: overmind not on PATH and -SkipPipInstall passed." -ForegroundColor Red
        Write-Host "  Install: pip install git+https://github.com/mahmood726-cyber/overmind.git"
        exit 1
    }
    Write-Step "Installing overmind (first-time setup)"
    try { Assert-RealPython } catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
    Install-OvermindPackage
    if (-not (Test-OvermindInstalled)) {
        Write-Host "ERROR: pip install completed but overmind is still not on PATH." -ForegroundColor Red
        Write-Host "  Restart PowerShell or add Python Scripts dir to PATH."
        exit 1
    }
    Write-Ok "overmind installed"
}

# Step 2: TRUTHCERT_HMAC_KEY
Write-Step "Setting TRUTHCERT_HMAC_KEY"
$existing = [Environment]::GetEnvironmentVariable('TRUTHCERT_HMAC_KEY', 'User')
if ($existing -and -not $HmacKey) {
    Write-Ok "User env var TRUTHCERT_HMAC_KEY already set (length: $($existing.Length))"
    Write-Host "    Use -HmacKey <new> to rotate." -ForegroundColor DarkGray
    Set-TruthCertHmacKey -Key $existing -Scope Process   # sync to current shell
} else {
    $key = if ($HmacKey) { $HmacKey } else { New-TruthCertHmacKey }
    Set-TruthCertHmacKey -Key $key -Scope User
    if ($HmacKey) {
        Write-Ok "User env var TRUTHCERT_HMAC_KEY set from argument"
    } else {
        Write-Ok "Generated new 64-hex-char HMAC key and saved to User env"
    }
    Write-Host "    Back it up somewhere safe -- losing this key invalidates all prior signed bundles." -ForegroundColor Yellow
}

# Step 3: quick sanity check
Write-Step "overmind meta-verify (canary)"
$canary = & overmind meta-verify 2>&1
$canary | Select-Object -First 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
if ($LASTEXITCODE -ne 0) {
    Write-Warning "overmind meta-verify returned non-zero ($LASTEXITCODE). Not necessarily fatal, but review above."
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Overmind + TruthCert ready. Typical use:"
Write-Host "    overmind scan --repo C:\Projects\my-paper"
Write-Host "    overmind run-once --repo C:\Projects\my-paper"
Write-Host "    overmind portfolio-audit"
Write-Host "======================================================" -ForegroundColor Green

exit 0
