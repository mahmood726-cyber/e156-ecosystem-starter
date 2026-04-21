#Requires -Version 5.1
# install.ps1 - e156-ecosystem-starter bootstrap (Windows)
#
# Turns your laptop into Mahmood's quality-dev environment. Installs:
#   - rules/*.md          -> ~/.claude/rules/ + ~/.gemini/rules/
#   - memory scaffolding  -> ~/.claude/rules/memory/ (starter MEMORY.md + templates)
#   - AGENTS.md, CLAUDE.md, GEMINI.md, CODEX.md as per-user global defaults
#
# Run from PowerShell (no admin needed):
#   .\install.ps1                 # full install
#   .\install.ps1 -DryRun         # just verify SHA gate, exit 0
#   .\install.ps1 -Force           # overwrite existing user files
#   .\install.ps1 -Import          # dot-source helpers only (used by tests)
#
# Non-negotiables (from AGENTS.md):
#   - Fails closed on missing source files
#   - Never overwrites user-filled memory without -Force
#   - Preserves existing rules/<name>.md when user has edited them (we append
#     a .starter backup rather than clobber)

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

# --- self-SHA verification --------------------------------------------------
if (-not $Import) {
    $hashFile = Join-Path $PSScriptRoot '..\docs\HASH.txt'
    if (-not (Test-Path $hashFile)) {
        Write-Host "ERROR: docs/HASH.txt not found. This zip may be damaged." -ForegroundColor Red
        Write-Host "Re-download from github.com/mahmood726-cyber/e156-ecosystem-starter/releases"
        exit 1
    }
    $expected = (Get-Content $hashFile -Raw).Trim().ToLower()
    $selfSha = (Get-FileHash -Algorithm SHA256 $PSCommandPath).Hash.ToLower()

    if ($expected -ne $selfSha) {
        Write-Host "ERROR: install.ps1 hash mismatch. File may have been tampered with." -ForegroundColor Red
        Write-Host "Expected: $expected"
        Write-Host "Got:      $selfSha"
        exit 1
    }

    if ($DryRun) {
        Write-Host "Dry run: self-SHA verified. Exiting before any install steps." -ForegroundColor Green
        exit 0
    }
}

# --- helpers (dot-sourceable) ----------------------------------------------

