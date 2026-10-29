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
    It "is true when sentinel is on PATH (author's machine contract)" {
        # Isolated PATH-discovery fixture: this tiny .cmd is NOT the real
        # Sentinel CLI. Never count this as a pinned full-system canary.
        $bin = Join-Path $TestDrive 'sentinel-probe-bin'
        New-Item -ItemType Directory -Force -Path $bin | Out-Null
        Set-Content -LiteralPath (Join-Path $bin 'sentinel.cmd') -Encoding Ascii -Value '@echo off'
        $previousPath = $env:PATH
        try {
            $env:PATH = "$bin;$previousPath"
            Test-SentinelInstalled | Should -BeTrue
        } finally {
            $env:PATH = $previousPath
        }
    }
    It "is false when Sentinel is not discoverable (isolated mock)" {
        Mock Get-Command { $null } -ParameterFilter { $Name -eq 'sentinel' }
        Test-SentinelInstalled | Should -BeFalse
        Should -Invoke Get-Command -Times 1 -Exactly -ParameterFilter { $Name -eq 'sentinel' }
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

Describe "Backup-ExistingPrePushHook (P0 - researcher's existing hook)" {
    BeforeAll {
        $script:hookTmp = Join-Path $env:TEMP "sentinel-hook-test-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path (Join-Path $script:hookTmp '.git\hooks') | Out-Null
    }
    AfterAll {
        if (Test-Path $script:hookTmp) {
            Remove-Item -Recurse -Force $script:hookTmp -ErrorAction SilentlyContinue
        }
    }
    BeforeEach {
        Get-ChildItem (Join-Path $script:hookTmp '.git\hooks') -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    It "returns nothing when no pre-push hook exists" {
        $r = Backup-ExistingPrePushHook -RepoPath $script:hookTmp
        $r | Should -BeNullOrEmpty
    }

    It "backs up a user-authored hook with a timestamped suffix" {
        $hook = Join-Path $script:hookTmp '.git\hooks\pre-push'
        Set-Content -Path $hook -Value "#!/bin/sh`nmy custom lint" -NoNewline
        $backup = Backup-ExistingPrePushHook -RepoPath $script:hookTmp
        $backup | Should -Match 'pre-push\.user-\d{8}-\d{6}$'
        Test-Path $backup | Should -BeTrue
        (Get-Content -Raw $backup) | Should -Match 'my custom lint'
    }

    It "skips backup when the hook is already a Sentinel-installed hook" {
        $hook = Join-Path $script:hookTmp '.git\hooks\pre-push'
        Set-Content -Path $hook -Value "#!/bin/sh`nsentinel run-pre-push --repo ." -NoNewline
        $r = Backup-ExistingPrePushHook -RepoPath $script:hookTmp
        $r | Should -BeNullOrEmpty
        # No backup file should exist
        (Get-ChildItem (Join-Path $script:hookTmp '.git\hooks') -Filter 'pre-push.user-*').Count | Should -Be 0
    }
}

Describe "Get-SentinelDefaultSource pins the supply chain (P0)" {
    BeforeEach { Remove-Item Env:SENTINEL_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:SENTINEL_REF -ErrorAction SilentlyContinue }

    It "defaults to an immutable ref (a version tag or commit SHA, not bare main)" {
        # Sentinel is pinned to a commit SHA (the 53-rule build) until a newer
        # semver tag ships - same supply-chain approach as the Overmind installer.
        # The guard rejects a mutable default like 'main'; both a version tag
        # (v1.2.3) and a 7-40 char hex SHA are accepted.
        $src = Get-SentinelDefaultSource
        $src | Should -Match '^git\+https://github\.com/mahmood726-cyber/Sentinel\.git@(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
    }
    It "the pin pattern itself rejects mutable refs (guards the guard)" {
        foreach ($mutable in 'main', 'master', 'HEAD', 'latest', 'dev', 'v1.0.0-rc', 'v1.x') {
            $mutable | Should -Not -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
        }
        foreach ($pinned in 'v1', 'v1.0', 'v1.0.0', '89b8474', '3f35954bf51c9f3e8c7215dc018ed9e66984b650') {
            $pinned | Should -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
        }
    }

    It "honours SENTINEL_REF override (rollback / bleeding-edge)" {
        $env:SENTINEL_REF = 'main'
        Get-SentinelDefaultSource | Should -Be 'git+https://github.com/mahmood726-cyber/Sentinel.git@main'
    }
}
