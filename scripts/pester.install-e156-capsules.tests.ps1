# Isolated Windows tests for the actual offline E156 capsule render gate.
# Synthetic fixtures exercise installer integrity, not clinical validation.
BeforeAll {
    . (Join-Path $PSScriptRoot 'install-e156-capsules.ps1') -Import
}
Describe 'E156 capsule copy safety' {
    It 'refuses to overwrite an existing nonempty destination' {
        $src = Join-Path (Split-Path -Parent $PSScriptRoot) 'templates/e156-capsule'
        $target = Join-Path $TestDrive 'existing-capsules'
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        $owned = Join-Path $target 'chartkit.py'
        Set-Content -LiteralPath $owned -Value 'human-owned content'
        { Copy-E156Template -Src $src -Dst $target } | Should -Throw '*REFUSED*'
        (Get-Content -LiteralPath $owned -Raw).Trim() | Should -BeExactly 'human-owned content'
        @(Get-ChildItem -LiteralPath $target -Force).Count | Should -Be 1
    }

    It 'copies the actual bundled template into a fresh target' {
        $src = Join-Path (Split-Path -Parent $PSScriptRoot) 'templates/e156-capsule'
        $target = Join-Path $TestDrive 'new-capsules'
        Copy-E156Template -Src $src -Dst $target
        (Test-Path -LiteralPath (Join-Path $target 'chartkit.py') -PathType Leaf) | Should -BeTrue
        (Test-Path -LiteralPath (Join-Path $target 'sample.capsule.json') -PathType Leaf) | Should -BeTrue
    }
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

    It 'refuses a renderer that writes non-SVG bytes despite exit zero' {
        Get-Command python -ErrorAction Stop | Should -Not -BeNullOrEmpty
        $fixture = Join-Path $TestDrive 'not-svg'
        New-Item -ItemType Directory -Path $fixture -Force | Out-Null
        $program = "from pathlib import Path`nimport sys`nPath(sys.argv[-1]).write_bytes(b'NOT SVG')"
        Set-Content -LiteralPath (Join-Path $fixture 'chartkit.py') -Value $program
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


    It 'refuses impostor SVG roots despite renderer exit zero' {
        Get-Command python -ErrorAction Stop | Should -Not -BeNullOrEmpty
        $impostors = @(
            '<svg xmlns="urn:not-svg"/>',
            '<foreign:svg xmlns:foreign="urn:not-svg"/>',
            '<SVG/>',
            '<svg xmlns="http://www.w3.org/2000/SVG"/>'
        )
        for ($i = 0; $i -lt $impostors.Count; $i++) {
            $fixture = Join-Path $TestDrive ("impostor-svg-" + $i)
            New-Item -ItemType Directory -Path $fixture -Force | Out-Null
            $program = "from pathlib import Path`nimport sys`nPath(sys.argv[-1]).write_bytes(b'$($impostors[$i])')"
            Set-Content -LiteralPath (Join-Path $fixture 'chartkit.py') -Value $program
            Set-Content -LiteralPath (Join-Path $fixture 'sample.capsule.json') -Value '{}'
            Test-E156Chartkit -TargetDir $fixture | Should -BeFalse -Because "XML root $($impostors[$i]) is not SVG"
        }
    }

    It 'accepts a correctly namespaced SVG root' {
        Get-Command python -ErrorAction Stop | Should -Not -BeNullOrEmpty
        $fixture = Join-Path $TestDrive 'namespaced-svg'
        New-Item -ItemType Directory -Path $fixture -Force | Out-Null
        $program = "from pathlib import Path`nimport sys`nPath(sys.argv[-1]).write_bytes(b'<svg xmlns=`"http://www.w3.org/2000/svg`"/>')"
        Set-Content -LiteralPath (Join-Path $fixture 'chartkit.py') -Value $program
        Set-Content -LiteralPath (Join-Path $fixture 'sample.capsule.json') -Value '{}'
        Test-E156Chartkit -TargetDir $fixture | Should -BeTrue
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
