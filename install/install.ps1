#Requires -Version 5.1
# install.ps1 - e156-ecosystem-starter bootstrap (Windows)
#
# Turns your laptop into Mahmood's quality-dev environment. Installs:
#   - rules/*.md          -> ~/.claude/rules/ + ~/.gemini/rules/
#   - memory scaffolding  -> ~/.claude/rules/memory/ (starter MEMORY.md + templates)
#   - AGENTS.md, CLAUDE.md, GEMINI.md, CODEX.md as per-user global defaults
#
# Run from PowerShell (no admin needed):
#   .\install.ps1                 # base install + interactive prompts for sub-installers
#   .\install.ps1 -Full            # everything non-interactively
#                                    (Sentinel in current repo, Overmind, ProjectIndex at C:\ProjectIndex)
#   .\install.ps1 -NonInteractive  # base only, skip all chain prompts (CI-safe)
#   .\install.ps1 -DryRun         # just verify SHA gate, exit 0
#   .\install.ps1 -Force           # overwrite existing user files
#   .\install.ps1 -Import          # dot-source helpers only (used by tests)
#
# Per-layer opt-in flags (override interactive prompts):
#   -InstallSentinel <repo-path>   # chain Sentinel hook install into this repo
#   -InstallOvermind               # chain Overmind + TruthCert HMAC-key setup
#   -ProjectIndexRoot <dir>        # chain ProjectIndex seed at this dir
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
    [switch]$Import,
    [switch]$Full,
    [switch]$NonInteractive,
    [string]$InstallSentinel,
    [switch]$InstallOvermind,
    [string]$ProjectIndexRoot,
    # Rules-template variables (substituted into rules/*.md + AGENTS.md on copy).
    # Defaults match Mahmood's working layout. Pass your own here to make the
    # rules point at YOUR paths. Leave $GitHubUser empty to keep the literal
    # {{GITHUB_USER}} placeholder (so you can see it and edit in place).
    # Default rule-template paths now align with where the installers ACTUALLY
    # land things on a fresh student machine (under %USERPROFILE%\code\). The
    # earlier C:\E156 / C:\ProjectIndex / C:\Sentinel / C:\overmind defaults
    # matched MA's personal layout but caused agents to look at non-existent
    # paths after a vanilla install -- students would get "C:\ProjectIndex not
    # found" errors when the rules referred to it. (Reported in code review.)
    [string]$E156Home        = (Join-Path $env:USERPROFILE 'code\E156'),
    [string]$PortfolioRoot   = (Join-Path $env:USERPROFILE 'code\ProjectIndex'),
    [string]$SentinelRoot    = (Join-Path $env:USERPROFILE 'code\Sentinel'),
    [string]$OvermindRoot    = (Join-Path $env:USERPROFILE 'code\overmind'),
    [string]$GitHubUser      = ''
)

$ErrorActionPreference = 'Stop'

