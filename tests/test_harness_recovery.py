"""Current OA replay fixtures must reach the recovery comparison boundary."""
import shutil
import subprocess
import json
import sys

import pytest

from benchmarks import harness_recovery as benchmark


@pytest.mark.parametrize('fixture', sorted(benchmark.ANCHORS))
def test_reviewed_recovery_anchor_recomputes_current_bundle(fixture):
    receipt = benchmark.replay.verify(
        benchmark.ROOT / 'examples' / ('synthesis-replay-' + fixture),
        benchmark.ANCHORS[fixture])
    assert receipt['status'] == 'REPLAY_MATCHED'


@pytest.mark.parametrize('fixture', sorted(benchmark.ANCHORS))
@pytest.mark.parametrize('target', ['manifest.json', 'result.json', 'source'])
def test_recovery_anchor_refuses_changed_bundle(tmp_path, fixture, target):
    root = tmp_path / 'bundle'
    shutil.copytree(benchmark.ROOT / 'examples' / ('synthesis-replay-' + fixture), root)
    path = next((root / 'sources').glob('*.xml')) if target == 'source' else root / target
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(benchmark.replay.Refused):
        benchmark.replay.verify(root, benchmark.ANCHORS[fixture])


@pytest.mark.parametrize('result', [
    subprocess.CompletedProcess([], 1, '{}'),
    subprocess.CompletedProcess([], 0, '{"outcome":"REFUSED"}'),
    subprocess.CompletedProcess([], 2, '{"outcome":"PAUSED"}'),
    subprocess.CompletedProcess([], 0, 'not json'),
])
def test_worker_apparatus_failures_are_not_refusals(monkeypatch, tmp_path, result):
    monkeypatch.setattr(benchmark.subprocess, 'run', lambda *a, **k: result)
    row = benchmark.invoke('direct_replay', 'start', tmp_path, 'stepwise')
    assert row['outcome'] == 'ERROR'


def test_failed_initialization_retains_every_recovery_denominator(monkeypatch):
    monkeypatch.setattr(benchmark, 'invoke', lambda *a: {'outcome': 'ERROR', 'reason': 'planted'})
    report = benchmark.evaluate()
    assert report['attempted_cases'] == 18
    assert all(row['initial']['outcome'] == 'ERROR' and
               row['resumed']['outcome'] == 'NOT_ATTEMPTED' and
               row['integrity_contract_satisfied'] is False for row in report['cases'])


def test_process_loss_retains_completed_attempts(tmp_path):
    output = tmp_path / 'interrupted.json'
    script = '''import os,sys
from benchmarks import harness_recovery as b
calls=0
def interrupted(*args):
    global calls
    calls += 1
    if calls == 2: os._exit(91)
    return {'outcome':'ERROR','reason':'SYNTHETIC interruption control'}
b.invoke=interrupted
sys.argv=['benchmark','--output',sys.argv[1]]
b.main()
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(output)],
                            cwd=benchmark.ROOT, capture_output=True, timeout=30)
    assert result.returncode == 91, result.stderr
    rows = [json.loads(line) for line in output.with_name(output.name + '.attempts.jsonl').read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]['initial']['outcome'] == 'ERROR'
    assert rows[0]['resumed']['outcome'] == 'NOT_ATTEMPTED'
    assert rows[0]['integrity_contract_satisfied'] is False
    assert output.read_bytes() == b''  # Never misrepresent an incomplete run as a final report.
