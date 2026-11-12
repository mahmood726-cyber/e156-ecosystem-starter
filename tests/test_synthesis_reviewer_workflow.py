"""Synthetic signing principals and ballots over real OA text; no human identity claims."""
from contextlib import closing
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

pytest.importorskip('cryptography', reason='optional reviewer signing dependencies')
pytest.importorskip('nacl', reason='optional hash-locked Ed25519 point validation')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts import synthesis_adjudication as adj
from scripts import synthesis_reviewer_auth as auth
from scripts import synthesis_decision_runner as runner

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'fc7e071298fc1fed636ed16dda1252358c026552d0d8209896607d72d23013f9'
TYPE = 'application/vnd.e156.reviewer-authorization.v1+json'


def write(path, value):
    path.write_bytes(adj.replay.canonical(value))
    return adj.replay.digest(path.read_bytes())


def wire(statement, key, keyid, typ=TYPE):
    payload = adj.replay.canonical(statement); t = typ.encode()
    pae = b'DSSEv1 ' + str(len(t)).encode() + b' ' + t + b' ' + str(len(payload)).encode() + b' ' + payload
    return {'payloadType': typ, 'payload': base64.b64encode(payload).decode(),
            'signatures': [{'keyid': keyid, 'sig': base64.b64encode(key.sign(pae)).decode()}]}


def refresh(c, *, signatures=True):
    for name in ('dossier', 'trust', 'roster'):
        c['args'][name + '_sha256'] = write(c['args'][name], c[name])
    if signatures:
        envelopes = []
        for r in c['dossier']['relations']:
            records = [('reviewer', b) for b in r['reviews']]
            if r['adjudication'] is not None: records.append(('adjudicator', r['adjudication']))
            for role, b in records:
                member = next(m for m in c['roster']['members'] if m['reviewer'] == b['reviewer'])
                statement = {'schema': 'e156-reviewer-authorization-v1', 'project': c['args']['project'],
                    'dossier_sha256': c['args']['dossier_sha256'], 'trust_sha256': c['args']['trust_sha256'],
                    'roster_sha256': c['args']['roster_sha256'], 'relation': r['id'], 'role': role,
                    'reviewer': b['reviewer'], 'context_sha256': b['context_sha256'],
                    'record_sha256': adj.replay.digest(adj.replay.canonical(b)), 'scientific_validity': 'NOT_ESTABLISHED'}
                envelopes.append(wire(statement, c['keys'][b['reviewer']], member['keyid']))
        c['signed'] = {'schema': 'e156-reviewer-signatures-v1', 'envelopes': envelopes}
    c['args']['signatures_sha256'] = write(c['args']['signatures'], c['signed'])


@pytest.fixture
def case(tmp_path):
    bundle = tmp_path / 'bundle'; shutil.copytree(ROOT/'examples/synthesis-replay-stepwise', bundle)
    quotes = ['103 attended baseline testing', 'After baseline testing, 97 participants (82 women, 15 men) were eligible to be randomized']
    d = {'schema': adj.SCHEMA, 'project': 'reviewer-control',
         'reports': [{'id': 'stepwise', 'manifest_sha256': MANIFEST}],
         'entities': [{'id': name, 'kind': 'cohort', 'report': 'stepwise',
                       'scope': {f: {'quote': q, 'locator': 'body p 32'} for f in ('definition','population','timepoint')}}
                      for name,q in zip(('baseline','eligible'),quotes)],
         'relations': [{'id': 'overlap', 'kind': 'cohort_overlap', 'left': 'baseline', 'right': 'eligible',
                        'reviews': [], 'adjudication': None}]}
    r = d['relations'][0]
    for who in ('reviewer-a','reviewer-b'):
        r['reviews'].append({'reviewer': who, 'decision': 'PARTIAL', 'rationale': 'Synthetic structural control, not a real review.',
                            'context_sha256': adj.review_context(d,r),
                            'evidence': [{'entity': e['id'], 'field': f} for e in d['entities'] for f in e['scope']]})
    keys = {who: Ed25519PrivateKey.generate() for who in ('reviewer-a','reviewer-b','reviewer-c')}
    trust = {'schema': auth.signing.TRUST_SCHEMA, 'project': d['project'], 'keys': []}
    members = []
    for who,k in keys.items():
        public = k.public_key().public_bytes_raw(); keyid = 'sha256:'+adj.replay.digest(public)
        trust['keys'].append({'keyid':keyid,'public_key':base64.b64encode(public).decode(),'status':'active'})
        members.append({'reviewer':who,'person_id':'principal-'+who,'keyid':keyid,'roles':['adjudicator','reviewer']})
    trust_sha = write(tmp_path/'trust.json',trust)
    roster = {'schema': 'e156-reviewer-roster-v1', 'project':d['project'],'trust_sha256':trust_sha,'members':members}
    args = {name:tmp_path/(name+'.json') for name in ('dossier','trust','roster','signatures')}
    args.update(project=d['project'],bundles={'stepwise':bundle})
    c = {'args':args,'dossier':d,'trust':trust,'roster':roster,'keys':keys,'tmp':tmp_path}
    refresh(c); return c


