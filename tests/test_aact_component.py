"""Isolated AACT source/install controls. Clinical data are never fixtures here."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import component_lock as lock
from scripts import aact_install as installer
from tests.test_component_install import bash_executable, git, commit, user_path_binding

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('__init__', 'tables', 'schema', 'location', 'aggregate')


@pytest.fixture
def origin(tmp_path, monkeypatch):
    home = tmp_path/'isolated-home'
    home.mkdir()
    for name in ('HOME', 'USERPROFILE'):
        monkeypatch.setenv(name, str(home))
    for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_COMMON_DIR'):
        monkeypatch.delenv(name, raising=False)
    for name, value in {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_ALLOW_PROTOCOL': 'file', 'BASH_ENV': '', 'ENV': ''}.items():
        monkeypatch.setenv(name, value)
    source = tmp_path/'origin'
    git('init', '--initial-branch=main', source)
    package = source/'src/aact_kit'
    package.mkdir(parents=True)
    for module in MODULES:
        (package/f'{module}.py').write_text('# synthetic source fixture\n', encoding='utf-8')
    (source/'pyproject.toml').write_text('[project]\nname="aact-kit"\nrequires-python=">=3.10"\ndependencies=["pandas>=2.0"]\n', encoding='utf-8')
    commit(source)
    component = copy.deepcopy(lock.load_lock()['aact-kit'])
    component.update(repository=str(source), commit=git('-C', source, 'rev-parse', 'HEAD'))
    return source, component


def test_source_only_receipt_never_claims_runtime_success(tmp_path, origin):
    _, component = origin
    report = installer.install(tmp_path/'target', component)
    assert report['status'] == 'source_verified'
    assert report['runtime_verified'] is False and report['smoke'] is None
    assert report['expected_commit'] == report['observed_commit'] == component['commit']
    assert len(report['source_files']) == len(MODULES) + 1


@pytest.mark.parametrize('mode', ['missing', 'syntax', 'wrong_package', 'bad_toml'])
def test_invalid_source_cannot_get_receipt(tmp_path, origin, mode):
    source, component = origin
    if mode == 'missing':
        (source/'src/aact_kit/schema.py').unlink()
    elif mode == 'syntax':
        (source/'src/aact_kit/tables.py').write_text('def broken(', encoding='utf-8')
    else:
        (source/'pyproject.toml').write_text('[project]\nname="different"' if mode == 'wrong_package' else '[broken', encoding='utf-8')
    commit(source)
    component['commit'] = git('-C', source, 'rev-parse', 'HEAD')
    with pytest.raises(installer.InstallRefused):
        installer.install(tmp_path/'target', component)


def test_mutable_ref_refuses_without_creating_target(tmp_path, origin):
    _, component = origin
    target = tmp_path/'target'
    with pytest.raises(installer.InstallRefused, match='full lowercase commit'):
        installer.install(target, component, ref='v1.0.0')
    assert not target.exists()


def test_dirty_and_wrong_head_refuse_without_overwriting_source(tmp_path, origin):
    _, component = origin
    target = tmp_path/'target'
    installer.install(target, component)
    with pytest.raises(installer.InstallRefused, match='fresh target'):
        installer.install(target, component, ref='0'*40, skip_clone=True)
    changed = target/'src/aact_kit/tables.py'
    changed.write_text('# user work\n', encoding='utf-8')
    with pytest.raises(installer.InstallRefused, match='dirty'):
        installer.install(target, component, skip_clone=True)
    assert changed.read_text() == '# user work\n'


def test_dependency_install_requires_active_venv_before_mutation(tmp_path, origin, monkeypatch):
    _, component = origin
    monkeypatch.setattr(sys, 'prefix', sys.base_prefix)
    target = tmp_path/'target'
    with pytest.raises(installer.InstallRefused, match='virtual environment'):
        installer.install(target, component, with_deps=True)
    assert not target.exists()


def test_runtime_failure_cannot_be_downgraded_to_source_success(tmp_path, origin):
    _, component = origin
    # This fixture parses but deliberately exposes none of the required API.
    with pytest.raises(installer.InstallRefused):
        installer.install(tmp_path/'target', component, verify_runtime=True)


def test_dependency_failure_is_fatal(tmp_path, origin, monkeypatch):
    _, component = origin
    monkeypatch.setattr(sys, 'prefix', str(tmp_path/'simulated-venv'))
    def failed(target):
        raise installer.InstallRefused('dependency install failed')
    monkeypatch.setattr(installer, 'install_dependencies', failed)
    with pytest.raises(installer.InstallRefused, match='dependency install failed'):
        installer.install(tmp_path/'target', component, with_deps=True)


@pytest.mark.parametrize('payload', ['{}', '{"runtime_verified": true}', 'not-json'])
def test_malformed_runtime_report_is_refused(tmp_path, origin, monkeypatch, payload):
    _, component = origin
    monkeypatch.setattr(installer, 'run_canary', lambda target: payload)
    with pytest.raises(installer.InstallRefused):
        installer.install(tmp_path/'target', component, verify_runtime=True)


def valid_canary():
    return {'schema': 'e156-aact-canary-v1', 'fixture_kind': 'synthetic_install_check',
            'runtime_verified': True, 'postgres_verified': False, 'scientific_accuracy_measured': False,
            'versions': {'python': 'fixture', 'pandas': 'fixture', 'numpy': 'fixture'},
            'backends': [{'backend': b, 'checks': installer.CHECKS, 'payload_sha256': 'a'*64}
                         for b in installer.BACKENDS]}


@pytest.mark.parametrize('mode', ['missing_backend', 'missing_check', 'different_hash', 'false', 'duplicate', 'extra'])
def test_canary_report_refuses_partial_or_misleading_results(mode):
    report = valid_canary()
    if mode == 'missing_backend': report['backends'].pop()
    elif mode == 'missing_check': report['backends'][0]['checks'] = ['load']
    elif mode == 'different_hash': report['backends'][0]['payload_sha256'] = 'b'*64
    elif mode == 'false': report['runtime_verified'] = False
    elif mode == 'extra': report['unmeasured_claim'] = True
    raw = json.dumps(report)
    if mode == 'duplicate': raw = raw.replace('"runtime_verified":', '"runtime_verified": false, "runtime_verified":', 1)
    with pytest.raises(installer.InstallRefused): installer.parse_canary(raw)


def test_runtime_receipt_requires_two_matching_reports(tmp_path, origin, monkeypatch):
    _, component = origin
    report = valid_canary()
    monkeypatch.setattr(installer, 'run_canary', lambda target: json.dumps(report))
    target = tmp_path/'target'
    result = installer.install(target, component, verify_runtime=True)
    assert result['runtime_verified'] is True and result['status'] == 'verified'
    altered = copy.deepcopy(report)
    for backend in altered['backends']: backend['payload_sha256'] = 'b'*64
    calls = iter([json.dumps(report), json.dumps(altered)])
    monkeypatch.setattr(installer, 'run_canary', lambda target: next(calls))
    with pytest.raises(installer.InstallRefused, match='deterministic'):
        installer.install(target, component, skip_clone=True, verify_runtime=True)


@pytest.mark.parametrize('shell', ['bash', 'powershell'] if os.name == 'nt' else ['bash'])
@pytest.mark.parametrize('runtime', [False, True])
def test_wrappers_preserve_user_configuration_and_propagate_failure(tmp_path, origin, shell, runtime):
    import shutil
    source, component = origin
    target = tmp_path/'wrapper'
    git('clone', source, target)
    git('-C', target, 'remote', 'set-url', 'origin', lock.load_lock()['aact-kit']['repository'])
    env = {**os.environ, 'AACT_KIT_REF': component['commit']}
    if shell == 'bash':
        command = [bash_executable(), '--noprofile', '--norc', str(ROOT/'scripts/install-aact-kit.sh'),
                   '--target', str(target), '--skip-clone', '--session-only']
        if runtime: command.append('--verify-runtime')
    else:
        command = [shutil.which('pwsh') or shutil.which('powershell'), '-NoProfile', '-NonInteractive',
                   '-File', str(ROOT/'scripts/install-aact-kit.ps1'), '-Target', str(target), '-SkipClone', '-SessionOnly']
        if runtime: command.append('-VerifyRuntime')
    before = user_path_binding('AACT_KIT_PATH')
    result = subprocess.run(command, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert (result.returncode == 0) is (not runtime), result.stdout + result.stderr
    assert ('"status": "source_verified"' in result.stdout) is (not runtime)
    assert not (tmp_path/'isolated-home/.bashrc').exists()
    assert not (tmp_path/'isolated-home/.zshrc').exists()
    assert user_path_binding('AACT_KIT_PATH') == before


def test_bash_source_persistence_uses_documented_binding(tmp_path, origin):
    source, component = origin
    target = tmp_path/'source with spaces'
    git('clone', source, target)
    git('-C', target, 'remote', 'set-url', 'origin', lock.load_lock()['aact-kit']['repository'])
    env = {**os.environ, 'AACT_KIT_REF': component['commit']}
    result = subprocess.run([bash_executable(), '--noprofile', '--norc', str(ROOT/'scripts/install-aact-kit.sh'),
                             '--target', str(target), '--skip-clone'], env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    rc = tmp_path/'isolated-home/.bashrc'
    assert rc.read_text().count('export AACT_KIT_PATH=') == 1
    result = subprocess.run([bash_executable(), '--noprofile', '--norc', '-c',
                             'source "$1"; test "$AACT_KIT_PATH" = "$(cd "$2" && pwd -P)"', 'fixture', str(rc), str(target)],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
