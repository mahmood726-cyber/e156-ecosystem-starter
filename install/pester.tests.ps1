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

Describe "Render-Template substitutes placeholders" {
    It "replaces {{NAME}} literals with hashtable values" {
        $text = "path is {{E156_HOME}} and user is {{GITHUB_USER}}"
        $vars = @{ 'E156_HOME' = 'D:\Research'; 'GITHUB_USER' = 'alice42' }
        $out = Render-Template -Text $text -Vars $vars
        $out | Should -Be "path is D:\Research and user is alice42"
    }
    It "leaves unmatched placeholders literal" {
        $out = Render-Template -Text "has {{FOO}} no {{BAR}}" -Vars @{ 'FOO' = 'X' }
        $out | Should -Be "has X no {{BAR}}"
    }
    It "handles empty vars hashtable" {
        (Render-Template -Text "unchanged" -Vars @{}) | Should -Be "unchanged"
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

    It "renders template vars when -Vars is passed" {
        $target = Join-Path $tmpRoot 'agent-render\rules'
        $vars = @{
            'E156_HOME' = 'D:\Mine\E156'
            'PROJECTINDEX_ROOT' = 'D:\Mine\Idx'
            'SENTINEL_ROOT' = 'D:\Mine\Sentinel'
            'OVERMIND_ROOT' = 'D:\Mine\overmind'
            'GITHUB_USER' = 'alice42'
        }
        $null = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Vars $vars
        $e156Content = Get-Content -Raw (Join-Path $target 'e156.md')
        # No Mahmood paths remain
        $e156Content | Should -Not -Match 'C:\\E156'
        $e156Content | Should -Not -Match 'mahmood726-cyber'
        # Student's values landed
        $e156Content | Should -Match 'D:\\Mine\\E156'
        $e156Content | Should -Match 'alice42'
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

Describe "Rollback: manifest-driven undo" {
    It "New-RollbackManifest returns a manifest with empty lists" {
        $m = New-RollbackManifest
        $m.CreatedFiles.Count | Should -Be 0
        $m.CreatedDirs.Count  | Should -Be 0
        $m.BackedUp.Count     | Should -Be 0
    }

    It "Copy-RulesToAgent populates the manifest with net-new files and dirs" {
        $target = Join-Path $tmpRoot ("rb-" + (Get-Random) + "\rules")
        $m = New-RollbackManifest
        $null = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Manifest $m
        $m.CreatedDirs.Count  | Should -BeGreaterOrEqual 1
        $m.CreatedFiles.Count | Should -Be 4
        $m.BackedUp.Count     | Should -Be 0
    }

    It "Copy-RulesToAgent tracks backups when overwriting a pre-existing file" {
        $target = Join-Path $tmpRoot ("rb-" + (Get-Random) + "\rules")
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Set-Content -Path (Join-Path $target 'lessons.md') -Value 'student-edit' -NoNewline -Encoding UTF8
        $m = New-RollbackManifest
        $null = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Manifest $m
        $m.BackedUp.Count | Should -Be 1
        ($m.BackedUp[0]) | Should -Match 'lessons\.md\.user$'
    }

    It "Invoke-InstallRollback deletes net-new files and restores backups" {
        $target = Join-Path $tmpRoot ("rb-" + (Get-Random) + "\rules")
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Set-Content -Path (Join-Path $target 'lessons.md') -Value 'pre-existing' -NoNewline -Encoding UTF8

        $m = New-RollbackManifest
        $null = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Manifest $m

        # Rollback
        Invoke-InstallRollback -Manifest $m -Reason "pester test"

        # Net-new files (rules.md, advanced-stats.md, e156.md) should be gone
        Test-Path (Join-Path $target 'rules.md')          | Should -BeFalse
        Test-Path (Join-Path $target 'advanced-stats.md') | Should -BeFalse
        Test-Path (Join-Path $target 'e156.md')           | Should -BeFalse

        # Pre-existing lessons.md should be RESTORED with original content
        Test-Path (Join-Path $target 'lessons.md') | Should -BeTrue
        (Get-Content (Join-Path $target 'lessons.md') -Raw).Trim() | Should -Be 'pre-existing'

        # Backup file itself should be gone (moved back)
        Test-Path (Join-Path $target 'lessons.md.user') | Should -BeFalse
    }
}

Describe "Copy-RulesToAgent timestamp-suffixes second-rerun backups (P2)" {
    It "preserves the original .user backup and writes .user-<ts> on the second re-install" {
        $src = Join-Path $starterRoot 'rules'
        $target = Join-Path $tmpRoot "rules-rerun-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path $target | Out-Null

        # Seed with a hand-edited file
        Set-Content -Path (Join-Path $target 'lessons.md') -Value 'edit-1'
        Copy-RulesToAgent -SourceRulesDir $src -TargetRulesDir $target | Out-Null
        # First .user backup should hold edit-1
        (Get-Content (Join-Path $target 'lessons.md.user') -Raw).Trim() | Should -Be 'edit-1'

        # Re-edit and re-install: original .user must NOT be overwritten;
        # a new .user-<ts> backup must capture edit-2.
        Set-Content -Path (Join-Path $target 'lessons.md') -Value 'edit-2'
        Copy-RulesToAgent -SourceRulesDir $src -TargetRulesDir $target | Out-Null
        (Get-Content (Join-Path $target 'lessons.md.user') -Raw).Trim() | Should -Be 'edit-1'
        $tsBackups = Get-ChildItem -Path $target -Filter 'lessons.md.user-*'
        $tsBackups.Count | Should -Be 1
        (Get-Content $tsBackups[0].FullName -Raw).Trim() | Should -Be 'edit-2'
    }
}

Describe "Invoke-LogRedaction scrubs secrets from transcripts (P1)" {
    BeforeAll {
        $script:redactDir = Join-Path $tmpRoot 'redact'
        New-Item -ItemType Directory -Force -Path $script:redactDir | Out-Null
    }

    It "scrubs Google API keys (AIza...)" {
        $f = Join-Path $script:redactDir 'google.log'
        $key = 'AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R'
        Set-Content -Path $f -Value "GEMINI_API_KEY=$key" -NoNewline
        Invoke-LogRedaction -Path $f
        $r = Get-Content -Raw $f
        $r | Should -Match '\[REDACTED'
        $r | Should -Not -Match $key
    }

    It "scrubs OpenAI keys (sk-...)" {
        $f = Join-Path $script:redactDir 'openai.log'
        $key = 'sk-1234567890abcdefABCDEFghijklmnopqrstuvwxyz0'
        Set-Content -Path $f -Value "OPENAI_API_KEY=$key" -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Not -Match $key
    }

    It "scrubs Anthropic keys (sk-ant-...)" {
        $f = Join-Path $script:redactDir 'anthropic.log'
        $key = 'sk-ant-api03-abcdef1234567890ABCDEFghijklmnopqrstuvwxyz'
        Set-Content -Path $f -Value "ANTHROPIC_API_KEY=$key" -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Not -Match $key
    }

    It "scrubs GitHub tokens (ghp_/gho_...)" {
        $f = Join-Path $script:redactDir 'gh.log'
        $key = 'ghp_1234567890abcdef1234567890abcdef1234'
        Set-Content -Path $f -Value "GH_TOKEN=$key" -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Not -Match $key
    }

    It "scrubs AWS access keys (AKIA...)" {
        $f = Join-Path $script:redactDir 'aws.log'
        $key = 'AKIAIOSFODNN7EXAMPLE'
        Set-Content -Path $f -Value "AWS_ACCESS_KEY_ID=$key" -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Not -Match $key
    }

    It "scrubs 64-hex HMAC keys" {
        $f = Join-Path $script:redactDir 'hmac.log'
        $key = '68c4bf3aecd57c8815e1a8fb74f74eb38c471155a0abf25a9b95e0f7429f97fc'
        Set-Content -Path $f -Value "TRUTHCERT_HMAC_KEY=$key" -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Not -Match $key
    }

    It "scrubs JWTs (eyJ...)" {
        $f = Join-Path $script:redactDir 'jwt.log'
        $token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        Set-Content -Path $f -Value "Bearer $token" -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Not -Match $token
    }

    It "scrubs setx VAR_KEY/TOKEN/SECRET values without breaking line structure" {
        $f = Join-Path $script:redactDir 'setx.log'
        $secret = 'aPlainTextSecret_!that_is_not_an_obvious_key_format'
        Set-Content -Path $f -Value "setx GEMINI_API_KEY `"$secret`"" -NoNewline
        Invoke-LogRedaction -Path $f
        $r = Get-Content -Raw $f
        $r | Should -Not -Match $secret
        $r | Should -Match 'setx\s+GEMINI_API_KEY\s+"\[REDACTED\]"'
    }

    It "leaves non-secret content untouched" {
        $f = Join-Path $script:redactDir 'safe.log'
        $line = 'Installing Sentinel from git+https://github.com/mahmood726-cyber/Sentinel.git@v0.1.0'
        Set-Content -Path $f -Value $line -NoNewline
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Be $line
    }

    It "is idempotent (running twice does not over-redact labels)" {
        $f = Join-Path $script:redactDir 'idempotent.log'
        Set-Content -Path $f -Value 'GEMINI_API_KEY=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R' -NoNewline
        Invoke-LogRedaction -Path $f
        $first = Get-Content -Raw $f
        Invoke-LogRedaction -Path $f
        (Get-Content -Raw $f) | Should -Be $first
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