function Get-EcoStarterRoot {
    [CmdletBinding()]
    param()
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Copy-RulesToAgent {
    [CmdletBinding()]
    param(
        [string]$SourceRulesDir,
        [string]$TargetRulesDir,
        [switch]$Force
    )
    if (-not (Test-Path $SourceRulesDir)) {
        throw "Source rules dir not found: $SourceRulesDir"
    }
    New-Item -ItemType Directory -Force -Path $TargetRulesDir | Out-Null

    $copied = @()
    $backed = @()
    Get-ChildItem -Path $SourceRulesDir -Filter "*.md" | ForEach-Object {
        $dest = Join-Path $TargetRulesDir $_.Name
        if ((Test-Path $dest) -and -not $Force) {
            # Preserve any student edits by renaming their version to .user.md
            # and dropping our canonical in place.
            $backup = "$dest.user"
            if (-not (Test-Path $backup)) {
                Copy-Item $dest $backup
                $backed += $_.Name
            }
        }
        Copy-Item $_.FullName $dest -Force
        $copied += $_.Name
    }
    return [PSCustomObject]@{ Copied = $copied; Backed = $backed }
}

function Copy-ContextFiles {
    [CmdletBinding()]
    param(
        [string]$SourceRoot,
        [string]$TargetDir,
        [switch]$Force
    )
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    $results = @{}
    foreach ($name in @('AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'CODEX.md')) {
        $src = Join-Path $SourceRoot $name
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $TargetDir $name
        if ((Test-Path $dst) -and -not $Force) {
            $backup = "$dst.user"
            if (-not (Test-Path $backup)) { Copy-Item $dst $backup }
        }
        Copy-Item $src $dst -Force
        $results[$name] = $dst
    }
    return $results
}

function Copy-MemoryScaffold {
    [CmdletBinding()]
    param(
        [string]$SourceMemoryDir,
        [string]$TargetMemoryDir
    )
    # Memory is PRESERVED by default (student's ongoing work). We only drop
    # templates + initial MEMORY.md if the target is empty.
    New-Item -ItemType Directory -Force -Path $TargetMemoryDir | Out-Null
    $existingFiles = @(Get-ChildItem -Path $TargetMemoryDir -Filter "*.md" -ErrorAction SilentlyContinue)
    if ($existingFiles.Count -eq 0) {
        Copy-Item (Join-Path $SourceMemoryDir 'MEMORY.md') (Join-Path $TargetMemoryDir 'MEMORY.md')
        $tmplDir = Join-Path $TargetMemoryDir 'templates'
        New-Item -ItemType Directory -Force -Path $tmplDir | Out-Null
        Copy-Item (Join-Path $SourceMemoryDir 'templates\*.md') $tmplDir -Force
        return $true
    }
    return $false
}

function Test-ToolInstalled {
    [CmdletBinding()]
    param([string]$Cmd)
    $null = Get-Command $Cmd -ErrorAction SilentlyContinue
    return $?
}

if ($Import) { return }   # dot-sourced by tests -- no execution

# === Real install flow =====================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Warning $msg }

$starterRoot = Get-EcoStarterRoot
$userHome = $env:USERPROFILE
if (-not $userHome) { $userHome = $HOME }

Write-Host ""
Write-Host "e156-ecosystem-starter bootstrap" -ForegroundColor Cyan
Write-Host "Installing Mahmood's quality-dev environment to $userHome"
Write-Host ""

# --- Step 1: agent CLI detection -------------------------------------------

Write-Step "Detecting agent CLIs"
$foundClaude = Test-ToolInstalled -Cmd 'claude'
$foundGemini = Test-ToolInstalled -Cmd 'gemini'
$foundCodex = Test-ToolInstalled -Cmd 'codex'

if ($foundClaude) { Write-Ok "claude: found" } else { Write-Host "    claude: not on PATH (install: https://docs.anthropic.com/en/docs/claude-code)" -ForegroundColor DarkGray }
if ($foundGemini) { Write-Ok "gemini: found" } else { Write-Host "    gemini: not on PATH (install: https://github.com/google-gemini/gemini-cli)" -ForegroundColor DarkGray }
if ($foundCodex)  { Write-Ok "codex: found"  } else { Write-Host "    codex: not on PATH (install: https://github.com/openai/codex)" -ForegroundColor DarkGray }

if (-not ($foundClaude -or $foundGemini -or $foundCodex)) {
    Write-Warn2 "No agent CLI found. Install at least one of claude/gemini/codex, then re-run."
    Write-Host "  (We'll still copy rules + context files for when you do install.)" -ForegroundColor DarkGray
}

# --- Step 2: copy rules to each detected agent's config dir -----------------

Write-Step "Copying rules/*.md"
$sourceRules = Join-Path $starterRoot 'rules'

$claudeRulesDir = Join-Path $userHome '.claude\rules'
$geminiRulesDir = Join-Path $userHome '.gemini\rules'
$codexRulesDir  = Join-Path $userHome '.codex\rules'

foreach ($target in @($claudeRulesDir, $geminiRulesDir, $codexRulesDir)) {
    $r = Copy-RulesToAgent -SourceRulesDir $sourceRules -TargetRulesDir $target -Force:$Force
    Write-Ok "$target  ($($r.Copied.Count) files copied, $($r.Backed.Count) backed up as .user)"
}

# --- Step 3: drop context files (AGENTS.md / CLAUDE.md / GEMINI.md / CODEX.md)

Write-Step "Writing context files to ~/.claude, ~/.gemini, ~/.codex"
foreach ($dir in @((Join-Path $userHome '.claude'), (Join-Path $userHome '.gemini'), (Join-Path $userHome '.codex'))) {
    $r = Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $dir -Force:$Force
    Write-Ok "$dir  ($($r.Count) context files)"
}

# --- Step 4: memory scaffold (only if the target is empty) ------------------

Write-Step "Setting up memory scaffolding"
$sourceMemory = Join-Path $starterRoot 'memory'
$claudeMemoryDir = Join-Path $userHome '.claude\memory'
$geminiMemoryDir = Join-Path $userHome '.gemini\memory'

foreach ($target in @($claudeMemoryDir, $geminiMemoryDir)) {
    $bootstrapped = Copy-MemoryScaffold -SourceMemoryDir $sourceMemory -TargetMemoryDir $target
    if ($bootstrapped) {
        Write-Ok "$target  (bootstrapped -- starter MEMORY.md + 4 templates)"
    } else {
        Write-Ok "$target  (already has memory -- preserved, templates not overwritten)"
    }
}

# --- Step 5: banner --------------------------------------------------------

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Ecosystem installed. You can now:"
Write-Host "    1. Run 'claude' or 'gemini' in any repo"
Write-Host "    2. Edit ~/.claude/memory/*.md as you learn preferences"
Write-Host "    3. (Phase 2) Install Sentinel in your workbook repo:"
Write-Host "         python -m sentinel install-hook --repo <path>"
Write-Host "    4. (Phase 3) Set TRUTHCERT_HMAC_KEY env var for signed bundles"
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""

exit 0
