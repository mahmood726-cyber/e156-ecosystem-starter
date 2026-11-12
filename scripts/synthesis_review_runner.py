"""Persist one offline Synthesis audit; every advance revalidates anchored inputs."""
from __future__ import annotations

import argparse
from contextlib import closing
import os
from pathlib import Path
import re
import sqlite3
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import synthesis_replay as replay

PROTOCOL_SCHEMA = 'e156-review-protocol-v1'
PROTOCOL_LIMIT = 8192
STATE_LIMIT = 1024 * 1024
EVENT_LIMIT = 65536
TABLE = 'CREATE TABLE events (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL)'
PROJECT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')


class Refused(ValueError):
    """The supplied state or dependencies cannot establish this workflow contract."""


def require(okay, message):
    if not okay: raise Refused(message)


def code_profile():
    return {'runner_sha256': replay.digest(replay.read(Path(__file__), replay.JSON_LIMIT).replace(b'\r\n', b'\n')),
            'replay': replay.code_profile()}


def _protocol(raw):
    require(len(raw) <= PROTOCOL_LIMIT, 'protocol exceeds size limit')
    try: data = replay.strict_json(raw)
    except replay.Refused as exc: raise Refused('invalid protocol JSON') from exc
    require(isinstance(data, dict) and set(data) == {'schema', 'project', 'stage', 'manifest_sha256'},
            'unsupported protocol fields')
    require(data['schema'] == PROTOCOL_SCHEMA and data['stage'] == 'source-replay-audit', 'unsupported protocol stage')
    require(isinstance(data['project'], str) and PROJECT.fullmatch(data['project']), 'invalid project identifier')
    require(isinstance(data['manifest_sha256'], str) and replay.SHA.fullmatch(data['manifest_sha256']),
            'protocol requires an external replay-manifest digest')
    return data


def _paths(state, bundle, protocol, *, initializing=False):
    try:
        state, bundle, protocol = (replay.guarded(p).resolve() for p in (state, bundle, protocol))
        if initializing: require(bundle.is_dir(), 'bundle directory is missing')
        require(state.parent.is_dir(), 'state parent directory is missing')
        for path in (state, *(Path(str(state) + s) for s in ('-journal', '-wal', '-shm'))):
            replay.guarded(path)
            require(not path.is_relative_to(bundle) and path != protocol, 'state overlaps evidence or protocol')
            if path.exists():
                require(path.is_file() and path.stat().st_nlink == 1 and path.stat().st_size <= STATE_LIMIT,
                        'state or sidecar is not a bounded private regular file')
        require(not protocol.is_relative_to(bundle), 'protocol must remain outside the sealed bundle')
    except replay.Refused as exc: raise Refused('linked paths are unsupported') from exc
    return state, bundle, protocol


def _anchor(expected):
    require(isinstance(expected, str) and replay.SHA.fullmatch(expected), 'external protocol SHA-256 required')


def _connect(state):
    # mode=rw: advance must never create a missing database.
    con = sqlite3.connect(state.as_uri() + '?mode=rw', uri=True, timeout=0, isolation_level=None)
    try:
        con.execute('PRAGMA trusted_schema=OFF')
        require(con.execute('PRAGMA trusted_schema').fetchone() == (0,), 'SQLite trusted-schema control unavailable')
        require(con.execute('PRAGMA journal_mode').fetchone() == ('delete',), 'unsupported SQLite journal mode')
        con.execute('PRAGMA synchronous=FULL')
        require(con.execute('PRAGMA synchronous').fetchone() == (2,), 'SQLite durability setting unavailable')
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, EVENT_LIMIT)
        return con
    except BaseException:
        con.close()
        raise


def _append(con, rows, body):
    event = {**body, 'previous_sha256': rows[-1][2] if rows else None}
    raw = replay.canonical(event)
    require(len(raw) <= EVENT_LIMIT, 'event exceeds size limit')
    row = (len(rows), raw.decode('utf-8'), replay.digest(raw))
    con.execute('INSERT INTO events(seq, body, sha256) VALUES (?, ?, ?)', row)
    rows.append(row)


def _completion(first, audit):
    protocol = _protocol(first['protocol_text'].encode('utf-8'))
    receipt = {'schema': 'e156-review-completion-v1', 'project': protocol['project'],
               'protocol_sha256': first['protocol_sha256'], 'manifest_sha256': audit['manifest_sha256'],
               'payload_sha256': audit['payload_sha256'],
               'code_profile_sha256': replay.digest(replay.canonical(first['profile'])),
               'review_state': 'HOLD', 'scientific_validity': 'NOT_ESTABLISHED', 'external_actions': 0}
    return {**receipt, 'receipt_id': replay.digest(replay.canonical(receipt))}


