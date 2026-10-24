# Pester tests for install-extractor.ps1 (helper functions only).
#
# Does NOT clone anything, hit the network, or pip-install. The real clone +
# import is covered by a bash smoke test and rct-extractor-v2's own suite;
# here we only verify the wrapper functions make correct decisions.

BeforeAll {
    $script:Script = Join-Path $PSScriptRoot 'install-extractor.ps1'
    . $Script -Import
}

Describe "Test-ExtractorPresent" {
    It "returns a boolean" {
        Test-ExtractorPresent -Dir $env:TEMP | Should -BeOfType [bool]
    }
    It "is false for a dir without scripts/build_metakit_config.py" {
        $tmp = Join-Path $env:TEMP "extractor-test-empty-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path $tmp | Out-Null
        try { Test-ExtractorPresent -Dir $tmp | Should -BeFalse }
        finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
    }
    It "is true when the bridge entrypoint exists" {
        $tmp = Join-Path $env:TEMP "extractor-test-present-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path (Join-Path $tmp 'scripts') | Out-Null
        Set-Content -Path (Join-Path $tmp 'scripts\build_metakit_config.py') -Value '# stub' -NoNewline
        try { Test-ExtractorPresent -Dir $tmp | Should -BeTrue }
        finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
    }
    It "is false for an empty/null dir" {
        Test-ExtractorPresent -Dir '' | Should -BeFalse
    }
}

Describe "Get-ExtractorRepoUrl points at the real repo" {
    It "is the rct-extractor-v2 GitHub URL" {
        Get-ExtractorRepoUrl | Should -Be 'https://github.com/mahmood726-cyber/rct-extractor-v2.git'
    }
}

Describe "Get-ExtractorDefaultRef pins the supply chain (P0)" {
    BeforeEach { Remove-Item Env:RCT_EXTRACTOR_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:RCT_EXTRACTOR_REF -ErrorAction SilentlyContinue }

    It "defaults to an immutable ref (a version tag or commit SHA, not bare main)" {
        # Same pinning discipline as Sentinel/Overmind: reject a mutable default
        # like 'main'. Accept a version tag (v1.2.3) or a 7-40 char hex SHA.
        Get-ExtractorDefaultRef | Should -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
    }
    It "the pin pattern itself rejects mutable refs (guards the guard)" {
        foreach ($mutable in 'main', 'master', 'HEAD', 'latest', 'dev', 'v1.0.0-rc', 'v1.x') {
            $mutable | Should -Not -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
        }
        foreach ($pinned in 'v1', 'v1.0', 'v1.0.0', '89b8474', '3f35954bf51c9f3e8c7215dc018ed9e66984b650') {
            $pinned | Should -Match '^(v\d+(\.\d+){0,2}|[0-9a-f]{7,40})$'
        }
    }
    It "honours RCT_EXTRACTOR_REF override (rollback / bleeding-edge)" {
        $env:RCT_EXTRACTOR_REF = 'main'
        Get-ExtractorDefaultRef | Should -Be 'main'
    }
}

Describe "Get-ExtractorDefaultTarget resolves under the user code workspace" {
    It "ends with code\rct-extractor-v2" {
        Get-ExtractorDefaultTarget | Should -Match 'code[\\\/]rct-extractor-v2$'
    }
    It "lives under the user profile" {
        Get-ExtractorDefaultTarget | Should -BeLike "$env:USERPROFILE*"
    }
}


