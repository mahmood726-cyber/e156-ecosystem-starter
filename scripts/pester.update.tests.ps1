# Pester tests for update-ecosystem.ps1 helpers.
# Network-free: only tests URL resolution + workspace naming.

BeforeAll {
    . (Join-Path $PSScriptRoot 'update-ecosystem.ps1') -Import
}

Describe "Resolve-DownloadUrl" {
    It "points at a tag zip when ref starts with v + digit" {
        $u = Resolve-DownloadUrl -RefName 'v0.7.0'
        $u | Should -Match 'archive/refs/tags/v0\.7\.0\.zip$'
    }
    It "points at a branch zip for non-tag refs" {
        $u = Resolve-DownloadUrl -RefName 'main'
        $u | Should -Match 'archive/refs/heads/main\.zip$'
    }
    It "treats arbitrary branch names as branches, not tags" {
        $u = Resolve-DownloadUrl -RefName 'feature/experimental'
        $u | Should -Match 'archive/refs/heads/'
    }
}

Describe "Get-ExpectedExtractRoot" {
    It "strips leading v from tag refs (github zip naming)" {
        $p = Get-ExpectedExtractRoot -RefName 'v0.7.0' -Workspace 'C:\tmp'
        $p | Should -Match 'e156-ecosystem-starter-0\.7\.0$'
    }
    It "uses the raw ref for branch names" {
        $p = Get-ExpectedExtractRoot -RefName 'main' -Workspace 'C:\tmp'
        $p | Should -Match 'e156-ecosystem-starter-main$'
    }
}

Describe "Get-UpdateWorkspace" {
    It "produces a timestamped path under TEMP" {
        $w = Get-UpdateWorkspace
        $w | Should -Match 'e156-update-\d{8}-\d{6}$'
        $w | Should -BeLike "$env:TEMP*"
    }
    It "returns different paths on rapid successive calls (timestamp differs)" {
        $a = Get-UpdateWorkspace
        Start-Sleep -Milliseconds 1100
        $b = Get-UpdateWorkspace
        $a | Should -Not -Be $b
    }
}
