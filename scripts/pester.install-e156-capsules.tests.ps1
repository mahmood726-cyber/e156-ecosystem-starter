# Offline E156 capsule installer: real renderer canary + failure injection.
# These checks do not install Sentinel, Overmind or an E156 publication.
BeforeAll {
    $script:Installer = Join-Path $PSScriptRoot 'install-e156-capsules.ps1'
    . $script:Installer -Import
    $script:Bundled = Join-Path (Split-Path -Parent $PSScriptRoot) 'templates/e156-capsule'
}

Describe 'E156 offline chart-kit installer refuses unverified canaries' {
    It 'executes the real bundled chart-kit and creates an SVG' {
        # Verifies a genuine local renderer execution, not only a mocked return value.
        Test-E156Chartkit -TargetDir $script:Bundled | Should -BeTrue
    }

    It 'does not treat absent Python as a passed canary' {
        $oldPath = $env:PATH
        try {
            $env:PATH = Join-Path $env:TEMP ('no-python-' + [guid]::NewGuid().ToString('N'))
            Test-E156Chartkit -TargetDir $script:Bundled | Should -BeFalse
        } finally {
            $env:PATH = $oldPath
        }
    }

    It 'refuses a zero-exit renderer that produced no SVG and does not report installed' {
        $fixture = Join-Path $env:TEMP ('e156-canary-empty-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $fixture | Out-Null
        try {
            Set-Content -Path (Join-Path $fixture 'chartkit.py') -Value 'raise SystemExit(0)' -Encoding ascii
            $output = & pwsh -NoProfile -File $script:Installer -SkipCopy -Target $fixture 2>&1
            $exitCode = $LASTEXITCODE
            $exitCode | Should -Not -Be 0
            ($output -join "`n") | Should -Match 'REFUSED:'
            ($output -join "`n") | Should -Not -Match 'e156-capsules installed at'
        } finally {
            Remove-Item -Recurse -Force $fixture -ErrorAction SilentlyContinue
        }
    }

    It 'refuses nonempty garbage that is not SVG' {
        $fixture = Join-Path $env:TEMP ('e156-canary-invalid-svg-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $fixture | Out-Null
        try {
            Set-Content -Path (Join-Path $fixture 'chartkit.py') -Value 'import sys; from pathlib import Path; Path(sys.argv[sys.argv.index("--out") + 1]).write_text("garbage, not SVG")' -Encoding ascii
            $output = & pwsh -NoProfile -File $script:Installer -SkipCopy -Target $fixture 2>&1
            $LASTEXITCODE | Should -Not -Be 0
            ($output -join "`n") | Should -Match 'REFUSED:'
            ($output -join "`n") | Should -Not -Match 'e156-capsules installed at'
        } finally {
            Remove-Item -Recurse -Force $fixture -ErrorAction SilentlyContinue
        }
    }

    It 'refuses a namespace-correct SVG root without chart primitives' {
        $fixture = Join-Path $env:TEMP ('e156-canary-chartless-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $fixture | Out-Null
        try {
            Set-Content -Path (Join-Path $fixture 'chartkit.py') -Value 'import sys; from pathlib import Path; Path(sys.argv[sys.argv.index("--out") + 1]).write_text("<svg xmlns=\\\"http://www.w3.org/2000/svg\\\"></svg>")' -Encoding ascii
            $output = & pwsh -NoProfile -File $script:Installer -SkipCopy -Target $fixture 2>&1
            $LASTEXITCODE | Should -Not -Be 0
            ($output -join "`n") | Should -Match 'REFUSED:'
            ($output -join "`n") | Should -Not -Match 'e156-capsules installed at'
        } finally {
            Remove-Item -Recurse -Force $fixture -ErrorAction SilentlyContinue
        }
    }

    It 'refuses a nonzero renderer and does not report installed' {
        $fixture = Join-Path $env:TEMP ('e156-canary-fail-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $fixture | Out-Null
        try {
            Set-Content -Path (Join-Path $fixture 'chartkit.py') -Value 'raise SystemExit(17)' -Encoding ascii
            $output = & pwsh -NoProfile -File $script:Installer -SkipCopy -Target $fixture 2>&1
            $exitCode = $LASTEXITCODE
            $exitCode | Should -Not -Be 0
            ($output -join "`n") | Should -Match 'REFUSED:'
            ($output -join "`n") | Should -Not -Match 'e156-capsules installed at'
        } finally {
            Remove-Item -Recurse -Force $fixture -ErrorAction SilentlyContinue
        }
    }
}
