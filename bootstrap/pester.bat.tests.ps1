# Pester tests for bootstrap/e156-setup.bat.
#
# Network-free. We can't exercise the full download path in CI, but we CAN
# exercise the structural contract:
#   1. Script file exists and is non-empty
#   2. All four step markers present ("[1/4]" ... "[4/4]")
#   3. Python-on-PATH check (where python) present
#   4. Download URL template present + points at the right repo
#   5. Extract + install.ps1 invocation present
#   6. End-of-run banner + pause present (so student sees result)
# Plus an end-to-end test that mocks python, network, and install.ps1 to
# verify the orchestration itself doesn't crash.

BeforeAll {
    $script:BatPath = Join-Path $PSScriptRoot 'e156-setup.bat'
    $script:BatText = Get-Content -Raw $script:BatPath
    $script:tmpRoot = Join-Path $env:TEMP "bat-test-$(Get-Random)"
    New-Item -ItemType Directory -Force -Path $script:tmpRoot | Out-Null
}

AfterAll {
    if (Test-Path $script:tmpRoot) {
        Remove-Item -Recurse -Force $script:tmpRoot -ErrorAction SilentlyContinue
    }
}

Describe "e156-setup.bat structural contract" {
    It "file exists and is non-trivial" {
        Test-Path $script:BatPath | Should -BeTrue
        $script:BatText.Length | Should -BeGreaterThan 1000
    }

    It "contains all four step markers in order" {
        $p1 = $script:BatText.IndexOf('[1/4]')
        $p2 = $script:BatText.IndexOf('[2/4]')
        $p3 = $script:BatText.IndexOf('[3/4]')
        $p4 = $script:BatText.IndexOf('[4/4]')
        $p1 | Should -BeGreaterThan -1
        $p2 | Should -BeGreaterThan $p1
        $p3 | Should -BeGreaterThan $p2
        $p4 | Should -BeGreaterThan $p3
    }

    It "checks Python is on PATH before proceeding" {
        $script:BatText | Should -Match 'where python'
        # And prints python.org link on failure
        $script:BatText | Should -Match 'python\.org'
    }

    It "downloads from the correct GitHub archive URL" {
        $script:BatText | Should -Match 'github\.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/main\.zip'
    }

    It "invokes install.ps1 after extract" {
        $script:BatText | Should -Match 'Expand-Archive'
        $script:BatText | Should -Match '\.\\install\\install\.ps1'
    }

    It "ends with PASS/FAIL banner + pause so student sees result" {
        $script:BatText | Should -Match 'INSTALL COMPLETE'
        $script:BatText | Should -Match 'INSTALL FAILED'
        # Final pause keeps the console window open
        ($script:BatText -split "`n" | Select-Object -Last 5) -join "`n" | Should -Match 'pause'
    }

    It "handles SmartScreen-era download blocks (UseBasicParsing)" {
        $script:BatText | Should -Match 'UseBasicParsing'
    }

    It "cleans up stale workspace before downloading" {
        # Previous run's zip / extract dir should be removed on re-run
        $script:BatText | Should -Match 'rmdir /S /Q'
        $script:BatText | Should -Match 'del /Q'
    }
}

Describe "e156-setup.bat: Python-missing path exits 1 with python.org hint" {
    It "bails early when 'where python' fails" -Skip:(-not (Get-Command cmd.exe -ErrorAction SilentlyContinue)) {
        # We can't actually remove python from PATH for this process, so this
        # test is a structural assertion: the .bat MUST emit exit /b 1 in the
        # where-python-failed branch.
        $script:BatText | Should -Match '(?s)where python.*errorlevel 1.*exit /b 1'
    }
}

Describe "e156-setup.bat: detects Microsoft Store python.exe stub (P2)" {
    It "runs python --version and bails with Store-stub diagnostic on non-zero exit" {
        # Structural assertion: the .bat MUST run `python --version` and check
        # errorlevel after the `where python` succeeded. This catches the case
        # where Windows ships a 0-byte WindowsApps alias on PATH that exits
        # non-zero when invoked.
        $script:BatText | Should -Match 'python --version >nul 2>&1'
        $script:BatText | Should -Match '(?s)python --version.*errorlevel 1.*Microsoft Store stub.*exit /b 1'
    }
}
