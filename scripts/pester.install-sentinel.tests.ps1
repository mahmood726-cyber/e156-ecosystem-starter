# Pester tests for install-sentinel.ps1 (helper functions only).
#
# Does NOT install anything or hit pip. The actual install-hook call is
# covered by Sentinel's own test suite; here we only verify the wrapper
# functions make correct decisions.

BeforeAll {
    $script:Script = Join-Path $PSScriptRoot 'install-sentinel.ps1'
    . $Script -Import
}

Describe "Test-SentinelInstalled" {
    It "returns a boolean" {
        $r = Test-SentinelInstalled
        $r | Should -BeOfType [bool]
    }
    It "is true when sentinel is on PATH (author's machine contract)" -Skip:(-not (Get-Command sentinel -ErrorAction SilentlyContinue)) {
        # Documents the ecosystem-starter assumption on a developer machine.
        # Skipped in CI / fresh-runner environments where sentinel isn't
        # pre-installed; not a regression to ship.
        Test-SentinelInstalled | Should -BeTrue
    }
}

Describe "Install-SentinelHookInRepo refuses non-repos" {
    It "throws on a directory that has no .git/" {
        $tmp = Join-Path $env:TEMP "sentinel-test-not-a-repo-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path $tmp | Out-Null
        try {
            { Install-SentinelHookInRepo -RepoPath $tmp } | Should -Throw "*Not a git repo*"
        } finally {
            Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
        }
    }
}

Describe "Get-SentinelBypassLogPath resolves under the user home" {
    It "ends with .sentinel-logs\bypass.log" {
        $p = Get-SentinelBypassLogPath
        $p | Should -Match '\.sentinel-logs[\\\/]bypass\.log$'
    }
    It "lives under the user profile" {
        $p = Get-SentinelBypassLogPath
        $userHome = $env:USERPROFILE
        if (-not $userHome) { $userHome = $HOME }
        $p | Should -BeLike "$userHome*"
    }
}

Describe "Get-SentinelDefaultSource pins the supply chain (P0)" {
    BeforeEach { Remove-Item Env:SENTINEL_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:SENTINEL_REF -ErrorAction SilentlyContinue }

    It "defaults to a tagged release (not bare main)" {
        $src = Get-SentinelDefaultSource
        $src | Should -Match '^git\+https://github\.com/mahmood726-cyber/Sentinel\.git@v\d'
    }

    It "honours SENTINEL_REF override (rollback / bleeding-edge)" {
        $env:SENTINEL_REF = 'main'
        Get-SentinelDefaultSource | Should -Be 'git+https://github.com/mahmood726-cyber/Sentinel.git@main'
    }
}