# --- install-time transcript log ------------------------------------------
# Write the entire install console to %LOCALAPPDATA%\e156\logs\install-<ts>.log
# so doctor-report.ps1 has something to read when a student hits a problem.
# Failure here is non-fatal (Start-Transcript failures shouldn't kill an
# otherwise-fine install).
if (-not $Import) {
    try {
        $logDir = Join-Path $env:LOCALAPPDATA 'e156\logs'
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
        $logFile = Join-Path $logDir ("install-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
        Start-Transcript -Path $logFile -Force | Out-Null
        # Register a teardown so Stop-Transcript runs even on uncaught errors.
        $script:__transcriptStarted = $true
    } catch {
        $script:__transcriptStarted = $false
    }
}

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

function Resolve-StarterPath {
    # Path-disambiguation for student input. Treats:
    #   - absolute path                -> use as-is
    #   - relative path (no drive/UNC) -> resolve against $HOME\code\ (NOT cwd --
    #                                     CWD is often C:\Windows\System32 on
    #                                     freshly-launched PowerShell, which
    #                                     fails Permission Denied)
    #   - empty / null                 -> return $Default
    #
    # Refuses to silently land under C:\Windows or C:\Program Files.
    [CmdletBinding()]
    param(
        [string]$Input,
        [string]$Default = $null
    )
    if ([string]::IsNullOrWhiteSpace($Input)) {
        return $Default
    }
    $trimmed = $Input.Trim()
    # Absolute paths: drive-letter (C:\...) or UNC (\\server\share)
    if ($trimmed -match '^[A-Za-z]:[\\/]' -or $trimmed -match '^\\\\') {
        $resolved = $trimmed
    } else {
        # Relative -> $HOME\code\<input>
        $codeRoot = Join-Path $env:USERPROFILE 'code'
        $resolved = Join-Path $codeRoot $trimmed
    }
    # Refuse system-protected roots
    $forbidden = @('C:\Windows', 'C:\Program Files', 'C:\Program Files (x86)', 'C:\ProgramData')
    foreach ($f in $forbidden) {
        if ($resolved -like "$f\*" -or $resolved -eq $f) {
            throw "Refusing to install into protected system path: $resolved. Pick a path under $env:USERPROFILE."
        }
    }
    return $resolved
}

function Invoke-LogRedaction {
    # Scrubs API keys, tokens, and high-entropy secrets from a transcript file
    # in-place. Runs at end-of-install so a student attaching the log to an
    # issue, or sharing it for help, doesn't leak credentials.
    #
    # Patterns covered (each replaced with a labeled placeholder):
    #   AIza...                        -> Google AI Studio API key
    #   sk-... / sk-ant-...            -> OpenAI / Anthropic
    #   ghp_/gho_/ghs_/ghu_...         -> GitHub PAT/OAuth/Server/User token
    #   AKIA...                        -> AWS access key ID
    #   64-hex-char string             -> TruthCert HMAC / generic crypto key
    #   eyJ...token...                 -> JWT (3 base64url segments)
    #   setx VAR_KEY/TOKEN/SECRET "x"  -> windows env-var assignment value
    #
    # Conservative by design: false positives (a 64-hex hash that ISN'T a key)
    # become "[REDACTED-64hex]" in the log -- annoying for debugging but never
    # a security regression. False negatives (a leaked key NOT matched) are
    # the real risk; pattern set is reviewed against the 2026-04-* token
    # families.
    [CmdletBinding()]
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    $content = Get-Content -Raw -Path $Path
    if ($null -eq $content) { return }
    # Specific patterns first (preserve labels), then generic setx catch-all.
    $content = $content -replace 'AIza[A-Za-z0-9_-]{35}', '[REDACTED-google-api-key]'
    $content = $content -replace 'sk-ant-[A-Za-z0-9_-]{40,}', '[REDACTED-anthropic-key]'
    $content = $content -replace 'sk-[A-Za-z0-9]{40,}', '[REDACTED-openai-key]'
    $content = $content -replace 'gh[opsu]_[A-Za-z0-9]{36,}', '[REDACTED-github-token]'
    $content = $content -replace 'AKIA[A-Z0-9]{16}', '[REDACTED-aws-access-key]'
    $content = $content -replace 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', '[REDACTED-jwt]'
    $content = $content -replace '\b[0-9a-fA-F]{64}\b', '[REDACTED-64hex]'
    # setx VAR_NAME "value" where var name contains KEY/TOKEN/SECRET/PASS/HMAC.
    # Skip lines that already contain "[REDACTED" so we don't over-redact a
    # labeled scrub down to "[REDACTED]".
    $lines = $content -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -notmatch '\[REDACTED') {
            $lines[$i] = $lines[$i] -replace '(setx\s+[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASS|HMAC)[A-Za-z0-9_]*\s+")[^"]*(")', '$1[REDACTED]$2'
        }
    }
    $content = $lines -join "`n"
    Set-Content -Path $Path -Value $content -NoNewline -Encoding UTF8
}

function Render-Template {
    [CmdletBinding()]
    param(
        [string]$Text,
        [hashtable]$Vars
    )
    # Global literal-replace of {{NAME}} placeholders. String.Replace, not
    # regex, so dollar signs / backslashes in values pass through untouched.
    foreach ($k in $Vars.Keys) {
        $Text = $Text.Replace('{{' + $k + '}}', [string]$Vars[$k])
    }
    return $Text
}

