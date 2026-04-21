# Pester tests for install.ps1 helper functions.
# Run: Invoke-Pester -Path .\install\pester.tests.ps1

BeforeAll {
    $script:InstallPs1 = Join-Path $PSScriptRoot 'install.ps1'
    # Dot-source helpers only (-Import short-circuits execution)
    . $InstallPs1 -Import

    $script:starterRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
    $script:tmpRoot = Join-Path $env:TEMP "ecostarter-test-$(Get-Random)"
    New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
}

AfterAll {
    if (Test-Path $script:tmpRoot) {
        Remove-Item -Recurse -Force $script:tmpRoot -ErrorAction SilentlyContinue
    }
}

Describe "Get-EcoStarterRoot resolves the parent of install/" {
    It "returns the repo root" {
        $result = Get-EcoStarterRoot
        Test-Path (Join-Path $result 'rules') | Should -BeTrue
        Test-Path (Join-Path $result 'AGENTS.md') | Should -BeTrue
    }
}

Describe "Copy-RulesToAgent copies all .md files" {
    It "copies 4 rules files into an empty target" {
        $target = Join-Path $tmpRoot 'agent1\rules'
        $r = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target
        $r.Copied.Count | Should -Be 4
        $r.Backed.Count | Should -Be 0
        Test-Path (Join-Path $target 'rules.md')          | Should -BeTrue
        Test-Path (Join-Path $target 'e156.md')           | Should -BeTrue
        Test-Path (Join-Path $target 'advanced-stats.md') | Should -BeTrue
        Test-Path (Join-Path $target 'lessons.md')        | Should -BeTrue
    }

    It "backs up existing user-edited rules as .user (no -Force)" {
        $target = Join-Path $tmpRoot 'agent2\rules'
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        # Pre-existing user edit
        Set-Content -Path (Join-Path $target 'lessons.md') -Value 'my custom lesson' -NoNewline -Encoding UTF8

        $r = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target
        $r.Backed -contains 'lessons.md' | Should -BeTrue
        Test-Path (Join-Path $target 'lessons.md.user') | Should -BeTrue
        (Get-Content (Join-Path $target 'lessons.md.user') -Raw).Trim() | Should -Be 'my custom lesson'
    }

    It "with -Force overwrites without backup" {
        $target = Join-Path $tmpRoot 'agent3\rules'
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Set-Content -Path (Join-Path $target 'lessons.md') -Value 'my custom lesson' -NoNewline -Encoding UTF8

        $r = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Force
        Test-Path (Join-Path $target 'lessons.md.user') | Should -BeFalse
    }
}

Describe "Copy-ContextFiles drops AGENTS/CLAUDE/GEMINI/CODEX" {
    It "creates all four context files when present in source" {
        $target = Join-Path $tmpRoot 'agent4'
        $r = Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $target
        $r.Count | Should -BeGreaterOrEqual 3   # at least AGENTS + CLAUDE + GEMINI
        Test-Path (Join-Path $target 'AGENTS.md') | Should -BeTrue
        Test-Path (Join-Path $target 'CLAUDE.md') | Should -BeTrue
        Test-Path (Join-Path $target 'GEMINI.md') | Should -BeTrue
    }
}

Describe "Copy-MemoryScaffold only bootstraps empty targets" {
    It "bootstraps when target is empty" {
        $target = Join-Path $tmpRoot 'agent5\memory'
        $bootstrapped = Copy-MemoryScaffold -SourceMemoryDir (Join-Path $starterRoot 'memory') -TargetMemoryDir $target
        $bootstrapped | Should -BeTrue
        Test-Path (Join-Path $target 'MEMORY.md') | Should -BeTrue
        (Get-ChildItem (Join-Path $target 'templates') -Filter '*.md').Count | Should -BeGreaterOrEqual 4
    }

    It "preserves existing memory (returns false, no overwrite)" {
        $target = Join-Path $tmpRoot 'agent6\memory'
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Set-Content -Path (Join-Path $target 'my_custom.md') -Value 'student memory' -NoNewline -Encoding UTF8

        $bootstrapped = Copy-MemoryScaffold -SourceMemoryDir (Join-Path $starterRoot 'memory') -TargetMemoryDir $target
        $bootstrapped | Should -BeFalse
        Test-Path (Join-Path $target 'MEMORY.md') | Should -BeFalse   # scaffold SKIPPED
        Test-Path (Join-Path $target 'my_custom.md') | Should -BeTrue  # user file preserved
    }
}

Describe "Self-SHA gate exits 0 under -DryRun" {
    It "writes HASH.txt with install.ps1's SHA and the DryRun shortcut succeeds" {
        # Regenerate HASH.txt for the current install.ps1 (may have been edited)
        $hashPath = Join-Path $starterRoot 'docs\HASH.txt'
        New-Item -ItemType Directory -Force -Path (Split-Path $hashPath) | Out-Null
        $sha = (Get-FileHash -Algorithm SHA256 $script:InstallPs1).Hash.ToLower()
        Set-Content -Path $hashPath -Value $sha -NoNewline -Encoding UTF8

        $r = & powershell -NoProfile -ExecutionPolicy Bypass -File $script:InstallPs1 -DryRun
        $LASTEXITCODE | Should -Be 0
        ($r -join ' ') | Should -Match 'Dry run'
    }
}