# These are isolated real-Git tests against a disposable local bare remote,
# not a live extractor release, signed certificate, or end-to-end canary.
Describe "Install-ExtractorClone fetches and proves exact requested ref" {
    BeforeAll {
        $script:refSandbox = Join-Path ([IO.Path]::GetTempPath()) ("extractor-ref-" + [guid]::NewGuid().ToString('N'))
        $script:refRemote = Join-Path $script:refSandbox 'origin.git'
        $script:refSeed = Join-Path $script:refSandbox 'seed'
        New-Item -ItemType Directory -Force -Path $script:refSandbox | Out-Null

        & git init --bare --quiet $script:refRemote
        if ($LASTEXITCODE -ne 0) { throw 'local bare git fixture initialization failed' }
        & git init --quiet $script:refSeed
        if ($LASTEXITCODE -ne 0) { throw 'local git fixture initialization failed' }
        & git -C $script:refSeed config user.email 'fixture@example.invalid'
        & git -C $script:refSeed config user.name 'Local test fixture'
        New-Item -ItemType Directory -Force -Path (Join-Path $script:refSeed 'scripts') | Out-Null
        Set-Content -LiteralPath (Join-Path $script:refSeed 'scripts/build_metakit_config.py') -Value '# fixture entrypoint'
        & git -C $script:refSeed add scripts/build_metakit_config.py
        & git -C $script:refSeed commit --quiet -m 'fixture only'
        if ($LASTEXITCODE -ne 0) { throw 'local fixture commit failed' }
        $script:refSha = (& git -C $script:refSeed rev-parse HEAD).Trim()
        & git -C $script:refSeed tag v1.0.0
        & git -C $script:refSeed remote add origin $script:refRemote
        & git -C $script:refSeed push --quiet origin HEAD:refs/heads/main refs/tags/v1.0.0
        if ($LASTEXITCODE -ne 0) { throw 'local fixture push failed' }
        & git --git-dir $script:refRemote symbolic-ref HEAD refs/heads/main
        if ($LASTEXITCODE -ne 0) { throw 'local fixture HEAD setup failed' }
    }
    AfterAll {
        Remove-Item -LiteralPath $script:refSandbox -Recurse -Force -ErrorAction SilentlyContinue
    }
    BeforeEach {
        Mock Get-ExtractorRepoUrl { $script:refRemote }
    }

    It "checks out a requested tag to its exact detached commit" {
        $target = Join-Path $script:refSandbox 'tag-install'
        Install-ExtractorClone -TargetDir $target -Ref v1.0.0
        (& git -C $target rev-parse HEAD).Trim() | Should -Be $script:refSha
        Test-ExtractorPresent -Dir $target | Should -BeTrue
        & git -C $target symbolic-ref --quiet HEAD 2>$null
        $LASTEXITCODE | Should -Not -Be 0
    }

    It "checks out a requested full 40-character commit SHA" {
        $target = Join-Path $script:refSandbox 'sha-install'
        Install-ExtractorClone -TargetDir $target -Ref $script:refSha
        (& git -C $target rev-parse HEAD).Trim() | Should -Be $script:refSha
    }

    It "rejects an absent ref in an existing checkout without changing HEAD" {
        $target = Join-Path $script:refSandbox 'existing-install'
        Install-ExtractorClone -TargetDir $target -Ref v1.0.0
        $before = (& git -C $target rev-parse HEAD).Trim()
        { Install-ExtractorClone -TargetDir $target -Ref 'v9.9.9-missing' } |
            Should -Throw '*requested extractor Git ref unavailable*'
        (& git -C $target rev-parse HEAD).Trim() | Should -Be $before
    }

    It "refuses a missing ref for a new install without leaving a partial checkout" {
        $target = Join-Path $script:refSandbox 'missing-install'
        { Install-ExtractorClone -TargetDir $target -Ref 'v9.9.9-missing' } |
            Should -Throw '*requested extractor Git ref unavailable*'
        Test-Path -LiteralPath $target | Should -BeFalse
        @(Get-ChildItem -LiteralPath $script:refSandbox -Force -Filter '.extractor-stage-*').Count |
            Should -Be 0
    }

    It "allows a valid new installation after a rejected ref" {
        $target = Join-Path $script:refSandbox 'retry-install'
        { Install-ExtractorClone -TargetDir $target -Ref 'missing-tag' } | Should -Throw
        Install-ExtractorClone -TargetDir $target -Ref v1.0.0
        (& git -C $target rev-parse HEAD).Trim() | Should -Be $script:refSha
    }

    It "rejects option-shaped Git refs before network or filesystem mutation" {
        $target = Join-Path $script:refSandbox 'option-injection'
        { Install-ExtractorClone -TargetDir $target -Ref '--upload-pack=evil' } |
            Should -Throw '*invalid extractor Git ref*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
}
