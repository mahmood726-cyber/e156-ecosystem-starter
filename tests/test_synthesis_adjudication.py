"""Decision-record contracts: real OA text, explicitly synthetic reviewer ballots."""
from copy import deepcopy
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest

from scripts import synthesis_adjudication as adj

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/synthesis_adjudication.py'
ANCHOR = 'fc7e071298fc1fed636ed16dda1252358c026552d0d8209896607d72d23013f9'


@pytest.fixture
def rig(tmp_path):
    bundle = tmp_path / 'bundle'
    shutil.copytree(ROOT / 'examples/synthesis-replay-stepwise', bundle)
    # Real text, assigned to all fields as a synthetic structural control.
    # This is NOT a scientific cohort judgment or an actual human ballot.
    quotes = ['103 attended baseline testing',
              'After baseline testing, 97 participants (82 women, 15 men) were eligible to be randomized']
    data = {'schema': adj.SCHEMA, 'project': 'development-control',
            'reports': [{'id': 'stepwise', 'manifest_sha256': ANCHOR}],
            'entities': [{'id': name, 'kind': 'cohort', 'report': 'stepwise',
                          'scope': {field: {'quote': quote, 'locator': 'body p 32'}
                                    for field in ('definition', 'population', 'timepoint')}}
                         for name, quote in zip(('baseline', 'eligible'), quotes)],
            'relations': [{'id': 'overlap', 'kind': 'cohort_overlap', 'left': 'baseline',
                           'right': 'eligible', 'reviews': [], 'adjudication': None}]}
    return {'data': data, 'dossier': tmp_path / 'decisions.json', 'bundles': {'stepwise': bundle},
            'project': data['project']}


def check(rig):
    raw = adj.replay.canonical(rig['data'])
    rig['dossier'].write_bytes(raw)
    return adj.verify(dossier=rig['dossier'], bundles=rig['bundles'],
                      project=rig['project'], expected_sha256=adj.replay.digest(raw))


def ballot(rig, who, decision):
    return {'reviewer': who, 'decision': decision,
            'rationale': 'Synthetic software contract control; not a human assessment.',
            'context_sha256': adj.review_context(rig['data'], rig['data']['relations'][0]),
            'evidence': [{'entity': e['id'], 'field': f}
                         for e in rig['data']['entities'] for f, v in e['scope'].items() if v is not None]}


def reviews(rig, first='PARTIAL', second='PARTIAL'):
    rig['data']['relations'][0]['reviews'] = [ballot(rig, 'reviewer-a', first), ballot(rig, 'reviewer-b', second)]


def adjudicate(rig, decision='PARTIAL'):
    relation = rig['data']['relations'][0]
    relation['adjudication'] = {**ballot(rig, 'reviewer-c', decision),
                               'review_sha256': sorted(adj.replay.digest(adj.replay.canonical(v))
                                                       for v in relation['reviews'])}


def test_unreviewed_and_agreed_records_remain_hold(rig):
    assert check(rig)['relations'][0]['state'] == 'AWAITING_REVIEWS'
    reviews(rig); result = check(rig)
    assert result['relations'][0]['state'] == 'AGREEMENT_RECORDED'
    assert result['relations'][0]['decision'] == 'PARTIAL'
    assert result['release_eligible'] is False and result['pooling_readiness'] == 'HOLD'
    assert result['scientific_validity'] == 'NOT_ESTABLISHED'
    assert result['reviewer_identity'] == 'DECLARED_NOT_AUTHENTICATED'
    assert result['semantic_support'] == 'NOT_ASSESSED'
    assert check(rig) == result
    assert len(result['reports']) == 1
    assert result['entities'][0]['scope']['definition']['snapshot_sha256']


@pytest.mark.parametrize('decision', ['SAME', 'PARTIAL', 'DISJOINT', 'UNCLEAR'])
def test_cohort_decisions_and_unclear(rig, decision):
    reviews(rig, decision, decision); r = check(rig)['relations'][0]
    assert r['state'] == ('UNRESOLVED' if decision == 'UNCLEAR' else 'AGREEMENT_RECORDED')
    assert r['decision'] == (None if decision == 'UNCLEAR' else decision)


@pytest.mark.parametrize('decision', ['EQUIVALENT', 'DIFFERENT', 'UNCLEAR'])
def test_outcome_decisions(rig, decision):
    for e in rig['data']['entities']:
        e['kind'] = 'outcome'; e['scope']['measure'] = deepcopy(e['scope']['definition'])
    rig['data']['relations'][0]['kind'] = 'outcome_equivalence'
    reviews(rig, decision, decision)
    assert check(rig)['relations'][0]['state'] == ('UNRESOLVED' if decision == 'UNCLEAR' else 'AGREEMENT_RECORDED')


