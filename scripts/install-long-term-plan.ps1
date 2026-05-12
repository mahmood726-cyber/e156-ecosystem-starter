#Requires -Version 5.1
# install-long-term-plan.ps1 -- clone Mahmood's long-term-plan tool to a
# student's machine.
#
# long-term-plan is a weekly-refreshed, deterministic, locally-rendered project
# backlog (no LLM in the loop). The published repo at mahmood726-cyber/long-term-plan
# ships:
#   - scripts/weekly_plan_update.py      reranker + --pick / --add CLI
#   - scripts/mcp_server.py              local MCP server (9 tools)
#   - scripts/portfolio_state.py         + render.py + rerank.py + schema.py
#   - ideas.yaml / objectives.yaml /     Mahmood's real backlog as a reference;
#     north_star_tags.yaml / weights.yaml  fork or replace with your own.
#   - LICENSE-less by design: this is curated working-process documentation,
#     not a library — clone, fork, edit.
#
# Why this installer exists instead of `pip install`:
#   - the repo has no setup.py / pyproject — the tool is plain Python scripts
#     intended to be edited in place. Cloning is the right primitive.
#   - the only runtime dep is `pyyaml`, which we install for the student.
#
# Usage:
#   .\scripts\install-long-term-plan.ps1
#   .\scripts\install-long-term-plan.ps1 -Root C:\ProjectIndex\long-term-plan
#   .\scripts\install-long-term-plan.ps1 -Ref v0.7.0 -Force
#   .\scripts\install-long-term-plan.ps1 -Import   # dot-source for tests

[CmdletBinding()]
param(
    [string]$Root,
    [string]$Ref,
    [switch]$Force,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

$script:LongTermPlanDefaultRef  = 'v0.7.0'
$script:LongTermPlanRepoUrl     = 'https://github.com/mahmood726-cyber/long-term-plan.git'

function Get-LongTermPlanDefaultRoot {
    # Default: <user-home>\code\long-term-plan
    # Mirrors install-projectindex.ps1's default so a student running
    # install.ps1 -Full and a student running install-long-term-plan.ps1
    # standalone land at the same path. Override with -Root.
    $userHome = $env:USERPROFILE
    if (-not $userHome) { $userHome = $HOME }
    return Join-Path $userHome 'code\long-term-plan'
}

function Get-LongTermPlanDefaultRef {
    # Pinned to a tagged release by default so a fresh install is reproducible.
    # Override with $env:LONG_TERM_PLAN_REF = 'main' (or any branch/tag/SHA) to
    # opt into bleeding-edge or to roll back if a future release breaks something.
    if ($env:LONG_TERM_PLAN_REF) { return $env:LONG_TERM_PLAN_REF }
    return $script:LongTermPlanDefaultRef
}

function Assert-RealPython {
    # Same Microsoft Store stub defence as install-sentinel.ps1.
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
"@
    }
}

function Assert-Git {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        throw @"
git is not on PATH.

Install Git for Windows from https://git-scm.com/download/win, then close
and reopen PowerShell.
"@
    }
}

function Install-PyYamlIfMissing {
    # Idempotent: pip install --quiet pyyaml is a no-op when already present.
    # We don't pin a version; pyyaml's API has been stable for a decade.
    & python -m pip install --quiet --disable-pip-version-check pyyaml 2>&1 |
        ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) {
        throw "pip install pyyaml failed (exit $LASTEXITCODE). Check your Python/pip setup."
    }
}

function Test-IsLongTermPlanRepo {
    # Heuristic: a long-term-plan clone has both scripts/weekly_plan_update.py
    # and ideas.yaml at its root. We use this to decide whether to `git fetch`
    # into an existing dir vs. `git clone` afresh.
    [CmdletBinding()]
    param([string]$Path)
    if (-not (Test-Path (Join-Path $Path 'scripts\weekly_plan_update.py'))) { return $false }
    if (-not (Test-Path (Join-Path $Path 'ideas.yaml'))) { return $false }
    if (-not (Test-Path (Join-Path $Path '.git'))) { return $false }
    return $true
}

