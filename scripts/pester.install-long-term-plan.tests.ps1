# Pester tests for install-long-term-plan.ps1 (helper functions only).
#
# Does NOT hit the network, pip, or git clone. Real clone behaviour is covered
# by the long-term-plan repo's own integration tests; here we only verify the
# wrapper functions make correct decisions.

BeforeAll {
    $script:Script = Join-Path $PSScriptRoot 'install-long-term-plan.ps1'
    . $Script -Import
}

Describe "Get-LongTermPlanDefaultRoot lives under the user home" {
    It "ends with code\long-term-plan" {
        $p = Get-LongTermPlanDefaultRoot
        $p | Should -Match 'code[\\\/]long-term-plan$'
    }
    It "is rooted at the user profile" {
        $p = Get-LongTermPlanDefaultRoot
        $userHome = $env:USERPROFILE
        if (-not $userHome) { $userHome = $HOME }
        $p | Should -BeLike "$userHome*"
    }
}

Describe "Get-LongTermPlanDefaultRef pins the supply chain (P0)" {
    BeforeEach { Remove-Item Env:LONG_TERM_PLAN_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:LONG_TERM_PLAN_REF -ErrorAction SilentlyContinue }

    It "defaults to a tagged release (not bare main)" {
        $r = Get-LongTermPlanDefaultRef
        # Mirrors install-sentinel.tests.ps1 pinning check. A future bump
        # changes the version digits but the v-prefix tag pattern persists.
        $r | Should -Match '^v\d'
    }

    It "honours LONG_TERM_PLAN_REF override (rollback / bleeding-edge)" {
        $env:LONG_TERM_PLAN_REF = 'main'
        Get-LongTermPlanDefaultRef | Should -Be 'main'
    }

    It "honours LONG_TERM_PLAN_REF for arbitrary SHA pinning" {
        $env:LONG_TERM_PLAN_REF = 'abc1234'
        Get-LongTermPlanDefaultRef | Should -Be 'abc1234'
    }
}

Describe "Test-IsLongTermPlanRepo heuristic" {
    BeforeAll {
        $script:tmp = Join-Path $env:TEMP "ltp-test-isrepo-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path $script:tmp | Out-Null
    }
    AfterAll {
        if (Test-Path $script:tmp) {
            Remove-Item -Recurse -Force $script:tmp -ErrorAction SilentlyContinue
        }
    }
    BeforeEach {
        # Reset to empty between tests
        Get-ChildItem $script:tmp -Force -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    It "returns false for an empty directory" {
        Test-IsLongTermPlanRepo -Path $script:tmp | Should -BeFalse
    }

    It "returns false when scripts/weekly_plan_update.py exists but no ideas.yaml" {
        New-Item -ItemType Directory -Force -Path (Join-Path $script:tmp 'scripts') | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $script:tmp 'scripts\weekly_plan_update.py') | Out-Null
        Test-IsLongTermPlanRepo -Path $script:tmp | Should -BeFalse
    }

    It "returns false when ideas.yaml exists but no .git" {
        New-Item -ItemType Directory -Force -Path (Join-Path $script:tmp 'scripts') | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $script:tmp 'scripts\weekly_plan_update.py') | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $script:tmp 'ideas.yaml') | Out-Null
        Test-IsLongTermPlanRepo -Path $script:tmp | Should -BeFalse
    }

    It "returns true when all three sentinel paths exist" {
        New-Item -ItemType Directory -Force -Path (Join-Path $script:tmp 'scripts') | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $script:tmp 'scripts\weekly_plan_update.py') | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $script:tmp 'ideas.yaml') | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $script:tmp '.git') | Out-Null
        Test-IsLongTermPlanRepo -Path $script:tmp | Should -BeTrue
    }
}

Describe "Install-LongTermPlanClone refuses to clone over a non-empty non-repo dir" {
    BeforeAll {
        $script:tmpNonRepo = Join-Path $env:TEMP "ltp-test-nonrepo-$(Get-Random)"
        New-Item -ItemType Directory -Force -Path $script:tmpNonRepo | Out-Null
        # Put one foreign file in there so it's non-empty and definitely not a clone.
        Set-Content -Path (Join-Path $script:tmpNonRepo 'foreign.txt') -Value 'hello' -NoNewline
    }
    AfterAll {
        if (Test-Path $script:tmpNonRepo) {
            Remove-Item -Recurse -Force $script:tmpNonRepo -ErrorAction SilentlyContinue
        }
    }

    It "throws rather than overwriting the foreign file" {
        # Should fail at the "non-empty but not a clone" check before any
        # git binary is invoked; safe to run in offline CI.
        { Install-LongTermPlanClone -Path $script:tmpNonRepo -RefToCheckout 'v0.7.0' } |
            Should -Throw "*Refusing to clone over it*"
        # Foreign file must survive the refusal.
        (Get-Content -Raw (Join-Path $script:tmpNonRepo 'foreign.txt')) | Should -Match 'hello'
    }
}
