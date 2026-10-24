# Pester tests for install-meta-harness.ps1 (verify + unpack helpers, on local files).
#
# Does NOT hit the network. The fetch is exercised end to end (bash) in
# tests/test_install_meta_harness.py; here the PowerShell helpers must make the
# same decisions: refuse a mismatched or unlisted asset, never overwrite a
# non-empty target, unpack a verified release with its entry point.

BeforeAll {
    $script:Script = Join-Path $PSScriptRoot 'install-meta-harness.ps1'
    . $Script -Import

    function New-TestRelease {
        param([string]$Dir, [string]$SumsLine)
        $tag = 'v9.9.9-test'
        $src = Join-Path $Dir "src\meta-harness-$tag\scripts"
        New-Item -ItemType Directory -Force $src | Out-Null
        Set-Content -LiteralPath (Join-Path $src 'replay_offline.py') -Value "print('replay')" -Encoding ascii
        $zip = Join-Path $Dir "meta-harness-$tag.zip"
        Compress-Archive -Path (Join-Path $Dir "src\meta-harness-$tag") -DestinationPath $zip
        $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
        if (-not $SumsLine) { $SumsLine = "$sha  meta-harness-$tag.zip" }
        [IO.File]::WriteAllText((Join-Path $Dir 'SHA256SUMS'), "$SumsLine`n")
        return $zip
    }
}

Describe "Get-MetaHarnessDefaultRef pins the published release" {
    BeforeEach { Remove-Item Env:META_HARNESS_REF -ErrorAction SilentlyContinue }
    AfterEach  { Remove-Item Env:META_HARNESS_REF -ErrorAction SilentlyContinue }
    It "defaults to v1.0.0" { Get-MetaHarnessDefaultRef | Should -Be 'v1.0.0' }
    It "honours META_HARNESS_REF" { $env:META_HARNESS_REF = 'v2.0.0'; Get-MetaHarnessDefaultRef | Should -Be 'v2.0.0' }
    It "names the asset after the tag" { Get-MetaHarnessAssetName -Tag 'v1.0.0' | Should -Be 'meta-harness-v1.0.0.zip' }
}

Describe "Test-MetaHarnessAsset is fail-closed" {
    It "accepts the digest SHA256SUMS records" {
        $d = Join-Path $TestDrive 'ok'; $zip = New-TestRelease -Dir $d
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath (Join-Path $d 'SHA256SUMS') } | Should -Not -Throw
    }
    It "refuses a digest mismatch" {
        $d = Join-Path $TestDrive 'bad'
        $zip = New-TestRelease -Dir $d -SumsLine ("0" * 64 + "  meta-harness-v9.9.9-test.zip")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath (Join-Path $d 'SHA256SUMS') } | Should -Throw '*mismatch*'
    }
    It "refuses when SHA256SUMS has no line for the asset" {
        $d = Join-Path $TestDrive 'nolines'
        $zip = New-TestRelease -Dir $d -SumsLine ("a" * 64 + "  other.zip")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath (Join-Path $d 'SHA256SUMS') } | Should -Throw '*no line*'
    }
    It "accepts a single GNU binary-marker checksum record" {
        $d = Join-Path $TestDrive 'binary-marker'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
        [IO.File]::WriteAllText($sums, "$sha *meta-harness-v9.9.9-test.zip`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Not -Throw
    }
    It "refuses two identical checksum records instead of taking the first" {
        $d = Join-Path $TestDrive 'duplicate'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $line = (Get-Content -LiteralPath $sums)[0]
        [IO.File]::AppendAllText($sums, "$line`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*duplicate or malformed*'
    }
    It "refuses a conflicting checksum record using the binary marker" {
        $d = Join-Path $TestDrive 'conflicting'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        [IO.File]::AppendAllText($sums, "$(('0' * 64)) *meta-harness-v9.9.9-test.zip`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*duplicate or malformed*'
    }
    It "refuses a malformed second record for the requested asset" {
        $d = Join-Path $TestDrive 'malformed-second'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        [IO.File]::AppendAllText($sums, "invalid-sha256  meta-harness-v9.9.9-test.zip`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*duplicate or malformed*'
    }
    It "refuses a sole malformed matching record, distinct from no line" {
        $d = Join-Path $TestDrive 'malformed-only'
        $zip = New-TestRelease -Dir $d -SumsLine 'invalid-sha256  meta-harness-v9.9.9-test.zip'
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath (Join-Path $d 'SHA256SUMS') } |
            Should -Throw '*duplicate or malformed*'
    }
}

Describe "Expand-MetaHarness" {
    It "unpacks the single top-level folder as the target, with the entry point" {
        $d = Join-Path $TestDrive 'unpack'; $zip = New-TestRelease -Dir $d
        $t = Join-Path $TestDrive 'out\mh'
        Expand-MetaHarness -ZipPath $zip -TargetDir $t
        Test-MetaHarnessPresent $t | Should -BeTrue
    }
    It "never overwrites a non-empty target" {
        $d = Join-Path $TestDrive 'keep'; $zip = New-TestRelease -Dir $d
        $t = Join-Path $TestDrive 'mine'
        New-Item -ItemType Directory -Force $t | Out-Null
        Set-Content -LiteralPath (Join-Path $t 'mine.txt') -Value 'keep'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $t } | Should -Throw '*not empty*'
        Get-Content -LiteralPath (Join-Path $t 'mine.txt') | Should -Be 'keep'
    }
}
