# Isolated Windows tests for the actual offline E156 capsule render gate.
# Synthetic fixtures exercise installer integrity, not clinical validation.
BeforeAll {
    . (Join-Path $PSScriptRoot 'install-e156-capsules.ps1') -Import
}
Describe 'E156 capsule installer refuses invalid canaries' {
    It 'refuses a missing Python interpreter' {
        Mock Get-Command { $null } -ParameterFilter { $Name -eq 'python' }
        Test-E156Chartkit -TargetDir $TestDrive | Should -BeFalse
    }

    It 'refuses a renderer that returns zero but writes no SVG' {
        Get-Command python -ErrorAction Stop | Should -Not -BeNullOrEmpty
        $fixture = Join-Path $TestDrive 'no-svg'
        New-Item -ItemType Directory -Path $fixture -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $fixture 'chartkit.py') -Value 'pass'
        Set-Content -LiteralPath (Join-Path $fixture 'sample.capsule.json') -Value '{}'
        Test-E156Chartkit -TargetDir $fixture | Should -BeFalse
    }

    It 'refuses a renderer that returns nonzero in a real installer process' {
        Get-Command python -ErrorAction Stop | Should -Not -BeNullOrEmpty
        $fixture = Join-Path $TestDrive 'broken'
        New-Item -ItemType Directory -Path $fixture -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $fixture 'chartkit.py') -Value 'raise SystemExit(7)'
        Set-Content -LiteralPath (Join-Path $fixture 'sample.capsule.json') -Value '{}'
        $installer = Join-Path $PSScriptRoot 'install-e156-capsules.ps1'
        $output = & pwsh -NoProfile -File $installer -Target $fixture -SkipCopy 2>&1 | Out-String
        $LASTEXITCODE | Should -Be 1
        $output | Should -Match 'refusing a successful installation'
    }

    It 'accepts an actual non-empty SVG written by Python' {
        Get-Command python -ErrorAction Stop | Should -Not -BeNullOrEmpty
        $fixture = Join-Path $TestDrive 'valid'
        New-Item -ItemType Directory -Path $fixture -Force | Out-Null
        $program = "from pathlib import Path`nimport sys`nPath(sys.argv[-1]).write_bytes(b'<svg/>')"
        Set-Content -LiteralPath (Join-Path $fixture 'chartkit.py') -Value $program
        Set-Content -LiteralPath (Join-Path $fixture 'sample.capsule.json') -Value '{}'
        Test-E156Chartkit -TargetDir $fixture | Should -BeTrue
    }
}
