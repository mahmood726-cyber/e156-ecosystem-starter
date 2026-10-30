# Pester tests for Phase 3 scripts (install-overmind.ps1, install-projectindex.ps1).
# Does NOT pip install. Only exercises helper functions.

BeforeAll {
    $script:OvermindScript = Join-Path $PSScriptRoot 'install-overmind.ps1'
    $script:ProjectIndexScript = Join-Path $PSScriptRoot 'install-projectindex.ps1'
    . $script:OvermindScript -Import
    . $script:ProjectIndexScript -Import

    $script:tmpRoot = Join-Path $env:TEMP "phase3-test-$(Get-Random)"
    New-Item -ItemType Directory -Force -Path $script:tmpRoot | Out-Null
}

AfterAll {
    if (Test-Path $script:tmpRoot) {
        Remove-Item -Recurse -Force $script:tmpRoot -ErrorAction SilentlyContinue
    }
}

Describe "Overmind: Test-OvermindInstalled" {
    It "returns a boolean" {
        Test-OvermindInstalled | Should -BeOfType [bool]
    }

    It "rejects a missing CLI instead of trusting PowerShell's assignment status" {
        # An isolated command-lookup mock: no network or Overmind installation.
        Mock Get-Command { $null } -ParameterFilter { $Name -eq 'overmind' }
        Test-OvermindInstalled | Should -BeFalse
        Should -Invoke Get-Command -Times 1 -Exactly -ParameterFilter {
            $Name -eq 'overmind' -and $CommandType -eq 'Application'
        }
    }

    It "accepts a discoverable executable via a local PATH fixture" {
        # A .cmd file tests Windows executable discovery, not Overmind itself.
        $bin = Join-Path $TestDrive 'overmind-probe-bin'
        New-Item -ItemType Directory -Force -Path $bin | Out-Null
        Set-Content -LiteralPath (Join-Path $bin 'overmind.cmd') -Encoding Ascii -Value '@echo off'
        $priorPath = $env:PATH
        try {
            $env:PATH = "$bin;$priorPath"
            Test-OvermindInstalled | Should -BeTrue
        } finally {
            $env:PATH = $priorPath
        }
    }
}

Describe "Overmind: New-TruthCertHmacKey" {
    It "returns a 64-hex-character string" {
        $k = New-TruthCertHmacKey
        $k.Length | Should -Be 64
        $k | Should -Match '^[0-9a-f]{64}$'
    }
    It "returns different values on repeated calls (probabilistic)" {
        (New-TruthCertHmacKey) | Should -Not -Be (New-TruthCertHmacKey)
    }
}

Describe "Overmind: Set-TruthCertHmacKey" {
    It "rejects empty keys" {
        { Set-TruthCertHmacKey -Key '' -Scope Process } | Should -Throw '*empty*'
    }
    It "sets Process env in current shell" {
        $key = 'a' * 64
        Set-TruthCertHmacKey -Key $key -Scope Process
        $env:TRUTHCERT_HMAC_KEY | Should -Be $key
    }
}

Describe "Overmind: explicit blank signing-key rotation is refused" {
    # Execute the shipped entrypoint in a fresh Windows PowerShell 5.1 host,
    # not a copied helper. EncodedCommand preserves an intentionally empty
    # argument across the pwsh -> powershell.exe native-process boundary.
    It "refuses explicit <Label> -HmacKey before any installer side effects" -ForEach @(
        @{ Label = 'empty'; Key = '' },
        @{ Label = 'whitespace'; Key = '   ' }
    ) {
        $userKeyBefore = [Environment]::GetEnvironmentVariable('TRUTHCERT_HMAC_KEY', 'User')
        # Use .NET's native argument list to preserve even a zero-length
        # argument in a real -File invocation on Windows. Redirect output at
        # the OS process boundary so Write-Host is included in assertions.
        $info = [System.Diagnostics.ProcessStartInfo]::new()
        $info.FileName = (Get-Command powershell.exe).Source
        $info.UseShellExecute = $false
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        foreach ($arg in @('-NoProfile', '-NonInteractive', '-File',
                            $script:OvermindScript, '-SkipPipInstall', '-HmacKey', $Key)) {
            [void]$info.ArgumentList.Add([string]$arg)
        }
        $child = [System.Diagnostics.Process]::Start($info)
        try {
            $output = $child.StandardOutput.ReadToEnd() + $child.StandardError.ReadToEnd()
            $child.WaitForExit()
            $exitCode = $child.ExitCode
        } finally {
            $child.Dispose()
        }
        $exitCode | Should -Be 2
        $output | Should -Match 'REFUSED: -HmacKey was explicitly empty or whitespace'
        $output | Should -Not -Match 'Overmind \\+ TruthCert ready'
        $output | Should -Not -Match 'Installing overmind'
        [Environment]::GetEnvironmentVariable('TRUTHCERT_HMAC_KEY', 'User') |
            Should -Be $userKeyBefore
    }
}

