"""Signing development controls; disposable keys never establish reviewer identity."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

pytest.importorskip('cryptography', reason='optional signing dependencies: scripts/requirements-signing.lock')
pytest.importorskip('nacl', reason='optional public-key validation: scripts/requirements-signing.lock')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts import synthesis_replay as replay
from scripts import synthesis_signing as signing

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = 'fc7e071298fc1fed636ed16dda1252358c026552d0d8209896607d72d23013f9'
PROJECT = 'synthetic-signing-control'


@pytest.fixture
def case(tmp_path, monkeypatch):
    def forbidden(*a, **k): raise AssertionError('signing attempted source retrieval')
    monkeypatch.setattr(replay.capture, 'build_opener', forbidden)
    root = tmp_path/'bundle'
    shutil.copytree(ROOT/'examples/synthesis-replay-stepwise', root)
    key = Ed25519PrivateKey.generate()
    private = tmp_path/'disposable-key'
    private.write_bytes(key.private_bytes_raw())
    public = key.public_key().public_bytes_raw()
    policy = {'schema': signing.TRUST_SCHEMA, 'project': PROJECT, 'keys': [
        {'keyid': 'sha256:'+replay.digest(public), 'public_key': base64.b64encode(public).decode(), 'status': 'active'}]}
    policy_path = tmp_path/'policy.json'
    policy_path.write_bytes(replay.canonical(policy))
    return {'root': root, 'key': key, 'private': private, 'policy': policy,
            'policy_path': policy_path, 'trust': replay.digest(policy_path.read_bytes()), 'output': tmp_path/'signature.json'}


def sign(c, output=None):
    pytest.importorskip('overmind.verification.signers', reason='Overmind signer required; dedicated signing CI installs the locked source')
    return signing.sign(c['root'], ANCHOR, c['private'], c['policy_path'], c['trust'], PROJECT, output or c['output'])


def verify(c, **kw):
    args = dict(root=c['root'], envelope_path=c['output'], policy_path=c['policy_path'], trust_sha256=c['trust'], project=PROJECT)
    return signing.verify(**(args | kw))


def external_envelope(c):
    """Independent cryptography signer constructs the DSSE wire bytes directly."""
    receipt = replay.verify(c['root'], ANCHOR)
    payload = replay.canonical({'schema': signing.SCHEMA, 'project': PROJECT,
        'manifest_sha256': ANCHOR, 'payload_sha256': receipt['payload_sha256'],
        'scientific_validity': 'NOT_ESTABLISHED'})
    typ = signing.PAYLOAD_TYPE.encode()
    pae = b'DSSEv1 '+str(len(typ)).encode()+b' '+typ+b' '+str(len(payload)).encode()+b' '+payload
    envelope = {'payloadType': signing.PAYLOAD_TYPE, 'payload': base64.b64encode(payload).decode(),
        'signatures': [{'keyid': c['policy']['keys'][0]['keyid'], 'sig': base64.b64encode(c['key'].sign(pae)).decode()}]}
    c['output'].write_bytes(replay.canonical(envelope))
    return envelope


def test_overmind_roundtrip_is_deterministic_and_preserves_hold(case, tmp_path):
    before = {p.relative_to(case['root']): p.read_bytes() for p in case['root'].rglob('*') if p.is_file()}
    result = sign(case)
    assert result['status'] == 'TRUSTED_SIGNATURE_REPLAY_MATCHED'
    assert result['scientific_validity'] == 'NOT_ESTABLISHED'
    assert verify(case) == result
    sign(case, tmp_path/'second.json')
    assert case['output'].read_bytes() == (tmp_path/'second.json').read_bytes()
    assert before == {p.relative_to(case['root']): p.read_bytes() for p in case['root'].rglob('*') if p.is_file()}
    assert json.loads(before[Path('result.json')])['ledger'][0]['effective'] == 'HOLD'
    assert case['private'].read_bytes() not in case['output'].read_bytes()


def test_independent_dsse_signature_verifies_and_cli_needs_no_private_key(case):
    external_envelope(case)
    case['private'].unlink()
    assert verify(case)['status'] == 'TRUSTED_SIGNATURE_REPLAY_MATCHED'
    proc = subprocess.run([sys.executable, str(ROOT/'scripts/synthesis_signing.py'), 'verify', str(case['root']),
        '--envelope', str(case['output']), '--policy', str(case['policy_path']), '--trust-sha256', case['trust'],
        '--project', PROJECT], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['scientific_validity'] == 'NOT_ESTABLISHED'


@pytest.mark.parametrize('mutation', ['signature', 'payload', 'type', 'extra', 'duplicate-signature', 'unknown-key', 'base64'])
def test_modified_or_ambiguous_envelope_refuses(case, mutation):
    e = external_envelope(case)
    if mutation == 'signature': e['signatures'][0]['sig'] = base64.b64encode(bytes(64)).decode()
    if mutation == 'payload': e['payload'] = base64.b64encode(b'{}').decode()
    if mutation == 'type': e['payloadType'] += '-other'
    if mutation == 'extra': e['public_key'] = case['policy']['keys'][0]['public_key']
    if mutation == 'duplicate-signature': e['signatures'] *= 2
    if mutation == 'unknown-key': e['signatures'][0]['keyid'] = 'sha256:'+'0'*64
    if mutation == 'base64': e['signatures'][0]['sig'] += '\n'
    case['output'].write_bytes(replay.canonical(e))
    with pytest.raises(replay.Refused): verify(case)


@pytest.mark.parametrize('mutation', ['revoked', 'empty', 'duplicate', 'wrong-id', 'wrong-key', 'unknown-status', 'wrong-project', 'extra'])
def test_rejected_trust_policies_even_with_matching_policy_digest(case, mutation):
    external_envelope(case)
    p = case['policy']
    if mutation == 'revoked': p['keys'][0]['status'] = 'revoked'
    if mutation == 'empty': p['keys'] = []
    if mutation == 'duplicate': p['keys'] *= 2
    if mutation == 'wrong-id': p['keys'][0]['keyid'] = 'sha256:'+'0'*64
    if mutation == 'wrong-key': p['keys'][0]['public_key'] = base64.b64encode(bytes(32)).decode()
    if mutation == 'unknown-status': p['keys'][0]['status'] = 'maybe'
    if mutation == 'wrong-project': p['project'] = 'other'
    if mutation == 'extra': p['allow_unsigned'] = True
    case['policy_path'].write_bytes(replay.canonical(p))
    with pytest.raises(replay.Refused): verify(case, trust_sha256=replay.digest(case['policy_path'].read_bytes()))


def test_policy_substitution_and_project_confusion_refuse(case):
    external_envelope(case)
    with pytest.raises(replay.Refused): verify(case, project='other')
    case['policy_path'].write_bytes(case['policy_path'].read_bytes()+b' ')
    with pytest.raises(replay.Refused, match='policy digest'): verify(case)


@pytest.mark.parametrize('name', ['manifest.json', 'packet.json', 'result.json'])
def test_signature_never_substitutes_for_replay(case, name):
    external_envelope(case)
    path = case['root']/name
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(replay.Refused): verify(case)


def test_changed_implementation_refuses_after_valid_signature(case, monkeypatch):
    external_envelope(case)
    monkeypatch.setattr(replay, 'code_profile', lambda: {})
    with pytest.raises(replay.Refused, match='verifier'): verify(case)


def test_missing_anchor_nested_policy_and_duplicate_json_refuse(case):
    external_envelope(case)
    with pytest.raises(replay.Refused): verify(case, trust_sha256='')
    nested = case['root']/'policy.json'
    nested.write_bytes(case['policy_path'].read_bytes())
    with pytest.raises(replay.Refused, match='outside'): verify(case, policy_path=nested)
    nested.unlink()
    case['output'].write_bytes(b'{"payloadType":"a","payloadType":"b"}')
    with pytest.raises(replay.Refused, match='duplicate'): verify(case)


def test_signing_refuses_wrong_private_key_overwrite_and_nested_output(case):
    sign(case)
    before = case['output'].read_bytes()
    with pytest.raises(replay.Refused): sign(case)
    assert case['output'].read_bytes() == before
    with pytest.raises(replay.Refused, match='outside'): sign(case, case['root']/'signature.json')
    case['output'].unlink()
    case['private'].write_bytes(Ed25519PrivateKey.generate().private_bytes_raw())
    with pytest.raises(replay.Refused, match='trusted'): sign(case)
    assert not case['output'].exists()


def test_signature_does_not_override_scientific_claim_or_signed_project(case):
    e = external_envelope(case)
    payload = json.loads(base64.b64decode(e['payload']))
    for field, value in [('scientific_validity', 'ESTABLISHED'), ('project', 'other')]:
        altered = replay.canonical(payload | {field: value})
        e['payload'] = base64.b64encode(altered).decode()
        e['signatures'][0]['sig'] = base64.b64encode(case['key'].sign(signing.pae(altered))).decode()
        case['output'].write_bytes(replay.canonical(e))
        with pytest.raises(replay.Refused): verify(case)


@pytest.mark.parametrize('public', [b'\x01'+bytes(31), bytes(32), b'\xff'*32])
def test_degenerate_public_key_forgery_is_rejected(case, public):
    e = external_envelope(case)
    keyid = 'sha256:'+replay.digest(public)
    case['policy']['keys'][0].update(keyid=keyid, public_key=base64.b64encode(public).decode())
    case['policy_path'].write_bytes(replay.canonical(case['policy']))
    e['signatures'][0] = {'keyid': keyid, 'sig': base64.b64encode(public+bytes(32)).decode()}
    case['output'].write_bytes(replay.canonical(e))
    with pytest.raises(replay.Refused, match='Ed25519 public key'):
        verify(case, trust_sha256=replay.digest(case['policy_path'].read_bytes()))


def test_dotdot_cannot_place_signature_inside_bundle(case):
    with pytest.raises(replay.Refused, match='outside'):
        sign(case, case['root'].parent/'unused'/'..'/'bundle'/'signature.json')


def test_cli_outside_repo_with_another_scripts_namespace(case, tmp_path):
    external_envelope(case)
    component = tmp_path/'other-component'
    (component/'scripts').mkdir(parents=True)
    (component/'scripts'/'unrelated.py').write_text('# Namespace only.\n', encoding='utf-8')
    proc = subprocess.run([sys.executable, str(ROOT/'scripts/synthesis_signing.py'), 'verify', str(case['root']),
        '--envelope', str(case['output']), '--policy', str(case['policy_path']), '--trust-sha256', case['trust'],
        '--project', PROJECT], cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(component)),
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['status'] == 'TRUSTED_SIGNATURE_REPLAY_MATCHED'
