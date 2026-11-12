"""Export integration controls on existing attributed development bundles."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import synthesis_replay as replay
from scripts import synthesis_rocrate as crate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    'stepwise': '9d3e611c2d06485c9f004e73d7b94847e9dec6b69e026700b1ace23c3f76dd0d',
    'strokewalk': 'e0e02c64467a9a34ad41230eb64d4586c010f5531ed3091a01ffdd3cead31481',
}


@pytest.fixture(params=EXAMPLES)
def exported(request, tmp_path, monkeypatch):
    def forbidden(*a, **k): raise AssertionError('export attempted source retrieval')
    monkeypatch.setattr(replay.capture, 'build_opener', forbidden)
    source = ROOT/'examples'/('synthesis-replay-'+request.param)
    output = tmp_path/'crate'
    receipt = crate.export(source, EXAMPLES[request.param], output)
    return source, output, receipt


def test_real_export_preserves_replay_bytes_and_has_resolvable_provenance(exported):
    source, output, receipt = exported
    for path in source.rglob('*'):
        if path.is_file(): assert path.read_bytes() == (output/'replay'/path.relative_to(source)).read_bytes()
    graph = json.loads((output/'ro-crate-metadata.json').read_bytes())['@graph']
    nodes = {n['@id']: n for n in graph}
    run = json.loads((output/'run.json').read_bytes())
    action = nodes[run['action_id']]
    assert action['@type'] == 'CreateAction'
    assert action['instrument'] == {'@id': 'software/synthesis_replay.py'}
    assert action['result'] == {'@id': 'replay/result.json'}
    assert {'@id': 'replay/packet.json'} in action['object']
    assert {'@id': 'replay/prompt.md'} in action['object']
    assert 'agent' not in action
    assert datetime.fromisoformat(action['startTime']) <= datetime.fromisoformat(action['endTime'])
    assert run['scientific_validity'] == 'NOT_ESTABLISHED'
    for n in graph:
        if 'File' in ([n['@type']] if isinstance(n['@type'], str) else n['@type']):
            raw = (output/n['@id']).read_bytes()
            assert replay.digest(raw) == n['sha256']
            assert n['contentSize'] == len(raw)
    assert crate.verify(output, receipt['metadata_sha256'])['status'] == 'EXPORT_MATCHED'
    result = json.loads((output/'replay/result.json').read_bytes())
    if 'study_links' in result:
        assert result['study_links']['links'][0]['reference_type'] == 'DERIVED'
        assert result['study_links']['pooling_readiness'] == 'HOLD'


def test_separate_exports_preserve_payload_but_record_distinct_executions(exported, tmp_path):
    source, output, receipt = exported
    other = tmp_path/'other'
    anchor = replay.digest((source/'manifest.json').read_bytes())
    second = crate.export(source, anchor, other)
    assert receipt['payload_sha256'] == second['payload_sha256']
    assert receipt['metadata_sha256'] != second['metadata_sha256']
    a = json.loads((output/'run.json').read_bytes())
    b = json.loads((other/'run.json').read_bytes())
    assert a['action_id'] != b['action_id']


@pytest.mark.parametrize('path', ['replay/packet.json', 'replay/result.json', 'run.json',
                                  'software/synthesis_replay.py', 'software/LICENSE', 'ro-crate-metadata.json'])
def test_changed_export_file_refuses(exported, path):
    _, root, receipt = exported
    file = root/path
    file.write_bytes(file.read_bytes()+b' ')
    with pytest.raises(replay.Refused): crate.verify(root, receipt['metadata_sha256'])


@pytest.mark.parametrize('change', [
    lambda nodes: nodes['./'].pop('license'),
    lambda nodes: nodes['./'].update(datePublished='1900-01-01'),
    lambda nodes: nodes['replay/result.json'].update(sha256='0'*64),
    lambda nodes: nodes['replay/result.json'].update(contentSize=float(nodes['replay/result.json']['contentSize'])),
    lambda nodes: nodes['software/synthesis_replay.py'].update(**{'@id': '../escape.py'}),
    lambda nodes: next(n for n in nodes.values() if n['@type'] == 'CreateAction').pop('instrument'),
])
def test_even_reanchored_graph_changes_refuse(exported, change):
    _, root, _ = exported
    path = root/'ro-crate-metadata.json'
    data = json.loads(path.read_bytes())
    change({n['@id']: n for n in data['@graph']})
    raw = replay.canonical(data)
    path.write_bytes(raw)
    with pytest.raises(replay.Refused): crate.verify(root, replay.digest(raw))


def test_extra_file_and_existing_output_refuse(exported):
    source, root, receipt = exported
    with pytest.raises(replay.Refused): crate.export(source, receipt['manifest_sha256'], root)
    (root/'unlisted.txt').write_text('Unexpected', encoding='utf-8')
    with pytest.raises(replay.Refused): crate.verify(root, receipt['metadata_sha256'])


def test_invalid_input_trust_anchor_prevents_output(tmp_path):
    source = ROOT/'examples/synthesis-replay-stepwise'
    with pytest.raises(replay.Refused): crate.export(source, '0'*64, tmp_path/'crate')
    assert not (tmp_path/'crate').exists()


def test_changed_input_is_not_exported(tmp_path):
    source = tmp_path/'input'
    shutil.copytree(ROOT/'examples/synthesis-replay-strokewalk', source)
    registry = next((source/'registries').iterdir())
    registry.write_bytes(registry.read_bytes()+b' ')
    with pytest.raises(replay.Refused): crate.export(source, EXAMPLES['strokewalk'], tmp_path/'crate')
    assert not (tmp_path/'crate').exists()


def test_linked_paths_refuse(exported, monkeypatch):
    _, root, receipt = exported
    original = replay.linked
    monkeypatch.setattr(replay, 'linked', lambda p: p.name == 'run.json' or original(p))
    with pytest.raises(replay.Refused): crate.verify(root, receipt['metadata_sha256'])


def test_cli_verify_uses_external_anchor(exported):
    _, root, receipt = exported
    run = subprocess.run([sys.executable, str(Path(crate.__file__)), 'verify', str(root),
                          '--expected-sha256', receipt['metadata_sha256']], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['status'] == 'EXPORT_MATCHED'


def test_export_failure_leaves_no_completion_metadata(tmp_path, monkeypatch):
    source = ROOT/'examples/synthesis-replay-stepwise'
    output = tmp_path/'incomplete'
    original = Path.open
    def fail(path, *args, **kwargs):
        if path == output/'run.json' and args == ('xb',): raise OSError('synthetic disk failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail)
    with pytest.raises(OSError): crate.export(source, EXAMPLES['stepwise'], output)
    assert not (output/'ro-crate-metadata.json').exists()


@pytest.mark.parametrize('change', [
    lambda run: run.update(start_time='yesterday'),
    lambda run: run.update(end_time='1900-01-01T00:00:00+00:00'),
    lambda run: run.update(action_id='urn:uuid:not-a-uuid'),
    lambda run: run.update(scientific_validity='VALIDATED'),
])
def test_malformed_execution_record_refuses(exported, change):
    _, root, receipt = exported
    path = root/'run.json'
    run = json.loads(path.read_bytes())
    change(run)
    path.write_bytes(replay.canonical(run))
    with pytest.raises(replay.Refused): crate.verify(root, receipt['metadata_sha256'])