Describe "Overmind: Get-OvermindDefaultSource pins the supply chain (P0)" {
    BeforeEach { Remove-Item Env:OVERMIND_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:OVERMIND_REF -ErrorAction SilentlyContinue }

    It "defaults to a SHA-or-tag (not bare main)" {
        $src = Get-OvermindDefaultSource
        $src | Should -Be 'git+https://github.com/mahmood726-cyber/overmind.git@d3d2de5f84d852f27d64d1686f1e105e190ac375'
    }

    It "honours OVERMIND_REF override (rollback / bleeding-edge)" {
        $env:OVERMIND_REF = 'main'
        Get-OvermindDefaultSource | Should -Be 'git+https://github.com/mahmood726-cyber/overmind.git@main'
    }
}

Describe "Overmind: strict local verifier-health JSON gate (synthetic fixtures)" {
    BeforeAll {
        $script:CanaryChecker = Join-Path $PSScriptRoot 'check-overmind-canary.py'
        $script:Python = (Get-Command python -ErrorAction Stop).Source
    }

    It "accepts the pinned Overmind CERTIFIED shape with a 16-hex bundle hash" {
        '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}' |
            & $script:Python $script:CanaryChecker | Out-Null
        $LASTEXITCODE | Should -Be 0
    }

    It "refuses a zero-exit CLI payload containing passed=false" {
        '{"passed":false,"verdict":"REJECT","alarm_written":"alarm.json"}' |
            & $script:Python $script:CanaryChecker 2>$null | Out-Null
        $LASTEXITCODE | Should -Not -Be 0
    }

    It "refuses conflicting duplicate passed members" {
        '{"passed":false,"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}' |
            & $script:Python $script:CanaryChecker 2>$null | Out-Null
        $LASTEXITCODE | Should -Not -Be 0
    }
}

Describe "ProjectIndex: Get-DefaultProjectIndexRoot" {
    It "returns a filesystem-absolute path" {
        $r = Get-DefaultProjectIndexRoot
        [System.IO.Path]::IsPathRooted($r) | Should -BeTrue
    }
}

Describe "ProjectIndex: Write-IndexMarkdownTemplate" {
    It "creates an INDEX.md with required sections" {
        $target = Join-Path $script:tmpRoot 'INDEX.md'
        Write-IndexMarkdownTemplate -Path $target
        Test-Path $target | Should -BeTrue
        $content = Get-Content -Raw $target
        $content | Should -Match '## Active projects'
        $content | Should -Match '## Submission-ready'
        $content | Should -Match '## Shipped'
        $content | Should -Match '## Triage'
    }
}

Describe "ProjectIndex: Write-ReconcileScript" {
    It "writes a valid Python script" {
        $target = Join-Path $script:tmpRoot 'reconcile_counts.py'
        Write-ReconcileScript -Path $target
        Test-Path $target | Should -BeTrue
        $content = Get-Content -Raw $target
        # Should declare the functions + CLI entry
        $content | Should -Match 'def load_projects_from_index'
        $content | Should -Match 'def main\(\)'
        $content | Should -Match 'PROJECTINDEX_ROOT'
    }

    It "reconcile_counts.py runs clean on an empty INDEX.md template" {
        # Build a fresh dir with just the template INDEX.md + the script
        $sandbox = Join-Path $script:tmpRoot 'reconcile-sandbox'
        New-Item -ItemType Directory -Force -Path $sandbox | Out-Null
        Write-IndexMarkdownTemplate -Path (Join-Path $sandbox 'INDEX.md')
        Write-ReconcileScript -Path (Join-Path $sandbox 'reconcile_counts.py')

        # NOTE: don't use 2>&1 -- PS 5.1 wraps native stderr as ErrorRecord.
        $stdout = & python (Join-Path $sandbox 'reconcile_counts.py') --root $sandbox
        $LASTEXITCODE | Should -Be 0
        ($stdout -join ' ') | Should -Match 'OK: 0'
    }

    It "reconcile_counts.py fails closed on missing-path drift" {
        $sandbox = Join-Path $script:tmpRoot 'drift-sandbox'
        New-Item -ItemType Directory -Force -Path $sandbox | Out-Null
        # INDEX.md references a path that does not exist
        $idx = @"
# Portfolio

## Active projects
- [ghost-project](./ghost-project) -- does not exist. Status: active
"@
        [System.IO.File]::WriteAllText(
            (Join-Path $sandbox 'INDEX.md'),
            $idx,
            (New-Object System.Text.UTF8Encoding $false)
        )
        Write-ReconcileScript -Path (Join-Path $sandbox 'reconcile_counts.py')

        # Script writes to stderr on drift. Use cmd.exe to do the redirect so
        # PowerShell doesn't wrap stderr as ErrorRecord (PS 5.1 quirk).
        $errFile = Join-Path $sandbox 'err.txt'
        $scriptPath = Join-Path $sandbox 'reconcile_counts.py'
        cmd.exe /c "python `"$scriptPath`" --root `"$sandbox`" 2>`"$errFile`""
        $LASTEXITCODE | Should -Be 1
        (Get-Content -Raw $errFile) | Should -Match 'missing'
    }
}

