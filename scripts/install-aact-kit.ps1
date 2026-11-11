#Requires -Version 5.1
# Install the locked AACT-kit source; verify before changing user configuration.
# -SkipClone still verifies identity and source. -SessionOnly avoids User env writes.
[CmdletBinding()]
param([string]$Target, [switch]$SkipClone, [switch]$SessionOnly, [switch]$Import, [switch]$WithDeps, [switch]$VerifyRuntime)
$ErrorActionPreference = 'Stop'
$script:AactKitScriptRoot = $PSScriptRoot

function Get-AactKitPython {
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
function Get-AactKitLockField {
    param([string]$Field)
    $pythonExe = Get-AactKitPython
    $result = & $pythonExe (Join-Path $script:AactKitScriptRoot 'component_lock.py') --component aact-kit --field $Field
    if ($LASTEXITCODE -ne 0) { throw 'REFUSED: invalid component lock' }
    return ($result -join "`n").Trim()
}
function Get-AactKitRepoUrl { return Get-AactKitLockField -Field 'repository' }
function Get-AactKitDefaultRef {
    $ref = if ($env:AACT_KIT_REF) { $env:AACT_KIT_REF } else { Get-AactKitLockField -Field 'commit' }
    if ($ref -cnotmatch '^[0-9a-f]{40}$') { throw 'REFUSED: AACT-kit requires a full lowercase commit SHA' }
    return $ref
}
function Get-AactKitDefaultTarget { return (Join-Path $env:USERPROFILE 'code/aact-kit') }
function Test-AactKitPresent {
    param([string]$Dir)
    return [bool]($Dir -and (Test-Path -LiteralPath (Join-Path $Dir 'src/aact_kit/__init__.py') -PathType Leaf))
}
function Set-AactKitPathEnv {
    param([string]$TargetDir, [switch]$SessionOnly)
    if (-not $SessionOnly) {
        $existing = [Environment]::GetEnvironmentVariable('AACT_KIT_PATH', 'User')
        if ($existing -and $existing -ne $TargetDir) {
            throw 'REFUSED: conflicting User AACT_KIT_PATH; update it explicitly or use -SessionOnly'
        }
        [Environment]::SetEnvironmentVariable('AACT_KIT_PATH', $TargetDir, 'User')
    }
    $env:AACT_KIT_PATH = $TargetDir
}
if ($Import) { return }
try {
    $pythonExe = Get-AactKitPython
    if (-not $Target) { $Target = Get-AactKitDefaultTarget }
    $ref = Get-AactKitDefaultRef
    $helperArgs = @('--target', $Target, '--ref', $ref)
    if ($SkipClone) { $helperArgs += '--skip-clone' }
    if ($WithDeps) { $helperArgs += '--with-deps' }
    if ($VerifyRuntime) { $helperArgs += '--verify-runtime' }
    $receipt = & $pythonExe (Join-Path $script:AactKitScriptRoot 'aact_install.py') @helperArgs
    if ($LASTEXITCODE -ne 0) { throw 'REFUSED: AACT-kit verification failed' }
    $report = ($receipt -join "`n") | ConvertFrom-Json
    if ($report.status -notin @('verified', 'source_verified') -or $report.expected_commit -ne $ref -or $report.observed_commit -ne $ref) {
        throw 'REFUSED: invalid AACT-kit verification receipt'
    }
    if (($WithDeps -or $VerifyRuntime) -and ($report.status -ne 'verified' -or $report.runtime_verified -ne $true)) {
        throw 'REFUSED: AACT runtime verification was requested but not completed'
    }
    $Target = (Resolve-Path -LiteralPath $Target).Path
    Set-AactKitPathEnv -TargetDir $Target -SessionOnly:$SessionOnly
    Write-Output ($receipt -join "`n")
    if ($report.runtime_verified) {
        Write-Output 'AACT-kit source and four local backends verified on synthetic fixtures.'
    } else {
        Write-Output 'AACT-kit source verified only; runtime has not been checked.'
    }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 2
}
exit 0
