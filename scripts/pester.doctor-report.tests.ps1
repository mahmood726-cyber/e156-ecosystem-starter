# Pester tests for scripts/doctor-report.ps1 helpers.

BeforeAll {
    . (Join-Path $PSScriptRoot 'doctor-report.ps1') -Import
}

Describe "Get-RedactedPath" {
    It "returns the path unchanged if it has <=2 components" {
        (Get-RedactedPath -Path 'foo\bar') | Should -Be 'foo\bar'
        (Get-RedactedPath -Path 'foo')     | Should -Be 'foo'
    }
    It "redacts leading segments of deep paths" {
        $out = Get-RedactedPath -Path 'C:\Users\alice\Projects\my-paper\index.html'
        $out | Should -Be '...\my-paper\index.html'
    }
    It "handles empty / null without throwing" {
        (Get-RedactedPath -Path '')   | Should -Be ''
    }
}

Describe "Test-CLIPresent" {
    It "returns boolean" {
        (Test-CLIPresent -Name 'powershell') | Should -BeOfType [bool]
    }
    It "returns true for a command we know exists" {
        Test-CLIPresent -Name 'powershell' | Should -BeTrue
    }
    It "returns false for a command that definitely does not exist" {
        Test-CLIPresent -Name 'no-such-tool-abcxyz123' | Should -BeFalse
    }
}

Describe "Build-IssueUrl" {
    It "produces a URL pointing at the ecosystem-starter issues endpoint" {
        $u = Build-IssueUrl -Body 'hello world' -Title 'test'
        $u | Should -Match 'https://github\.com/mahmood726-cyber/e156-ecosystem-starter/issues/new'
        $u | Should -Match 'title='
        $u | Should -Match 'body='
    }
    It "URL-encodes the body so spaces don't break the link" {
        $u = Build-IssueUrl -Body 'has spaces & ampersands'
        $u | Should -Not -Match ' '      # raw space would be invalid in a URL
        $u | Should -Match '(has(%20|\+)spaces|%20)'
    }
    It "handles a 100 KB body by truncating to <=60 KB encoded" {
        $huge = 'x' * 100000
        $u = Build-IssueUrl -Body $huge
        # "body=" prefix + up to 60K payload
        $bodyPart = ($u -split 'body=')[1]
        $bodyPart.Length | Should -BeLessOrEqual 60005  # 60000 + "..."
    }
}

Describe "Build-Report structure" {
    It "returns a multi-section markdown report" {
        $r = Build-Report
        $r | Should -Match '# e156-ecosystem-starter install report'
        $r | Should -Match '## Environment'
        $r | Should -Match '## Agent CLIs on PATH'
        $r | Should -Match '## Layers installed'
        $r | Should -Match '## Recent error logs'
    }
    It "does NOT leak env var values (names only)" {
        # Set a secret-looking env var and confirm its value doesn't show up
        $env:E156_DOCTOR_TEST_SECRET = 'super-secret-dont-leak-12345'
        try {
            $r = Build-Report
            $r | Should -Not -Match 'super-secret-dont-leak-12345'
        } finally {
            Remove-Item 'Env:E156_DOCTOR_TEST_SECRET' -ErrorAction SilentlyContinue
        }
    }
}