function Install-LongTermPlanClone {
    # Clone or update the repo at $Root, checked out to $Ref.
    # Idempotent: re-running with the same ref is a no-op git-fetch.
    [CmdletBinding()]
    param(
        [string]$Path,
        [string]$RefToCheckout
    )
    if (Test-IsLongTermPlanRepo -Path $Path) {
        Write-Host "  long-term-plan clone already present at $Path; updating" -ForegroundColor DarkGray
        Push-Location $Path
        try {
            & git fetch --tags --depth 1 origin $RefToCheckout 2>&1 |
                ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
            if ($LASTEXITCODE -ne 0) { throw "git fetch failed (exit $LASTEXITCODE)" }
            & git checkout --quiet $RefToCheckout 2>&1 |
                ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
            if ($LASTEXITCODE -ne 0) { throw "git checkout $RefToCheckout failed (exit $LASTEXITCODE)" }
        } finally {
            Pop-Location
        }
    } else {
        if (Test-Path $Path) {
            $children = Get-ChildItem -Force -Path $Path -ErrorAction SilentlyContinue
            if ($children) {
                throw @"
Target directory $Path already exists and is non-empty but is not a
long-term-plan clone. Refusing to clone over it.

Either pick a different -Root, or empty / remove $Path first.
"@
            }
        }
        & git clone --quiet --branch $RefToCheckout --depth 1 $script:LongTermPlanRepoUrl $Path 2>&1 |
            ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
        if ($LASTEXITCODE -ne 0) {
            throw "git clone failed (exit $LASTEXITCODE). Check network + ref name."
        }
    }
}

if ($Import) { return }   # dot-sourced by tests

# === Real flow =============================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Root) {
    $Root = Get-LongTermPlanDefaultRoot
    Write-Host "Using default -Root: $Root" -ForegroundColor DarkGray
}

# Path disambiguation: a relative input like 'plan' would otherwise resolve
# against CWD, which on a freshly-launched PowerShell is C:\WINDOWS\system32 --
# guaranteed PermissionDenied. Resolve relative inputs against $HOME\code\.
if ($Root -notmatch '^[A-Za-z]:[\\/]' -and $Root -notmatch '^\\\\') {
    $resolved = Join-Path (Join-Path $env:USERPROFILE 'code') $Root
    Write-Host "Relative path '$Root' interpreted as: $resolved" -ForegroundColor DarkGray
    $Root = $resolved
}

# Refuse system-protected roots.
$forbidden = @('C:\Windows', 'C:\Program Files', 'C:\Program Files (x86)', 'C:\ProgramData')
foreach ($f in $forbidden) {
    if ($Root -like "$f\*" -or $Root -eq $f) {
        Write-Host "Refusing to install into protected system path: $Root" -ForegroundColor Red
        Write-Host "Pick a path under $env:USERPROFILE." -ForegroundColor Red
        exit 1
    }
}

if (-not $Ref) { $Ref = Get-LongTermPlanDefaultRef }

Write-Host ""
Write-Host "long-term-plan installer" -ForegroundColor Cyan
Write-Host "Target: $Root"
Write-Host "Ref:    $Ref"
Write-Host ""

Write-Step "Checking prerequisites (python + git)"
try { Assert-RealPython; Assert-Git } catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
Write-Ok "python + git on PATH"

Write-Step "Installing pyyaml (long-term-plan's only runtime dep)"
Install-PyYamlIfMissing
Write-Ok "pyyaml ready"

Write-Step "Cloning / updating long-term-plan at $Root"
$parent = Split-Path -Parent $Root
if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
Install-LongTermPlanClone -Path $Root -RefToCheckout $Ref
Write-Ok "cloned at ref $Ref"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  long-term-plan installed at $Root"
Write-Host ""
Write-Host "  The published clone ships Mahmood's real backlog as a"
Write-Host "  REFERENCE. Build your own:"
Write-Host "    1. Edit $Root\ideas.yaml -- delete the seeded ideas,"
Write-Host "       add your own."
Write-Host "    2. Edit $Root\objectives.yaml -- replace the Q3-2026"
Write-Host "       milestones with yours."
Write-Host "    3. Edit $Root\north_star_tags.yaml -- replace with your"
Write-Host "       own north stars."
Write-Host ""
Write-Host "  Then weekly:"
Write-Host "    cd $Root"
Write-Host "    python scripts\weekly_plan_update.py"
Write-Host ""
Write-Host "  Flip an idea to in-progress:"
Write-Host "    python scripts\weekly_plan_update.py --pick <idea-id>"
Write-Host ""
Write-Host "  Add an idea inline:"
Write-Host "    python scripts\weekly_plan_update.py --add ""my new idea"""
Write-Host "======================================================" -ForegroundColor Green

exit 0