def workflow(c):
    protocol = {'schema': 'e156-decision-protocol-v1', 'project':c['args']['project'], 'stage':'authenticated-decisions',
                **{k:v for k,v in c['args'].items() if k.endswith('_sha256')}}
    path=c['tmp']/'protocol.json'; sha=write(path,protocol)
    return {'state':c['tmp']/'decision.sqlite','protocol':path,'expected_sha256':sha,
            **{k:v for k,v in c['args'].items() if k in ('dossier','trust','roster','signatures','bundles')}}


def events(args):
    with closing(sqlite3.connect(args['state'])) as db:
        return db.execute('SELECT seq,body,sha256 FROM events ORDER BY seq').fetchall()


def test_external_signatures_bind_policy_and_preserve_limits(case):
    r=auth.verify(**case['args'])
    assert r['status']=='SIGNATURES_REVALIDATED' and r['decision_ready'] is True
    assert r['reviewer_authorization']=='KEY_AUTHENTICATED_UNDER_POLICY'
    assert r['human_identity']=='NOT_ESTABLISHED' and r['independence']=='NOT_ESTABLISHED'
    assert r['release_eligible'] is False and r['pooling_readiness']=='HOLD'
    assert len(r['authorizations'])==2 and auth.verify(**case['args'])==r


def test_signing_uses_explicit_key_and_verifies_returned_signature(case):
    pytest.importorskip('overmind.verification.signers', reason='locked Overmind signer in dedicated CI')
    args={k:v for k,v in case['args'].items() if k not in ('signatures','signatures_sha256')}
    private=case['tmp']/'disposable-key'; private.write_bytes(case['keys']['reviewer-a'].private_bytes_raw())
    output=case['tmp']/'signed.json'
    auth.sign(**args,relation='overlap',reviewer='reviewer-a',role='reviewer',private_key=private,output=output)
    assert json.loads(output.read_text())==case['signed']['envelopes'][0]
    before=output.read_bytes()
    with pytest.raises(auth.Refused): auth.sign(**args,relation='overlap',reviewer='reviewer-a',role='reviewer',private_key=private,output=output)
    assert output.read_bytes()==before and private.read_bytes() not in before


def test_authorization_cli_sign_and_public_only_verify_outside_repo(case):
    pytest.importorskip('overmind.verification.signers', reason='locked signer in dedicated CI')
    script=ROOT/'scripts/synthesis_reviewer_auth.py'
    private=case['tmp']/'cli-key'; private.write_bytes(case['keys']['reviewer-a'].private_bytes_raw())
    output=case['tmp']/'cli-envelope.json'
    common=[]
    for k,v in case['args'].items():
        if k in ('signatures','signatures_sha256'): continue
        if k=='bundles':
            for alias,path in v.items(): common.extend(['--bundle',alias+'='+str(path)])
        else: common.extend(['--'+k.replace('_','-'),str(v)])
    sign_cmd=[sys.executable,str(script),'sign',*common,'--relation','overlap','--reviewer','reviewer-a',
              '--role','reviewer','--private-key',str(private),'--output',str(output)]
    p=subprocess.run(sign_cmd,cwd=case['tmp'],capture_output=True,text=True,timeout=30)
    assert p.returncode==0 and not p.stderr and json.loads(p.stdout)['status']=='REVIEWER_SIGNATURE_WRITTEN'
    assert json.loads(output.read_text())==case['signed']['envelopes'][0]
    private.unlink()
    verify_cmd=[sys.executable,str(script),'verify',*common,'--signatures',str(case['args']['signatures']),
                '--signatures-sha256',case['args']['signatures_sha256']]
    p=subprocess.run(verify_cmd,cwd=case['tmp'],capture_output=True,text=True,timeout=30)
    assert p.returncode==0 and not p.stderr and json.loads(p.stdout)==auth.verify(**case['args'])


