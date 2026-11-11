#!/usr/bin/env python3
"""Detached replay signatures with externally anchored, project-scoped trust.

One Ed25519 signature in a DSSE envelope. A trusted signature authenticates the
declared bundle under that policy; it never establishes scientific correctness.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import sys

if __package__:
    from scripts import synthesis_replay as replay
else:
    # Direct CLI execution must also resolve the replay's package-qualified
    # imports when another component exposes a `scripts` namespace on PYTHONPATH.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import synthesis_replay as replay

SCHEMA = 'e156-synthesis-signature-v1'
TRUST_SCHEMA = 'e156-synthesis-trust-v1'
PAYLOAD_TYPE = 'application/vnd.e156.synthesis-replay-signature.v1+json'
LIMIT = 32768
PROJECT = re.compile(r'[a-z0-9][a-z0-9._/-]{0,127}')


def b64(raw):
    return base64.b64encode(raw).decode('ascii')


def unb64(value, size=None):
    if not isinstance(value, str) or len(value) > LIMIT:
        raise replay.Refused('invalid base64 field')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise replay.Refused('invalid base64 encoding') from exc
    if b64(raw) != value or (size is not None and len(raw) != size):
        raise replay.Refused('noncanonical base64 or wrong byte length')
    return raw


def pae(payload):
    """DSSE v1 pre-authentication encoding binds type and exact payload bytes."""
    typ = PAYLOAD_TYPE.encode('utf-8')
    return b'DSSEv1 '+str(len(typ)).encode()+b' '+typ+b' '+str(len(payload)).encode()+b' '+payload


def outside(root, *paths):
    root = replay.guarded(root).resolve()
    result = [replay.guarded(p).resolve() for p in paths]
    if any(p.is_relative_to(root) for p in result):
        raise replay.Refused('signatures, policies and private keys must stay outside the replay bundle')
    if len(set(result)) != len(result):
        raise replay.Refused('signature, policy and private-key paths must differ')
    return result


def load_policy(path, trust_sha256, project):
    if not isinstance(project, str) or not PROJECT.fullmatch(project):
        raise replay.Refused('an explicit canonical project identifier is required')
    if not isinstance(trust_sha256, str) or not replay.SHA.fullmatch(trust_sha256):
        raise replay.Refused('an external SHA-256 trust-policy digest is required')
    raw = replay.read(path, LIMIT)
    if replay.digest(raw) != trust_sha256:
        raise replay.Refused('trust policy digest differs from the external anchor')
    policy = replay.strict_json(raw)
    if (not isinstance(policy, dict) or set(policy) != {'schema', 'project', 'keys'}
            or policy['schema'] != TRUST_SCHEMA or policy['project'] != project
            or not isinstance(policy['keys'], list) or not 1 <= len(policy['keys']) <= 32):
        raise replay.Refused('invalid trust policy or project mismatch')
    keys = {}
    try:
        from importlib.metadata import version
        from nacl.bindings import crypto_core_ed25519_is_valid_point
        if tuple(int(v) for v in version('PyNaCl').split('.')) < (1, 6, 2):
            raise replay.Refused('PyNaCl 1.6.2 or newer is required for corrected point validation')
    except ImportError as exc:
        raise replay.Refused('install the optional hash-locked signing dependencies') from exc
    for item in policy['keys']:
        if (not isinstance(item, dict) or set(item) != {'keyid', 'public_key', 'status'}
                or not isinstance(item['keyid'], str) or item['status'] not in ('active', 'revoked')):
            raise replay.Refused('invalid trust key record')
        public = unb64(item['public_key'], 32)
        if not crypto_core_ed25519_is_valid_point(public):
            raise replay.Refused('invalid, noncanonical or weak Ed25519 public key')
        keyid = 'sha256:'+replay.digest(public)
        if item['keyid'] != keyid or keyid in keys:
            raise replay.Refused('trust key fingerprint mismatch or duplicate key')
        keys[keyid] = (public, item['status'])
    return keys


def verify_envelope(raw, keys, project):
    envelope = replay.strict_json(raw)
    if (not isinstance(envelope, dict) or set(envelope) != {'payloadType', 'payload', 'signatures'}
            or envelope['payloadType'] != PAYLOAD_TYPE or not isinstance(envelope['signatures'], list)
            or len(envelope['signatures']) != 1):
        raise replay.Refused('expected the single-signature replay DSSE profile')
    sig = envelope['signatures'][0]
    if (not isinstance(sig, dict) or set(sig) != {'keyid', 'sig'}
            or not isinstance(sig['keyid'], str) or sig['keyid'] not in keys):
        raise replay.Refused('signature key is not trusted for this project')
    public, status = keys[sig['keyid']]
    if status != 'active': raise replay.Refused('signature key is revoked')
    payload, signature = unb64(envelope['payload']), unb64(sig['sig'], 64)
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise replay.Refused('install the optional hash-locked signing dependencies') from exc
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, pae(payload))
    except (InvalidSignature, ValueError) as exc:
        raise replay.Refused('invalid Ed25519 signature') from exc
    statement = replay.strict_json(payload)
    fields = {'schema', 'project', 'manifest_sha256', 'payload_sha256', 'scientific_validity'}
    if (not isinstance(statement, dict) or set(statement) != fields or statement['schema'] != SCHEMA
            or statement['project'] != project or statement['scientific_validity'] != 'NOT_ESTABLISHED'
            or any(not isinstance(statement[k], str) or not replay.SHA.fullmatch(statement[k])
                   for k in ('manifest_sha256', 'payload_sha256'))
            or payload != replay.canonical(statement)):
        raise replay.Refused('unsupported signed statement, project or scientific-validity claim')
    return statement, sig['keyid']


def verified_receipt(root, raw, keys, trust_sha256, project):
    statement, keyid = verify_envelope(raw, keys, project)
    receipt = replay.verify(root, statement['manifest_sha256'])
    if receipt['payload_sha256'] != statement['payload_sha256']:
        raise replay.Refused('signed payload digest differs from the replayed result')
    return {**receipt, 'status': 'TRUSTED_SIGNATURE_REPLAY_MATCHED', 'project': project,
            'keyid': keyid, 'trust_policy_sha256': trust_sha256, 'envelope_sha256': replay.digest(raw),
            'source_authenticity': 'NOT_ESTABLISHED', 'human_adjudication': 'NOT_ESTABLISHED',
            'freshness': 'NOT_ESTABLISHED'}


def verify(root, envelope_path, policy_path, trust_sha256, project):
    envelope_path, policy_path = outside(root, envelope_path, policy_path)
    keys = load_policy(policy_path, trust_sha256, project)
    return verified_receipt(root, replay.read(envelope_path, LIMIT), keys, trust_sha256, project)


def sign(root, expected_sha256, private_key, policy_path, trust_sha256, project, output):
    private_key, policy_path, output = outside(root, private_key, policy_path, output)
    if output.exists(): raise replay.Refused('signature output already exists')
    keys = load_policy(policy_path, trust_sha256, project)
    receipt = replay.verify(root, expected_sha256)
    # Explicit key input only: no environment selection, key discovery or generation.
    private_bytes = replay.read(private_key, 32)
    if len(private_bytes) != 32: raise replay.Refused('an explicit raw 32-byte Ed25519 key is required')
    try:
        from overmind.verification.signers import Ed25519Signer
    except ImportError as exc:
        raise replay.Refused('Overmind Ed25519 signer must be installed to sign') from exc
    payload = replay.canonical({'schema': SCHEMA, 'project': project,
        'manifest_sha256': receipt['manifest_sha256'], 'payload_sha256': receipt['payload_sha256'],
        'scientific_validity': 'NOT_ESTABLISHED'})
    signed = Ed25519Signer(private_bytes).sign(pae(payload))
    if signed.method != 'ed25519': raise replay.Refused('Overmind returned an unsupported signing method')
    public = unb64(signed.public_key, 32)
    raw = replay.canonical({'payloadType': PAYLOAD_TYPE, 'payload': b64(payload), 'signatures': [
        {'keyid': 'sha256:'+replay.digest(public), 'sig': signed.signature}]})
    # Independently verify the returned signature and re-execute before publishing.
    result = verified_receipt(root, raw, keys, trust_sha256, project)
    with output.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('sign', 'verify'):
        sub = commands.add_parser(command)
        sub.add_argument('root', type=Path)
        sub.add_argument('--policy', type=Path, required=True)
        sub.add_argument('--trust-sha256', required=True)
        sub.add_argument('--project', required=True)
        if command == 'sign':
            sub.add_argument('--private-key', type=Path, required=True)
            sub.add_argument('--expected-sha256', required=True)
            sub.add_argument('--output', type=Path, required=True)
        else:
            sub.add_argument('--envelope', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'sign':
            result = sign(args.root, args.expected_sha256, args.private_key, args.policy,
                          args.trust_sha256, args.project, args.output)
        else:
            result = verify(args.root, args.envelope, args.policy, args.trust_sha256, args.project)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({'status': 'REFUSED', 'reason': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