def _audit_shape(receipt, protocol):
    return (isinstance(receipt, dict)
            and set(receipt) == {'status', 'manifest_sha256', 'payload_sha256', 'scope', 'scientific_validity'}
            and receipt['status'] == 'REPLAY_MATCHED' and receipt['manifest_sha256'] == protocol['manifest_sha256']
            and isinstance(receipt['payload_sha256'], str) and replay.SHA.fullmatch(receipt['payload_sha256'])
            and receipt['scope'] in ('source_bound_participant_preflight', 'source_bound_preflight_with_study_links')
            and receipt['scientific_validity'] == 'NOT_ESTABLISHED')


def _bundle_snapshot(bundle):
    """Bound changes during replay as well as changes between process invocations."""
    files, directories = {}, []
    for folder, subdirs, names in os.walk(bundle, followlinks=False):
        for name in subdirs:
            path = replay.guarded(Path(folder) / name)
            directories.append(path.relative_to(bundle).as_posix())
        if len(directories) > 2 or len(files) + len(names) > 24:
            raise replay.Refused('unexpected bundle inventory')
        for name in names:
            path = Path(folder) / name
            files[path.relative_to(bundle).as_posix()] = replay.digest(replay.read(path, replay.capture.MAX_BYTES))
    return files, sorted(directories)


def _history(con):
    schema = con.execute('SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name').fetchall()
    require(schema == [('table', 'events', 'events', TABLE)], 'unsupported database schema')
    require(con.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'corrupt database')
    rows = con.execute('SELECT seq, body, sha256 FROM events ORDER BY seq LIMIT 5').fetchall()
    require(1 <= len(rows) <= 4, 'invalid history length')
    decoded = []
    for seq, (index, body, digest) in enumerate(rows):
        require(type(index) is int and index == seq and isinstance(body, str) and isinstance(digest, str),
                'invalid history sequence or field type')
        raw = body.encode('utf-8')
        require(len(raw) <= EVENT_LIMIT and replay.digest(raw) == digest, 'history checksum mismatch')
        try:
            event = replay.strict_json(raw)
            canonical = replay.canonical(event)
        except (replay.Refused, UnicodeError, ValueError, RecursionError) as exc:
            raise Refused('invalid history JSON') from exc
        require(isinstance(event, dict) and canonical == raw, 'noncanonical history')
        require(event.get('previous_sha256') == (rows[seq-1][2] if seq else None), 'broken history chain')
        kind = event.get('kind')
        if seq == 0:
            require(set(event) == {'kind', 'previous_sha256', 'protocol_sha256', 'protocol_text', 'profile'}
                    and kind == 'READY' and isinstance(event['protocol_text'], str), 'invalid initial event')
            raw_protocol = event['protocol_text'].encode('utf-8')
            protocol = _protocol(raw_protocol)
            require(replay.digest(raw_protocol) == event['protocol_sha256'], 'stored protocol differs from anchor')
            profile = event['profile']
            require(isinstance(profile, dict) and set(profile) == {'runner_sha256', 'replay'}
                    and isinstance(profile['runner_sha256'], str) and replay.SHA.fullmatch(profile['runner_sha256'])
                    and isinstance(profile['replay'], dict) and set(profile['replay']) == set(replay.CODE)
                    and all(isinstance(v, str) and replay.SHA.fullmatch(v) for v in profile['replay'].values()),
                    'invalid code profile')
        elif kind == 'AUDITED':
            require(seq == 1 and set(event) == {'kind', 'previous_sha256', 'receipt'}
                    and _audit_shape(event['receipt'], protocol), 'invalid audit event')
        elif kind == 'COMPLETED':
            require(seq == 2 and decoded[-1]['kind'] == 'AUDITED'
                    and set(event) == {'kind', 'previous_sha256', 'completion'}
                    and replay.canonical(event['completion']) == replay.canonical(_completion(decoded[0], decoded[1]['receipt'])),
                    'invalid completion event')
        elif kind == 'INVALIDATED':
            require(seq == len(rows)-1 and decoded[-1]['kind'] in ('READY', 'AUDITED', 'COMPLETED')
                    and set(event) == {'kind', 'previous_sha256', 'reason'}
                    and event['reason'] == 'DEPENDENCY_REVALIDATION_FAILED', 'invalid invalidation event')
        else: raise Refused('unknown event or transition')
        decoded.append(event)
    return rows, decoded