@pytest.mark.parametrize('mutation',['missing','extra','duplicate','bad_signature','wrong_type','wrong_key','noncanonical_base64'])
def test_signature_set_failures(case,mutation):
    env=case['signed']['envelopes']
    if mutation=='missing': env.pop()
    if mutation in ('extra','duplicate'): env.append(deepcopy(env[0]))
    if mutation=='bad_signature': env[0]['signatures'][0]['sig']=base64.b64encode(bytes(64)).decode()
    if mutation=='wrong_type': env[0]['payloadType']=auth.signing.PAYLOAD_TYPE
    if mutation=='wrong_key': env[0]['signatures'][0]['keyid']=case['roster']['members'][1]['keyid']
    if mutation=='noncanonical_base64': env[0]['payload']+='\n'
    refresh(case,signatures=False)
    with pytest.raises(auth.Refused): auth.verify(**case['args'])


@pytest.mark.parametrize('mutation',['same_person','same_key','same_reviewer','wrong_role','unknown_key','wrong_project','wrong_trust','revoked'])
def test_roster_and_trust_failures(case,mutation):
    a,b=case['roster']['members'][:2]
    if mutation=='same_person': b['person_id']=a['person_id']
    if mutation=='same_key': b['keyid']=a['keyid']
    if mutation=='same_reviewer': b['reviewer']=a['reviewer']
    if mutation=='wrong_role': a['roles']=['adjudicator']
    if mutation=='unknown_key': a['keyid']='sha256:'+'0'*64
    if mutation=='wrong_project': case['roster']['project']='other'
    if mutation=='wrong_trust': case['roster']['trust_sha256']='0'*64
    if mutation=='revoked':
        case['trust']['keys'][0]['status']='revoked'
        case['roster']['trust_sha256']=adj.replay.digest(adj.replay.canonical(case['trust']))
    refresh(case,signatures=False)
    with pytest.raises(auth.Refused): auth.verify(**case['args'])


def test_frozen_dossier_changes_require_every_signature_again(case):
    case['dossier']['relations'][0]['reviews'][0]['rationale']='Changed recorded judgment'
    refresh(case,signatures=False)
    with pytest.raises(auth.Refused): auth.verify(**case['args'])
    refresh(case); assert auth.verify(**case['args'])['decision_ready'] is True


def test_disagreement_authenticates_but_cannot_complete_stage(case):
    case['dossier']['relations'][0]['reviews'][1]['decision']='DISJOINT'; refresh(case)
    assert auth.verify(**case['args'])['decision_ready'] is False
    args=workflow(case)
    with pytest.raises(runner.Refused): runner.initialize(**args)
    assert not args['state'].exists()


def test_adjudication_requires_all_three_signed_records(case):
    r=case['dossier']['relations'][0]; r['reviews'][1]['decision']='DISJOINT'
    r['adjudication']={**deepcopy(r['reviews'][0]),'reviewer':'reviewer-c',
                       'review_sha256':sorted(adj.replay.digest(adj.replay.canonical(b)) for b in r['reviews'])}
    refresh(case); assert len(auth.verify(**case['args'])['authorizations'])==3
    case['signed']['envelopes'].pop(1); refresh(case,signatures=False)
    with pytest.raises(auth.Refused): auth.verify(**case['args'])


