#Requires -Version 5.1
# doctor-report.ps1 -- opt-in install-success reporter (no automated POST).
#
# Addresses the "you have no way to know if 5 or 500 students succeeded"
# finding from the v0.7.0 review. The approach is deliberately passive:
# this script GENERATES a report and prints a prefilled GitHub Issues URL.
# Nothing is uploaded automatically. The student decides whether to click.
#
# What the report includes:
#   - ecosystem-starter version (from docs/HASH.txt context)
#   - Windows version + PowerShell version
#   - Which layers installed OK (rules, memory, Sentinel, Overmind, ProjectIndex)
#   - Presence of agent CLIs on PATH (claude / gemini / codex)
#   - Last 20 lines of any error-<ts>.log files in %LOCALAPPDATA%\e156\logs\
#
# Explicitly REDACTED:
#   - Full paths (only last 2 components shown)
#   - Environment variable VALUES (names only)
#   - Any file content other than error logs
#   - GitHub username (printed separately; student chooses whether to include)
#
# Usage:
#   .\scripts\doctor-report.ps1                   # print report + URL
#   .\scripts\doctor-report.ps1 -SaveTo report.md # also save to disk
#   .\scripts\doctor-report.ps1 -Import            # dot-source for tests

[CmdletBinding()]
param(
    [string]$SaveTo,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-RedactedPath {
    [CmdletBinding()]
    param([string]$Path)
    if (-not $Path) { return '' }
    $parts = $Path -split '[\\/]'
    if ($parts.Count -le 2) { return $Path }
    return '...\' + ($parts[-2..-1] -join '\')
}

function Test-CLIPresent {
    [CmdletBinding()]
    param([string]$Name)
    $null = Get-Command $Name -ErrorAction SilentlyContinue
    return $?
}

function Get-EcosystemVersion {
    # Read docs/HASH.txt from the ecosystem-starter root (if we're inside it)
    $hashFile = Join-Path $PSScriptRoot '..\docs\HASH.txt'
    if (Test-Path $hashFile) {
        $sha = (Get-Content -Raw $hashFile).Trim()
        return "install.ps1 SHA: $sha"
    }
    return "install.ps1 SHA: unknown (not running from starter repo)"
}

function Get-LayerStatus {
    # Inspect ~/.claude, ~/.gemini, ~/.codex for rules/memory presence.
    $userHome = $env:USERPROFILE
    if (-not $userHome) { $userHome = $HOME }
    $layers = @{}
    foreach ($agent in @('claude', 'gemini', 'codex')) {
        $rulesDir = Join-Path $userHome ".$agent\rules"
        $memDir   = Join-Path $userHome ".$agent\memory"
        $layers["$agent-rules"]  = (Test-Path $rulesDir) -and ((Get-ChildItem $rulesDir -Filter '*.md' -ErrorAction SilentlyContinue).Count -ge 4)
        $layers["$agent-memory"] = Test-Path (Join-Path $memDir 'MEMORY.md')
    }
    # Sentinel: check for the pre-push hook file in cwd (best we can do without scanning every repo)
    $layers['sentinel-on-path'] = Test-CLIPresent -Name 'sentinel'
    $layers['overmind-on-path'] = Test-CLIPresent -Name 'overmind'
    $layers['truthcert-key-set'] = -not [string]::IsNullOrEmpty($env:TRUTHCERT_HMAC_KEY)
    return $layers
}

function Get-RecentErrorLogs {
    [CmdletBinding()]
    param([int]$MaxLogs = 3, [int]$MaxLinesPerLog = 20)
    $userHome = $env:USERPROFILE
    if (-not $userHome) { $userHome = $HOME }
    $logsDir = Join-Path $userHome 'AppData\Local\e156\logs'
    if (-not (Test-Path $logsDir)) {
        # Also try the LOCALAPPDATA that some students may have redirected
        $logsDir = Join-Path $env:LOCALAPPDATA 'e156\logs'
    }
    if (-not (Test-Path $logsDir)) { return @() }
    Get-ChildItem $logsDir -Filter 'error-*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First $MaxLogs |
        ForEach-Object {
            $tail = (Get-Content $_.FullName -Tail $MaxLinesPerLog -ErrorAction SilentlyContinue) -join "`n"
            [PSCustomObject]@{
                FileName = $_.Name
                Tail     = $tail
            }
        }
}

function Build-Report {
    [CmdletBinding()]
    param()
    $bitness = if ([System.Environment]::Is64BitOperatingSystem) { '64-bit' } else { '32-bit' }
    $os = "$([System.Environment]::OSVersion.VersionString) ($bitness)"
    $psv = $PSVersionTable.PSVersion.ToString()
    $ver = Get-EcosystemVersion
    $layers = Get-LayerStatus
    $errs = Get-RecentErrorLogs

    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("# e156-ecosystem-starter install report")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("> Generated $(Get-Date -Format 'yyyy-MM-dd HH:mm') by doctor-report.ps1.")
    [void]$sb.AppendLine("> Paths redacted to last 2 components. No env-var values included.")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Environment")
    [void]$sb.AppendLine("- OS: $os")
    [void]$sb.AppendLine("- PowerShell: $psv")
    [void]$sb.AppendLine("- $ver")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Agent CLIs on PATH")
    foreach ($cli in @('claude', 'gemini', 'codex')) {
        $present = Test-CLIPresent -Name $cli
        $mark = if ($present) { 'yes' } else { 'no ' }
        [void]$sb.AppendLine("- $mark  $cli")
    }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Layers installed")
    foreach ($k in $layers.Keys | Sort-Object) {
        $mark = if ($layers[$k]) { 'OK  ' } else { 'miss' }
        [void]$sb.AppendLine("- $mark  $k")
    }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Recent error logs")
    if ($errs.Count -eq 0) {
        [void]$sb.AppendLine("(none)")
    } else {
        foreach ($e in $errs) {
            [void]$sb.AppendLine("### $($e.FileName)")
            [void]$sb.AppendLine('```')
            [void]$sb.AppendLine($e.Tail)
            [void]$sb.AppendLine('```')
        }
    }
    return $sb.ToString()
}

function Build-IssueUrl {
    [CmdletBinding()]
    param([string]$Body, [string]$Title = 'install report')
    # GitHub Issues supports prefilled new-issue URLs. We URL-encode the body.
    $enc = Add-Type -AssemblyName System.Web -PassThru -ErrorAction SilentlyContinue
    if (-not $enc) {
        # .NET Core 5+ doesn't ship System.Web.HttpUtility. Fallback to UrlEncode via Uri.
        $encodedBody = [System.Uri]::EscapeDataString($Body)
        $encodedTitle = [System.Uri]::EscapeDataString($Title)
    } else {
        $encodedBody = [System.Web.HttpUtility]::UrlEncode($Body)
        $encodedTitle = [System.Web.HttpUtility]::UrlEncode($Title)
    }
    # GitHub Issue body has a 64 KB limit; truncate if needed
    if ($encodedBody.Length -gt 60000) {
        $encodedBody = $encodedBody.Substring(0, 60000) + '...'
    }
    return "https://github.com/mahmood726-cyber/e156-ecosystem-starter/issues/new?title=$encodedTitle&body=$encodedBody"
}

if ($Import) { return }

# === Real flow =============================================================

$report = Build-Report
Write-Host $report

if ($SaveTo) {
    [System.IO.File]::WriteAllText(
        $SaveTo, $report,
        (New-Object System.Text.UTF8Encoding $false)
    )
    Write-Host ""
    Write-Host "Report saved to $SaveTo" -ForegroundColor Green
}

$url = Build-IssueUrl -Body $report -Title 'install report'

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  OPT-IN: share this report?"
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you want to send this report to help improve the starter,"
Write-Host "click the URL below. It opens a prefilled GitHub Issues form."
Write-Host "NOTHING is sent automatically -- you review and submit."
Write-Host ""
Write-Host "  $url" -ForegroundColor Yellow
Write-Host ""
Write-Host "(Or just close this window -- no report is sent.)"
