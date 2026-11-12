"""Persist authorization of a frozen decision dossier; completion always retains HOLD."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import synthesis_reviewer_auth as auth

adj, replay, audit = auth.adj, auth.replay, auth.adj.audit
Refused = adj.Refused
require = adj.require
SCHEMA = 'e156-decision-protocol-v1'
HASH_FIELDS = ('dossier_sha256','trust_sha256','roster_sha256','signatures_sha256')
INPUTS = ('dossier','trust','roster','signatures')


def code_profile():
    return {'decision_runner_sha256':replay.digest(replay.read(Path(__file__),replay.JSON_LIMIT).replace(b'\r\n',b'\n')),
            'authorization':auth.code_profile()}


def _profile_sha():
    return replay.digest(replay.canonical(code_profile()))


def _protocol(raw):
    require(len(raw) <= audit.PROTOCOL_LIMIT, 'protocol is oversized')
    d = replay.strict_json(raw)
    adj.fields(d, ('schema','project','stage',*HASH_FIELDS), 'decision protocol')
    require(d['schema'] == SCHEMA and d['stage'] == 'authenticated-decisions', 'unsupported decision stage')
    adj.identifier(d['project'])
    for field in HASH_FIELDS: adj.anchor(d[field])
    return d


def _paths(state, protocol, inputs, initializing=False):
    roots, paths = auth._paths(inputs['bundles'], protocol, *(inputs[n] for n in INPUTS))
    protocol = paths[0]; inputs = {**dict(zip(INPUTS,paths[1:])), 'bundles':roots}
    for root in roots.values():
        state, _, _ = audit._paths(state, root, protocol, initializing=initializing)
    require(all(p != source for p in (state,*(Path(str(state)+s) for s in ('-journal','-wal','-shm')))
                for source in paths), 'state or sidecar overlaps protected input')
    return state, protocol, inputs


def _authorized(inputs, declared):
    receipt = auth.verify(**inputs, project=declared['project'], **{f:declared[f] for f in HASH_FIELDS})
    require(receipt['status'] == 'SIGNATURES_REVALIDATED' and receipt['decision_ready'] is True
            and receipt['release_eligible'] is False and receipt['pooling_readiness'] == 'HOLD'
            and receipt['scientific_validity'] == 'NOT_ESTABLISHED', 'complete authenticated decisions required')
    summary = {k:receipt[k] for k in ('status','project','receipt_id',*HASH_FIELDS)}
    _summary(summary, declared)
    return summary


def _summary(value, declared):
    adj.fields(value, ('status','project','receipt_id',*HASH_FIELDS), 'authorization summary')
    require(value['status'] == 'SIGNATURES_REVALIDATED' and value['project'] == declared['project'],
            'invalid authorization summary')
    adj.anchor(value['receipt_id'])
    require(all(value[k] == declared[k] for k in HASH_FIELDS), 'authorization belongs to another protocol')


def _completion(first, authorized):
    result = {'schema':'e156-decision-completion-v1','project':authorized['project'],
              'protocol_sha256':first['protocol_sha256'],'profile_sha256':first['profile_sha256'],
              'authorization_receipt_id':authorized['receipt_id'],
              'review_state':'HOLD','human_identity':'NOT_ESTABLISHED','independence':'NOT_ESTABLISHED',
              'scientific_validity':'NOT_ESTABLISHED','external_actions':0}
    return {**result,'receipt_id':replay.digest(replay.canonical(result))}


def _history(con):
    require(con.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name').fetchall()
            == [('table','events','events',audit.TABLE)], 'unsupported database schema')
    require(con.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'corrupt database')
    rows = con.execute('SELECT seq,body,sha256 FROM events ORDER BY seq LIMIT 5').fetchall()
    require(1 <= len(rows) <= 4, 'invalid history length'); history = []
    for seq,(index,body,digest) in enumerate(rows):
        require(type(index) is int and index == seq and isinstance(body,str) and isinstance(digest,str), 'invalid event row')
        try:
            raw = body.encode('utf-8'); event = replay.strict_json(raw)
            require(len(raw) <= audit.EVENT_LIMIT and replay.digest(raw) == digest
                    and replay.canonical(event) == raw and isinstance(event,dict), 'invalid canonical event')
        except (UnicodeError, replay.Refused) as exc: raise Refused('invalid event JSON') from exc
        require(event.get('previous_sha256') == (rows[seq-1][2] if seq else None), 'broken event chain')
        kind = event.get('kind')
        if seq == 0:
            adj.fields(event, ('kind','previous_sha256','protocol_sha256','protocol_text','profile_sha256'), 'initial event')
            require(kind == 'READY' and isinstance(event['protocol_text'],str), 'invalid initial event')
            protocol_raw = event['protocol_text'].encode('utf-8'); declared = _protocol(protocol_raw)
            require(replay.digest(protocol_raw) == event['protocol_sha256'], 'protocol differs from anchor')
            adj.anchor(event['profile_sha256'])
        elif kind == 'AUTHENTICATED':
            adj.fields(event, ('kind','previous_sha256','receipt'), 'authenticated event')
            require(seq == 1, 'invalid authorization transition'); _summary(event['receipt'],declared)
        elif kind == 'COMPLETED':
            adj.fields(event, ('kind','previous_sha256','completion'), 'completed event')
            require(seq == 2 and history[-1]['kind'] == 'AUTHENTICATED'
                    and replay.canonical(event['completion']) == replay.canonical(_completion(history[0],history[1]['receipt'])),
                    'invalid completion transition or content')
        elif kind == 'INVALIDATED':
            adj.fields(event, ('kind','previous_sha256','reason'), 'invalidated event')
            require(seq == len(rows)-1 and history[-1]['kind'] in ('READY','AUTHENTICATED','COMPLETED')
                    and event['reason'] == 'DEPENDENCY_REVALIDATION_FAILED', 'invalid invalidation transition')
        else: raise Refused('unsupported event transition')
        history.append(event)
    return rows, history


def initialize(*, state, protocol, expected_sha256, **inputs):
    adj.anchor(expected_sha256)
    try:
        state, protocol, inputs = _paths(state,protocol,inputs,True)
        require(not state.exists(), 'existing state cannot be initialized')
        require(not any(Path(str(state)+s).exists() for s in ('-journal','-wal','-shm')), 'orphaned SQLite sidecar')
        raw = auth._read(protocol,expected_sha256,audit.PROTOCOL_LIMIT); declared = _protocol(raw)
        profile = _profile_sha(); _authorized(inputs,declared)
        require(replay.read(protocol,audit.PROTOCOL_LIMIT) == raw and _profile_sha() == profile,
                'protocol or code changed during initialization')
        first = {'kind':'READY','protocol_sha256':expected_sha256,'protocol_text':raw.decode('utf-8'),
                 'profile_sha256':profile}
        fd = os.open(state,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
        with closing(audit._connect(state)) as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                con.execute(audit.TABLE); rows=[]; audit._append(con,rows,first); con.commit()
            except BaseException: con.rollback(); raise
        return audit._result(rows)
    except (replay.Refused,audit.Refused) as exc: raise Refused(str(exc)) from exc


def advance(*, state, protocol, expected_sha256, **inputs):
    adj.anchor(expected_sha256)
    try:
        state, protocol, inputs = _paths(state,protocol,inputs)
        require(state.is_file(), 'state is missing; explicit initialization required')
        with closing(audit._connect(state)) as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                rows, history = _history(con); first,last = history[0],history[-1]
                require(expected_sha256 == first['protocol_sha256'], 'external anchor belongs to another run')
                if last['kind'] == 'INVALIDATED': con.rollback(); return audit._result(rows)
                declared = _protocol(first['protocol_text'].encode('utf-8'))
                try:
                    raw = auth._read(protocol,expected_sha256,audit.PROTOCOL_LIMIT)
                    require(_profile_sha() == first['profile_sha256'], 'implementing code changed')
                    current = _authorized(inputs,declared)
                    require(len(history) == 1 or replay.canonical(current) == replay.canonical(history[1]['receipt']),
                            'current authorization differs from stored result')
                    require(replay.read(protocol,audit.PROTOCOL_LIMIT) == raw and _profile_sha() == first['profile_sha256'],
                            'protocol or code changed during authorization')
                except (Refused,replay.Refused):
                    audit._append(con,rows,{'kind':'INVALIDATED','reason':'DEPENDENCY_REVALIDATION_FAILED'})
                else:
                    if last['kind'] == 'READY': audit._append(con,rows,{'kind':'AUTHENTICATED','receipt':current})
                    elif last['kind'] == 'AUTHENTICATED':
                        audit._append(con,rows,{'kind':'COMPLETED','completion':_completion(first,current)})
                con.commit()
            except BaseException: con.rollback(); raise
        return audit._result(rows)
    except (replay.Refused,audit.Refused) as exc: raise Refused(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('init','advance'))
    for name in ('state','protocol',*INPUTS): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--bundle',dest='bundles',action='append',required=True,metavar='ALIAS=PATH')
    args = vars(parser.parse_args(argv)); operation = args.pop('operation')
    try:
        args['bundles'] = auth.bundle_arguments(args['bundles'])
        result = (initialize if operation == 'init' else advance)(**args)
        code = 2 if result['status'] == 'INVALIDATED' else 0
    except Refused as exc:
        result = {'status':'REFUSED','reason':str(exc),'completion':None,'release_eligible':False}; code = 2
    except (OSError,sqlite3.Error):
        result = {'status':'ERROR','reason':'storage failure; no current receipt','completion':None,'release_eligible':False}; code = 3
    print(json.dumps(result,sort_keys=True,ensure_ascii=True,allow_nan=False)); return code


if __name__ == '__main__':
    raise SystemExit(main())
