"""Integration contracts for one persistent audit; real OA inputs, disposable state."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

from scripts import synthesis_review_runner as runner

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/synthesis_review_runner.py'
ANCHORS = {
    'stepwise': 'c7fb904293fcf13ec542553b9667bfec51ca7c713d1183b418ec93b6cbb177d3',
    'strokewalk': '8ebe174bf7613830c5c919b989d8967c3f56d3ea5b742dd4a8b561293faf4533',
}


@pytest.fixture(params=ANCHORS)
def rig(tmp_path, request):
    bundle = tmp_path / 'bundle'
    shutil.copytree(ROOT / 'examples' / ('synthesis-replay-' + request.param), bundle)
    protocol = tmp_path / 'protocol.json'
    protocol.write_text(json.dumps({'schema': 'e156-review-protocol-v1',
        'project': 'development-' + request.param, 'stage': 'source-replay-audit',
        'manifest_sha256': ANCHORS[request.param]}), encoding='utf-8')
    anchor = sha256(protocol.read_bytes()).hexdigest()
    return {'state': tmp_path / 'review.sqlite', 'bundle': bundle,
            'protocol': protocol, 'expected_sha256': anchor}


def cli(rig, command='advance', cwd=None):
    args = [sys.executable, str(SCRIPT), command, '--state', str(rig['state']),
            '--bundle', str(rig['bundle']), '--protocol', str(rig['protocol']),
            '--expected-sha256', rig['expected_sha256']]
    p = subprocess.run(args, cwd=cwd or ROOT, capture_output=True, text=True, timeout=30)
    assert not p.stderr, p.stderr
    return p.returncode, json.loads(p.stdout)


def events(rig):
    with closing(sqlite3.connect(rig['state'])) as db:
        return db.execute('SELECT seq, body, sha256 FROM events ORDER BY seq').fetchall()


def completed(rig):
    assert runner.initialize(**rig)['status'] == 'READY'
    assert runner.advance(**rig)['status'] == 'AUDITED'
    result = runner.advance(**rig)
    assert result['status'] == 'COMPLETED'
    return result


def test_new_process_resume_and_idempotent_completion_preserve_hold(rig, tmp_path):
    for command, want in [('init', 'READY'), ('advance', 'AUDITED'), ('advance', 'COMPLETED')]:
        code, result = cli(rig, command, tmp_path)
        assert code == 0 and result['status'] == want
        assert result['release_eligible'] is False
    before = events(rig)
    code, again = cli(rig, cwd=tmp_path)
    assert code == 0 and again == result
    assert events(rig) == before and len(before) == 3
    assert result['completion']['review_state'] == 'HOLD'
    assert result['completion']['scientific_validity'] == 'NOT_ESTABLISHED'
    assert result['completion']['external_actions'] == 0
    assert result['completion']['payload_sha256'] == sha256((rig['bundle'] / 'result.json').read_bytes()).hexdigest()


@pytest.mark.parametrize('when', ['AUDITED', 'COMPLETED'])
@pytest.mark.parametrize('changed', ['source', 'result', 'protocol', 'missing_source'])
def test_dependency_change_invalidates_descendants_permanently(rig, when, changed):
    runner.initialize(**rig); runner.advance(**rig)
    if when == 'COMPLETED': runner.advance(**rig)
    path = (next((rig['bundle'] / 'sources').glob('*.xml')) if 'source' in changed else
            rig['bundle'] / 'result.json' if changed == 'result' else rig['protocol'])
    original = path.read_bytes()
    if changed == 'missing_source': path.unlink()
    else: path.write_bytes(original + b' ')
    result = runner.advance(**rig)
    assert result['status'] == 'INVALIDATED' and result['completion'] is None
    assert result['release_eligible'] is False
    path.write_bytes(original)
    assert runner.advance(**rig) == result


def test_changed_code_invalidates_without_rebinding_history(rig, monkeypatch):
    completed(rig)
    profile = runner.code_profile()
    profile['runner_sha256'] = '0' * 64
    monkeypatch.setattr(runner, 'code_profile', lambda: profile)
    result = runner.advance(**rig)
    assert result['status'] == 'INVALIDATED' and result['completion'] is None


def test_input_change_during_replay_cannot_commit_a_current_receipt(rig, monkeypatch):
    completed(rig)
    original = runner.replay.verify
    def changed_after_read(*args):
        result = original(*args)
        path = rig['bundle'] / 'result.json'
        path.write_bytes(path.read_bytes() + b' ')
        return result
    monkeypatch.setattr(runner.replay, 'verify', changed_after_read)
    result = runner.advance(**rig)
    assert result['status'] == 'INVALIDATED' and result['completion'] is None


def test_missing_entire_bundle_is_terminal_even_after_restoration(rig, tmp_path):
    completed(rig)
    moved = tmp_path / 'temporarily-absent'
    rig['bundle'].rename(moved)
    result = runner.advance(**rig)
    assert result['status'] == 'INVALIDATED'
    moved.rename(rig['bundle'])
    assert runner.advance(**rig) == result


def test_infrastructure_error_rolls_back_without_becoming_an_integrity_refusal(rig, monkeypatch):
    completed(rig); before = events(rig)
    def failed_storage(*args): raise OSError('injected read failure')
    monkeypatch.setattr(runner.replay, 'verify', failed_storage)
    with pytest.raises(OSError): runner.advance(**rig)
    assert events(rig) == before


def test_wrong_external_anchor_and_reinit_leave_existing_history(rig):
    completed(rig); before = events(rig)
    with pytest.raises(runner.Refused): runner.initialize(**rig)
    wrong = {**rig, 'expected_sha256': '0' * 64}
    with pytest.raises(runner.Refused): runner.advance(**wrong)
    assert events(rig) == before


def test_missing_or_corrupt_state_never_becomes_new_run(rig):
    code, result = cli(rig)
    assert code == 2 and result['status'] == 'REFUSED'
    assert not rig['state'].exists()
    rig['state'].write_bytes(b'not a SQLite database')
    code, result = cli(rig)
    assert code != 0 and result['completion'] is None
    assert rig['state'].read_bytes() == b'not a SQLite database'


@pytest.mark.parametrize('change', ['duplicate_key', 'unknown_field', 'wrong_stage', 'nonfinite', 'oversized'])
def test_protocol_rejects_unsupported_contract_before_state_creation(rig, change):
    protocol = json.loads(rig['protocol'].read_text())
    if change == 'unknown_field': protocol['commands'] = ['anything']
    if change == 'wrong_stage': protocol['stage'] = 'publish'
    raw = json.dumps(protocol).encode()
    if change == 'duplicate_key': raw = raw.replace(b'"stage":', b'"stage":"source-replay-audit","stage":')
    if change == 'nonfinite': raw = raw.replace(b'"source-replay-audit"', b'NaN')
    if change == 'oversized': raw += b' ' * 20000
    rig['protocol'].write_bytes(raw); rig['expected_sha256'] = sha256(raw).hexdigest()
    with pytest.raises(runner.Refused): runner.initialize(**rig)
    assert not rig['state'].exists()


def test_input_paths_and_sqlite_sidecars_cannot_alias_protocol_or_bundle(rig):
    for path in [rig['protocol'], rig['bundle'] / 'state.sqlite', rig['bundle'] / '..' / 'bundle' / 'state.sqlite']:
        with pytest.raises(runner.Refused): runner.initialize(**{**rig, 'state': path})
    state = rig['protocol'].with_name('protocol')
    sidecar = Path(str(state) + '-journal')
    sidecar.write_bytes(rig['protocol'].read_bytes())
    with pytest.raises(runner.Refused): runner.initialize(**{**rig, 'state': state, 'protocol': sidecar})
    assert not state.exists()


def test_busy_writer_cannot_emit_a_cached_success(rig):
    completed(rig); before = events(rig)
    with closing(sqlite3.connect(rig['state'], isolation_level=None)) as db:
        db.execute('BEGIN IMMEDIATE')
        code, result = cli(rig)
        assert code != 0 and result['completion'] is None
        db.rollback()
    assert events(rig) == before
    assert runner.advance(**rig)['status'] == 'COMPLETED'


@pytest.mark.parametrize('fault', ['checksum', 'sequence', 'forged_receipt', 'boolean_numeric',
                                  'unknown_table', 'trigger', 'empty'])
def test_invalid_state_history_and_schema_refuse_without_receipt(rig, fault):
    completed(rig)
    with closing(sqlite3.connect(rig['state'])) as db, db:
        if fault == 'checksum': db.execute("UPDATE events SET sha256=? WHERE seq=1", ('0'*64,))
        elif fault == 'sequence': db.execute('DELETE FROM events WHERE seq=1')
        elif fault == 'empty': db.execute('DELETE FROM events')
        elif fault == 'unknown_table': db.execute('CREATE TABLE extra(x)')
        elif fault == 'trigger': db.execute('CREATE TRIGGER extra AFTER INSERT ON events BEGIN DELETE FROM events; END')
        else:
            body = json.loads(db.execute('SELECT body FROM events WHERE seq=2').fetchone()[0])
            if fault == 'boolean_numeric': body['completion']['external_actions'] = False
            else: body['completion']['review_state'] = 'RELEASE_READY'
            raw = runner.replay.canonical(body)
            db.execute('UPDATE events SET body=?, sha256=? WHERE seq=2', (raw.decode(), sha256(raw).hexdigest()))
    code, result = cli(rig)
    assert code == 2 and result['status'] == 'REFUSED' and result['completion'] is None


def kill_at_marker(code, rig, tmp_path):
    marker = tmp_path / 'worker-ready'
    data = {k: str(v) for k,v in rig.items()}
    p = subprocess.Popen([sys.executable, '-c', code, json.dumps(data), str(marker)],
                         cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and p.poll() is None and time.monotonic() < deadline: time.sleep(.02)
        assert marker.exists(), p.communicate(timeout=2)
        p.kill(); p.wait(timeout=10)
        assert p.returncode != 0
    finally:
        if p.poll() is None: p.kill(); p.wait(timeout=10)
        p.communicate(timeout=2)


@pytest.mark.parametrize('stage', ['AUDITED', 'COMPLETED'])
def test_abrupt_process_death_before_commit_rolls_back_and_releases_lock(rig, tmp_path, stage):
    runner.initialize(**rig)
    if stage == 'COMPLETED': runner.advance(**rig)
    before = events(rig)
    code = '''
import json,sys,time
from pathlib import Path
from scripts import synthesis_review_runner as r
kw=json.loads(sys.argv[1]); kw={k:Path(v) if k!='expected_sha256' else v for k,v in kw.items()}
original=r._append
def interrupted(*args,**kwargs):
    original(*args,**kwargs)
    Path(sys.argv[2]).write_text('uncommitted',encoding='utf-8')
    time.sleep(60)
r._append=interrupted
r.advance(**kw)
'''
    kill_at_marker(code, rig, tmp_path)
    assert events(rig) == before
    assert runner.advance(**rig)['status'] == stage


def test_death_after_commit_before_response_retry_does_not_duplicate_completion(rig, tmp_path):
    runner.initialize(**rig); runner.advance(**rig)
    code = '''
import json,sys,time
from pathlib import Path
from scripts import synthesis_review_runner as r
kw=json.loads(sys.argv[1]); kw={k:Path(v) if k!='expected_sha256' else v for k,v in kw.items()}
result=r.advance(**kw)
Path(sys.argv[2]).write_text(json.dumps(result),encoding='utf-8')
time.sleep(60)
'''
    kill_at_marker(code, rig, tmp_path)
    before = events(rig)
    expected = json.loads((tmp_path/'worker-ready').read_text())
    assert runner.advance(**rig) == expected
    assert len(events(rig)) == 3 and events(rig) == before