# E156 offline capsule installer: fail-closed render canary, using a disposable
# chartkit fixture and actual Windows PowerShell execution (no network).
Describe "E156 capsules: Windows render canary integrity" {
    BeforeAll {
        $script:CapsulesScript = Join-Path $PSScriptRoot 'install-e156-capsules.ps1'
        . $script:CapsulesScript -Import
        $script:CapsulesDir = Join-Path $script:tmpRoot 'capsule-canary'
        New-Item -ItemType Directory -Force -Path $script:CapsulesDir | Out-Null
        Set-Content -Path (Join-Path $script:CapsulesDir 'sample.capsule.json') -Value '{}' -Encoding UTF8
        $script:SvgWriter = @'
from pathlib import Path
import sys
Path(sys.argv[-1]).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
'@
    }

    It "refuses an unavailable Python command rather than treating it as a pass" {
        Mock Get-Command { $null } -ParameterFilter { $Name -eq 'python' }
        Test-E156Chartkit -TargetDir $script:CapsulesDir | Should -BeFalse
    }

    It "refuses an exit-0 renderer that writes no SVG" {
        Set-Content -Path (Join-Path $script:CapsulesDir 'chartkit.py') -Value 'import sys; sys.exit(0)' -Encoding UTF8
        Test-E156Chartkit -TargetDir $script:CapsulesDir | Should -BeFalse
    }

    It "refuses non-SVG XML despite an exit-0 renderer" {
        Set-Content -Path (Join-Path $script:CapsulesDir 'chartkit.py') -Value 'import sys; open(sys.argv[-1], "w").write("<html/>")' -Encoding UTF8
        Test-E156Chartkit -TargetDir $script:CapsulesDir | Should -BeFalse
    }

    It "accepts a real, parsable SVG output from the fixture renderer" {
        Set-Content -Path (Join-Path $script:CapsulesDir 'chartkit.py') -Value $script:SvgWriter -Encoding UTF8
        Test-E156Chartkit -TargetDir $script:CapsulesDir | Should -BeTrue
    }

    It "renders the repository's real bundled chartkit and illustrative sample" {
        $template = Join-Path (Split-Path -Parent $PSScriptRoot) 'templates/e156-capsule'
        Test-Path (Join-Path $template 'chartkit.py') | Should -BeTrue
        Test-E156Chartkit -TargetDir $template | Should -BeTrue
    }

    It "runs the actual installer: failed rendering exits nonzero without setting User env or printing ready" {
        Set-Content -Path (Join-Path $script:CapsulesDir 'chartkit.py') -Value 'import sys; sys.exit(17)' -Encoding UTF8
        $priorUser = [Environment]::GetEnvironmentVariable('E156_CAPSULES_PATH', 'User')
        try {
            $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script:CapsulesScript -SkipCopy -Target $script:CapsulesDir 2>&1 | Out-String
            $code = $LASTEXITCODE
            $code | Should -Not -Be 0
            $output | Should -Match 'REFUSED: chart-kit render canary failed'
            $output | Should -Not -Match 'e156-capsules installed at'
            [Environment]::GetEnvironmentVariable('E156_CAPSULES_PATH', 'User') | Should -Be $priorUser
        } finally {
            # Restore even if a prior implementation erroneously persisted the path.
            [Environment]::SetEnvironmentVariable('E156_CAPSULES_PATH', $priorUser, 'User')
        }
    }
}