def test_disagreement_and_third_reviewer_preserve_original_ballots(rig):
    reviews(rig, 'PARTIAL', 'DISJOINT')
    assert check(rig)['relations'][0]['state'] == 'DISAGREEMENT'
    adjudicate(rig); result = check(rig)['relations'][0]
    assert result['state'] == 'ADJUDICATION_RECORDED'
    assert result['reviews'] == rig['data']['relations'][0]['reviews']
    assert result['adjudication'] == rig['data']['relations'][0]['adjudication']


def test_missing_scope_cannot_resolve(rig):
    rig['data']['entities'][1]['scope']['timepoint'] = None
    reviews(rig); result = check(rig)['relations'][0]
    assert result['state'] == 'INCOMPLETE_SCOPE' and result['decision'] is None


@pytest.mark.parametrize('mutation', ['same_reviewer', 'self_adjudication', 'stale_ballot',
    'stale_adjudication', 'missing_endpoint', 'unknown_field', 'unknown_decision', 'blank_rationale',
    'empty_evidence', 'unbound_evidence', 'third_ballot', 'premature_adjudication'])
def test_bad_decisions_refused(rig, mutation):
    reviews(rig, 'PARTIAL', 'DISJOINT'); adjudicate(rig); r = rig['data']['relations'][0]
    if mutation == 'same_reviewer': r['reviews'][1]['reviewer'] = 'reviewer-a'
    if mutation == 'self_adjudication': r['adjudication']['reviewer'] = 'reviewer-a'
    if mutation == 'stale_ballot': rig['data']['entities'][0]['scope']['timepoint'] = None
    if mutation == 'stale_adjudication': r['reviews'][0]['rationale'] = 'Changed judgment rationale'
    if mutation == 'missing_endpoint': r['reviews'][0]['evidence'] = [v for v in r['reviews'][0]['evidence'] if v['entity'] == 'baseline']
    if mutation == 'unknown_field': r['reviews'][0]['approved'] = True
    if mutation == 'unknown_decision': r['reviews'][0]['decision'] = 'EQUIVALENT'
    if mutation == 'blank_rationale': r['reviews'][0]['rationale'] = ' '
    if mutation == 'empty_evidence': r['reviews'][0]['evidence'] = []
    if mutation == 'unbound_evidence': r['reviews'][0]['evidence'][0]['field'] = 'fiction'
    if mutation == 'third_ballot': r['reviews'].append(ballot(rig, 'reviewer-d', 'SAME'))
    if mutation == 'premature_adjudication': r['reviews'].pop()
    with pytest.raises(adj.Refused): check(rig)


@pytest.mark.parametrize('mutation', ['self_pair', 'reverse_pair', 'wrong_type', 'duplicate_entity',
    'unknown_report', 'extra_bundle', 'empty_relations', 'unused_entity', 'duplicate_report',
    'false_quote', 'wrong_locator', 'missing_definition', 'unknown_scope'])
def test_bad_structure_and_bindings(rig, mutation):
    d = rig['data']; r = d['relations'][0]; e = d['entities'][0]
    if mutation == 'self_pair': r['right'] = r['left']
    if mutation == 'reverse_pair': d['relations'].append({**r, 'id': 'reversed', 'left': r['right'], 'right': r['left']})
    if mutation == 'wrong_type': r['kind'] = 'outcome_equivalence'
    if mutation == 'duplicate_entity': d['entities'].append(deepcopy(e))
    if mutation == 'unknown_report': e['report'] = 'absent'
    if mutation == 'extra_bundle': rig['bundles']['unreviewed'] = rig['bundles']['stepwise']
    if mutation == 'empty_relations': d['relations'] = []
    if mutation == 'unused_entity': d['entities'].append({**deepcopy(e), 'id': 'unused'})
    if mutation == 'duplicate_report':
        d['reports'].append({**d['reports'][0], 'id': 'copy'})
        rig['bundles']['copy'] = rig['bundles']['stepwise']; d['entities'][1]['report'] = 'copy'
    if mutation == 'false_quote': e['scope']['definition']['quote'] = 'unreported exact text'
    if mutation == 'wrong_locator': e['scope']['definition']['locator'] = 'body p 1'
    if mutation == 'missing_definition': e['scope']['definition'] = None
    if mutation == 'unknown_scope': e['scope']['unsupported'] = None
    with pytest.raises(adj.Refused): check(rig)


@pytest.mark.parametrize('field', ['decision', 'reviewer', 'context_sha256'])
@pytest.mark.parametrize('value', [True, 1, [], {}])
def test_malformed_scalars(rig, field, value):
    reviews(rig); rig['data']['relations'][0]['reviews'][0][field] = value
    with pytest.raises(adj.Refused): check(rig)


def test_revalidation_rejects_changed_source_and_wrong_anchor(rig):
    original = check(rig); args = {k: rig[k] for k in ('dossier', 'bundles', 'project')}
    args['expected_sha256'] = original['dossier_sha256']
    with pytest.raises(adj.Refused): adj.verify(**{**args, 'expected_sha256': '0' * 64})
    with pytest.raises(adj.Refused): adj.verify(**{**args, 'project': 'wrong-project'})
    p = next((rig['bundles']['stepwise'] / 'sources').glob('*.xml')); p.write_bytes(p.read_bytes() + b' ')
    with pytest.raises(adj.Refused): adj.verify(**args)


