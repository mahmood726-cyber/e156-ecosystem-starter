"""Synthetic only: policy and arithmetic regression/negative controls."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cvpr_synthetic_benchmark', ROOT / 'scripts' / 'cvpr_synthetic_benchmark.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
CASES = mod.load_fixture(ROOT / 'benchmarks' / 'cvpr' / 'worker09_synthetic.json')


def test_frozen_split_and_adjudicated_provenance():
    assert len(CASES) == 24
    assert len({c['case_id'] for c in CASES}) == 24
    assert sum(c['split'] == 'dev' for c in CASES) == 12
    assert sum(c['split'] == 'test' for c in CASES) == 12
    assert all(c['adjudication'] and c['source_version'] and c['comparison_version'] for c in CASES)
    assert all(c['fixture_type'] == 'invented_synthetic' and c['source_rights'] == 'first_party_synthetic' for c in CASES)


def test_synthetic_dev_baseline():
    r = mod.evaluate(CASES, 'dev')
    assert r['counts'] == {'tp': 5, 'fp': 0, 'fn': 0, 'tn': 5, 'abstained_adjudicated': 0,
                           'abstained_ambiguous': 2, 'flagged_ambiguous': 0, 'cleared_ambiguous': 0}


def test_frozen_heldout_baseline():
    r = mod.evaluate(CASES, 'test')
    assert r['counts'] == {'tp': 5, 'fp': 0, 'fn': 0, 'tn': 5, 'abstained_adjudicated': 0,
                           'abstained_ambiguous': 2, 'flagged_ambiguous': 0, 'cleared_ambiguous': 0}
    assert r['precision'] == r['recall_over_evaluable'] == r['specificity_over_evaluable'] == 1.0
    assert r['recall_wilson_95pct'][0] < 0.6


@pytest.mark.parametrize('id_suffix,expected', [('TEST-002','FLAG'),('TEST-004','FLAG'),('TEST-006','FLAG'),
                                               ('TEST-008','FLAG'),('TEST-010','FLAG'),('TEST-011','ABSTAIN'),('TEST-012','ABSTAIN')])
def test_regression_and_abstention(id_suffix, expected):
    c = next(c for c in CASES if c['case_id'].endswith(id_suffix))
    assert mod.assess(c)['prediction'] == expected


def test_fail_closed_non_synthetic():
    c = CASES[0].copy()
    for value in ('cvpr_paper', 'unknown', None):
        c['fixture_type'] = value
        with pytest.raises(ValueError, match='synthetic'):
            mod.assess(c)


def test_wrong_version_abstains():
    c = next(c for c in CASES if c['case_id'] == 'CVPR-W09-DEV-012')
    assert mod.assess(c)['prediction'] == 'ABSTAIN'


def test_missing_evidence_abstains():
    c = {**CASES[0], 'operands': {'numerator': '5'}}
    assert mod.assess(c)['prediction'] == 'ABSTAIN'


def test_duplicate_case_id_blocks_benchmark():
    with pytest.raises(ValueError, match='Duplicate'):
        mod.evaluate([CASES[0], CASES[0]], 'dev')


def test_zero_denominator_abstains():
    c = next(c for c in CASES if c['case_id'] == 'CVPR-W09-DEV-011')
    assert mod.assess(c)['prediction'] == 'ABSTAIN'


def test_nonfinite_json_blocks(tmp_path):
    p = tmp_path / 'bad.json'
    p.write_text('{"schema_version":1,"fixture_type":"invented_synthetic","rights":"first_party_synthetic","cases":[NaN]}')
    with pytest.raises(ValueError, match='Nonfinite'):
        mod.load_fixture(p)