function Copy-RulesToAgent {
    [CmdletBinding()]
    param(
        [string]$SourceRulesDir,
        [string]$TargetRulesDir,
        [switch]$Force,
        [hashtable]$Vars = $null,
        [PSCustomObject]$Manifest = $null
    )
    if (-not (Test-Path $SourceRulesDir)) {
        throw "Source rules dir not found: $SourceRulesDir"
    }
    $newDir = -not (Test-Path $TargetRulesDir)
    New-Item -ItemType Directory -Force -Path $TargetRulesDir | Out-Null
    if ($newDir -and $Manifest) { $Manifest.CreatedDirs.Add($TargetRulesDir) }

    $copied = @()
    $backed = @()
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    Get-ChildItem -Path $SourceRulesDir -Filter "*.md" | ForEach-Object {
        $dest = Join-Path $TargetRulesDir $_.Name
        $preExisted = Test-Path $dest
        $backupPath = "$dest.user"
        $newBackup = $false
        if ($preExisted -and -not $Force) {
            if (-not (Test-Path $backupPath)) {
                Copy-Item $dest $backupPath
                $newBackup = $true
                $backed += $_.Name
                if ($Manifest) { $Manifest.BackedUp.Add($backupPath) }
            }
        }
        # Render template if $Vars given; else straight copy.
        if ($Vars) {
            $text = [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8)
            $rendered = Render-Template -Text $text -Vars $Vars
            [System.IO.File]::WriteAllText($dest, $rendered, $utf8NoBom)
        } else {
            Copy-Item $_.FullName $dest -Force
        }
        # Track net-new files (not pre-existing overwrites -- the backup covers those)
        if (-not $preExisted -and $Manifest) { $Manifest.CreatedFiles.Add($dest) }
        $copied += $_.Name
    }
    return [PSCustomObject]@{ Copied = $copied; Backed = $backed }
}

