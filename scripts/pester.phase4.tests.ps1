# Pester tests for Phase 4 (push-portfolio.py).
# Does NOT call `gh` or network. Tests discovery + arg resolution only.

BeforeAll {
    $script:Script = Join-Path $PSScriptRoot 'push-portfolio.py'
    $script:tmpRoot = Join-Path $env:TEMP "phase4-test-$(Get-Random)"
    New-Item -ItemType Directory -Force -Path $script:tmpRoot | Out-Null

    # Build a little fake portfolio under tmpRoot:
    #   repo-a/.git  (no remote)
    #   repo-b/.git  (has remote)
    #   not-a-repo/  (no .git)
    #   node_modules/... (should be skipped)
    # Use real `git init` so the scan can't fall back to a parent repo's config
    # (the home dir may itself be a git repo; a bare .git subdir would inherit
    # that remote, breaking the NEW-vs-OK classification).
    foreach ($r in @('repo-a', 'repo-b')) {
        $d = Join-Path $script:tmpRoot $r
        New-Item -ItemType Directory -Force -Path $d | Out-Null
        & git init -q $d 2>&1 | Out-Null
    }
    # Add a remote to repo-b
    & git -C (Join-Path $script:tmpRoot 'repo-b') remote add origin 'https://github.com/fake/repo-b.git' 2>&1 | Out-Null
    # Not-a-repo (no .git)
    New-Item -ItemType Directory -Force -Path (Join-Path $script:tmpRoot 'not-a-repo') | Out-Null
    # node_modules with a nested .git that should be SKIPPED (via skip_names filter)
    New-Item -ItemType Directory -Force -Path (Join-Path $script:tmpRoot 'node_modules\pkg\.git') | Out-Null
}

AfterAll {
    if (Test-Path $script:tmpRoot) {
        Remove-Item -Recurse -Force $script:tmpRoot -ErrorAction SilentlyContinue
    }
}

Describe "push-portfolio.py --report" {
    It "finds both real repos and skips non-repo + node_modules noise" {
        $out = & python $script:Script --scan-dir $script:tmpRoot --report
        $LASTEXITCODE | Should -Be 0
        ($out -join "`n") | Should -Match 'repo-a'
        ($out -join "`n") | Should -Match 'repo-b'
        # Our fake node_modules child MUST NOT appear. "Total: 2 repos" is the proof.
        ($out -join "`n") | Should -Match 'Total: 2 repos'
    }

    It "classifies repo-b as having a remote and repo-a as new" {
        $out = & python $script:Script --scan-dir $script:tmpRoot --report
        ($out -join "`n") | Should -Match 'NEW.*repo-a'
        ($out -join "`n") | Should -Match 'OK.*repo-b'
    }
}

Describe "push-portfolio.py --dry-run" {
    It "shows would-do messages without calling gh or git push" {
        $out = & python $script:Script --scan-dir $script:tmpRoot --dry-run --github-user fake-student
        $LASTEXITCODE | Should -Be 0
        ($out -join "`n") | Should -Match 'dry-run'
    }
}

Describe "push-portfolio.py --new-only" {
    It "processes only repos without existing remote" {
        $out = & python $script:Script --scan-dir $script:tmpRoot --dry-run --new-only --github-user fake-student
        $LASTEXITCODE | Should -Be 0
        # repo-a (no remote) should appear; repo-b (has remote) filtered out
        ($out -join "`n") | Should -Match 'repo-a'
        ($out -join "`n") | Should -Not -Match 'PUSH\s+repo-b'
    }
}

Describe "push-portfolio.py config errors" {
    It "exits 2 when no scan dirs given" {
        $errFile = Join-Path $script:tmpRoot 'err.txt'
        # Isolate from any existing PORTFOLIO_SCAN_DIRS env
        cmd.exe /c "set PORTFOLIO_SCAN_DIRS=&& python `"$script:Script`" --report 2>`"$errFile`""
        $LASTEXITCODE | Should -Be 2
        (Get-Content -Raw $errFile) | Should -Match 'no --scan-dir'
    }

    It "exits 2 when scan dirs present but no github-user and not --report" {
        $errFile = Join-Path $script:tmpRoot 'err2.txt'
        cmd.exe /c "set PORTFOLIO_GITHUB_USER=&& python `"$script:Script`" --scan-dir `"$script:tmpRoot`" --dry-run 2>`"$errFile`""
        $LASTEXITCODE | Should -Be 2
        (Get-Content -Raw $errFile) | Should -Match 'github-user'
    }
}