def test_persistent_transitions_and_idempotent_completion(case):
    args=workflow(case)
    assert runner.initialize(**args)['status']=='READY'
    assert runner.advance(**args)['status']=='AUTHENTICATED'
    result=runner.advance(**args); before=events(args)
    assert result['status']=='COMPLETED' and result['completion']['review_state']=='HOLD'
    assert result['release_eligible'] is False and runner.advance(**args)==result
    assert events(args)==before and len(before)==3


@pytest.mark.parametrize('when',['READY','AUTHENTICATED','COMPLETED'])
@pytest.mark.parametrize('changed',['dossier','trust','roster','signatures','source','protocol'])
def test_changed_dependencies_terminally_invalidate(case,when,changed):
    args=workflow(case); runner.initialize(**args)
    if when!='READY': runner.advance(**args)
    if when=='COMPLETED': runner.advance(**args)
    path=(next((case['args']['bundles']['stepwise']/'sources').glob('*.xml')) if changed=='source' else args[changed])
    original=path.read_bytes(); path.write_bytes(original+b' ')
    result=runner.advance(**args)
    assert result['status']=='INVALIDATED' and result['completion'] is None
    path.write_bytes(original); assert runner.advance(**args)==result


def test_wrong_anchor_reinitialization_and_busy_writer_preserve_history(case):
    args=workflow(case); runner.initialize(**args); before=events(args)
    with pytest.raises(runner.Refused): runner.initialize(**args)
    with pytest.raises(runner.Refused): runner.advance(**{**args,'expected_sha256':'0'*64})
    with closing(sqlite3.connect(args['state'],isolation_level=None)) as db:
        db.execute('BEGIN IMMEDIATE')
        with pytest.raises(sqlite3.OperationalError): runner.advance(**args)
        db.rollback()
    assert events(args)==before


def test_missing_state_is_never_recreated_and_storage_error_rolls_back(case,monkeypatch):
    args=workflow(case)
    with pytest.raises(runner.Refused): runner.advance(**args)
    assert not args['state'].exists()
    runner.initialize(**args); before=events(args)
    def fail(**kwargs): raise OSError('injected storage failure')
    monkeypatch.setattr(runner.auth,'verify',fail)
    with pytest.raises(OSError): runner.advance(**args)
    assert events(args)==before


def cli(args, operation):
    command=[sys.executable,str(ROOT/'scripts/synthesis_decision_runner.py'),operation]
    for k,v in args.items():
        if k=='bundles':
            for alias,path in v.items(): command.extend(['--bundle',alias+'='+str(path)])
        else: command.extend(['--'+k.replace('_','-'),str(v)])
    p=subprocess.run(command,cwd=args['state'].parent,capture_output=True,text=True,timeout=30)
    assert not p.stderr,p.stderr
    return p.returncode,json.loads(p.stdout)


def test_separate_process_cli_recovery(case):
    args=workflow(case)
    for operation,want in [('init','READY'),('advance','AUTHENTICATED'),('advance','COMPLETED')]:
        code,result=cli(args,operation); assert code==0 and result['status']==want
    assert cli(args,'advance')==(0,result)


@pytest.mark.parametrize('fault',['checksum','sequence','forged_completion','boolean_numeric','unknown_table','trigger','empty'])
def test_forged_history_and_schema_refused(case,fault):
    args=workflow(case); runner.initialize(**args); runner.advance(**args); runner.advance(**args)
    with closing(sqlite3.connect(args['state'])) as db,db:
        if fault=='checksum': db.execute('UPDATE events SET sha256=? WHERE seq=1',('0'*64,))
        elif fault=='sequence': db.execute('DELETE FROM events WHERE seq=1')
        elif fault=='unknown_table': db.execute('CREATE TABLE extra(x)')
        elif fault=='trigger': db.execute('CREATE TRIGGER extra AFTER INSERT ON events BEGIN DELETE FROM events; END')
        elif fault=='empty': db.execute('DELETE FROM events')
        else:
            body=json.loads(db.execute('SELECT body FROM events WHERE seq=2').fetchone()[0])
            if fault=='boolean_numeric': body['completion']['external_actions']=False
            else: body['completion']['review_state']='RELEASE_READY'
            raw=adj.replay.canonical(body)
            db.execute('UPDATE events SET body=?,sha256=? WHERE seq=2',(raw.decode(),adj.replay.digest(raw)))
    code,result=cli(args,'advance')
    assert code==2 and result['status']=='REFUSED' and result['completion'] is None


