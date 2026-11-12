"""Authenticate frozen decision records under an explicit key policy and reviewer roster."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import synthesis_adjudication as adj
from scripts import synthesis_signing as signing

replay = adj.replay
Refused = adj.Refused
require = adj.require
PAYLOAD_TYPE = 'application/vnd.e156.reviewer-authorization.v1+json'
SCHEMA = 'e156-reviewer-authorization-v1'
ROSTER_SCHEMA = 'e156-reviewer-roster-v1'
SET_SCHEMA = 'e156-reviewer-signatures-v1'
SET_LIMIT = 512 * 1024
ROLES = ('adjudicator', 'reviewer')


def code_profile():
    return {'authorization_sha256': replay.digest(replay.read(Path(__file__), replay.JSON_LIMIT).replace(b'\r\n', b'\n')),
            'signing_sha256': replay.digest(replay.read(Path(signing.__file__), replay.JSON_LIMIT).replace(b'\r\n', b'\n')),
            'adjudication': adj.code_profile()}


def pae(payload):
    typ = PAYLOAD_TYPE.encode('ascii')
    return b'DSSEv1 '+str(len(typ)).encode()+b' '+typ+b' '+str(len(payload)).encode()+b' '+payload


def _paths(bundles, *paths):
    require(isinstance(bundles, dict) and 1 <= len(bundles) <= 8, 'explicit bundle mapping required')
    for alias in bundles: adj.identifier(alias)
    roots = {k: replay.guarded(v).resolve() for k,v in bundles.items()}
    paths = [replay.guarded(p).resolve() for p in paths]
    require(len(set(paths)) == len(paths), 'decision, policy, signature, key and output paths must differ')
    require(all(not p.is_relative_to(root) for root in roots.values() for p in paths),
            'decision inputs, keys and signatures must remain outside sealed bundles')
    return roots, paths


def _read(path, expected, limit):
    adj.anchor(expected)
    raw = replay.read(path, limit)
    require(replay.digest(raw) == expected, 'input differs from retained external anchor')
    return raw


def _members(raw, project, trust_sha256, keys):
    roster = replay.strict_json(raw)
    adj.fields(roster, ('schema','project','trust_sha256','members'), 'reviewer roster')
    require(roster['schema'] == ROSTER_SCHEMA and roster['project'] == project
            and roster['trust_sha256'] == trust_sha256, 'roster project or key policy mismatch')
    require(isinstance(roster['members'], list) and 2 <= len(roster['members']) <= 32, 'invalid roster size')
    members, people, assigned_keys = {}, set(), set()
    for m in roster['members']:
        adj.fields(m, ('reviewer','person_id','keyid','roles'), 'roster member')
        adj.identifier(m['reviewer']); adj.identifier(m['person_id'])
        require(isinstance(m['keyid'], str) and m['keyid'] in keys, 'roster key is absent from trust policy')
        require(isinstance(m['roles'], list) and 1 <= len(m['roles']) <= 2
                and all(isinstance(r, str) and r in ROLES for r in m['roles'])
                and m['roles'] == sorted(set(m['roles'])), 'invalid or repeated reviewer roles')
        require(m['reviewer'] not in members and m['person_id'] not in people
                and m['keyid'] not in assigned_keys, 'duplicate reviewer, assigned person or key')
        members[m['reviewer']] = m; people.add(m['person_id']); assigned_keys.add(m['keyid'])
    return members


def _prepare(*, dossier, dossier_sha256, trust, trust_sha256, roster, roster_sha256, project, bundles):
    adj.identifier(project)
    roots, paths = _paths(bundles, dossier, trust, roster)
    dossier, trust, roster = paths
    profile = code_profile()
    inventories = {k: adj.audit._bundle_snapshot(p) for k,p in roots.items()}
    raw = {dossier: _read(dossier, dossier_sha256, adj.LIMIT),
           trust: _read(trust, trust_sha256, signing.LIMIT),
           roster: _read(roster, roster_sha256, signing.LIMIT)}
    keys = signing.load_policy(trust, trust_sha256, project)
    members = _members(raw[roster], project, trust_sha256, keys)
    checked = adj.verify(dossier=dossier, bundles=roots, project=project, expected_sha256=dossier_sha256)
    data = replay.strict_json(raw[dossier]); targets = {}
    for relation in data['relations']:
        records = [('reviewer', b) for b in relation['reviews']]
        if relation['adjudication'] is not None: records.append(('adjudicator', relation['adjudication']))
        for role, record in records:
            who = record['reviewer']
            require(who in members and role in members[who]['roles'], 'reviewer is not authorized for this role')
            targets[(relation['id'], role, who)] = {
                'schema': SCHEMA, 'project': project, 'dossier_sha256': dossier_sha256,
                'trust_sha256': trust_sha256, 'roster_sha256': roster_sha256,
                'relation': relation['id'], 'role': role, 'reviewer': who,
                'context_sha256': record['context_sha256'],
                'record_sha256': replay.digest(replay.canonical(record)), 'scientific_validity': 'NOT_ESTABLISHED'}
    require(1 <= len(targets) <= 192, 'at least one actual reviewer record is required')
    return {'keys':keys, 'members':members, 'targets':targets, 'checked':checked, 'raw':raw,
            'roots':roots, 'inventories':inventories, 'profile':profile}


def _unchanged(prepared):
    require(code_profile() == prepared['profile']
            and all(replay.read(p, max(adj.LIMIT, signing.LIMIT)) == raw for p,raw in prepared['raw'].items())
            and {k: adj.audit._bundle_snapshot(p) for k,p in prepared['roots'].items()} == prepared['inventories'],
            'dependency changed during reviewer verification')


def _envelope(envelope, prepared):
    adj.fields(envelope, ('payloadType','payload','signatures'), 'DSSE envelope')
    require(envelope['payloadType'] == PAYLOAD_TYPE, 'unsupported reviewer signature domain')
    require(isinstance(envelope['signatures'], list) and len(envelope['signatures']) == 1,
            'each reviewer envelope requires one signature')
    sig = envelope['signatures'][0]; adj.fields(sig, ('keyid','sig'), 'signature')
    require(isinstance(sig['keyid'], str) and sig['keyid'] in prepared['keys'], 'signature key is not trusted')
    public, status = prepared['keys'][sig['keyid']]
    require(status == 'active', 'signature key is revoked')
    payload = signing.unb64(envelope['payload']); signature = signing.unb64(sig['sig'], 64)
    statement = replay.strict_json(payload)
    require(isinstance(statement, dict), 'invalid signed statement')
    for field in ('relation','role','reviewer'): adj.identifier(statement.get(field))
    target = (statement['relation'],statement['role'],statement['reviewer'])
    require(target in prepared['targets'], 'signature does not target a current reviewer record')
    # Exact bytes bind all expected fields and reject alternate schemas or values.
    require(payload == replay.canonical(prepared['targets'][target]), 'signed dossier, context, ballot or policy changed')
    require(prepared['members'][target[2]]['keyid'] == sig['keyid'], 'key is not assigned to this reviewer')
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc: raise Refused('install optional hash-locked signing dependencies') from exc
    try: Ed25519PublicKey.from_public_bytes(public).verify(signature, pae(payload))
    except (InvalidSignature, ValueError) as exc: raise Refused('invalid reviewer signature') from exc
    return target, {'relation':target[0], 'role':target[1], 'reviewer':target[2], 'keyid':sig['keyid']}


def _verify(*, signatures, signatures_sha256, **args):
    _, paths = _paths(args['bundles'], args['dossier'], args['trust'], args['roster'], signatures)
    signatures = paths[-1]
    raw = _read(signatures, signatures_sha256, SET_LIMIT)
    signed = replay.strict_json(raw)
    adj.fields(signed, ('schema','envelopes'), 'signature set')
    require(signed['schema'] == SET_SCHEMA and isinstance(signed['envelopes'], list)
            and 1 <= len(signed['envelopes']) <= 192, 'invalid signature set')
    p = _prepare(**args); seen = {}
    for envelope in signed['envelopes']:
        target, verified = _envelope(envelope, p)
        require(target not in seen, 'duplicate reviewer signature'); seen[target] = verified
    require(set(seen) == set(p['targets']), 'every original ballot and adjudication must be signed exactly once')
    _unchanged(p)
    require(replay.read(signatures, SET_LIMIT) == raw, 'signature set changed during verification')
    result = {'schema':'e156-reviewer-auth-receipt-v1', 'status':'SIGNATURES_REVALIDATED', 'project':args['project'],
              **{k:args[k] for k in ('dossier_sha256','trust_sha256','roster_sha256')},
              'signatures_sha256':signatures_sha256, 'adjudication_receipt_id':p['checked']['receipt_id'],
              'code_profile':p['profile'], 'authorizations':[seen[k] for k in sorted(seen)],
              'decision_ready':all(r['state'] in ('AGREEMENT_RECORDED','ADJUDICATION_RECORDED') for r in p['checked']['relations']),
              'reviewer_authorization':'KEY_AUTHENTICATED_UNDER_POLICY', 'human_identity':'NOT_ESTABLISHED',
              'independence':'NOT_ESTABLISHED', 'semantic_support':'NOT_ASSESSED',
              'scientific_validity':'NOT_ESTABLISHED', 'pooling_readiness':'HOLD', 'release_eligible':False}
    return {**result,'receipt_id':replay.digest(replay.canonical(result))}


def verify(**args):
    try: return _verify(**args)
    except replay.Refused as exc: raise Refused(str(exc)) from exc


def _sign(*, relation, reviewer, role, private_key, output, **args):
    _, paths = _paths(args['bundles'], args['dossier'], args['trust'], args['roster'], private_key, output)
    private_key, output = paths[-2:]
    require(not output.exists(), 'signature output already exists')
    for value in (relation,reviewer,role): adj.identifier(value)
    p = _prepare(**args); target = (relation,role,reviewer)
    require(target in p['targets'], 'selected reviewer record is missing')
    secret = replay.read(private_key, 32); require(len(secret) == 32, 'explicit raw 32-byte private key required')
    try: from overmind.verification.signers import Ed25519Signer
    except ImportError as exc: raise Refused('Overmind Ed25519 signer is required to sign') from exc
    payload = replay.canonical(p['targets'][target]); signed = Ed25519Signer(secret).sign(pae(payload))
    require(signed.method == 'ed25519', 'unsupported signer method')
    public = signing.unb64(signed.public_key, 32)
    envelope = {'payloadType':PAYLOAD_TYPE,'payload':signing.b64(payload),
                'signatures':[{'keyid':'sha256:'+replay.digest(public),'sig':signed.signature}]}
    _, authorized = _envelope(envelope, p); _unchanged(p)
    raw = replay.canonical(envelope)
    with output.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return {'status':'REVIEWER_SIGNATURE_WRITTEN', **authorized, 'envelope_sha256':replay.digest(raw),
            'scientific_validity':'NOT_ESTABLISHED','release_eligible':False}


def sign(**args):
    try: return _sign(**args)
    except replay.Refused as exc: raise Refused(str(exc)) from exc


def bundle_arguments(values):
    bundles = {}
    for value in values:
        alias, separator, path = value.partition('='); adj.identifier(alias)
        require(separator and path and alias not in bundles, 'invalid or duplicate bundle argument')
        bundles[alias] = Path(path)
    return bundles


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    for operation in ('sign','verify'):
        sub = commands.add_parser(operation); sub.add_argument('--project',required=True)
        sub.add_argument('--bundle',dest='bundles',action='append',required=True,metavar='ALIAS=PATH')
        for name in ('dossier','trust','roster'):
            sub.add_argument('--'+name,type=Path,required=True); sub.add_argument('--'+name+'-sha256',required=True)
        if operation == 'verify':
            sub.add_argument('--signatures',type=Path,required=True); sub.add_argument('--signatures-sha256',required=True)
        else:
            for name in ('relation','reviewer','role'): sub.add_argument('--'+name,required=True)
            sub.add_argument('--private-key',type=Path,required=True); sub.add_argument('--output',type=Path,required=True)
    args = vars(parser.parse_args(argv)); operation = args.pop('operation')
    try:
        args['bundles'] = bundle_arguments(args['bundles'])
        result = (sign if operation == 'sign' else verify)(**args); code = 0
    except Refused as exc:
        result = {'status':'REFUSED','reason':str(exc),'receipt':None,'release_eligible':False}; code = 2
    except OSError:
        result = {'status':'ERROR','reason':'storage failure; no current receipt','receipt':None,'release_eligible':False}; code = 3
    print(json.dumps(result,sort_keys=True,ensure_ascii=True,allow_nan=False)); return code


if __name__ == '__main__':
    raise SystemExit(main())
