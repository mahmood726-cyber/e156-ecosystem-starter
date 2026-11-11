"""Verify and atomically select a RapidMeta/AACT pair in an explicit managed root.

No shell/registry changes, pip installation, automatic deletion or project release
verdict. Candidate directories and previous generations are retained on failure.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

if __package__:
    from . import component_source as source, rapidmeta_install as rapidmeta, aact_install as aact
    from .component_lock import DEFAULT_LOCK, SCHEMA as LOCK_SCHEMA, load_lock, unique_pairs
else:
    import component_source as source
    import rapidmeta_install as rapidmeta
    import aact_install as aact
    from component_lock import DEFAULT_LOCK, SCHEMA as LOCK_SCHEMA, load_lock, unique_pairs

Refused = source.InstallRefused
SCOPE = ['rapidmeta', 'aact-kit']
DIGEST = re.compile(r'[0-9a-f]{64}')
MARKER = {'schema': 'e156-research-root-v1'}
VERIFIERS = ('research_environment.py', 'component_lock.py', 'component_source.py',
             'rapidmeta_install.py', 'aact_install.py', 'aact_canary.py')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def guarded(path):
    if os.path.lexists(path) and source.linked(path):
        raise Refused(f'linked managed path refused: {path.name}')
    return path


def parse(raw, name):
    def invalid_constant(_):
        raise ValueError('non-standard JSON constant')
    try:
        return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise Refused(f'invalid managed JSON: {name}') from exc


def read_file(path):
    guarded(path)
    if not path.is_file():
        raise Refused(f'missing managed file: {path.name}')
    return path.read_bytes()


def write_new(path, raw):
    guarded(path)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def managed_root(root, *, create=False):
    root = guarded(root.expanduser().absolute()).resolve()
    if not root.exists():
        if not create:
            raise Refused('managed root does not exist')
        root.mkdir(parents=True)
    if not root.is_dir():
        raise Refused('managed root must be a directory')
    marker = guarded(root/'.e156-research-root.json')
    if not marker.exists():
        if not create or any(root.iterdir()):
            raise Refused('refusing to adopt a nonempty unmanaged root')
        write_new(marker, canonical(MARKER))
    if parse(read_file(marker), marker.name) != MARKER:
        raise Refused('invalid managed root marker')
    releases = guarded(root/'releases')
    if create:
        releases.mkdir(exist_ok=True)
    if not releases.is_dir():
        raise Refused('managed releases directory missing')
    guarded(root/'active.json')
    guarded(root/'.operation.lock')
    return root


@contextmanager
def operation(root):
    path = root/'.operation.lock'
    token = canonical({'pid': os.getpid(), 'owner': uuid.uuid4().hex})
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Refused('operation lock exists; another or interrupted operation needs review') from exc
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(token)
            stream.flush()
        yield
    finally:
        # Never reclaim a different writer's lock or delete a candidate tree.
        if read_file(path) == token:
            path.unlink()


def runtime_profile():
    probe = ('import json,sys,pandas,numpy; print(json.dumps(dict('
             'python=sys.version.split()[0],platform=sys.platform,'
             'pandas=pandas.__version__,numpy=numpy.__version__)))')
    try:
        return parse(source.run([sys.executable, '-I', '-B', '-c', probe]), 'runtime profile')
    except Refused as exc:
        raise Refused('paired runtime requires pandas and NumPy in the selected Python environment') from exc


def specification(components):
    return {'scope': SCOPE, 'components': components, 'runtime': runtime_profile(),
            'verifiers': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in VERIFIERS}}


def pointer(root):
    path = guarded(root/'active.json')
    if not path.exists():
        return None, None
    raw = read_file(path)
    value = parse(raw, path.name)
    if (not isinstance(value, dict) or set(value) != {'schema', 'release', 'record_sha256'}
            or value['schema'] != 'e156-research-active-v1'
            or not isinstance(value['release'], str) or not DIGEST.fullmatch(value['release'])
            or not isinstance(value['record_sha256'], str) or not DIGEST.fullmatch(value['record_sha256'])):
        raise Refused('invalid active pointer')
    return raw, value


def check_receipts(receipts, components):
    if not isinstance(receipts, dict) or set(receipts) != set(SCOPE):
        raise Refused('incomplete component receipts')
    for name in SCOPE:
        r = receipts[name]
        if (not isinstance(r, dict) or r.get('schema') != 'e156-component-install-v1'
                or r.get('component') != name or r.get('status') != 'verified'
                or r.get('adapter') != components[name]['verification']
                or r.get('expected_commit') != components[name]['commit']
                or r.get('observed_commit') != components[name]['commit']
                or (name == 'aact-kit' and r.get('runtime_verified') is not True)):
            raise Refused(f'unverified component receipt: {name}')


def generation(root, release, *, expected_hash=None, require_profile=True):
    if not isinstance(release, str) or not DIGEST.fullmatch(release):
        raise Refused('invalid release identifier')
    directory = guarded(root/'releases'/release)
    raw = read_file(directory/'release.json')
    if expected_hash is not None and digest(raw) != expected_hash:
        raise Refused('active release record hash mismatch')
    record = parse(raw, 'release.json')
    if (not isinstance(record, dict) or set(record) != {'schema', 'release', 'specification', 'receipts'}
            or record['schema'] != 'e156-research-release-v1' or record['release'] != release):
        raise Refused('invalid release record')
    spec = record['specification']
    if (not isinstance(spec, dict) or set(spec) != {'scope', 'components', 'runtime', 'verifiers'}
            or spec['scope'] != SCOPE or digest(canonical(spec)) != release):
        raise Refused('release specification hash mismatch')
    lock = guarded(directory/'component-lock.json')
    try:
        components = load_lock(lock)
    except (OSError, ValueError, TypeError) as exc:
        raise Refused('invalid saved component lock') from exc
    if components != spec['components']:
        raise Refused('saved component lock differs from release specification')
    check_receipts(record['receipts'], components)
    if require_profile and specification(components) != spec:
        raise Refused('runtime or verifier profile changed; install a new generation')
    return directory, record, raw


def run_components(directory, components):
    results = {}
    for name, adapter in [('rapidmeta', rapidmeta), ('aact-kit', aact)]:
        target = guarded(directory/name)
        extra = {'verify_runtime': True} if name == 'aact-kit' else {}
        results[name] = adapter.install(target, components[name], skip_clone=target.exists(), **extra)
    check_receipts(results, components)
    # A later adapter must not leave an earlier source changed after its canary.
    for name in SCOPE:
        source.finish(directory/name, components[name], components[name]['commit'])
    return results


def recheck(directory, record):
    results = run_components(directory, record['specification']['components'])
    if results != record['receipts']:
        raise Refused('current component results differ from the saved verification record')
    if specification(record['specification']['components']) != record['specification']:
        raise Refused('runtime or verifier profile changed during verification')


def result(directory):
    return {'status': 'verified', 'scope': SCOPE, 'release': directory.name,
            'paths': {name: str(directory/name) for name in SCOPE}}


def publish(root, release, raw_record, previous):
    current = read_file(root/'active.json') if (root/'active.json').exists() else None
    if current != previous:
        raise Refused('active pointer changed during verification')
    raw = canonical({'schema': 'e156-research-active-v1', 'release': release, 'record_sha256': digest(raw_record)})
    temp = root/f'.active-{uuid.uuid4().hex}.tmp'
    try:
        write_new(temp, raw)
        os.replace(temp, guarded(root/'active.json'))
    finally:
        if temp.exists():
            guarded(temp).unlink()


def install(root: Path, lock: Path = DEFAULT_LOCK):
    components = load_lock(lock)
    spec = specification(components)  # missing runtime refuses before creating a root
    release = digest(canonical(spec))
    root = managed_root(root, create=True)
    with operation(root):
        previous, active = pointer(root)
        if active:
            generation(root, active['release'], expected_hash=active['record_sha256'], require_profile=False)
        directory = guarded(root/'releases'/release)
        directory.mkdir(exist_ok=True)
        if (directory/'release.json').exists():
            directory, record, raw_record = generation(root, release)
            recheck(directory, record)
        else:
            saved_lock = guarded(directory/'component-lock.json')
            lock_bytes = canonical({'schema': LOCK_SCHEMA, 'components': components})
            if saved_lock.exists():
                if read_file(saved_lock) != lock_bytes:
                    raise Refused('candidate lock changed; review incomplete generation')
            else:
                write_new(saved_lock, lock_bytes)
            receipts = run_components(directory, components)
            # A long verification must not publish against a changed runtime/code profile.
            if specification(components) != spec:
                raise Refused('runtime or verifier profile changed during installation')
            raw_record = canonical({'schema': 'e156-research-release-v1', 'release': release,
                                    'specification': spec, 'receipts': receipts})
            write_new(directory/'release.json', raw_record)
        publish(root, release, raw_record, previous)
        return result(directory)


def verify(root: Path):
    root = managed_root(root)
    with operation(root):
        previous, active = pointer(root)
        if active is None:
            raise Refused('no active research environment')
        directory, record, _ = generation(root, active['release'], expected_hash=active['record_sha256'])
        recheck(directory, record)
        if read_file(root/'active.json') != previous:
            raise Refused('active pointer changed during verification')
        return result(directory)


def rollback(root: Path, release: str):
    root = managed_root(root)
    with operation(root):
        previous, active = pointer(root)
        if active is None:
            raise Refused('no active environment to roll back')
        generation(root, active['release'], expected_hash=active['record_sha256'], require_profile=False)
        directory, record, raw = generation(root, release)
        recheck(directory, record)
        publish(root, release, raw, previous)
        return result(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('install', 'verify', 'rollback'):
        child = sub.add_parser(command)
        child.add_argument('--root', type=Path, required=True)
        if command == 'install': child.add_argument('--lock', type=Path, default=DEFAULT_LOCK)
        if command == 'rollback': child.add_argument('--release', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'install': report = install(args.root, args.lock)
        elif args.command == 'rollback': report = rollback(args.root, args.release)
        else: report = verify(args.root)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'refused', 'error': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
