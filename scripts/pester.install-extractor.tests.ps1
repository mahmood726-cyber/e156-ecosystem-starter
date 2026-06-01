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
        Get-ExtractorDefaultRef | Should -Match '^(v\d|[0-9a-f]{7,40})$'
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
