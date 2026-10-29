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
        $src | Should -Be 'git+https://github.com/mahmood726-cyber/Sentinel.git@5808f2bdc024506fa3d49a367c88b42b15fdf164'
    }
    It "the pin pattern itself rejects mutable refs (guards the guard)" {
        foreach ($mutable in 'main', 'master', 'HEAD', 'latest', 'dev', 'v1.0.0-rc', 'v1.x') {
            $mutable | Should -Not -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
        }
        foreach ($pinned in 'v1', 'v1.0', 'v1.0.0', '89b8474', '3f35954bf51c9f3e8c7215dc018ed9e66984b650') {
            $pinned | Should -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
        }
    }

    # Retain the historic test identity for the honest-ratchet; the override is
    # permitted only for an exact immutable SHA, including rollback/newer commits.
    It "honours SENTINEL_REF override (rollback / bleeding-edge)" {
        $env:SENTINEL_REF = 'f' * 40
        Get-SentinelDefaultSource | Should -Be ("git+https://github.com/mahmood726-cyber/Sentinel.git@" + ('f' * 40))
    }

    It "refuses mutable or malformed SENTINEL_REF overrides" {
        foreach ($unsafe in @('main', 'master', 'HEAD', 'v1.0.0', 'deadbeef', ('f' * 39), ('f' * 41), ('F' * 40))) {
            $env:SENTINEL_REF = $unsafe
            { Get-SentinelDefaultSource } | Should -Throw '*40-character commit SHA*'
        }
    }
}

Describe "Windows Sentinel post-install hook integrity (isolated failure injection)" {
    BeforeAll {
        # A deliberately bounded fake CLI: these tests exercise the STARTER
        # postcondition, not a real Sentinel installation or a live scan.
        function global:sentinel {
            if ($null -ne $global:SentinelStubContent) {
                [System.IO.File]::WriteAllText(
                    $global:SentinelStubHook, [string]$global:SentinelStubContent
                )
            }
            $global:LASTEXITCODE = 0
        }
        $script:canonicalMarker = '# === SENTINEL PRE-PUSH HOOK (do not edit above this line) ==='
        $script:scanner = 'output="$(python -m sentinel scan --repo "$REPO_TOPLEVEL" 2>&1)"'
    }
    AfterAll {
        Remove-Item Function:\global:sentinel -ErrorAction SilentlyContinue
        Remove-Variable SentinelStubContent -Scope Global -ErrorAction SilentlyContinue
        Remove-Variable SentinelStubHook -Scope Global -ErrorAction SilentlyContinue
    }
    BeforeEach {
        $script:stubRoot = Join-Path $env:TEMP "sentinel-hook-postcondition-$([guid]::NewGuid().ToString('N'))"
        $hookDir = Join-Path $script:stubRoot '.git\hooks'
        New-Item -ItemType Directory -Force -Path $hookDir | Out-Null
        $global:SentinelStubHook = Join-Path $hookDir 'pre-push'
        $global:SentinelStubContent = $null
        $global:LASTEXITCODE = 0
    }
    AfterEach {
        Remove-Item -LiteralPath $script:stubRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    It "refuses exit zero with no generated pre-push hook" {
        { Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode block } |
            Should -Throw "*no pre-push hook exists*"
    }

    It "refuses a non-Sentinel hook even if CLI reports success" {
        $global:SentinelStubContent = "#!/bin/sh`necho fake success`n"
        { Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode block } |
            Should -Throw "*identity/mode verification failed*"
    }

    It "refuses a hook that merely claims the Sentinel banner without invoking the scanner" {
        $global:SentinelStubContent = "#!/bin/sh`n$script:canonicalMarker`n" +
            'MODE="${SENTINEL_MODE:-block}"'
        { Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode block } |
            Should -Throw "*identity/mode verification failed*"
    }

    It "refuses the wrong installed mode despite a successful CLI exit" {
        $global:SentinelStubContent = "#!/bin/sh`n$script:canonicalMarker`n$script:scanner`n" +
            'MODE="${SENTINEL_MODE:-warn}"'
        { Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode block } |
            Should -Throw "*identity/mode verification failed*"
    }

    It "accepts a canonical-looking fixture with the requested block mode" {
        $global:SentinelStubContent = "#!/bin/sh`n$script:canonicalMarker`n$script:scanner`n" +
            'MODE="${SENTINEL_MODE:-block}"'
        $result = Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode block
        $result | Should -Be $script:stubRoot
    }

    It "defaults to a verified BLOCK hook when HookMode is omitted" {
        $global:SentinelStubContent = ("#!/bin/sh" + [char]10 + $script:canonicalMarker + [char]10 + $script:scanner + [char]10 +
            'MODE="${SENTINEL_MODE:-block}"')
        $result = Install-SentinelHookInRepo -RepoPath $script:stubRoot
        $result | Should -Be $script:stubRoot
    }

    It "permits explicit WARN opt-in without silently changing the default" {
        $global:SentinelStubContent = ("#!/bin/sh" + [char]10 + $script:canonicalMarker + [char]10 + $script:scanner + [char]10 +
            'MODE="${SENTINEL_MODE:-warn}"')
        $result = Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode warn
        $result | Should -Be $script:stubRoot
    }

    It "refuses off-mode before a hook can be created" {
        { Install-SentinelHookInRepo -RepoPath $script:stubRoot -HookMode off } | Should -Throw
        (Test-Path -LiteralPath $global:SentinelStubHook) | Should -BeFalse
    }

    It "the Starter Windows entrypoint itself defaults to BLOCK" {
        $source = Get-Content -LiteralPath $script:Script -Raw
        $source.Contains('    [ValidateSet(''warn'', ''block'')][string]$Mode = ''block'',') | Should -BeTrue
    }

}
