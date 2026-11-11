#Requires -Version 5.1
# Install the locked RapidMeta source; verify before changing user configuration.
# -SkipClone still verifies identity and generation. -SessionOnly avoids User env writes.
[CmdletBinding()]
param([string]$Target, [switch]$SkipClone, [switch]$SessionOnly, [switch]$Import)
$ErrorActionPreference = 'Stop'
$script:RapidmetaScriptRoot = $PSScriptRoot

function Get-RapidmetaPython {
    foreach ($candidate in @('python', 'python3')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd -or $cmd.Source -like '*WindowsApps*') { continue }
        try {
            & $cmd.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $cmd.Source }
        } catch { continue }
    }
    throw 'REFUSED: Python 3.11+ is required'
}
function Get-RapidmetaLockField {
    param([string]$Field)
    $pythonExe = Get-RapidmetaPython
    $result = & $pythonExe (Join-Path $script:RapidmetaScriptRoot 'component_lock.py') --component rapidmeta --field $Field
    if ($LASTEXITCODE -ne 0) { throw 'REFUSED: invalid component lock' }
    return ($result -join "`n").Trim()
}
function Get-RapidmetaRepoUrl { return Get-RapidmetaLockField -Field 'repository' }
function Get-RapidmetaDefaultRef {
    $ref = if ($env:RAPIDMETA_REF) { $env:RAPIDMETA_REF } else { Get-RapidmetaLockField -Field 'commit' }
    if ($ref -cnotmatch '^[0-9a-f]{40}$') { throw 'REFUSED: RapidMeta requires a full lowercase commit SHA' }
    return $ref
}
function Get-RapidmetaDefaultTarget { return (Join-Path $env:USERPROFILE 'code/rapidmeta-kit') }
function Test-RapidmetaPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path -LiteralPath (Join-Path $Dir 'clone.py') -PathType Leaf))
}
function Set-RapidmetaPathEnv {
    param([string]$TargetDir, [switch]$SessionOnly)
    if (-not $SessionOnly) {
        $existing = [Environment]::GetEnvironmentVariable('RAPIDMETA_KIT_PATH', 'User')
        if ($existing -and $existing -ne $TargetDir) {
            throw 'REFUSED: conflicting User RAPIDMETA_KIT_PATH; update it explicitly or use -SessionOnly'
        }
        [Environment]::SetEnvironmentVariable('RAPIDMETA_KIT_PATH', $TargetDir, 'User')
    }
    $env:RAPIDMETA_KIT_PATH = $TargetDir
}
if ($Import) { return }
try {
    $pythonExe = Get-RapidmetaPython
    if (-not $Target) { $Target = Get-RapidmetaDefaultTarget }
    $ref = Get-RapidmetaDefaultRef
    $helperArgs = @('--target', $Target, '--ref', $ref)
    if ($SkipClone) { $helperArgs += '--skip-clone' }
    $receipt = & $pythonExe (Join-Path $script:RapidmetaScriptRoot 'rapidmeta_install.py') @helperArgs
    if ($LASTEXITCODE -ne 0) { throw 'REFUSED: RapidMeta verification failed' }
    $report = ($receipt -join "`n") | ConvertFrom-Json
    if ($report.status -ne 'verified' -or $report.expected_commit -ne $ref -or $report.observed_commit -ne $ref) {
        throw 'REFUSED: invalid RapidMeta verification receipt'
    }
    $Target = (Resolve-Path -LiteralPath $Target).Path
    Set-RapidmetaPathEnv -TargetDir $Target -SessionOnly:$SessionOnly
    Write-Output ($receipt -join "`n")
    Write-Output 'RapidMeta source and generator verified. Browser and scientific validation are separate.'
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 2
}
exit 0