def _result(rows):
    first, last = (replay.strict_json(rows[i][1].encode('utf-8')) for i in (0, -1))
    return {'status': last['kind'], 'protocol_sha256': first['protocol_sha256'],
            'state_head_sha256': rows[-1][2], 'release_eligible': False,
            'completion': last.get('completion') if last['kind'] == 'COMPLETED' else None}


def initialize(*, state: Path, bundle: Path, protocol: Path, expected_sha256: str):
    _anchor(expected_sha256)
    state, bundle, protocol = _paths(state, bundle, protocol, initializing=True)
    require(not state.exists(), 'existing state cannot be initialized again')
    require(not any(Path(str(state)+s).exists() for s in ('-journal', '-wal', '-shm')), 'orphaned SQLite sidecar')
    try: raw = replay.read(protocol, PROTOCOL_LIMIT)
    except replay.Refused as exc: raise Refused('protocol is missing or oversized') from exc
    require(replay.digest(raw) == expected_sha256, 'protocol differs from external anchor')
    declared = _protocol(raw)
    require(replay.digest(replay.read(bundle/'manifest.json', replay.JSON_LIMIT)) == declared['manifest_sha256'],
            'bundle manifest differs from reviewed protocol')
    first = {'kind': 'READY', 'protocol_sha256': expected_sha256, 'protocol_text': raw.decode('utf-8'),
             'profile': code_profile()}
    # Interrupted initialization leaves an incomplete file for inspection.
    fd = os.open(state, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(_connect(state)) as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            con.execute(TABLE)
            rows = []
            _append(con, rows, first)
            con.commit()
        except BaseException:
            con.rollback()
            raise
    return _result(rows)


def advance(*, state: Path, bundle: Path, protocol: Path, expected_sha256: str):
    _anchor(expected_sha256)
    state, bundle, protocol = _paths(state, bundle, protocol)
    require(state.is_file(), 'state is missing; explicit initialization required')
    with closing(_connect(state)) as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            rows, history = _history(con)
            first, last = history[0], history[-1]
            require(expected_sha256 == first['protocol_sha256'], 'external anchor belongs to a different run')
            if last['kind'] == 'INVALIDATED':
                con.rollback()
                return _result(rows)
            declared = _protocol(first['protocol_text'].encode('utf-8'))
            try:
                raw = replay.read(protocol, PROTOCOL_LIMIT)
                if replay.digest(raw) != expected_sha256 or code_profile() != first['profile']:
                    raise replay.Refused('protocol or code changed')
                before = _bundle_snapshot(bundle)
                current = replay.verify(bundle, declared['manifest_sha256'])
                if not _audit_shape(current, declared): raise replay.Refused('unsupported replay result')
                if len(history) > 1 and current != history[1]['receipt']:
                    raise replay.Refused('audit result changed')
                if (replay.read(protocol, PROTOCOL_LIMIT) != raw or code_profile() != first['profile']
                        or _bundle_snapshot(bundle) != before):
                    raise replay.Refused('dependency changed during audit')
            except replay.Refused:
                _append(con, rows, {'kind': 'INVALIDATED', 'reason': 'DEPENDENCY_REVALIDATION_FAILED'})
            else:
                if last['kind'] == 'READY': _append(con, rows, {'kind': 'AUDITED', 'receipt': current})
                elif last['kind'] == 'AUDITED':
                    _append(con, rows, {'kind': 'COMPLETED', 'completion': _completion(first, current)})
                # COMPLETED is revalidated above; retry adds no new event.
            con.commit()
        except BaseException:
            con.rollback()
            raise
    return _result(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('init', 'advance'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = vars(parser.parse_args(argv))
    operation = args.pop('operation')
    try:
        result = (initialize if operation == 'init' else advance)(**args)
        code = 2 if result['status'] == 'INVALIDATED' else 0
    except (Refused, replay.Refused) as exc:
        result = {'status': 'REFUSED', 'reason': str(exc), 'completion': None, 'release_eligible': False}
        code = 2
    except (OSError, sqlite3.Error):
        result = {'status': 'ERROR', 'reason': 'storage operation failed; no current receipt established',
                  'completion': None, 'release_eligible': False}
        code = 3
    print(replay.canonical(result).decode('utf-8'), end='')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
