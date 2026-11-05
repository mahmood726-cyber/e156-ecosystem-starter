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
    It "copies the 4 rules .md files plus the _index.yaml routing table into an empty target" {
        $target = Join-Path $tmpRoot 'agent1\rules'
        $r = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target
        # 4 rule .md files + rules/_index.yaml (the JIT routing table the installer copies
        # since 7f04858). Each one is named below, so a missing OR an extra file fails.
        $r.Copied.Count | Should -Be 5
        $r.Copied       | Should -Contain '_index.yaml'
        $r.Backed.Count | Should -Be 0
        Test-Path (Join-Path $target 'rules.md')          | Should -BeTrue
        Test-Path (Join-Path $target 'e156.md')           | Should -BeTrue
        Test-Path (Join-Path $target 'advanced-stats.md') | Should -BeTrue
        Test-Path (Join-Path $target 'lessons.md')        | Should -BeTrue
        Test-Path (Join-Path $target '_index.yaml')       | Should -BeTrue
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

# The routing index is user-editable configuration, just like rules .md files.
# Use disposable Windows fixtures; never touch any real agent profile.
Describe "Rules routing-index backup and rollback" {
    It "preserves an existing custom _index.yaml and restores it on rollback" {
        $target = Join-Path $tmpRoot "index preservation-Ü-$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $index = Join-Path $target '_index.yaml'
        Set-Content -LiteralPath $index -Value 'custom routing before install' -NoNewline -Encoding UTF8
        $m = New-RollbackManifest
        $r = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Manifest $m
        $r.Backed | Should -Contain '_index.yaml'
        (Get-Content -LiteralPath "$index.user" -Raw).Trim() | Should -Be 'custom routing before install'
        $m.BackedUp | Should -Contain "$index.user"
        Invoke-InstallRollback -Manifest $m -Reason 'synthetic routing index rollback'
        (Get-Content -LiteralPath $index -Raw).Trim() | Should -Be 'custom routing before install'
        Test-Path -LiteralPath "$index.user" | Should -BeFalse
    }

    It "preserves successive routing-index edits without overwriting the first backup" {
        $target = Join-Path $tmpRoot "index rerun-Ü-$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $index = Join-Path $target '_index.yaml'
        Set-Content -LiteralPath $index -Value 'original custom route' -NoNewline -Encoding UTF8
        Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target | Out-Null
        Set-Content -LiteralPath $index -Value 'most recent custom route' -NoNewline -Encoding UTF8
        $m = New-RollbackManifest
        Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Manifest $m | Out-Null
        (Get-Content -LiteralPath "$index.user" -Raw).Trim() | Should -Be 'original custom route'
        $later = @($m.BackedUp | Where-Object { $_ -like "$index.user-*" })
        $later.Count | Should -Be 1
        (Get-Content -LiteralPath $later[0] -Raw).Trim() | Should -Be 'most recent custom route'
        Invoke-InstallRollback -Manifest $m -Reason 'synthetic routing index reinstall rollback'
        (Get-Content -LiteralPath $index -Raw).Trim() | Should -Be 'most recent custom route'
        (Get-Content -LiteralPath "$index.user" -Raw).Trim() | Should -Be 'original custom route'
    }

    It "honours explicit -Force for the routing index without creating a backup" {
        $target = Join-Path $tmpRoot "index force-$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $index = Join-Path $target '_index.yaml'
        Set-Content -LiteralPath $index -Value 'replaceable custom route' -NoNewline -Encoding UTF8
        $r = Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Force
        $r.Backed | Should -Not -Contain '_index.yaml'
        Test-Path -LiteralPath "$index.user" | Should -BeFalse
        (Get-Content -LiteralPath $index -Raw).Trim() | Should -Not -Be 'replaceable custom route'
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
        $m.CreatedFiles.Count | Should -Be 5   # 4 rule .md files + _index.yaml
        @($m.CreatedFiles | Where-Object { $_ -like '*_index.yaml' }).Count | Should -Be 1
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

Describe "Windows reinstall backups preserve edits and rollback" {
    It "captures second context edit when the first .user backup exists" {
        $target = Join-Path $tmpRoot "ctx-rerun-$([guid]::NewGuid().ToString('N'))-雪"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $dst = Join-Path $target 'AGENTS.md'
        Set-Content -LiteralPath $dst -Value 'first edit' -NoNewline -Encoding UTF8
        Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $target | Out-Null
        Set-Content -LiteralPath $dst -Value 'second edit' -NoNewline -Encoding UTF8
        $m = New-RollbackManifest
        Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $target -Manifest $m | Out-Null
        (Get-Content -LiteralPath "$dst.user" -Raw).Trim() | Should -Be 'first edit'
        $m.BackedUp.Count | Should -BeGreaterThan 0
        $second = @($m.BackedUp | Where-Object { $_ -like "$dst.user-*" })
        $second.Count | Should -Be 1
        (Get-Content -LiteralPath $second[0] -Raw).Trim() | Should -Be 'second edit'
    }

    It "restores current context edit on rollback without removing older .user" {
        $target = Join-Path $tmpRoot "ctx-rollback-$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $dst = Join-Path $target 'AGENTS.md'
        Set-Content -LiteralPath $dst -Value 'older edit' -NoNewline -Encoding UTF8
        Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $target | Out-Null
        Set-Content -LiteralPath $dst -Value 'newest edit' -NoNewline -Encoding UTF8
        $m = New-RollbackManifest
        Copy-ContextFiles -SourceRoot $starterRoot -TargetDir $target -Manifest $m | Out-Null
        Invoke-InstallRollback -Manifest $m -Reason 'synthetic context rollback'
        (Get-Content -LiteralPath $dst -Raw).Trim() | Should -Be 'newest edit'
        (Get-Content -LiteralPath "$dst.user" -Raw).Trim() | Should -Be 'older edit'
        @(Get-ChildItem -LiteralPath $target -Filter 'AGENTS.md.user-*').Count | Should -Be 0
    }

    It "does not overwrite an existing same-second rules backup and can roll back" {
        $target = Join-Path $tmpRoot "rules-collision-$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $dst = Join-Path $target 'lessons.md'
        Set-Content -LiteralPath $dst -Value 'first edit' -NoNewline -Encoding UTF8
        Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target | Out-Null
        Set-Content -LiteralPath $dst -Value 'latest edit' -NoNewline -Encoding UTF8
        $sameSecond = "$dst.user-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Set-Content -LiteralPath $sameSecond -Value 'older snapshot' -NoNewline -Encoding UTF8
        $m = New-RollbackManifest
        Copy-RulesToAgent -SourceRulesDir (Join-Path $starterRoot 'rules') -TargetRulesDir $target -Manifest $m | Out-Null
        (Get-Content -LiteralPath $sameSecond -Raw).Trim() | Should -Be 'older snapshot'
        Invoke-InstallRollback -Manifest $m -Reason 'synthetic rules rollback'
        (Get-Content -LiteralPath $dst -Raw).Trim() | Should -Be 'latest edit'
        (Get-Content -LiteralPath "$dst.user" -Raw).Trim() | Should -Be 'first edit'
        (Get-Content -LiteralPath $sameSecond -Raw).Trim() | Should -Be 'older snapshot'
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

# SHA-only checks must not initialise the transcript directory in LOCALAPPDATA.
# All paths are isolated test fixtures; the real user profile is never touched.
Describe "Dry-run must not initialize LOCALAPPDATA" {
    It "verifies a matching SHA without creating a transcript directory" {
        $stateRoot = Join-Path $script:tmpRoot 'valid dry run state-Ü'
        $prior = $env:LOCALAPPDATA
        try {
            $env:LOCALAPPDATA = $stateRoot
            $output = & powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $script:InstallPs1 -DryRun 2>&1
            $LASTEXITCODE | Should -Be 0
            ($output -join ' ') | Should -Match 'Dry run: self-SHA verified'
            Test-Path -LiteralPath $stateRoot | Should -BeFalse
        }
        finally {
            $env:LOCALAPPDATA = $prior
        }
    }

    It "rejects a mismatched SHA without creating a transcript directory" {
        $fixtureRoot = Join-Path $script:tmpRoot 'bad SHA fixture-Ü with spaces'
        $fixtureInstall = Join-Path $fixtureRoot 'install'
        $fixtureDocs = Join-Path $fixtureRoot 'docs'
        New-Item -ItemType Directory -Force -Path $fixtureInstall, $fixtureDocs | Out-Null
        Copy-Item -LiteralPath $script:InstallPs1 -Destination (Join-Path $fixtureInstall 'install.ps1')
        Set-Content -LiteralPath (Join-Path $fixtureDocs 'HASH.txt') -Value ('0' * 64) -NoNewline -Encoding ASCII
        $stateRoot = Join-Path $script:tmpRoot 'bad dry run state-Ü'
        $prior = $env:LOCALAPPDATA
        try {
            $env:LOCALAPPDATA = $stateRoot
            $output = & powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $fixtureInstall 'install.ps1') -DryRun 2>&1
            $LASTEXITCODE | Should -Not -Be 0
            ($output -join ' ') | Should -Match 'SHA does not match'
            Test-Path -LiteralPath $stateRoot | Should -BeFalse
        }
        finally {
            $env:LOCALAPPDATA = $prior
        }
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

# A full/requested install must NEVER treat an absent Sentinel/Overmind script as
# a successful skip. These deliberately use isolated temporary paths and never
# execute Sentinel, Overmind, pip, a hook, or the full user-profile installer.
Describe "Assert-RequiredCoreInstallerPresent (Windows fail-closed core chains)" {
    It "refuses a requested Sentinel script that is missing" {
        $path = Join-Path $tmpRoot 'missing-sentinel.ps1'
        { Assert-RequiredCoreInstallerPresent -Component 'Sentinel' -ScriptPath $path } |
            Should -Throw '*REFUSED: requested Sentinel installer is missing*'
    }

    It "refuses a requested Overmind/TruthCert script that is missing" {
        $path = Join-Path $tmpRoot 'missing-overmind.ps1'
        { Assert-RequiredCoreInstallerPresent -Component 'Overmind/TruthCert' -ScriptPath $path } |
            Should -Throw '*REFUSED: requested Overmind/TruthCert installer is missing*'
    }

    It "refuses a directory masquerading as a component script" {
        $dir = Join-Path $tmpRoot 'not-a-script.ps1'
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        { Assert-RequiredCoreInstallerPresent -Component 'Sentinel' -ScriptPath $dir } |
            Should -Throw '*REFUSED: requested Sentinel installer is missing*'
    }

    It "accepts a genuine existing script file without executing it" {
        $path = Join-Path $tmpRoot 'present-sentinel.ps1'
        Set-Content -LiteralPath $path -Value 'throw "should never execute this file"' -Encoding UTF8
        Assert-RequiredCoreInstallerPresent -Component 'Sentinel' -ScriptPath $path |
            Should -BeTrue
    }


    It "refuses a glob-shaped missing path even when a matching decoy exists" {
        $decoy = Join-Path $tmpRoot 'core-0.ps1'
        $missing = Join-Path $tmpRoot 'core-[0].ps1'
        Set-Content -LiteralPath $decoy -Value 'throw "decoy must never execute"' -Encoding UTF8
        { Assert-RequiredCoreInstallerPresent -Component 'Sentinel' -ScriptPath $missing } |
            Should -Throw '*REFUSED: requested Sentinel installer is missing*'
    }

    It "accepts a literal filename with bracket characters without executing it" {
        $path = Join-Path $tmpRoot 'present-[1].ps1'
        Set-Content -LiteralPath $path -Value 'throw "should never execute this file"' -Encoding UTF8
        Assert-RequiredCoreInstallerPresent -Component 'Sentinel' -ScriptPath $path |
            Should -BeTrue
    }
}