function Copy-ContextFiles {
    [CmdletBinding()]
    param(
        [string]$SourceRoot,
        [string]$TargetDir,
        [switch]$Force,
        [hashtable]$Vars = $null,
        [PSCustomObject]$Manifest = $null
    )
    $newDir = -not (Test-Path $TargetDir)
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    if ($newDir -and $Manifest) { $Manifest.CreatedDirs.Add($TargetDir) }

    $results = @{}
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    foreach ($name in @('AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'CODEX.md')) {
        $src = Join-Path $SourceRoot $name
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $TargetDir $name
        $preExisted = Test-Path $dst
        if ($preExisted -and -not $Force) {
            $backupPath = "$dst.user"
            if (-not (Test-Path $backupPath)) {
                Copy-Item $dst $backupPath
                if ($Manifest) { $Manifest.BackedUp.Add($backupPath) }
            }
        }
        if ($Vars) {
            $text = [System.IO.File]::ReadAllText($src, [System.Text.Encoding]::UTF8)
            $rendered = Render-Template -Text $text -Vars $Vars
            [System.IO.File]::WriteAllText($dst, $rendered, $utf8NoBom)
        } else {
            Copy-Item $src $dst -Force
        }
        if (-not $preExisted -and $Manifest) { $Manifest.CreatedFiles.Add($dst) }
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

# --- Rollback support ------------------------------------------------------
# We track every file we create so that a mid-install failure can undo
# itself. Net-new files are deleted. Existing user files we preemptively
# moved to .user (as "backup") are restored. Pre-existing user memory is
# never touched (Copy-MemoryScaffold already short-circuits).

function New-RollbackManifest {
    [CmdletBinding()]
    param()
    return [PSCustomObject]@{
        CreatedFiles = New-Object System.Collections.Generic.List[string]
        CreatedDirs  = New-Object System.Collections.Generic.List[string]
        BackedUp     = New-Object System.Collections.Generic.List[string]  # original .user paths created as backup
    }
}

function Invoke-InstallRollback {
    [CmdletBinding()]
    param([PSCustomObject]$Manifest, [string]$Reason)
    Write-Host ""
    Write-Host "Rollback triggered: $Reason" -ForegroundColor Yellow
    # Delete net-new files first (in reverse order so nested paths go before parents)
    $createdReversed = @($Manifest.CreatedFiles) ; [Array]::Reverse($createdReversed)
    foreach ($f in $createdReversed) {
        if (Test-Path $f) {
            Remove-Item $f -Force -ErrorAction SilentlyContinue
        }
    }
    # Restore .user backups back to their original names. Each entry is the
    # backup path ("<orig>.user"); we move it back to <orig>.
    foreach ($backup in $Manifest.BackedUp) {
        if (Test-Path $backup) {
            $orig = $backup.Substring(0, $backup.Length - 5)  # strip ".user"
            Move-Item $backup $orig -Force -ErrorAction SilentlyContinue
        }
    }
    # Then remove net-new directories (in reverse so deepest first)
    $dirsReversed = @($Manifest.CreatedDirs) ; [Array]::Reverse($dirsReversed)
    foreach ($d in $dirsReversed) {
        if ((Test-Path $d) -and
            ((Get-ChildItem $d -Force -ErrorAction SilentlyContinue).Count -eq 0)) {
            Remove-Item $d -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Rollback complete. Any pre-existing user files were restored." -ForegroundColor Green
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

# Manifest drives rollback. Steps 2-4 push onto it via helper functions.
# If any step throws, Invoke-InstallRollback undoes everything it did.
$manifest = New-RollbackManifest

try {

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

# --- Step 1.5: resolve rules-template vars ---------------------------------
# These are substituted into {{E156_HOME}}, {{PROJECTINDEX_ROOT}}, etc.
# Prompt only for GitHub user (no reasonable default); others already have
# defaults from the param block (Mahmood-style layout). Students can override
# any of them with install.ps1 -E156Home D:\MyE156 etc.

if (-not $GitHubUser -and -not $NonInteractive -and [Console]::IsInputRedirected -eq $false) {
    $GitHubUser = (Read-Host "Your GitHub username (or Enter to leave placeholder)").Trim()
}

$rulesVars = @{
    'E156_HOME'         = $E156Home
    'PROJECTINDEX_ROOT' = $PortfolioRoot
    'SENTINEL_ROOT'     = $SentinelRoot
    'OVERMIND_ROOT'     = $OvermindRoot
    'GITHUB_USER'       = if ($GitHubUser) { $GitHubUser } else { '{{GITHUB_USER}}' }
}

# --- Step 2: copy rules to each detected agent's config dir -----------------

Write-Step "Copying rules/*.md (with your paths substituted in)"
$sourceRules = Join-Path $starterRoot 'rules'

$claudeRulesDir = Join-Path $userHome '.claude\rules'
$geminiRulesDir = Join-Path $userHome '.gemini\rules'
$codexRulesDir  = Join-Path $userHome '.codex\rules'

foreach ($target in @($claudeRulesDir, $geminiRulesDir, $codexRulesDir)) {
    $r = Copy-RulesToAgent -SourceRulesDir $sourceRules -TargetRulesDir $target -Force:$Force -Vars $rulesVars -Manifest $manifest
    Write-Ok "$target  ($($r.Copied.Count) files copied, $($r.Backed.Count) backed up as .user)"
}

# --- Step 3: drop context files (AGENTS.md / CLAUDE.md / GEMINI.md / CODEX.md)

Write-Step "Writing context files to ~/.claude, ~/.gemini, ~/.codex"
foreach ($dir in @((Join-Path $userHome '.claude'), (Join-Path $userHome '.gemini'), (Join-Path $userHome '.codex'))) {
    $r = Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $dir -Force:$Force -Vars $rulesVars -Manifest $manifest
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

# --- Step 5: chain sub-installers -----------------------------------------
#
# Three optional chains: Sentinel (pre-push hook), Overmind (verifier), and
# ProjectIndex (portfolio seed). Under -Full, all three run with defaults.
# Under -NonInteractive (or piped stdin), all three skip unless an explicit
# -InstallXxx flag was passed. Otherwise we prompt.

function Test-CanPrompt {
    return -not $NonInteractive -and -not [Console]::IsInputRedirected
}

function Prompt-YesNo {
    param([string]$Question, [bool]$DefaultYes = $true)
    $hint = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
    $ans = (Read-Host "$Question $hint").Trim().ToLower()
    if ($ans -eq '') { return $DefaultYes }
    return $ans -in @('y', 'yes')
}

$scriptsDir = Join-Path $starterRoot 'scripts'

# Track per-chain outcomes for the honest end-of-run summary.
# Status values: 'ok' | 'failed' | 'skipped'
$chainStatus = [ordered]@{
    'rules+memory'  = 'ok'   # we got this far, so step 1-4 succeeded
    'sentinel'      = 'skipped'
    'overmind'      = 'skipped'
    'projectindex'  = 'skipped'
}
$chainDetails = [ordered]@{}

# Default install location for student-typed relative paths.
$studentCodeRoot = Join-Path $env:USERPROFILE 'code'

# 5a: Sentinel
$doSentinel = $false
$sentinelRepo = $null
if ($InstallSentinel) {
    $doSentinel = $true
    $sentinelRepo = Resolve-StarterPath -Input $InstallSentinel -Default $InstallSentinel
} elseif ($Full) {
    $doSentinel = $true
    $sentinelRepo = Join-Path $studentCodeRoot 'my-first-repo'
    Write-Host "    (-Full) Will install Sentinel hook in: $sentinelRepo" -ForegroundColor DarkGray
} elseif (Test-CanPrompt) {
    Write-Host ""
    Write-Step "Sentinel pre-push hook (blocks 20 defect patterns before git push)"
    if (Prompt-YesNo -Question "Install Sentinel in a repo now?") {
        $defaultRepo = Join-Path $studentCodeRoot 'my-first-repo'
        $userInput = (Read-Host "Target repo path (absolute, or name only -> goes under $studentCodeRoot\) [default: $defaultRepo]").Trim()
        try {
            $sentinelRepo = Resolve-StarterPath -Input $userInput -Default $defaultRepo
            $doSentinel = $true
        } catch {
            Write-Warning $_.Exception.Message
            $chainStatus['sentinel'] = 'failed'
            $chainDetails['sentinel'] = "rejected target: $($_.Exception.Message)"
        }
    }
}
if ($doSentinel) {
    $sentinelScript = Join-Path $scriptsDir 'install-sentinel.ps1'
    if (Test-Path $sentinelScript) {
        Write-Step "Chaining: install-sentinel.ps1 -Repo $sentinelRepo"
        # Ensure the repo directory exists (create if missing) and is initialized as a git repo.
        if (-not (Test-Path $sentinelRepo)) {
            try {
                New-Item -ItemType Directory -Force -Path $sentinelRepo | Out-Null
                Write-Host "    Created $sentinelRepo"
            } catch {
                Write-Warning "Could not create $sentinelRepo : $($_.Exception.Message)"
                $chainStatus['sentinel'] = 'failed'
                $chainDetails['sentinel'] = "could not create directory $sentinelRepo"
                $doSentinel = $false
            }
        }
        if ($doSentinel -and -not (Test-Path (Join-Path $sentinelRepo '.git'))) {
            try {
                & git -C $sentinelRepo init --quiet 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
                Write-Host "    git init at $sentinelRepo"
            } catch {
                Write-Warning "Could not git init in $sentinelRepo : $($_.Exception.Message)"
            }
        }
        if ($doSentinel) {
            try {
                & powershell -NoProfile -ExecutionPolicy Bypass -File $sentinelScript -Repo $sentinelRepo
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "install-sentinel.ps1 exited $LASTEXITCODE"
                    $chainStatus['sentinel'] = 'failed'
                    $chainDetails['sentinel'] = "exited $LASTEXITCODE (often: Python on PATH is the Microsoft Store stub -- see prereqs)"
                } else {
                    $chainStatus['sentinel'] = 'ok'
                    $chainDetails['sentinel'] = "installed in $sentinelRepo"
                }
            } catch {
                Write-Warning "install-sentinel.ps1 failed: $($_.Exception.Message)"
                $chainStatus['sentinel'] = 'failed'
                $chainDetails['sentinel'] = $_.Exception.Message
            }
        }
    }
}

# 5b: Overmind
$doOvermind = $false
if ($InstallOvermind) {
    $doOvermind = $true
} elseif ($Full) {
    $doOvermind = $true
    Write-Host "    (-Full) Will install Overmind + TruthCert" -ForegroundColor DarkGray
} elseif (Test-CanPrompt) {
    Write-Host ""
    Write-Step "Overmind verifier + TruthCert HMAC signing (~5 MB pip deps)"
    if (Prompt-YesNo -Question "Install Overmind + TruthCert now?") { $doOvermind = $true }
}
if ($doOvermind) {
    $overmindScript = Join-Path $scriptsDir 'install-overmind.ps1'
    if (Test-Path $overmindScript) {
        Write-Step "Chaining: install-overmind.ps1"
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $overmindScript
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "install-overmind.ps1 exited $LASTEXITCODE"
                $chainStatus['overmind'] = 'failed'
                $chainDetails['overmind'] = "exited $LASTEXITCODE (often: Python stub -- see prereqs)"
            } else {
                $chainStatus['overmind'] = 'ok'
                $chainDetails['overmind'] = "installed"
            }
        } catch {
            Write-Warning "install-overmind.ps1 failed: $($_.Exception.Message)"
            $chainStatus['overmind'] = 'failed'
            $chainDetails['overmind'] = $_.Exception.Message
        }
    }
}

# 5c: ProjectIndex
$doProjectIndex = $false
$piRoot = $null
$piDefault = Join-Path $studentCodeRoot 'ProjectIndex'
if ($ProjectIndexRoot) {
    $doProjectIndex = $true
    $piRoot = Resolve-StarterPath -Input $ProjectIndexRoot -Default $ProjectIndexRoot
} elseif ($Full) {
    $doProjectIndex = $true
    $piRoot = $piDefault
    Write-Host "    (-Full) Will seed ProjectIndex at: $piRoot" -ForegroundColor DarkGray
} elseif (Test-CanPrompt) {
    Write-Host ""
    Write-Step "ProjectIndex seed (portfolio INDEX.md + reconcile_counts.py)"
    if (Prompt-YesNo -Question "Seed ProjectIndex now?") {
        $userInput = (Read-Host "Target dir (absolute, or name only -> goes under $studentCodeRoot\) [default: $piDefault]").Trim()
        try {
            $piRoot = Resolve-StarterPath -Input $userInput -Default $piDefault
            $doProjectIndex = $true
        } catch {
            Write-Warning $_.Exception.Message
            $chainStatus['projectindex'] = 'failed'
            $chainDetails['projectindex'] = "rejected target: $($_.Exception.Message)"
        }
    }
}
if ($doProjectIndex) {
    $piScript = Join-Path $scriptsDir 'install-projectindex.ps1'
    if (Test-Path $piScript) {
        Write-Step "Chaining: install-projectindex.ps1 -Root $piRoot"
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $piScript -Root $piRoot
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "install-projectindex.ps1 exited $LASTEXITCODE"
                $chainStatus['projectindex'] = 'failed'
                $chainDetails['projectindex'] = "exited $LASTEXITCODE"
            } else {
                $chainStatus['projectindex'] = 'ok'
                $chainDetails['projectindex'] = "seeded at $piRoot"
            }
        } catch {
            Write-Warning "install-projectindex.ps1 failed: $($_.Exception.Message)"
            $chainStatus['projectindex'] = 'failed'
            $chainDetails['projectindex'] = $_.Exception.Message
        }
    }
}

# --- Step 6: honest summary ------------------------------------------------

$nFailed = ($chainStatus.Values | Where-Object { $_ -eq 'failed' }).Count
$nOk     = ($chainStatus.Values | Where-Object { $_ -eq 'ok' }).Count

$bannerColor = if ($nFailed -gt 0) { 'Yellow' } else { 'Green' }
$bannerText  = if ($nFailed -gt 0) { "Install completed with $nFailed component(s) failing -- see below" } else { "Ecosystem installed cleanly" }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor $bannerColor
Write-Host "  $bannerText" -ForegroundColor $bannerColor
Write-Host "=====================================================" -ForegroundColor $bannerColor

# Per-chain breakdown
foreach ($chain in $chainStatus.Keys) {
    $status = $chainStatus[$chain]
    $detail = $chainDetails[$chain]
    switch ($status) {
        'ok'      { $sym = '[OK]'; $color = 'Green' }
        'failed'  { $sym = '[X]'; $color = 'Red' }
        default   { $sym = '-'; $color = 'DarkGray' }
    }
    $line = "  $sym  $($chain.PadRight(14)) $status"
    if ($detail) { $line += "  -- $detail" }
    Write-Host $line -ForegroundColor $color
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "    1. Read STUDENT-WORKFLOW.md  (brainstorm -> spec-lock -> plan-lock -> TDD -> audit method,"
Write-Host "       worked-example repos, quality gates):" -ForegroundColor DarkGray
Write-Host "         https://github.com/mahmood726-cyber/e156-ecosystem-starter/blob/main/STUDENT-WORKFLOW.md"
Write-Host "    2. Run 'claude' or 'gemini' in any repo"
Write-Host "    3. Edit ~/.claude/memory/*.md as you learn preferences"
if ($chainStatus['sentinel'] -ne 'ok') {
    Write-Host "    4. Re-try Sentinel later:"
    Write-Host "         .\scripts\install-sentinel.ps1 -Repo $studentCodeRoot\<your-repo>"
}
if ($chainStatus['overmind'] -ne 'ok') {
    Write-Host "    5. Re-try Overmind + TruthCert later:"
    Write-Host "         .\scripts\install-overmind.ps1"
}
if ($chainStatus['projectindex'] -ne 'ok') {
    Write-Host "    6. Re-try ProjectIndex later:"
    Write-Host "         .\scripts\install-projectindex.ps1 -Root $studentCodeRoot\ProjectIndex"
}
if ($nFailed -gt 0) {
    Write-Host ""
    Write-Host "If a sub-installer reported a Python error, the most common cause is that 'python' on PATH is the Microsoft Store alias rather than a real Python. Install Python 3.11+ from https://www.python.org/downloads/ (tick 'Add to PATH'), reopen PowerShell, then re-run a sub-installer." -ForegroundColor Yellow
}
Write-Host ""

# Stop the install transcript before exit (non-fatal if it never started).
# Then scrub the log of API keys / tokens / HMAC values that may have been
# pasted, echoed, or otherwise captured during the run -- so attaching the
# log to an issue or sharing it doesn't leak credentials.
if ($script:__transcriptStarted) {
    try { Stop-Transcript | Out-Null } catch { }
    if ($logFile -and (Test-Path $logFile)) {
        try { Invoke-LogRedaction -Path $logFile } catch { }
    }
}

# Exit non-zero if ANY chain failed, so the .bat wrapper / CI / parent
# scripts can detect partial-failure rather than reporting a green
# "INSTALL COMPLETE" off our exit code. Base install (rules + memory)
# succeeded if we got here; the failure(s) are in the sub-installers,
# enumerated above. Code 2 = "rules ok, sub-chain failed".
if ($nFailed -gt 0) { exit 2 } else { exit 0 }

}  # end try
catch {
    Invoke-InstallRollback -Manifest $manifest -Reason $_.Exception.Message
    Write-Host ""
    Write-Host "Install FAILED. No partial state left on disk." -ForegroundColor Red
    Write-Host "If you want to report this, include:"
    Write-Host "  - error: $($_.Exception.Message)"
    Write-Host "  - rolled-back files: $($manifest.CreatedFiles.Count)"
    Write-Host "  - restored backups:  $($manifest.BackedUp.Count)"
    exit 1
}
