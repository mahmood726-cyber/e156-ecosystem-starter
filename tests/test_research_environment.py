"""Synthetic filesystem controls for paired activation, never real installers.

The component adapters are replaced at their Python boundary. Real Git/source
adapters are covered elsewhere and the combined live path runs in disposable CI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import research_environment as env
from scripts.component_lock import DEFAULT_LOCK


@pytest.fixture
def rig(tmp_path, monkeypatch):
    root = tmp_path/'managed'
    lock = tmp_path/'components.json'
    lock.write_bytes(DEFAULT_LOCK.read_bytes())
    state = {'fail': None, 'calls': [], 'mutate_active': False, 'source_only': False, 'mutate_first': False}
    monkeypatch.setattr(env, 'runtime_profile', lambda: {'python': 'fixture', 'pandas': 'fixture', 'numpy': 'fixture', 'platform': 'fixture'})

    def adapter(target, component, **kwargs):
        name = 'aact-kit' if 'aact' in component['repository'] else 'rapidmeta'
        state['calls'].append(name)
        if state['fail'] == name:
            raise env.Refused('synthetic component failure')
        target.mkdir(parents=True, exist_ok=True)
        marker = target/'fixture.txt'
        if marker.exists():
            if marker.read_text() != component['commit']:
                raise env.Refused('synthetic dirty component')
        else:
            marker.write_text(component['commit'], encoding='utf-8')
        if name == 'aact-kit' and state['mutate_active']:
            (root/'active.json').write_text('external edit', encoding='utf-8')
        if name == 'aact-kit' and state['mutate_first']:
            (target.parent/'rapidmeta/fixture.txt').write_text('changed during later adapter')
        return {'schema': 'e156-component-install-v1', 'component': name,
                'adapter': component['verification'], 'expected_commit': component['commit'],
                'observed_commit': component['commit'], 'status': 'source_verified' if state['source_only'] else 'verified',
                'runtime_verified': True, 'fixture_kind': 'synthetic_coordinator_test'}

    monkeypatch.setattr(env.rapidmeta, 'install', adapter)
    monkeypatch.setattr(env.aact, 'install', adapter)
    def finish(target, component, expected):
        if (target/'fixture.txt').read_text() != expected:
            raise env.Refused('synthetic final source mismatch')
    monkeypatch.setattr(env.source, 'finish', finish)
    return root, lock, state


def advance(lock):
    data = json.loads(lock.read_text())
    data['components']['rapidmeta']['commit'] = 'a'*40  # synthetic adapter fixture
    lock.write_text(json.dumps(data), encoding='utf-8')


def test_install_verify_and_repeat_recheck_both_components(rig):
    root, lock, state = rig
    first = env.install(root, lock)
    assert first['scope'] == ['rapidmeta', 'aact-kit']
    assert first['status'] == 'verified'
    before = (root/'active.json').read_bytes()
    assert env.verify(root) == first
    assert env.install(root, lock) == first
    assert (root/'active.json').read_bytes() == before
    assert state['calls'] == ['rapidmeta', 'aact-kit']*3


@pytest.mark.parametrize('failed', ['rapidmeta', 'aact-kit'])
def test_failed_upgrade_preserves_active_bytes_and_previous_sources(rig, failed):
    root, lock, state = rig
    first = env.install(root, lock)
    before = (root/'active.json').read_bytes()
    marker = Path(first['paths']['rapidmeta'])/'fixture.txt'
    original = marker.read_bytes()
    advance(lock)
    state['fail'] = failed
    with pytest.raises(env.Refused): env.install(root, lock)
    assert (root/'active.json').read_bytes() == before
    assert marker.read_bytes() == original
    state['fail'] = None
    assert env.verify(root) == first


def test_failed_first_install_never_creates_active_pointer(rig):
    root, lock, state = rig
    state['fail'] = 'aact-kit'
    with pytest.raises(env.Refused): env.install(root, lock)
    assert not (root/'active.json').exists()


def test_verified_upgrade_and_explicit_rollback(rig):
    root, lock, _ = rig
    first = env.install(root, lock)
    advance(lock)
    second = env.install(root, lock)
    assert second['release'] != first['release']
    assert env.rollback(root, first['release']) == first
    assert Path(second['paths']['rapidmeta']).is_dir()


def test_rollback_rechecks_sources_before_switching(rig):
    root, lock, _ = rig
    first = env.install(root, lock)
    advance(lock)
    env.install(root, lock)
    before = (root/'active.json').read_bytes()
    (Path(first['paths']['aact-kit'])/'fixture.txt').write_text('changed')
    with pytest.raises(env.Refused): env.rollback(root, first['release'])
    assert (root/'active.json').read_bytes() == before


def test_source_only_receipt_cannot_activate_pair(rig):
    root, lock, state = rig
    state['source_only'] = True
    with pytest.raises(env.Refused, match='receipt'): env.install(root, lock)
    assert not (root/'active.json').exists()


def test_atomic_publish_failure_preserves_prior_pointer(rig, monkeypatch):
    root, lock, _ = rig
    env.install(root, lock)
    before = (root/'active.json').read_bytes()
    advance(lock)
    replace = env.os.replace
    def fail_pointer(src, dst):
        if Path(dst).name == 'active.json': raise OSError('synthetic publish failure')
        return replace(src, dst)
    monkeypatch.setattr(env.os, 'replace', fail_pointer)
    with pytest.raises(OSError): env.install(root, lock)
    assert (root/'active.json').read_bytes() == before


def test_other_writer_lock_refuses_without_touching_active(rig):
    root, lock, _ = rig
    env.install(root, lock)
    before = (root/'active.json').read_bytes()
    held = root/'.operation.lock'
    held.write_text('another writer')
    with pytest.raises(env.Refused, match='lock'): env.install(root, lock)
    assert held.read_text() == 'another writer'
    assert (root/'active.json').read_bytes() == before


def test_unmanaged_nonempty_root_is_not_adopted(rig):
    root, lock, _ = rig
    root.mkdir()
    (root/'user.txt').write_text('keep')
    with pytest.raises(env.Refused, match='managed'): env.install(root, lock)
    assert list(root.iterdir()) == [root/'user.txt']


@pytest.mark.parametrize('raw', ['{}', '{"schema":"a","schema":"b"}', '{"release":"../escape"}', 'null'])
def test_corrupt_active_pointer_is_refused(rig, raw):
    root, lock, _ = rig
    env.install(root, lock)
    (root/'active.json').write_text(raw)
    with pytest.raises(env.Refused): env.verify(root)
    with pytest.raises(env.Refused): env.install(root, lock)
    assert (root/'active.json').read_text() == raw


@pytest.mark.parametrize('part', ['release.json', 'component-lock.json'])
def test_changed_saved_record_or_lock_is_refused(rig, part):
    root, lock, _ = rig
    first = env.install(root, lock)
    path = root/'releases'/first['release']/part
    path.write_text('{}')
    with pytest.raises(env.Refused): env.verify(root)


def test_stale_runtime_requires_new_verified_generation(rig, monkeypatch):
    root, lock, _ = rig
    first = env.install(root, lock)
    monkeypatch.setattr(env, 'runtime_profile', lambda: {'python': 'different fixture'})
    with pytest.raises(env.Refused, match='profile'): env.verify(root)
    second = env.install(root, lock)
    assert second['release'] != first['release']


def test_missing_runtime_is_refused_before_root_creation(rig, monkeypatch):
    root, lock, _ = rig
    def missing(): raise env.Refused('missing runtime')
    monkeypatch.setattr(env, 'runtime_profile', missing)
    with pytest.raises(env.Refused): env.install(root, lock)
    assert not root.exists()


def test_manual_pointer_edit_during_build_is_preserved(rig):
    root, lock, state = rig
    env.install(root, lock)
    advance(lock)
    state['mutate_active'] = True
    with pytest.raises(env.Refused, match='changed'): env.install(root, lock)
    assert (root/'active.json').read_text() == 'external edit'


def test_later_adapter_cannot_change_earlier_verified_source(rig):
    root, lock, state = rig
    state['mutate_first'] = True
    with pytest.raises(env.Refused, match='final source mismatch'): env.install(root, lock)
    assert not (root/'active.json').exists()


def test_pointer_change_during_read_verification_is_refused(rig):
    root, lock, state = rig
    env.install(root, lock)
    state['mutate_active'] = True
    with pytest.raises(env.Refused, match='changed'): env.verify(root)


def test_linked_managed_directory_is_refused(rig, monkeypatch):
    root, lock, _ = rig
    env.install(root, lock)
    original = env.source.linked
    monkeypatch.setattr(env.source, 'linked', lambda p: p == root/'releases' or original(p))
    with pytest.raises(env.Refused, match='linked'): env.verify(root)


@pytest.mark.parametrize('release', ['../escape', '', 'A'*64, '0'*64])
def test_invalid_or_missing_rollback_release_refuses(rig, release):
    root, lock, _ = rig
    env.install(root, lock)
    before = (root/'active.json').read_bytes()
    with pytest.raises(env.Refused): env.rollback(root, release)
    assert (root/'active.json').read_bytes() == before
