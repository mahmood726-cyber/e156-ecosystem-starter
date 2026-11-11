#!/usr/bin/env python3
"""Export a verified Synthesis replay as Process Run Crate 0.5 / RO-Crate 1.1.

Local export/integrity verification is offline. Profile conformance is checked
separately by the pinned upstream validator. Neither establishes scientific truth.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import sys
from uuid import UUID, uuid4

if __package__:
    from scripts import synthesis_replay as replay
else:
    import synthesis_replay as replay

SCHEMA = 'e156-synthesis-rocrate-v1'
PROFILE = 'https://w3id.org/ro/wfrun/process/0.5'
BASE = 'https://w3id.org/ro/crate/1.1'
METADATA = 'ro-crate-metadata.json'
REPO_URL = 'https://github.com/mahmood726-cyber/e156-ecosystem-starter'
TERMS = 'https://clinicaltrials.gov/about-site/terms-conditions'
LIMITS = ('This records a new replay during export. REPLAY_MATCHED establishes payload reconstruction only. '
          'Scientific validity is NOT_ESTABLISHED; source authenticity, human adjudication, cohort overlap '
          'and outcome equivalence are not established by this execution. Existing HOLD decisions are preserved.')


def ref(identifier):
    return {'@id': identifier}


def software():
    directory = Path(__file__).parent
    files = {'software/'+name: replay.read(directory/name, replay.JSON_LIMIT).replace(b'\r\n', b'\n')
             for name in (*replay.CODE, 'synthesis_rocrate.py')}
    files['software/LICENSE'] = replay.read(directory.parent/'LICENSE', replay.JSON_LIMIT).replace(b'\r\n', b'\n')
    return files


def bundle_files(root, anchor):
    """Recompute first; then bind every subsequently read byte to that manifest."""
    receipt = replay.verify(root, anchor)
    raw = replay.read(root/'manifest.json', replay.JSON_LIMIT)
    if replay.digest(raw) != anchor: raise replay.Refused('manifest changed during export')
    manifest = replay.strict_json(raw)
    files = {'replay/manifest.json': raw}
    for path, expected in manifest['artifacts'].items():
        limit = replay.capture.MAX_BYTES if path == 'result.json' or path.startswith('sources/') else replay.JSON_LIMIT
        data = replay.read(root/path, limit)
        if replay.digest(data) != expected['sha256'] or len(data) != expected['size']:
            raise replay.Refused('bundle changed during export')
        files['replay/'+path] = data
    return receipt, manifest, files


def check_run(run):
    keys = {'schema', 'action_id', 'start_time', 'end_time', 'python_version', 'platform',
            'manifest_sha256', 'payload_sha256', 'exporter_sha256', 'scientific_validity'}
    if not isinstance(run, dict) or set(run) != keys or run['schema'] != SCHEMA:
        raise replay.Refused('unsupported export execution record')
    if run['scientific_validity'] != 'NOT_ESTABLISHED': raise replay.Refused('export cannot establish scientific validity')
    for key in ('manifest_sha256', 'payload_sha256', 'exporter_sha256'):
        if not isinstance(run[key], str) or not replay.SHA.fullmatch(run[key]):
            raise replay.Refused('invalid execution digest')
    try:
        if not run['action_id'].startswith('urn:uuid:'): raise ValueError('UUID URI required')
        identifier = UUID(run['action_id'][9:])
        if identifier.version != 4 or 'urn:uuid:'+str(identifier) != run['action_id']: raise ValueError('UUID4 required')
        times = [datetime.fromisoformat(run[key]) for key in ('start_time', 'end_time')]
        if any(t.tzinfo is None or t.utcoffset().total_seconds() != 0 for t in times) or times[0] > times[1]:
            raise ValueError('ordered UTC times required')
    except (TypeError, ValueError, AttributeError) as exc:
        raise replay.Refused('invalid execution identity/time') from exc
    if (not isinstance(run['python_version'], str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', run['python_version'])
            or not isinstance(run['platform'], str) or run['platform'] not in ('Windows', 'Linux', 'Darwin')):
        raise replay.Refused('unsupported runtime observation')


def metadata(manifest, files, run):
    """Map verified byte inventory to a closed, flattened JSON-LD graph."""
    source = manifest['sources'][manifest['main_source']]
    action_id = run['action_id']
    nodes = [
        {'@id': METADATA, '@type': 'CreativeWork', 'about': ref('./'), 'conformsTo': ref(BASE)},
        {'@id': './', '@type': 'Dataset', 'name': 'Synthesis replay '+source['version'],
         'description': LIMITS, 'datePublished': run['end_time'], 'license': ref('#mixed-rights'),
         'conformsTo': ref(PROFILE), 'hasPart': [ref(p) for p in sorted(files)], 'mentions': ref(action_id)},
        {'@id': PROFILE, '@type': 'CreativeWork', 'name': 'Process Run Crate', 'version': '0.5'},
        {'@id': BASE, '@type': 'CreativeWork', 'name': 'RO-Crate', 'version': '1.1'},
        {'@id': '#mixed-rights', '@type': 'CreativeWork', 'name': 'Per-file rights apply',
         'description': 'Article licences are preserved per snapshot. Software is MIT licensed. Registry '
                        'metadata remains subject to service terms. No new rights are asserted for input packets '
                        'or prompts, and no blanket licence replaces the source-specific terms.'},
        {'@id': action_id, '@type': 'CreateAction', 'name': 'Reconstruct the archived Synthesis payload',
         'description': LIMITS, 'startTime': run['start_time'], 'endTime': run['end_time'],
         'instrument': ref('software/synthesis_replay.py'),
         'object': [ref(p) for p in sorted(files) if p.startswith('replay/') and p != 'replay/result.json'],
         'result': ref('replay/result.json'), 'actionStatus': ref('http://schema.org/CompletedActionStatus')},
    ]
    licences = {}
    for path, raw in sorted(files.items()):
        suffix = Path(path).suffix
        formats = {'.json': 'application/json', '.xml': 'application/xml', '.md': 'text/markdown', '.py': 'text/x-python'}
        entity = {'@id': path, '@type': 'File', 'name': path, 'contentSize': len(raw),
                  'encodingFormat': formats.get(suffix, 'text/plain'), 'sha256': replay.digest(raw),
                  'description': 'Exact archived replay artifact.' if path.startswith('replay/') else 'Export execution or implementation artifact.'}
        if path.startswith('software/'):
            entity['license'] = ref('software/LICENSE') if path != 'software/LICENSE' else ref('#mixed-rights')
        if path in ('software/synthesis_replay.py', 'software/synthesis_rocrate.py'):
            entity.update({'@type': ['File', 'SoftwareApplication'],
                           'name': 'E156 Synthesis '+('replay' if 'replay.py' in path else 'RO-Crate exporter'),
                           'url': REPO_URL, 'softwareVersion': 'sha256:'+entity['sha256'],
                           'runtimePlatform': 'Python '+run['python_version']+' on '+run['platform']})
        if path == 'software/LICENSE':
            entity.update(name='MIT License', description='Licence for the included harness software.')
        record = manifest['sources'].get(path.removeprefix('replay/')) if path.startswith('replay/sources/') else None
        if record:
            licence = record['license']
            licences[licence] = {'@id': licence, '@type': 'CreativeWork', 'name': 'Article licence: '+licence,
                                 'description': 'Licence declared in the archived article. Original attribution is retained in its XML.'}
            entity.update(license=ref(licence), url=record['source_url'], version=record['version'],
                          identifier=[record['pmcid'], 'doi:'+record['doi']]+(['pmid:'+record['pmid']] if 'pmid' in record else []),
                          description='Original article XML with author/publication metadata; archive bytes are not network-authenticated.')
        if path.startswith('replay/registries/'):
            licences[TERMS] = {'@id': TERMS, '@type': 'CreativeWork', 'name': 'ClinicalTrials.gov terms',
                               'description': 'Service terms for archived registry metadata; no article licence is applied to these data.'}
            entity.update(license=ref(TERMS), description='Archived registry JSON. Identity linkage does not establish cohort or outcome equivalence.')
        nodes.append(entity)
    nodes.extend(licences.values())
    return {'@context': [BASE+'/context', 'https://w3id.org/ro/terms/workflow-run/context',
                         {'sha256': 'http://schema.org/sha256'}],
            '@graph': sorted(nodes, key=lambda n: n['@id'])}


def receipt(raw, run, status):
    return {'status': status, 'metadata_sha256': replay.digest(raw), 'manifest_sha256': run['manifest_sha256'],
            'payload_sha256': run['payload_sha256'], 'profile': PROFILE,
            'profile_validation': 'NOT_RUN_BY_LOCAL_INTEGRITY_CHECK', 'scientific_validity': 'NOT_ESTABLISHED'}


def export(bundle: Path, expected_sha256: str, output: Path):
    bundle, output = replay.guarded(bundle), replay.guarded(output)
    if output.exists() or bundle in output.parents:
        raise replay.Refused('output must be new and outside the input bundle')
    start = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    replay_receipt, manifest, files = bundle_files(bundle, expected_sha256)
    code = software()
    if {n: replay.digest(code['software/'+n]) for n in replay.CODE} != manifest['verifiers']:
        raise replay.Refused('software changed since replay')
    files.update(code)
    output.mkdir(parents=False, exist_ok=False)
    for path, raw in files.items():
        target = output/path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write(raw)
    # Validate the copied bytes with trusted local code; never import crate code.
    replay.verify(output/'replay', expected_sha256)
    run = {'schema': SCHEMA, 'action_id': 'urn:uuid:'+str(uuid4()), 'start_time': start,
           'end_time': datetime.now(timezone.utc).isoformat(timespec='milliseconds'), 'python_version': platform.python_version(),
           'platform': platform.system(), 'manifest_sha256': expected_sha256,
           'payload_sha256': replay_receipt['payload_sha256'],
           'exporter_sha256': replay.digest(code['software/synthesis_rocrate.py']), 'scientific_validity': 'NOT_ESTABLISHED'}
    check_run(run)
    if software() != code: raise replay.Refused('software changed during export')
    files['run.json'] = replay.canonical(run)
    raw_metadata = replay.canonical(metadata(manifest, files, run))
    # Completion metadata is last; failures leave an inspectable incomplete crate.
    for path, raw in (('run.json', files['run.json']), (METADATA, raw_metadata)):
        with (output/path).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return receipt(raw_metadata, run, 'EXPORTED')


def verify(root: Path, expected_sha256: str):
    if not isinstance(expected_sha256, str) or not replay.SHA.fullmatch(expected_sha256):
        raise replay.Refused('external metadata SHA-256 required')
    root = replay.guarded(root)
    raw = replay.read(root/METADATA, replay.JSON_LIMIT)
    if replay.digest(raw) != expected_sha256: raise replay.Refused('metadata differs from trusted digest')
    graph = replay.strict_json(raw)
    run_raw = replay.read(root/'run.json', replay.JSON_LIMIT)
    run = replay.strict_json(run_raw)
    check_run(run)
    result, manifest, files = bundle_files(root/'replay', run['manifest_sha256'])
    if run['payload_sha256'] != result['payload_sha256']: raise replay.Refused('execution payload differs from replay')
    code = software()
    if run['exporter_sha256'] != replay.digest(code['software/synthesis_rocrate.py']):
        raise replay.Refused('exporter profile changed; use the recorded implementation')
    for path, expected in code.items():
        data = replay.read(root/path, replay.JSON_LIMIT)
        if data != expected: raise replay.Refused('packaged software differs from trusted implementation')
        files[path] = data
    files['run.json'] = run_raw
    expected_dirs = {p.as_posix() for name in files for p in Path(name).parents if str(p) != '.'}
    observed = set()
    for folder, directories, names in os.walk(root, followlinks=False):
        for name in [*directories, *names]: replay.guarded(Path(folder)/name)
        if any((Path(folder)/d).relative_to(root).as_posix() not in expected_dirs for d in directories):
            raise replay.Refused('unexpected export directory')
        observed.update((Path(folder)/n).relative_to(root).as_posix() for n in names)
    if observed != set(files) | {METADATA}: raise replay.Refused('unexpected export file inventory')
    if replay.canonical(graph) != replay.canonical(metadata(manifest, files, run)):
        raise replay.Refused('export graph differs from verified bytes and execution record')
    if software() != code: raise replay.Refused('software changed during verification')
    return receipt(raw, run, 'EXPORT_MATCHED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('export')
    create.add_argument('bundle', type=Path)
    create.add_argument('--expected-sha256', required=True)
    create.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('root', type=Path)
    check.add_argument('--expected-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        result = (export(args.bundle, args.expected_sha256, args.output) if args.command == 'export'
                  else verify(args.root, args.expected_sha256))
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'REFUSED', 'reason': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