@pytest.mark.parametrize('target',['dossier','trust','roster','source','code'])
def test_mid_verification_mutations_refuse_authorization(case,monkeypatch,target):
    real=auth.adj.verify
    def changed(**kwargs):
        result=real(**kwargs)
        if target=='code': monkeypatch.setattr(auth,'code_profile',lambda:{'changed':True})
        else:
            path=next((case['args']['bundles']['stepwise']/'sources').glob('*.xml')) if target=='source' else case['args'][target]
            path.write_bytes(path.read_bytes()+b' ')
        return result
    monkeypatch.setattr(auth.adj,'verify',changed)
    with pytest.raises(auth.Refused): auth.verify(**case['args'])


def test_missing_bundle_or_changed_code_invalidates_completion(case,monkeypatch):
    args=workflow(case); runner.initialize(**args); runner.advance(**args); runner.advance(**args)
    bundle=case['args']['bundles']['stepwise']; moved=bundle.with_name('absent'); bundle.rename(moved)
    assert runner.advance(**args)['status']=='INVALIDATED'
    moved.rename(bundle); assert runner.advance(**args)['status']=='INVALIDATED'
    args['state']=case['tmp']/'second.sqlite'; runner.initialize(**args)
    monkeypatch.setattr(runner,'code_profile',lambda:{'changed':True})
    assert runner.advance(**args)['status']=='INVALIDATED'


def test_state_cannot_overlap_inputs_or_sidecars(case):
    args=workflow(case)
    for name in ('dossier','trust','roster','signatures','protocol'):
        with pytest.raises(runner.Refused): runner.initialize(**{**args,'state':args[name]})
    with pytest.raises(runner.Refused):
        runner.initialize(**{**args,'state':case['args']['bundles']['stepwise']/'review.sqlite'})
    args['state'].with_name(args['state'].name+'-journal').write_bytes(b'orphan')
    with pytest.raises(runner.Refused): runner.initialize(**args)


@pytest.mark.parametrize('point',['before_auth_commit','before_completion_commit','after_completion_commit'])
def test_own_worker_termination_preserves_transaction_and_retry(case,point):
    args=workflow(case); runner.initialize(**args)
    if point!='before_auth_commit': runner.advance(**args)
    before=events(args); marker=case['tmp']/'worker-ready'
    code='''
import json,sys,time
from pathlib import Path
from scripts import synthesis_decision_runner as r
kw=json.loads(sys.argv[1]); kw={k:({a:Path(p) for a,p in v.items()} if k=='bundles' else v if k=='expected_sha256' else Path(v)) for k,v in kw.items()}
if sys.argv[3]!='after_completion_commit':
    original=r.audit._append
    def interrupted(*a,**k):
        original(*a,**k)
        Path(sys.argv[2]).write_text('uncommitted',encoding='utf-8')
        time.sleep(45)
    r.audit._append=interrupted
result=r.advance(**kw)
Path(sys.argv[2]).write_text(json.dumps(result),encoding='utf-8')
time.sleep(45)
'''
    data={k:({a:str(p) for a,p in v.items()} if k=='bundles' else str(v)) for k,v in args.items()}
    p=subprocess.Popen([sys.executable,'-c',code,json.dumps(data),str(marker),point],cwd=ROOT,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+20
        while not marker.exists() and p.poll() is None and time.monotonic()<deadline: time.sleep(.03)
        assert marker.exists(),p.communicate(timeout=2)
        p.kill(); p.wait(timeout=10)
    finally:
        if p.poll() is None: p.kill(); p.wait(timeout=10)
        p.communicate(timeout=2)
    if point=='after_completion_commit':
        expected=json.loads(marker.read_text()); saved=events(args)
        assert runner.advance(**args)==expected and events(args)==saved and len(saved)==3
    else:
        assert events(args)==before
        assert runner.advance(**args)['status']==('AUTHENTICATED' if point=='before_auth_commit' else 'COMPLETED')
