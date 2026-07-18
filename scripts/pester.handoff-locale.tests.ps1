# Pester tests for the locale picker in scripts/write-gemini-handoff.ps1.
# P1-D from the 2026-04-27 second-pass review: the handoff translations
# exist on disk, but the path-resolution logic was untested. A typo in
# the substring extraction or precedence order would silently fall back
# to English without anyone noticing.

BeforeAll {
    $script:HandoffPs1 = Join-Path $PSScriptRoot 'write-gemini-handoff.ps1'
    # Dot-source helpers only; -Import short-circuits before any side effects.
    . $HandoffPs1 -Import

    $script:starterRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

Describe "Get-HandoffPromptLocale precedence" {
    # Pester 5 requires BeforeEach inside a Describe / Context block.
    BeforeEach {
        Remove-Item Env:E156_LANG -ErrorAction SilentlyContinue
        Remove-Item Env:LC_ALL    -ErrorAction SilentlyContinue
        Remove-Item Env:LANG      -ErrorAction SilentlyContinue
    }
    It "defaults to 'en' when no env vars set" {
        Get-HandoffPromptLocale | Should -Be 'en'
    }
    It "picks 'fr' from LANG=fr_FR.UTF-8" {
        $env:LANG = 'fr_FR.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'fr'
    }
    It "picks 'pt' from LANG=pt_BR.UTF-8" {
        $env:LANG = 'pt_BR.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'pt'
    }
    It "picks 'ar' from LANG=ar_EG.UTF-8" {
        $env:LANG = 'ar_EG.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'ar'
    }
    It "picks 'ur' from LANG=ur_PK.UTF-8" {
        $env:LANG = 'ur_PK.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'ur'
    }
    It "LC_ALL beats LANG (POSIX canonical precedence)" {
        $env:LANG = 'fr_FR.UTF-8'
        $env:LC_ALL = 'pt_BR.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'pt'
    }
    It "E156_LANG beats both LC_ALL and LANG" {
        $env:LANG = 'fr_FR.UTF-8'
        $env:LC_ALL = 'pt_BR.UTF-8'
        $env:E156_LANG = 'ar'
        Get-HandoffPromptLocale | Should -Be 'ar'
    }
    It "picks 'sw' from LANG=sw_KE.UTF-8" {
        $env:LANG = 'sw_KE.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'sw'
    }
    It "falls back to 'en' for unsupported locales (de, ja, etc.)" {
        $env:LANG = 'de_DE.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'en'
        $env:LANG = 'ja_JP.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'en'
    }
    It "is case-insensitive (LANG=FR_FR.UTF-8 -> fr)" {
        $env:LANG = 'FR_FR.UTF-8'
        Get-HandoffPromptLocale | Should -Be 'fr'
    }
}

Describe "Get-HandoffPromptPath returns the right localised file" {
    BeforeEach {
        Remove-Item Env:E156_LANG -ErrorAction SilentlyContinue
        Remove-Item Env:LC_ALL    -ErrorAction SilentlyContinue
        Remove-Item Env:LANG      -ErrorAction SilentlyContinue
    }
    It "returns .fr.md when locale=fr and file exists" {
        $env:LANG = 'fr_FR.UTF-8'
        $p = Get-HandoffPromptPath -StarterRoot $script:starterRoot
        $p | Should -Match 'gemini-handoff-prompt\.fr\.md$'
        Test-Path $p | Should -BeTrue
    }
    It "returns .pt.md when locale=pt and file exists" {
        $env:LANG = 'pt_BR.UTF-8'
        $p = Get-HandoffPromptPath -StarterRoot $script:starterRoot
        $p | Should -Match 'gemini-handoff-prompt\.pt\.md$'
    }
    It "returns .ar.md when locale=ar and file exists" {
        $env:LANG = 'ar_EG.UTF-8'
        $p = Get-HandoffPromptPath -StarterRoot $script:starterRoot
        $p | Should -Match 'gemini-handoff-prompt\.ar\.md$'
    }
    It "returns .ur.md when locale=ur and file exists" {
        $env:LANG = 'ur_PK.UTF-8'
        $p = Get-HandoffPromptPath -StarterRoot $script:starterRoot
        $p | Should -Match 'gemini-handoff-prompt\.ur\.md$'
        Test-Path $p | Should -BeTrue
    }
    It "returns .sw.md when locale=sw and file exists" {
        $env:LANG = 'sw_KE.UTF-8'
        $p = Get-HandoffPromptPath -StarterRoot $script:starterRoot
        $p | Should -Match 'gemini-handoff-prompt\.sw\.md$'
        Test-Path $p | Should -BeTrue
    }
    It "falls back to .en.md when localised file is missing" {
        # Force a locale whose file does NOT exist by passing it directly
        $p = Get-HandoffPromptPath -StarterRoot $script:starterRoot -Locale 'de'
        $p | Should -Match 'gemini-handoff-prompt\.en\.md$'
        Test-Path $p | Should -BeTrue
    }
}

Describe "End-to-end -ResolveOnly hook returns same path" {
    BeforeEach {
        Remove-Item Env:E156_LANG -ErrorAction SilentlyContinue
        Remove-Item Env:LC_ALL    -ErrorAction SilentlyContinue
        Remove-Item Env:LANG      -ErrorAction SilentlyContinue
    }
    It "matches Get-HandoffPromptPath when invoked via the script entry point" {
        $env:LANG = 'fr_FR.UTF-8'
        $expected = Get-HandoffPromptPath -StarterRoot $script:starterRoot
        $actual = & powershell -NoProfile -ExecutionPolicy Bypass -File $script:HandoffPs1 -StarterRoot $script:starterRoot -ResolveOnly
        ($actual.Trim()) | Should -Be $expected
    }
}
