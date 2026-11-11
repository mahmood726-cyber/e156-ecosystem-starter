"""Synthetic integration controls, not real publications or scientific validation."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import synthesis_replay as replay


XML = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<article-id pub-id-type="pmcid">PMC123</article-id>
<article-id pub-id-type="pmcid-ver">PMC123.2</article-id>
<article-id pub-id-type="doi">10.1234/synthetic</article-id>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>
</article-meta></front><body><p>Synthetic counts by arm.</p>
<table-wrap id="counts"><table><tbody><tr><td>10</td><td>11</td><td>21</td></tr>
</tbody></table></table-wrap></body></article>'''
PROMPT = b'Synthetic replay control; no scientific finding.\n'


def packet(payload=XML):
    def cell(n): return {'table': 1, 'row': 1, 'cell': n}
    return {
        'schema_version': '1.1',
        'run': {'run_id': 'synthetic-replay', 'model_id': 'none', 'model_provider': 'manual',
                'tool_versions': {}, 'fixture_kind': 'synthetic_development_control',
                'prompt_sha256': sha256(PROMPT).hexdigest()},
        'document': {'identifier': '10.1234/synthetic', 'pmcid': 'PMC123', 'version': 'PMC123.2'},
        'sources': [{'id': 'main', 'access': 'ACCESSIBLE', 'full_text_checked': True,
                     'version': 'PMC123.2', 'retrieval_path': 'synthetic local XML',
                     'retrieved_at': '2026-11-11', 'locator': 'body table-wrap 1'}],
        'claims': [{'id': 'synthetic-C1', 'text': 'Synthetic arm total.', 'locator': 'body p 1',
                    'source_ids': ['main'], 'source_support': 'SUPPORTED', 'evidence_maturity': 'SOURCE_BACKED',
                    'priority': 'P4', 'proposed_disposition': 'NO_FLAG',
                    'participant_count_check': {
                        'kind': 'UNIQUE_ARMS', 'context_quote': 'Synthetic counts by arm.',
                        'scope_verified': True, 'snapshot_sha256': sha256(payload).hexdigest(),
                        'outcome': 'Synthetic outcome', 'timepoint': 'Synthetic visit', 'basis': 'Synthetic people',
                        'reported': cell(3), 'arms': [
                            {'trial': 'Synthetic trial', 'cohort': 'Synthetic cohort', 'arm': 'A', 'count': cell(1)},
                            {'trial': 'Synthetic trial', 'cohort': 'Synthetic cohort', 'arm': 'B', 'count': cell(2)}]}}],
        'deterministic_checks': [],
    }


@pytest.fixture
def rig(tmp_path, monkeypatch):
    # An attempted network call is a test failure, not a fake successful response.
    def forbidden(*args, **kwargs): raise AssertionError('replay attempted network')
    monkeypatch.setattr(replay.capture, 'build_opener', forbidden)
    inputs = tmp_path/'inputs'
    inputs.mkdir()
    (inputs/'packet.json').write_text(json.dumps(packet()), encoding='utf-8')
    (inputs/'prompt.md').write_bytes(PROMPT)
    (inputs/'article.xml').write_bytes(XML)
    return inputs, tmp_path/'bundle'


def seal(rig):
    inputs, output = rig
    return replay.seal(inputs/'packet.json', inputs/'prompt.md', inputs/'article.xml', output)


def rewrite_packet(rig, change):
    path = rig[0]/'packet.json'
    p = json.loads(path.read_text())
    change(p)
    path.write_text(json.dumps(p), encoding='utf-8')


def test_real_preflight_roundtrip_and_relocated_bundle(rig, tmp_path):
    receipt = seal(rig)
    assert receipt['status'] == 'REPLAY_RECORDED'
    result = json.loads((rig[1]/'result.json').read_text())
    assert result['participant_count_findings'][0]['unique_participants'] == 21
    assert result['participant_count_findings'][0]['count_validity'] == 'NOT_INDEPENDENTLY_VERIFIED'
    relocated = tmp_path/'relocated'
    shutil.copytree(rig[1], relocated)
    assert replay.verify(relocated, receipt['manifest_sha256'])['status'] == 'REPLAY_MATCHED'
    assert replay.verify(rig[1], receipt['manifest_sha256'])['payload_sha256'] == receipt['payload_sha256']


def test_repeated_seals_have_identical_payload_and_manifest(rig, tmp_path):
    first = seal(rig)
    second = seal((rig[0], tmp_path/'second'))
    assert first == second
    assert (rig[1]/'manifest.json').read_bytes() == (tmp_path/'second/manifest.json').read_bytes()


def test_replayed_legacy_count_retains_scope_and_decision_hold(rig):
    seal(rig)
    result = json.loads((rig[1]/'result.json').read_bytes())
    finding = result['participant_count_findings'][0]
    assert finding['unique_participants'] == 21
    assert finding['scope_status'] == 'REVIEWER_ATTESTATION_ONLY'
    assert finding['decision_status'] == 'HOLD'
    assert result['ledger'][0]['effective'] == 'HOLD'


def test_intake_evidence_checks_require_a_separate_replay_contract(rig):
    rewrite_packet(rig, lambda p: p['claims'][0].update(evidence_checks=[]))
    with pytest.raises(replay.Refused, match='intake evidence checks'):
        seal(rig)
    assert not rig[1].exists()


@pytest.mark.parametrize('file', ['packet.json', 'prompt.md', 'result.json', 'source'])
def test_changed_artifact_refuses_before_replay(rig, file):
    receipt = seal(rig)
    target = next((rig[1]/'sources').iterdir()) if file == 'source' else rig[1]/file
    target.write_bytes(target.read_bytes()+b' ')
    with pytest.raises(replay.Refused, match='artifact'): replay.verify(rig[1], receipt['manifest_sha256'])


def test_rehashed_forgery_still_fails_external_manifest_digest(rig):
    receipt = seal(rig)
    manifest = rig[1]/'manifest.json'
    data = json.loads(manifest.read_text())
    data['artifacts']['result.json']['sha256'] = 'a'*64
    manifest.write_bytes(replay.canonical(data))
    with pytest.raises(replay.Refused, match='manifest'): replay.verify(rig[1], receipt['manifest_sha256'])


@pytest.mark.parametrize('expected', [None, '', 'a'*63, 'A'*64, '0'*64])
def test_missing_invalid_or_wrong_trust_anchor_refuses(rig, expected):
    seal(rig)
    with pytest.raises(replay.Refused): replay.verify(rig[1], expected)


def test_changed_verifier_refuses(rig, monkeypatch):
    receipt = seal(rig)
    monkeypatch.setattr(replay, 'code_profile', lambda: {'different': 'a'*64})
    with pytest.raises(replay.Refused, match='verifier'): replay.verify(rig[1], receipt['manifest_sha256'])


def test_matching_hashes_do_not_replace_execution(rig, monkeypatch):
    receipt = seal(rig)
    original = replay.preflight.review_packet
    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        result['participant_count_findings'][0]['unique_participants'] = 99
        return result
    monkeypatch.setattr(replay.preflight, 'review_packet', altered)
    with pytest.raises(replay.Refused, match='payload'): replay.verify(rig[1], receipt['manifest_sha256'])


@pytest.mark.parametrize('change', [
    lambda p: p['document'].update(identifier='10.1234/other'),
    lambda p: p['document'].update(version='PMC123.1'),
    lambda p: p['run'].update(prompt_sha256='0'*64),
    lambda p: p['sources'][0].update(version='PMC123.1'),
    lambda p: p['claims'][0]['participant_count_check'].update(snapshot_sha256='0'*64),
    lambda p: p['claims'][0]['participant_count_check']['reported'].update(row=99),
    lambda p: p['claims'][0]['participant_count_check'].update(context_quote='Missing quote'),
    lambda p: p['claims'][0]['participant_count_check'].update(scope_verified=False),
    lambda p: p['claims'][0].pop('participant_count_check'),
    lambda p: p['claims'][0].update(locator='invented location'),
    lambda p: p['claims'][0].update(source_ids=[]),
    lambda p: p['deterministic_checks'].append({'kind': 'unbound numeric check'}),
])
def test_unbound_inputs_never_create_a_bundle(rig, change):
    rewrite_packet(rig, change)
    with pytest.raises(replay.Refused): seal(rig)
    assert not rig[1].exists()


@pytest.mark.parametrize('replacement', [b'licenses/by-nc/4.0/', b'unknown/4.0/'])
def test_unknown_or_restricted_licence_refuses(rig, replacement):
    (rig[0]/'article.xml').write_bytes(XML.replace(b'licenses/by/4.0/', replacement))
    with pytest.raises(replay.Refused): seal(rig)
    assert not rig[1].exists()


def test_unresolved_correction_link_refuses(rig):
    payload = XML.replace(b'</article-meta>', b'<related-article related-article-type="correction-forward" ext-link-type="pmc" xlink:href="PMC124"/></article-meta>')
    (rig[0]/'article.xml').write_bytes(payload)
    rewrite_packet(rig, lambda p: p['claims'][0]['participant_count_check'].update(snapshot_sha256=sha256(payload).hexdigest()))
    with pytest.raises(replay.Refused, match='correction'): seal(rig)


def test_review_candidate_replays_without_becoming_a_pass(rig):
    payload = XML.replace(b'<td>21</td>', b'<td>25</td>')
    (rig[0]/'article.xml').write_bytes(payload)
    rewrite_packet(rig, lambda p: p['claims'][0]['participant_count_check'].update(snapshot_sha256=sha256(payload).hexdigest()))
    receipt = seal(rig)
    replay.verify(rig[1], receipt['manifest_sha256'])
    result = json.loads((rig[1]/'result.json').read_text())
    assert result['participant_count_findings'][0]['status'] == 'REVIEW_CANDIDATE'
    assert result['ledger'][0]['effective'] == 'HOLD'


def test_duplicate_json_keys_refuse(rig):
    p = rig[0]/'packet.json'
    p.write_text(p.read_text().replace('"schema_version": "1.1"', '"schema_version": "1.1", "schema_version": "1.1"'))
    with pytest.raises(replay.Refused, match='duplicate'): seal(rig)


def test_extra_file_and_incomplete_bundle_refuse(rig):
    receipt = seal(rig)
    (rig[1]/'unexpected.txt').write_text('not covered')
    with pytest.raises(replay.Refused, match='inventory'): replay.verify(rig[1], receipt['manifest_sha256'])
    (rig[1]/'unexpected.txt').unlink()
    (rig[1]/'prompt.md').unlink()
    with pytest.raises(replay.Refused): replay.verify(rig[1], receipt['manifest_sha256'])


def test_existing_output_is_never_overwritten(rig):
    receipt = seal(rig)
    with pytest.raises(replay.Refused): seal(rig)
    assert replay.verify(rig[1], receipt['manifest_sha256'])['status'] == 'REPLAY_MATCHED'


def test_linked_bundle_file_refuses(rig, monkeypatch):
    receipt = seal(rig)
    original = replay.linked
    monkeypatch.setattr(replay, 'linked', lambda p: p.name == 'prompt.md' or original(p))
    with pytest.raises(replay.Refused, match='link'): replay.verify(rig[1], receipt['manifest_sha256'])


def test_cli_uses_explicit_trust_anchor(rig):
    receipt = seal(rig)
    script = Path(replay.__file__)
    run = subprocess.run([sys.executable, str(script), 'verify', str(rig[1]),
                          '--expected-sha256', receipt['manifest_sha256']], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['status'] == 'REPLAY_MATCHED'


def test_all_local_import_dependencies_are_bound_in_profile():
    root = Path(replay.__file__).parent
    visited, pending = set(), ['synthesis_replay.py']
    while pending:
        name = pending.pop()
        if name in visited: continue
        visited.add(name)
        for node in ast.walk(ast.parse((root/name).read_text(encoding='utf-8'))):
            candidates = []
            if isinstance(node, ast.Import): candidates = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                candidates = [n.name for n in node.names] if node.module == 'scripts' else [node.module or '']
            for module in candidates:
                file = module.removeprefix('scripts.')+'.py'
                if (root/file).is_file(): pending.append(file)
    assert set(replay.CODE) == visited


@pytest.mark.parametrize('change', [
    lambda m: m.update(main_source='../escape.xml'),
    lambda m: m.update(correction_sources=[True]),
    lambda m: m['artifacts']['packet.json'].update(size=True),
    lambda m: m.update(sources={}),
])
def test_even_trusted_malformed_manifests_are_refused(rig, change):
    seal(rig)
    path = rig[1]/'manifest.json'
    m = json.loads(path.read_text())
    change(m)
    raw = replay.canonical(m)
    path.write_bytes(raw)
    with pytest.raises(replay.Refused): replay.verify(rig[1], sha256(raw).hexdigest())


def test_rehashed_output_cannot_substitute_for_recomputation(rig):
    seal(rig)
    output = rig[1]/'result.json'
    data = json.loads(output.read_text())
    data['participant_count_findings'][0]['unique_participants'] = 99
    raw = replay.canonical(data)
    output.write_bytes(raw)
    manifest = rig[1]/'manifest.json'
    m = json.loads(manifest.read_text())
    m['artifacts']['result.json'] = {'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    raw_manifest = replay.canonical(m)
    manifest.write_bytes(raw_manifest)
    with pytest.raises(replay.Refused, match='payload'):
        replay.verify(rig[1], sha256(raw_manifest).hexdigest())


def test_valid_linked_correction_is_archived_and_replayed(rig):
    payload = XML.replace(b'</article-meta>', b'<related-article related-article-type="correction-forward" ext-link-type="pmc" xlink:href="PMC124"/></article-meta>')
    correction = XML.replace(b'PMC123', b'PMC124').replace(b'10.1234/synthetic', b'10.1234/correction')
    correction = correction.replace(b'</article-meta>', b'<related-article related-article-type="corrected-article" ext-link-type="pmc" xlink:href="PMC123"/></article-meta>')
    (rig[0]/'article.xml').write_bytes(payload)
    sidecar = rig[0]/'correction.xml'
    sidecar.write_bytes(correction)
    rewrite_packet(rig, lambda p: p['claims'][0]['participant_count_check'].update(snapshot_sha256=sha256(payload).hexdigest()))
    receipt = replay.seal(rig[0]/'packet.json', rig[0]/'prompt.md', rig[0]/'article.xml', rig[1], [sidecar])
    assert len(list((rig[1]/'sources').iterdir())) == 2
    assert replay.verify(rig[1], receipt['manifest_sha256'])['status'] == 'REPLAY_MATCHED'


@pytest.mark.parametrize('literal', ['NaN', 'Infinity', '-Infinity', '1e999'])
def test_nonfinite_json_refuses_before_execution(rig, literal):
    path = rig[0]/'packet.json'
    path.write_text(path.read_text().replace('"scope_verified": true', '"scope_verified": '+literal))
    with pytest.raises(replay.Refused, match='nonfinite'): seal(rig)


def test_partial_write_has_no_completion_marker(rig, monkeypatch):
    original = Path.open
    def fail(path, *args, **kwargs):
        if path == rig[1]/'result.json' and args == ('xb',): raise OSError('synthetic disk failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail)
    with pytest.raises(OSError): seal(rig)
    assert not (rig[1]/'manifest.json').exists()
    assert (rig[1]/'packet.json').is_file()


@pytest.fixture
def identity_rig(rig):
    """Invented report/registry identities; only the integration contract is real."""
    inputs, _ = rig
    payload = XML.replace(b'</article-meta>', b'<article-id pub-id-type="pmid">12345</article-id></article-meta>')
    payload = payload.replace(b'<table-wrap', b'<p>This trial is registered as NCT00000001.</p><table-wrap')
    registry = {'protocolSection': {
        'identificationModule': {'nctId': 'NCT00000001'},
        'statusModule': {'lastUpdatePostDateStruct': {'date': '2026-01-02'}},
        'referencesModule': {'references': [{'pmid': '12345', 'type': 'RESULT'}]},
    }}
    raw = replay.canonical(registry)
    (inputs/'registry.json').write_bytes(raw)
    (inputs/'article.xml').write_bytes(payload)
    def update(p):
        p['claims'][0]['participant_count_check']['snapshot_sha256'] = sha256(payload).hexdigest()
        p['study_links'] = {'schema': 'e156-study-links-v1', 'links': [{
            'nct_id': 'NCT00000001', 'registry_sha256': sha256(raw).hexdigest(), 'reference_type': 'RESULT',
            'registration': {'quote': 'This trial is registered as NCT00000001.', 'locator': 'body p 2'}}]}
    rewrite_packet(rig, update)
    return rig


def identity_seal(rig, registries=None):
    inputs, output = rig
    return replay.seal(inputs/'packet.json', inputs/'prompt.md', inputs/'article.xml', output,
                       registry_json=registries if registries is not None else [inputs/'registry.json'])


def change_registry(rig, change):
    path = rig[0]/'registry.json'
    record = json.loads(path.read_bytes())
    change(record['protocolSection'])
    raw = replay.canonical(record)
    path.write_bytes(raw)
    rewrite_packet(rig, lambda p: p['study_links']['links'][0].update(registry_sha256=sha256(raw).hexdigest()))


def test_report_and_registry_link_replays_without_cohort_or_outcome_inference(identity_rig):
    receipt = identity_seal(identity_rig)
    root = identity_rig[1]
    assert json.loads((root/'manifest.json').read_bytes())['schema'] == 'e156-synthesis-replay-v2'
    graph = json.loads((root/'result.json').read_bytes())['study_links']
    assert graph['report']['pmid'] == '12345'
    assert graph['trials'][0]['nct_id'] == 'NCT00000001'
    assert graph['links'][0]['reference_type'] == 'RESULT'
    assert graph['links'][0]['registry_reference_locator'] == '/protocolSection/referencesModule/references/0'
    assert graph['cohort_overlap'] == graph['outcome_equivalence'] == 'UNASSESSED'
    assert graph['pooling_readiness'] == 'HOLD'
    assert replay.verify(root, receipt['manifest_sha256'])['status'] == 'REPLAY_MATCHED'


def test_derived_registry_reference_preserves_its_distinct_type(identity_rig):
    change_registry(identity_rig, lambda p: p['referencesModule']['references'][0].update(type='DERIVED'))
    rewrite_packet(identity_rig, lambda p: p['study_links']['links'][0].update(reference_type='DERIVED'))
    receipt = identity_seal(identity_rig)
    result = json.loads((identity_rig[1]/'result.json').read_bytes())
    assert result['study_links']['links'][0]['reference_type'] == 'DERIVED'
    assert result['study_links']['pooling_readiness'] == 'HOLD'
    replay.verify(identity_rig[1], receipt['manifest_sha256'])


@pytest.mark.parametrize('change', [
    lambda p: p['identificationModule'].update(nctId='NCT00000002'),
    lambda p: p['referencesModule']['references'][0].update(pmid='99999'),
    lambda p: p['referencesModule']['references'][0].update(type='BACKGROUND'),
    lambda p: p['referencesModule']['references'][0].update(type='DERIVED'),
    lambda p: p['referencesModule']['references'].append({'pmid': '12345', 'type': 'RESULT'}),
    lambda p: p['referencesModule'].update(references=[]),
    lambda p: p['statusModule']['lastUpdatePostDateStruct'].update(date='2026-02-30'),
    lambda p: p['statusModule']['lastUpdatePostDateStruct'].update(date='2026-01'),
    lambda p: p.pop('referencesModule'),
])
def test_disagreeing_or_incomplete_registry_refuses(identity_rig, change):
    change_registry(identity_rig, change)
    with pytest.raises(replay.Refused): identity_seal(identity_rig)
    assert not identity_rig[1].exists()


@pytest.mark.parametrize('change', [
    lambda l: l.update(nct_id='NCT00000002'),
    lambda l: l.update(nct_id='nct00000001'),
    lambda l: l.update(registry_sha256='0'*64),
    lambda l: l['registration'].update(locator='body p 99'),
    lambda l: l['registration'].update(quote='A missing registration quote'),
    lambda l: l.update(cohort_verified=True),
])
def test_unbound_identity_declaration_refuses(identity_rig, change):
    rewrite_packet(identity_rig, lambda p: change(p['study_links']['links'][0]))
    with pytest.raises(replay.Refused): identity_seal(identity_rig)


def test_missing_registry_and_unused_registry_refuse(identity_rig, rig):
    with pytest.raises(replay.Refused): seal(identity_rig)
    rewrite_packet(identity_rig, lambda p: p.pop('study_links'))
    with pytest.raises(replay.Refused): identity_seal(identity_rig)


def test_changed_registry_bytes_in_bundle_refuse(identity_rig):
    receipt = identity_seal(identity_rig)
    path = next((identity_rig[1]/'registries').iterdir())
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(replay.Refused, match='artifact'):
        replay.verify(identity_rig[1], receipt['manifest_sha256'])


def test_duplicate_links_and_duplicate_registry_inputs_refuse(identity_rig):
    rewrite_packet(identity_rig, lambda p: p['study_links']['links'].append(p['study_links']['links'][0]))
    with pytest.raises(replay.Refused): identity_seal(identity_rig)
    rewrite_packet(identity_rig, lambda p: p['study_links']['links'].pop())
    path = identity_rig[0]/'registry.json'
    with pytest.raises(replay.Refused): identity_seal(identity_rig, [path, path])


def test_one_ascii_space_in_printed_registration_is_explicitly_normalized(identity_rig):
    path = identity_rig[0]/'article.xml'
    raw = path.read_bytes().replace(b'NCT00000001', b'NCT 00000001')
    path.write_bytes(raw)
    def update(p):
        p['claims'][0]['participant_count_check']['snapshot_sha256'] = sha256(raw).hexdigest()
        p['study_links']['links'][0]['registration']['quote'] = 'This trial is registered as NCT 00000001.'
    rewrite_packet(identity_rig, update)
    identity_seal(identity_rig)
    graph = json.loads((identity_rig[1]/'result.json').read_bytes())['study_links']
    assert graph['links'][0]['registration_literal'] == 'NCT 00000001'
    assert graph['trials'][0]['nct_id'] == 'NCT00000001'


def test_ambiguous_registration_quote_refuses(identity_rig):
    path = identity_rig[0]/'article.xml'
    raw = path.read_bytes().replace(b'This trial is registered as NCT00000001.', b'NCT00000001 and NCT00000002 are cited.')
    path.write_bytes(raw)
    def update(p):
        p['claims'][0]['participant_count_check']['snapshot_sha256'] = sha256(raw).hexdigest()
        p['study_links']['links'][0]['registration']['quote'] = 'NCT00000001 and NCT00000002 are cited.'
    rewrite_packet(identity_rig, update)
    with pytest.raises(replay.Refused): identity_seal(identity_rig)


def registration_only(rig):
    def update(p):
        claim = p['claims'][0]
        claim.pop('participant_count_check')
        binding = p['study_links']['links'][0]['registration']
        claim.update(registered_trial='NCT00000001', text=binding['quote'], locator=binding['locator'])
    rewrite_packet(rig, update)


def test_identity_only_claim_replays_without_inventing_participant_counts(identity_rig):
    registration_only(identity_rig)
    receipt = identity_seal(identity_rig)
    result = json.loads((identity_rig[1]/'result.json').read_bytes())
    assert not result.get('participant_count_findings')
    assert result['study_links']['pooling_readiness'] == 'HOLD'
    assert replay.verify(identity_rig[1], receipt['manifest_sha256'])['status'] == 'REPLAY_MATCHED'


@pytest.mark.parametrize('change', [
    lambda p: p['claims'][0].update(registered_trial='NCT00000002'),
    lambda p: p['claims'][0].update(text='The treatment works.'),
    lambda p: p['claims'][0].update(locator='body p 1'),
    lambda p: p['claims'][0].update(participant_count_check={}),
    lambda p: p.pop('study_links'),
])
def test_identity_only_claim_requires_its_own_exact_registration_passage(identity_rig, change):
    registration_only(identity_rig)
    rewrite_packet(identity_rig, change)
    with pytest.raises(replay.Refused): identity_seal(identity_rig)
    assert not identity_rig[1].exists()


def test_null_identity_contract_is_not_silently_ignored(rig):
    rewrite_packet(rig, lambda p: p.update(study_links=None))
    with pytest.raises(replay.Refused): seal(rig)


def test_registry_link_requires_source_pmid(identity_rig):
    path = identity_rig[0]/'article.xml'
    raw = path.read_bytes().replace(b'<article-id pub-id-type="pmid">12345</article-id>', b'')
    path.write_bytes(raw)
    rewrite_packet(identity_rig, lambda p: p['claims'][0]['participant_count_check'].update(snapshot_sha256=sha256(raw).hexdigest()))
    with pytest.raises(replay.Refused, match='PMID'): identity_seal(identity_rig)


@pytest.mark.parametrize('raw', [b'[]', b'null', b'{"protocolSection":1,"protocolSection":2}', b'{"protocolSection":NaN}'])
def test_malformed_registry_json_refuses(identity_rig, raw):
    (identity_rig[0]/'registry.json').write_bytes(raw)
    rewrite_packet(identity_rig, lambda p: p['study_links']['links'][0].update(registry_sha256=sha256(raw).hexdigest()))
    with pytest.raises(replay.Refused): identity_seal(identity_rig)


@pytest.mark.parametrize('inventory', [[], ['../escape.json'], [True], ['registries/'+'0'*64+'.json']*2])
def test_trusted_but_malformed_registry_manifest_refuses(identity_rig, inventory):
    identity_seal(identity_rig)
    path = identity_rig[1]/'manifest.json'
    m = json.loads(path.read_bytes())
    m['registry_sources'] = inventory
    raw = replay.canonical(m)
    path.write_bytes(raw)
    with pytest.raises(replay.Refused): replay.verify(identity_rig[1], sha256(raw).hexdigest())


def test_one_report_can_link_two_trials_with_input_order_independent_replay(identity_rig, tmp_path):
    inputs, output = identity_rig
    path = inputs/'article.xml'
    raw = path.read_bytes().replace(b'<table-wrap', b'<p>Second trial: NCT00000002.</p><table-wrap')
    path.write_bytes(raw)
    other = (inputs/'registry.json').read_bytes().replace(b'NCT00000001', b'NCT00000002')
    (inputs/'second-registry.json').write_bytes(other)
    def update(p):
        p['claims'][0]['participant_count_check']['snapshot_sha256'] = sha256(raw).hexdigest()
        p['study_links']['links'].append({
            'nct_id': 'NCT00000002', 'registry_sha256': sha256(other).hexdigest(), 'reference_type': 'RESULT',
            'registration': {'quote': 'Second trial: NCT00000002.', 'locator': 'body p 3'}})
    rewrite_packet(identity_rig, update)
    registries = [inputs/'registry.json', inputs/'second-registry.json']
    receipt = identity_seal(identity_rig, registries)
    second = identity_seal((inputs, tmp_path/'second-bundle'), list(reversed(registries)))
    assert receipt == second
    graph = json.loads((output/'result.json').read_bytes())['study_links']
    assert len(graph['trials']) == 2
    assert graph['cohort_overlap'] == 'UNASSESSED'
    replay.verify(output, receipt['manifest_sha256'])
