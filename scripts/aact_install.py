"""Verify locked AACT source, and optionally its runtime, before persistence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

if __package__:
    from . import component_source as source
    from .component_lock import load_lock, unique_pairs
    from .aact_canary import BACKENDS, CHECKS
else:
    import component_source as source
    from component_lock import load_lock, unique_pairs
    from aact_canary import BACKENDS, CHECKS

InstallRefused = source.InstallRefused
ADAPTER = 'aact-source-and-backends-v1'
CANARY = Path(__file__).with_name('aact_canary.py')


def inspect_source(target):
    required = [target/'pyproject.toml'] + [target/'src/aact_kit'/f'{m}.py'
        for m in ('__init__', 'tables', 'schema', 'location', 'aggregate')]
    for path in required:
        if not path.is_file() or source.linked(path) or not path.resolve().is_relative_to(target):
            raise InstallRefused('missing or linked AACT source file')
    try:
        project = tomllib.loads(required[0].read_text(encoding='utf-8'))['project']
        if project['name'] != 'aact-kit' or project['requires-python'] != '>=3.10' or project['dependencies'] != ['pandas>=2.0']:
            raise ValueError('unsupported AACT package contract')
        files = sorted((target/'src/aact_kit').rglob('*.py'))
        for path in files:
            if source.linked(path) or not path.resolve().is_relative_to(target):
                raise ValueError('linked AACT source')
            compile(path.read_bytes(), str(path), 'exec')
    except (ValueError, SyntaxError, KeyError, TypeError) as exc:
        raise InstallRefused('invalid AACT source or package metadata') from exc
    return [[p.relative_to(target).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()]
            for p in [required[0], *files]]


def run_canary(target):
    # -I prevents an ambient PYTHONPATH or user site package from satisfying the
    # import. The canary inserts only the verified source and checks __file__.
    try:
        return source.run([sys.executable, '-I', '-B', str(CANARY), '--source', str(target)], timeout=90)
    except InstallRefused as exc:
        raise InstallRefused('AACT runtime canary failed; check the selected Python environment and package API') from exc


def parse_canary(raw):
    try:
        result = json.loads(raw, object_pairs_hook=unique_pairs)
        if (not isinstance(result, dict) or set(result) != {'schema', 'runtime_verified', 'fixture_kind',
                'postgres_verified', 'scientific_accuracy_measured', 'backends', 'versions'}
                or result['schema'] != 'e156-aact-canary-v1' or result['runtime_verified'] is not True
                or result['fixture_kind'] != 'synthetic_install_check'
                or result['postgres_verified'] is not False or result['scientific_accuracy_measured'] is not False):
            raise ValueError('invalid canary semantics')
        rows = result['backends']
        if [row['backend'] for row in rows] != BACKENDS:
            raise ValueError('incomplete backend coverage')
        for row in rows:
            if set(row) != {'backend', 'checks', 'payload_sha256'} or row['checks'] != CHECKS or not isinstance(row['payload_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', row['payload_sha256']):
                raise ValueError('invalid backend result')
        if len({row['payload_sha256'] for row in rows}) != 1:
            raise ValueError('backend payload mismatch')
        if not isinstance(result['versions'], dict) or set(result['versions']) != {'python', 'pandas', 'numpy'} or not all(isinstance(v, str) and v for v in result['versions'].values()):
            raise ValueError('missing runtime versions')
        return result
    except (ValueError, TypeError, KeyError) as exc:
        raise InstallRefused('invalid AACT runtime canary report') from exc


def install_dependencies(target):
    source.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '-e', str(target)], timeout=300)


def install(target, component, *, ref=None, skip_clone=False, verify_runtime=False, with_deps=False):
    if with_deps and sys.prefix == sys.base_prefix:
        raise InstallRefused('--with-deps requires an active Python virtual environment')
    target, expected = source.prepare(target, component, adapter=ADAPTER, ref=ref, skip_clone=skip_clone)
    files = inspect_source(target)
    if with_deps:
        install_dependencies(target)
        verify_runtime = True
    smoke = None
    if verify_runtime:
        smoke = parse_canary(run_canary(target))
        if parse_canary(run_canary(target)) != smoke:
            raise InstallRefused('AACT runtime canary is not deterministic')
    source.finish(target, component, expected)
    return {'schema': 'e156-component-install-v1', 'component': 'aact-kit', 'adapter': ADAPTER,
            'status': 'verified' if verify_runtime else 'source_verified', 'runtime_verified': verify_runtime,
            'expected_commit': expected, 'observed_commit': expected, 'uses_locked_default': expected == component['commit'],
            'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_verifier_sha256': source.source_verifier_hash(),
            'canary_sha256': hashlib.sha256(CANARY.read_bytes()).hexdigest(),
            'component_spec_sha256': hashlib.sha256(json.dumps(component, sort_keys=True).encode()).hexdigest(),
            'source_files': files, 'smoke': smoke}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--ref')
    parser.add_argument('--skip-clone', action='store_true')
    parser.add_argument('--verify-runtime', action='store_true')
    parser.add_argument('--with-deps', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = install(args.target, load_lock()['aact-kit'], ref=args.ref, skip_clone=args.skip_clone,
                         verify_runtime=args.verify_runtime, with_deps=args.with_deps)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'refused', 'error': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