@pytest.mark.parametrize('target', ['dossier', 'source', 'code'])
def test_mid_audit_mutation(rig, monkeypatch, target):
    real = adj.replay.verify
    def mutate(*args):
        result = real(*args)
        if target == 'code': monkeypatch.setattr(adj, 'code_profile', lambda: {'changed': True})
        else:
            p = rig['dossier'] if target == 'dossier' else next((rig['bundles']['stepwise'] / 'sources').glob('*.xml'))
            p.write_bytes(p.read_bytes() + b' ')
        return result
    monkeypatch.setattr(adj.replay, 'verify', mutate)
    with pytest.raises(adj.Refused): check(rig)


def test_cli_new_process_determinism_and_refusal(rig, tmp_path):
    reviews(rig); result = check(rig)
    args = [sys.executable, str(SCRIPT), '--dossier', str(rig['dossier']), '--project', rig['project'],
            '--expected-sha256', result['dossier_sha256'], '--bundle', 'stepwise=' + str(rig['bundles']['stepwise'])]
    for _ in range(2):
        p = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=30)
        assert p.returncode == 0 and not p.stderr and json.loads(p.stdout) == result
    rig['dossier'].write_bytes(b'{}')
    p = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert p.returncode == 2 and not p.stderr and json.loads(p.stdout)['receipt'] is None


def test_storage_error_is_not_integrity_success(rig, monkeypatch):
    def broken(*args): raise OSError('injected I/O failure')
    monkeypatch.setattr(adj.replay, 'verify', broken)
    with pytest.raises(OSError): check(rig)


def test_valid_source_unicode_survives_legacy_windows_stdout(rig, tmp_path):
    bundle = tmp_path / 'strokewalk'
    shutil.copytree(ROOT / 'examples/synthesis-replay-strokewalk', bundle)
    rig['bundles'] = {'strokewalk': bundle}
    rig['data']['reports'] = [{'id': 'strokewalk', 'manifest_sha256':
        '3440da5463da48b023d7e85789a58035ba950e7c4a806a581b262490bf0e77f3'}]
    for e in rig['data']['entities']:
        e['report'] = 'strokewalk'
        for f in e['scope']:
            e['scope'][f] = {'quote': 'age \u2a7e18 years', 'locator': 'body p 6'}
    result = check(rig)
    p = subprocess.run([sys.executable, str(SCRIPT), '--dossier', str(rig['dossier']),
                        '--project', rig['project'], '--expected-sha256', result['dossier_sha256'],
                        '--bundle', 'strokewalk=' + str(bundle)],
                       env={**os.environ, 'PYTHONIOENCODING': 'cp1252'}, cwd=tmp_path,
                       capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert p.returncode == 0 and not p.stderr and json.loads(p.stdout) == result


def test_escaped_lone_surrogate_is_a_refusal(rig):
    reviews(rig)
    rig['data']['relations'][0]['reviews'][0]['rationale'] = 'invalid ' + chr(0xd800)
    raw = json.dumps(rig['data'], ensure_ascii=True).encode('utf-8')
    rig['dossier'].write_bytes(raw)
    with pytest.raises(adj.Refused, match='Unicode'):
        adj.verify(dossier=rig['dossier'], bundles=rig['bundles'], project=rig['project'],
                   expected_sha256=adj.replay.digest(raw))


@pytest.mark.parametrize('mutation', ['duplicate_key', 'nonfinite', 'oversized', 'unknown_field'])
def test_malformed_dossier_is_refused(rig, mutation):
    raw = adj.replay.canonical(rig['data'])
    if mutation == 'duplicate_key': raw = raw.replace(b'"schema":', b'"schema":"duplicate","schema":')
    if mutation == 'nonfinite': raw = raw.replace(b'"project":"development-control"', b'"project":NaN')
    if mutation == 'oversized': raw += b' ' * adj.LIMIT
    if mutation == 'unknown_field': raw = b'{"extra":true,' + raw[1:]
    rig['dossier'].write_bytes(raw)
    with pytest.raises(adj.Refused):
        adj.verify(dossier=rig['dossier'], bundles=rig['bundles'], project=rig['project'],
                   expected_sha256=adj.replay.digest(raw))


def test_real_unreviewed_example_and_documented_anchor():
    result = adj.verify(dossier=ROOT / 'examples/synthesis-adjudication-stepwise.json',
                        bundles={'stepwise': ROOT / 'examples/synthesis-replay-stepwise'},
                        project='stepwise-development',
                        expected_sha256='463ad965a725b508ebd2f6a54d0289dfe416ecc8c68a83a80067c7cd280552a0')
    assert result['relations'][0]['state'] == 'INCOMPLETE_SCOPE'
    assert result['relations'][0]['reviews'] == []
    assert result['relations'][0]['adjudication'] is None
    assert result['release_eligible'] is False
