#Requires -Version 5.1
# write-gemini-handoff.ps1
#
# Called at the tail of install.ps1 (under -Full or after a successful
# interactive run) to hand the rest of the bootstrap to an agent.
#
# Behaviour:
#   1. Reads scripts/gemini-handoff-prompt.md (the actual instruction body).
#   2. Writes it to ~/Desktop/paste-into-gemini.txt as a durable fallback.
#   3. Tries to copy it to the clipboard via Set-Clipboard.
#   4. Prints a one-screen "next step" block telling the student to launch
#      gemini / claude / codex and paste.
#
# Failure non-fatal: a clipboard or desktop write that fails should NOT take
# down a successful install. Print a warning and move on.

[CmdletBinding()]
param(
    [string]$StarterRoot,
    [switch]$Quiet,
    [switch]$Import,            # dot-source helpers only (used by Pester)
    [switch]$ResolveOnly        # print the resolved prompt path and exit (test hook)
)

if (-not $StarterRoot) {
    $StarterRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Get-HandoffPromptLocale {
    # Pure resolver: takes locale env vars, returns one of {en, fr, pt, ar}.
    # Precedence: explicit E156_LANG > LC_ALL (POSIX-canonical) > LANG > en.
    [CmdletBinding()]
    param(
        [string]$E156Lang = $env:E156_LANG,
        [string]$LcAll    = $env:LC_ALL,
        [string]$Lang     = $env:LANG
    )
    $raw = if ($E156Lang) { $E156Lang }
           elseif ($LcAll) { $LcAll }
           elseif ($Lang)  { $Lang }
           else            { 'en' }
    $code = $raw.Substring(0, [Math]::Min(2, $raw.Length)).ToLower()
    if ($code -in @('en','fr','pt','ar','ur','sw')) { return $code }
    return 'en'
}

function Get-HandoffPromptPath {
    # Resolves the on-disk prompt file path, falling back to English if the
    # localised file is missing (partial release / file corruption).
    [CmdletBinding()]
    param([string]$StarterRoot, [string]$Locale)
    if (-not $Locale) { $Locale = Get-HandoffPromptLocale }
    $localised = Join-Path $StarterRoot ("scripts\gemini-handoff-prompt.$Locale.md")
    if (Test-Path $localised) { return $localised }
    return (Join-Path $StarterRoot 'scripts\gemini-handoff-prompt.en.md')
}

if ($Import) { return }   # dot-sourced by Pester; no execution

$promptFile = Get-HandoffPromptPath -StarterRoot $StarterRoot

if ($ResolveOnly) {
    # Test hook: print path and exit so a Pester case can assert on it
    # without performing the clipboard/desktop side effects.
    Write-Output $promptFile
    return
}

if (-not (Test-Path $promptFile)) {
    if (-not $Quiet) { Write-Warning "Gemini handoff prompt not found: $promptFile" }
    return
}

$body = Get-Content -Raw -Path $promptFile

# Try Desktop file first -- works even when clipboard is locked (RDP, sandbox).
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) { $desktop = Join-Path $env:USERPROFILE 'Desktop' }
$paste   = Join-Path $desktop 'paste-into-gemini.txt'
$wroteFile = $false
try {
    [System.IO.File]::WriteAllText($paste, $body, (New-Object System.Text.UTF8Encoding $false))
    $wroteFile = $true
} catch {
    if (-not $Quiet) { Write-Warning "Could not write $paste : $($_.Exception.Message)" }
}

# Set-Clipboard is unavailable on PowerShell 5.1 in some constrained envs
# (CI, headless, server core). Fall back silently.
$wroteClip = $false
try {
    Set-Clipboard -Value $body -ErrorAction Stop
    $wroteClip = $true
} catch {
    # Pre-PS6 Set-Clipboard requires a user session; just skip.
}

if ($Quiet) { return }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Almost done -- one paste left" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The installer set up rules + memory + (optional) hooks." -ForegroundColor White
Write-Host "An AI agent finishes the rest: prereq diagnosis, smoke tests,"
Write-Host "scaffolding your first paper. Hand off to it now:" -ForegroundColor White
Write-Host ""
Write-Host "  1. In any folder, run one of:" -ForegroundColor Cyan
Write-Host "       gemini" -ForegroundColor Yellow
Write-Host "       claude" -ForegroundColor Yellow
Write-Host "       codex" -ForegroundColor Yellow
Write-Host "  2. Paste the handoff prompt:" -ForegroundColor Cyan
if ($wroteClip) {
    Write-Host "       (already in your clipboard -- just press Ctrl+V)" -ForegroundColor Green
} else {
    Write-Host "       (clipboard not available -- open the file below and copy)" -ForegroundColor Yellow
}
if ($wroteFile) {
    Write-Host "       Backup copy: $paste" -ForegroundColor DarkGray
}
Write-Host "  3. Hit Enter. The agent takes over from there." -ForegroundColor Cyan
Write-Host ""
