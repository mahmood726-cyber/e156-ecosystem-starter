#Requires -Version 5.1
<#
Real full-chain canary for a disposable GitHub-hosted Windows runner only.
Profile redirection cannot sandbox User-registry, known-folder or clipboard
APIs. This script therefore refuses local/self-hosted execution before writes.
Never spoof the runner metadata to use this against a personal Windows account.
#>
[CmdletBinding()]
param([switch]$Import)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-DisposableWindowsRunner {
    if ($env:GITHUB_ACTIONS -cne 'true' -or
        $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
        $env:RUNNER_OS -cne 'Windows' -or
        [Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'REFUSED: this command requires a disposable GitHub-hosted Windows runner.'
    }
}

function Assert-NewSmokeRoot {
    param([string]$ParentPath, [string]$CandidatePath)
    if (-not $ParentPath -or -not [IO.Path]::IsPathRooted($ParentPath)) {
        throw 'REFUSED: RUNNER_TEMP must be an existing absolute directory.'
    }
    $parentFull = [IO.Path]::GetFullPath($ParentPath).TrimEnd('\', '/')
    if (-not (Test-Path -LiteralPath $parentFull -PathType Container)) {
        throw 'REFUSED: RUNNER_TEMP does not exist.'
    }
    $candidateFull = [IO.Path]::GetFullPath($CandidatePath)
    if (-not $candidateFull.StartsWith($parentFull + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
        (Test-Path -LiteralPath $candidateFull)) {
        throw 'REFUSED: smoke root must be new and contained in RUNNER_TEMP.'
    }
    $ancestor = Get-Item -LiteralPath $parentFull -Force
    while ($null -ne $ancestor) {
        if (($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'REFUSED: RUNNER_TEMP ancestors must not be linked paths.'
        }
        $ancestor = $ancestor.Parent
    }
    return $candidateFull
}

function Invoke-CheckedNative {
    param([string]$FilePath, [string[]]$ArgumentList)
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "REFUSED: $FilePath failed (exit $LASTEXITCODE)."
    }
}

function Resolve-SmokeApplication {
    param([string]$Name)
    # -CommandType Application may enumerate every PATH match on Windows.
    # Match ordinary command invocation: use the first executable only.
    return (Get-Command -Name $Name -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
}

if ($Import) { return } # Imports safety helpers only; never calls an installer.

Assert-DisposableWindowsRunner
$starterRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$smokeRoot = Assert-NewSmokeRoot -ParentPath $env:RUNNER_TEMP -CandidatePath (
    Join-Path $env:RUNNER_TEMP ('e156-windows-full-' + [guid]::NewGuid().ToString('N')))

# Existing tools/keys would allow a fresh-install test to pass by reusing state.
foreach ($name in @('sentinel', 'overmind')) {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        throw "REFUSED: $name already exists on the disposable runner's PATH."
    }
}
foreach ($name in @('TRUTHCERT_HMAC_KEY', 'RCT_EXTRACTOR_PATH')) {
    if ([Environment]::GetEnvironmentVariable($name, 'User') -or
        [Environment]::GetEnvironmentVariable($name, 'Process')) {
        throw "REFUSED: $name is already set; this is not a fresh installer context."
    }
}
$pythonCommand = Resolve-SmokeApplication -Name 'python'
$windowsPowerShell = Resolve-SmokeApplication -Name 'powershell.exe'
$null = Get-Command git -CommandType Application -ErrorAction Stop
foreach ($relative in @('install/install.ps1', 'docs/HASH.txt',
        'scripts/check-overmind-canary.py', 'scripts/verify-full-install.py',
        'scripts/component_lock.py',
        'scripts/research_environment.py', 'scripts/check-research-upgrade.py',
        'requirements-aact-canary.lock')) {
    if (-not (Test-Path -LiteralPath (Join-Path $starterRoot $relative) -PathType Leaf)) {
        throw "REFUSED: missing integration ingredient: $relative"
    }
}

$null = New-Item -ItemType Directory -Path $smokeRoot
$installProfile = Join-Path $smokeRoot 'profile'
$virtualEnvironment = Join-Path $smokeRoot 'venv'
$researchRoot = Join-Path $smokeRoot 'research-pair'
$artifactRoot = Join-Path $smokeRoot 'public-evidence'
$null = New-Item -ItemType Directory -Path $installProfile, $artifactRoot
Invoke-CheckedNative $pythonCommand @('-m', 'venv', $virtualEnvironment)
$venvScripts = Join-Path $virtualEnvironment 'Scripts'
$venvPython = Join-Path $venvScripts 'python.exe'

# Process-scoped file destinations; User-registry and known-folder operations
# still belong to the disposable runner account and die with that runner.
$changes = @{
    USERPROFILE = $installProfile
    APPDATA = (Join-Path $installProfile 'AppData\Roaming')
    LOCALAPPDATA = (Join-Path $installProfile 'AppData\Local')
    TEMP = (Join-Path $smokeRoot 'temp')
    TMP = (Join-Path $smokeRoot 'temp')
    PATH = ($venvScripts + [IO.Path]::PathSeparator + $env:PATH)
    VIRTUAL_ENV = $virtualEnvironment
    PYTHONPATH = $null
    PYTHONHOME = $null
    PYTHONNOUSERSITE = '1'
    PYTHONUTF8 = '1'
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
    PIP_CONFIG_FILE = 'NUL'
    PIP_REQUIRE_VIRTUALENV = 'true'
    SENTINEL_REF = $null
    OVERMIND_REF = $null
    RCT_EXTRACTOR_REF = $null
}
$savedEnvironment = @{}
foreach ($name in $changes.Keys) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    foreach ($name in $changes.Keys) {
        [Environment]::SetEnvironmentVariable($name, $changes[$name], 'Process')
    }
    $null = New-Item -ItemType Directory -Path $env:APPDATA, $env:LOCALAPPDATA, $env:TEMP
    Push-Location $starterRoot
    try {
        # The installer and all four legacy subinstallers execute unmodified.
        Invoke-CheckedNative $windowsPowerShell @('-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-File', 'install/install.ps1', '-DryRun')
        Invoke-CheckedNative $windowsPowerShell @('-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-File', 'install/install.ps1', '-Full',
            '-GitHubUser', 'e156-integration-ci')
        Invoke-CheckedNative $venvPython @('scripts/component_lock.py', '--check')
        Invoke-CheckedNative $venvPython @('-m', 'pip', 'install', '--require-hashes',
            '--only-binary=:all:', '-r', 'requirements-aact-canary.lock')
        Invoke-CheckedNative $venvPython @('scripts/research_environment.py', 'install', '--root', $researchRoot)
        Invoke-CheckedNative $venvPython @('scripts/research_environment.py', 'verify', '--root', $researchRoot)
        Invoke-CheckedNative $venvPython @('scripts/check-research-upgrade.py', '--root', $researchRoot)
        Invoke-CheckedNative $venvPython @('-m', 'pip', 'check')

        # Windows stores the key in HKCU\Environment, not Linux's key file.
        # Verify that real contract directly; never fabricate a Linux key file
        # or export the registry, transcripts, environment or private profile.
        $probe = @'
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import winreg

profile, starter, paired, output = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('full_install', starter/'scripts/verify-full-install.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def run(argv, timeout=240):
    return subprocess.run(argv, capture_output=True, text=True, errors='replace',
                          check=True, timeout=timeout).stdout.strip()

for agent in ('.claude', '.gemini', '.codex'):
    for name in contract.RULE_FILES:
        require((profile/agent/'rules'/name).is_file(), f'missing {agent} rule {name}')
    for name in contract.CONTEXT_FILES:
        require((profile/agent/name).is_file(), f'missing {agent} context {name}')
    rules = (profile/agent/'rules/rules.md').read_text(encoding='utf-8')
    require(str(profile/'code/ProjectIndex') in rules and '{{PROJECTINDEX_ROOT}}' not in rules,
            f'incorrect {agent} ProjectIndex binding')
for agent in ('.claude', '.gemini'):
    require((profile/agent/'memory/MEMORY.md').is_file(), f'missing {agent} memory')

sample = profile/'code/my-first-repo'
hook = (sample/'.git/hooks/pre-push').read_text(encoding='utf-8')
require('# === SENTINEL PRE-PUSH HOOK (do not edit above this line) ===' in hook
        and 'python -m sentinel scan' in hook
        and re.search(r'(?m)^MODE="\$\{SENTINEL_MODE:-block\}"[ \t]*$', hook),
        'Sentinel hook is not the required blocking hook')
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
    secret, _ = winreg.QueryValueEx(registry, 'TRUTHCERT_HMAC_KEY')
    require(isinstance(secret, str) and re.fullmatch('[0-9a-fA-F]{64}', secret),
            'Windows TruthCert key missing or malformed')
    del secret
    extractor_binding, _ = winreg.QueryValueEx(registry, 'RCT_EXTRACTOR_PATH')
extractor = profile/'code/rct-extractor-v2'
require(Path(extractor_binding).resolve() == extractor.resolve(), 'incorrect persisted extractor binding')
require((extractor/'scripts/build_metakit_config.py').is_file(), 'missing extractor bridge')
index = profile/'code/ProjectIndex'
for relative in ('INDEX.md', 'reconcile_counts.py', 'agent-records/restart-manifest.json'):
    require((index/relative).is_file(), f'missing ProjectIndex {relative}')

run(['sentinel', 'scan', '--repo', str(sample)])
require(contract._overmind_certified_result(run(['overmind', 'meta-verify'])),
        'Overmind health fixture was not CERTIFIED')
run([sys.executable, str(index/'reconcile_counts.py'), '--root', str(index)])
run([sys.executable, '-c',
     "import sys; sys.path.insert(0, sys.argv[1]); "
     "from rct_extractor import SPECIALTIES, detect_specialty; assert len(SPECIALTIES) == 17; "
     "assert detect_specialty('viral suppression with dolutegravir')[0] == 'hiv'; "
     "assert detect_specialty('empagliflozin type 2 diabetes HbA1c')[0] == 'diabetes'", str(extractor)])

lock = json.loads((starter/'scripts/component-lock.json').read_text(encoding='utf-8'))
components = {}
for name in ('sentinel', 'overmind'):
    distribution = metadata.distribution(name)
    direct = json.loads(distribution.read_text('direct_url.json'))
    expected = lock['components'][name]
    require(direct['url'] == expected['repository']
            and direct['vcs_info']['commit_id'] == expected['commit'],
            f'{name} installed source differs from lock')
    components[name] = {'version': distribution.version, 'commit': direct['vcs_info']['commit_id']}
components['extractor'] = {'commit': run(['git', '-C', str(extractor), 'rev-parse', 'HEAD']),
                           'selection': 'legacy installer release tag (not immutable authentication)'}
pair_result = json.loads(run([sys.executable, str(starter/'scripts/research_environment.py'),
                             'verify', '--root', str(paired)]))
record = json.loads((paired/'releases'/pair_result['release']/'release.json').read_text(encoding='utf-8'))
manifest = {
    'schema': 'e156-windows-install-smoke-v1', 'status': 'verified',
    'scope': ['Windows base rules/memory', 'Sentinel', 'Overmind verifier health',
              'TruthCert registry key setup', 'ProjectIndex', 'extractor core', 'RapidMeta/AACT pair'],
    'starter_commit': run(['git', '-C', str(starter), 'rev-parse', 'HEAD']),
    'installer_sha256': hashlib.sha256((starter/'install/install.ps1').read_bytes()).hexdigest(),
    'component_lock_sha256': hashlib.sha256((starter/'scripts/component-lock.json').read_bytes()).hexdigest(),
    'components': components, 'research_release': pair_result['release'],
    'runtime': record['specification']['runtime'],
    'controls': {'blocking_hook': True, 'registry_key_format': True,
                 'live_canaries': True, 'failed_research_upgrade_preserved_active_pair': True},
    'limitations': ['disposable hosted account, not a fresh consumer Windows image',
                    'legacy pip dependencies are not hash-locked',
                    'no agent CLI login, PDF extras, PostgreSQL, scientific validation or power-loss proof'],
    'release_authorized': False,
}
output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print('PASS: Windows full-chain artifacts, live canaries, source identities and research runtime verified.')
'@
        $probePath = Join-Path $smokeRoot 'verify_windows.py'
        [IO.File]::WriteAllText($probePath, $probe, (New-Object Text.UTF8Encoding $false))
        Invoke-CheckedNative $venvPython @($probePath, $installProfile, $starterRoot,
            $researchRoot, (Join-Path $artifactRoot 'windows-install-manifest.json'))
        if ($env:GITHUB_OUTPUT) {
            [IO.File]::AppendAllText($env:GITHUB_OUTPUT, "evidence=$artifactRoot`n",
                (New-Object Text.UTF8Encoding $false))
        }
    } finally {
        Pop-Location
    }
} finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
}
