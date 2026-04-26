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
