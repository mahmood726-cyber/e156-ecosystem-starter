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
    function New-TestIncompleteRelease {
        param([string]$Dir, [switch]$EntrypointIsDirectory)
        $zip = New-TestRelease -Dir $Dir
        $entrypoint = Join-Path $Dir 'src\meta-harness-v9.9.9-test\scripts\replay_offline.py'
        Remove-Item -LiteralPath $entrypoint
        if ($EntrypointIsDirectory) {
            New-Item -ItemType Directory -Path $entrypoint | Out-Null
        }
        Remove-Item -LiteralPath $zip
        Compress-Archive -Path (Join-Path $Dir 'src\meta-harness-v9.9.9-test') -DestinationPath $zip
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

Describe "Assert-MetaHarnessRef refuses path and URL syntax" {
    It "allows ordinary version tags and commit tokens" {
        foreach ($good in @('v1.0.0', 'v9.9.9-test', '5a1bcdef0123456789')) {
            { Assert-MetaHarnessRef -Tag $good } | Should -Not -Throw
        }
    }
    It "rejects traversal, URI fragments, escaped separators, whitespace and empty refs" {
        foreach ($bad in @('../escape', 'tag/../../escape', '..\..\escape',
                            'v1.0.0?x=1', 'v1.0.0#latest', 'v1.0.0%2Ffoo',
                            'v1.0.0 latest', '-option', '')) {
            { Assert-MetaHarnessRef -Tag $bad } | Should -Throw '*invalid Meta-Harness release ref*'
        }
    }
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
    It "refuses duplicate checksum entries even when both digests agree" {
        $d = Join-Path $TestDrive 'same-digest-duplicate'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $line = [IO.File]::ReadAllText($sums).Trim()
        [IO.File]::AppendAllText($sums, "$line`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*multiple entries*'
    }
    It "refuses mixed text and GNU binary-marker checksum entries for one asset" {
        $d = Join-Path $TestDrive 'binary-marker-duplicate'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
        [IO.File]::AppendAllText($sums, "$digest *meta-harness-v9.9.9-test.zip`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*multiple entries*'
    }
    It "refuses a malformed matching checksum rather than silently skipping it" {
        $d = Join-Path $TestDrive 'malformed'; $zip = New-TestRelease -Dir $d -SumsLine 'invalid-sha  meta-harness-v9.9.9-test.zip'
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath (Join-Path $d 'SHA256SUMS') } |
            Should -Throw '*malformed entry*'
    }
    It "refuses a malformed duplicate following a valid checksum" {
        $d = Join-Path $TestDrive 'malformed-after-valid'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        [IO.File]::AppendAllText($sums, "invalid-sha  meta-harness-v9.9.9-test.zip`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*multiple entries*'
    }
    It "accepts a single GNU binary-marker checksum and an unrelated line" {
        $d = Join-Path $TestDrive 'binary-single'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
        [IO.File]::WriteAllText($sums, "$digest *meta-harness-v9.9.9-test.zip`n$('0' * 64)  different.zip`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Not -Throw
    }
}

Describe "Meta-Harness Windows checksum-manifest ambiguity" {
    It "refuses duplicate identical asset checksum records" {
        $d = Join-Path $TestDrive 'sha-duplicate-same'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $valid = Get-Content -LiteralPath $sums -Raw
        [IO.File]::WriteAllText($sums, $valid + $valid)
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*multiple entries*'
    }
    It "refuses conflicting asset checksum records rather than selecting the first" {
        $d = Join-Path $TestDrive 'sha-duplicate-conflict'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $valid = (Get-Content -LiteralPath $sums -Raw)
        [IO.File]::WriteAllText($sums, $valid + ('0' * 64) + '  meta-harness-v9.9.9-test.zip' + "`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*multiple entries*'
    }
    It "refuses a malformed matching checksum even when no valid digest exists" {
        $d = Join-Path $TestDrive 'sha-malformed'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        [IO.File]::WriteAllText($sums, 'not-a-digest  meta-harness-v9.9.9-test.zip' + "`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*malformed entry*'
    }
    It "refuses a malformed matching record after a valid checksum" {
        $d = Join-Path $TestDrive 'sha-malformed-after'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $valid = (Get-Content -LiteralPath $sums -Raw)
        [IO.File]::WriteAllText($sums, $valid + 'not-a-digest  meta-harness-v9.9.9-test.zip' + "`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*multiple entries*'
    }
    It "refuses extra fields on the selected asset checksum" {
        $d = Join-Path $TestDrive 'sha-extra-token'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $valid = (Get-Content -LiteralPath $sums -Raw).Trim()
        [IO.File]::WriteAllText($sums, $valid + ' attacker-trailing-field' + "`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Throw '*malformed entry*'
    }
    It "accepts one valid target record beside unrelated asset records" {
        $d = Join-Path $TestDrive 'sha-unrelated'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $valid = (Get-Content -LiteralPath $sums -Raw)
        [IO.File]::WriteAllText($sums, $valid + ('0' * 64) + '  unrelated.zip' + "`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Not -Throw
    }
    It "accepts a single GNU binary-marker checksum record" {
        $d = Join-Path $TestDrive 'sha-binary'; $zip = New-TestRelease -Dir $d
        $sums = Join-Path $d 'SHA256SUMS'
        $valid = (Get-Content -LiteralPath $sums -Raw).Trim()
        $sha = ($valid -split '\s+')[0]
        [IO.File]::WriteAllText($sums, "$sha *meta-harness-v9.9.9-test.zip" + "`n")
        { Test-MetaHarnessAsset -ZipPath $zip -SumsPath $sums } | Should -Not -Throw
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

Describe "Expand-MetaHarness refuses incomplete releases before publishing" {
    It "does not publish a missing replay entry point or leave staging debris" {
        $d = Join-Path $TestDrive 'missing-replay'; $zip = New-TestIncompleteRelease -Dir $d
        $target = Join-Path $d 'out\mh'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*replay_offline.py is missing*'
        Test-Path -LiteralPath $target | Should -BeFalse
        @(Get-ChildItem -LiteralPath (Split-Path $target -Parent) -Filter '.mh-stage-*' -Force).Count | Should -Be 0
    }
    It "preserves a pre-existing empty target on invalid release" {
        $d = Join-Path $TestDrive 'empty-target'; $zip = New-TestIncompleteRelease -Dir $d
        $target = Join-Path $d 'out\mh'
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*replay_offline.py is missing*'
        Test-Path -LiteralPath $target -PathType Container | Should -BeTrue
        @(Get-ChildItem -LiteralPath $target -Force).Count | Should -Be 0
        @(Get-ChildItem -LiteralPath (Split-Path $target -Parent) -Filter '.mh-stage-*' -Force).Count | Should -Be 0
    }
    It "refuses a directory masquerading as replay_offline.py" {
        $d = Join-Path $TestDrive 'fake-replay'; $zip = New-TestIncompleteRelease -Dir $d -EntrypointIsDirectory
        $target = Join-Path $d 'out\mh'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*replay_offline.py is missing*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
}

Describe "Expand-MetaHarness rejects unsafe archive members before unpacking" {
    It "refuses ../ traversal without publishing the target" {
        $d = Join-Path $TestDrive 'zip-traversal'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try { $archive.CreateEntry('../outside.txt') | Out-Null } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*unsafe archive entry*'
        Test-Path -LiteralPath $target | Should -BeFalse
        Test-Path -LiteralPath (Join-Path $d 'outside.txt') | Should -BeFalse
    }
    It "refuses Windows backslash traversal" {
        $d = Join-Path $TestDrive 'zip-backslash'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try { $archive.CreateEntry(('..' + [char]92 + 'outside.txt')) | Out-Null } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*unsafe archive entry*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
    It "refuses drive-rooted or ADS-style archive member names" {
        foreach ($bad in @('C:/outside.txt', 'file.txt:payload')) {
            $d = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            $zip = New-TestRelease -Dir $d
            $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
            try { $archive.CreateEntry($bad) | Out-Null } finally { $archive.Dispose() }
            $target = Join-Path $d 'published'
            { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*unsafe archive entry*'
            Test-Path -LiteralPath $target | Should -BeFalse
        }
    }
    It "refuses ZIP entries marked as Unix symbolic links" {
        $d = Join-Path $TestDrive 'zip-symlink'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try {
            $link = $archive.CreateEntry('meta-harness-v9.9.9-test/link')
            $link.ExternalAttributes = -1610612736  # 0xA0000000: POSIX symlink type
        } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*symlink entry*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
}

Describe "Expand-MetaHarness refuses ambiguous Windows ZIP member paths" {
    It "refuses an exact duplicate member before extraction" {
        $d = Join-Path $TestDrive 'duplicate-member'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try {
            $archive.CreateEntry('meta-harness-v9.9.9-test/scripts/replay_offline.py') | Out-Null
        } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*duplicate or case-colliding*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
    It "refuses paths that collide after Windows case-folding" {
        $d = Join-Path $TestDrive 'case-member'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try {
            $archive.CreateEntry('meta-harness-v9.9.9-test/SCRIPTS/REPLAY_OFFLINE.PY') | Out-Null
        } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*duplicate or case-colliding*'
        Test-Path -LiteralPath $target | Should -BeFalse
    }
    It "refuses reserved Windows device names at any path depth" {
        foreach ($bad in @(
            'AUX.txt', 'nul', 'docs/CONIN$', 'docs/conout$.txt',
            'docs/COM1.log', 'docs/lPt9.ext',
            ('docs/COM' + [char]0x00B9), ('docs/COM' + [char]0x00B2 + '.log'),
            ('docs/COM' + [char]0x00B3 + '.txt'), ('docs/LPT' + [char]0x00B9),
            ('docs/lpt' + [char]0x00B2 + '.dat'), ('docs/LPT' + [char]0x00B3)
        )) {
            $d = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            $zip = New-TestRelease -Dir $d
            $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
            try {
                $archive.CreateEntry("meta-harness-v9.9.9-test/$bad") | Out-Null
            } finally { $archive.Dispose() }
            $target = Join-Path $d 'published'
            { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*reserved device name*'
            Test-Path -LiteralPath $target | Should -BeFalse
        }
    }
    It "still accepts an ordinary path with a similar prefix" {
        $d = Join-Path $TestDrive 'non-device'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try {
            $archive.CreateEntry('meta-harness-v9.9.9-test/COM10.txt') | Out-Null
            $archive.CreateEntry('meta-harness-v9.9.9-test/docs/console.txt') | Out-Null
            $archive.CreateEntry('meta-harness-v9.9.9-test/docs/CONINPUT.txt') | Out-Null
            $archive.CreateEntry('meta-harness-v9.9.9-test/docs/CONOUTSIDE.txt') | Out-Null
            $archive.CreateEntry("meta-harness-v9.9.9-test/docs/README$([char]0x00B9).md") | Out-Null
        } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Not -Throw
        Test-MetaHarnessPresent $target | Should -BeTrue
    }
}

# The checksum text is the public v1.0.0 release metadata (90 bytes), NOT a
# locally generated scientific result. ZIP bytes are not downloaded in Pester.
Describe "Meta-Harness published manifest is independently pinned" {
    It "accepts the exact 90-byte reviewed v1.0.0 SHA256SUMS file" {
        $p = Join-Path $TestDrive 'published-v1-SHA256SUMS'
        $line = '694dc82f51fcde9040a8e1a5f0172978cb1a6f3eeade237fcd81df61185c2d0d  meta-harness-v1.0.0.zip'
        [IO.File]::WriteAllText($p, "$line`n", [System.Text.Encoding]::ASCII)
        { Assert-MetaHarnessReleaseManifest -SumsPath $p -Tag 'v1.0.0' -BaseUrl 'https://github.com/mahmood726-cyber/meta-harness/releases/download/v1.0.0' } | Should -Not -Throw
        (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() |
            Should -Be '3bf1d1f9eaa6f423f3130ca5f6413b05dcf2994833a9fce038e1ee8e9ad00ddb'
    }
    It "refuses a replacement manifest even when the new ZIP checksum is well formed" {
        $p = Join-Path $TestDrive 'replaced-v1-SHA256SUMS'
        [IO.File]::WriteAllText($p, ('0' * 64 + "  meta-harness-v1.0.0.zip`n"))
        { Assert-MetaHarnessReleaseManifest -SumsPath $p -Tag 'v1.0.0' -BaseUrl 'file:///fixture' } |
            Should -Throw '*differs from reviewed pinned digest*'
    }
    It "refuses remote unreviewed tags rather than silently using co-hosted SHA256SUMS" {
        $p = Join-Path $TestDrive 'unreviewed-SHA256SUMS'
        [IO.File]::WriteAllText($p, "anything")
        { Assert-MetaHarnessReleaseManifest -SumsPath $p -Tag 'v1.0.1' -BaseUrl 'https://github.com/mahmood726-cyber/meta-harness/releases/download/v1.0.1' } |
            Should -Throw '*unreviewed meta-harness release*'
    }
    It "keeps the only unpinned path explicitly local for isolated fixture tests" {
        $p = Join-Path $TestDrive 'fixture-SHA256SUMS'
        [IO.File]::WriteAllText($p, "fixture")
        { Assert-MetaHarnessReleaseManifest -SumsPath $p -Tag 'v9.9.9-test' -BaseUrl 'file:///fixture' } |
            Should -Not -Throw
    }
}

Describe "Expand-MetaHarness rejects canonically equivalent Unicode names" {
    It "refuses NFC/NFD aliases without modifying an empty target" {
        $d = Join-Path $TestDrive 'unicode-alias'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try {
            # Two different UTF-8 archive names that normalise to the same path.
            $nfc = "meta-harness-v9.9.9-test/notes/caf$([char]0x00E9).txt"
            $nfd = "meta-harness-v9.9.9-test/notes/cafe$([char]0x0301).txt"
            $archive.CreateEntry($nfc) | Out-Null
            $archive.CreateEntry($nfd) | Out-Null
        } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        New-Item -ItemType Directory -Path $target | Out-Null
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Throw '*duplicate or case-colliding*'
        Test-Path -LiteralPath $target -PathType Container | Should -BeTrue
        @(Get-ChildItem -LiteralPath $target -Force).Count | Should -Be 0
        @(Get-ChildItem -LiteralPath $d -Filter '.mh-stage-*' -Force).Count | Should -Be 0
    }
    It "still installs a release with one decomposed Unicode filename" {
        $d = Join-Path $TestDrive 'unicode-single'; $zip = New-TestRelease -Dir $d
        $archive = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Update)
        try {
            $name = "meta-harness-v9.9.9-test/notes/cafe$([char]0x0301).txt"
            $archive.CreateEntry($name) | Out-Null
        } finally { $archive.Dispose() }
        $target = Join-Path $d 'published'
        { Expand-MetaHarness -ZipPath $zip -TargetDir $target } | Should -Not -Throw
        Test-MetaHarnessPresent $target | Should -BeTrue
    }
}
