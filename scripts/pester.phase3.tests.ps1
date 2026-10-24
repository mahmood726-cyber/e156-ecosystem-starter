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

Describe "Overmind: Get-OvermindDefaultSource pins the supply chain (P0)" {
    BeforeEach { Remove-Item Env:OVERMIND_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:OVERMIND_REF -ErrorAction SilentlyContinue }

    It "defaults to a SHA-or-tag (not bare main)" {
        $src = Get-OvermindDefaultSource
        $src | Should -Match '^git\+https://github\.com/mahmood726-cyber/overmind\.git@[A-Za-z0-9._-]+$'
        $src | Should -Not -Match '@main$'
    }

    It "honours OVERMIND_REF override (rollback / bleeding-edge)" {
        $env:OVERMIND_REF = 'main'
        Get-OvermindDefaultSource | Should -Be 'git+https://github.com/mahmood726-cyber/overmind.git@main'
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
