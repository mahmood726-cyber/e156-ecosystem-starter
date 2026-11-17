"""Portable deterministic checks for the standalone mathematical research replay."""
import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reviews" / "smd-covariance-2026-11-17"
spec = importlib.util.spec_from_file_location("smd_audit", BASE / "audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_published_equation_sign_reversal():
    assert audit.eq11(2, 2, .5, 50, 50) == pytest.approx(.030)
    assert audit.eq11(2, -2, -.5, 50, 50) == pytest.approx(-.010)
    assert audit.eq11(2, -2, -.5, 50, 50, True) == pytest.approx(-.025)


def test_j_direction_against_exact_gamma_ratio():
    assert audit.j_exact(18) == pytest.approx(.9576464270237166, abs=1e-12)
    assert audit.j_approx(18) < 1 < 1 / audit.j_approx(18)


@pytest.mark.parametrize("n1,n2,m", [(7, 12, 3), (9, 6, 2), (8, 13, 1), (10, 10, 10), (5, 9, 0)])
def test_overlap_trace_against_independent_centering_matrix_sum(n1, n2, m):
    # trace(H1 C H2 C') reduces to a sum over pairs of shared patients.
    direct = sum(((1 if i == j else 0) - 1 / n1) *
                 ((1 if i == j else 0) - 1 / n2) for i in range(m) for j in range(m))
    assert audit.overlap_trace(n1, n2, m) == pytest.approx(direct, abs=1e-12)


def test_full_overlap_and_disjoint_limits():
    assert audit.k_fixed((10, 10), (10, 10), 10, 10) == pytest.approx(1 / 9)
    assert audit.k_printed((10, 10), (10, 10)) == pytest.approx(1 / 19)
    assert audit.k_fixed((12, 17), (12, 17), 0, 0) == 0


def test_asymptotic_size_against_independent_tail_identity():
    result = audit.limiting_size(2, .5)
    assert result["true_n_variance"] == 3.5
    assert result["reported_n_variance"] == 2.75
    assert result["variance_ratio"] == pytest.approx(11 / 14)
    assert result["limiting_rejection_rate"] == pytest.approx(.082330282314393, abs=1e-12)


@pytest.mark.parametrize("rho", [-.8, -.1, .5, .9])
def test_zero_effect_calibration_control(rho):
    assert audit.limiting_size(0, rho)["limiting_rejection_rate"] == pytest.approx(.05, abs=1e-14)


def test_original_example_all_34_fingerprints():
    result = audit.example_scale()
    assert result["supplied_rows"] == 17 and result["values"] == 34
    assert result["maximum_fingerprint_residual"] < 1e-14
    case = next(x for x in result["checks"] if x["row"] == "Kaste 1994/120 mg" and x["outcome"] == "SBP")
    assert case["stored"] / case["stated_raw_d"] == pytest.approx(1 / math.sqrt(2))


@pytest.mark.parametrize("call", [lambda: audit.overlap_trace(2, 3, 3),
    lambda: audit.overlap_trace(1, 3, 0), lambda: audit.overlap_trace(4, 5, -1),
    lambda: audit.limiting_size(1, 1), lambda: audit.limiting_size(float("nan"), .5),
    lambda: audit.limiting_size(1, .5, 0)])
def test_invalid_inputs_fail_explicitly(call):
    with pytest.raises(ValueError):
        call()
