"""Synthetic-only tests of conservative Synthesis v1.3 candidate gates.

Passing these tests does not establish real-world error-detection accuracy.
"""
import unittest

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "synthesis_v13_checks", Path(__file__).resolve().parents[1] / "scripts" / "synthesis_v13_checks.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sig(**overrides):
    base = dict(zip(m.ESTIMATOR_FIELDS, (
        "adult ITT", "30-day mortality", "day 30", "risk ratio", "ITT", "GLM",
        "none", "none", "complete", "none", "sandwich", "main RR",
    )))
    base.update(overrides)
    return base


def candidate(**overrides):
    base = {"severity": "S3", "version": "FINAL_CURRENT", "source_access": "ACCESSIBLE",
            "source_locator": "Table 2", "source_support": "CONTRADICTED",
            "maturity": "SOURCE_BACKED", "alternative": "different population",
            "alternative_locator": "Methods 2.1", "alternative_result": "REFUTED",
            "estimator_status": "MATCHED", "root_cause_id": "CODE-001"}
    base.update(overrides)
    return base


class EstimatorTests(unittest.TestCase):
    def test_full_match(self):
        self.assertEqual(m.compatible(sig(), sig())["status"], "MATCHED")

    def test_km_vs_crude(self):
        self.assertEqual(m.compatible(sig(effect_measure="KM probability"), sig())["status"], "NOT_COMPARABLE")

    def test_mitt_vs_itt(self):
        self.assertIn("population", m.compatible(sig(population="mITT"), sig())["fields"])

    def test_unknown_statistic(self):
        self.assertIn("test_statistic_identity", m.compatible(sig(test_statistic_identity="UNKNOWN"), sig())["fields"])

    def test_invalid_signature(self):
        self.assertEqual(m.compatible([], sig())["status"], "INVALID")

    def test_restricted_crossdocument_equality(self):
        self.assertEqual(m.cross_document(40, 40, sig(), sig(), ("population", "endpoint"))["status"], "CONSISTENT")

    def test_crossdocument_uses_identity(self):
        self.assertEqual(m.cross_document(40, 50, sig(endpoint="A"), sig(endpoint="B"), ("endpoint",))["status"], "NOT_COMPARABLE")

    def test_crossdocument_numeric_mismatch(self):
        self.assertEqual(m.cross_document(40, 50, sig(), sig(), ("endpoint",))["status"], "REVIEW")


class DeterministicTests(unittest.TestCase):
    def test_ci_reversal(self):
        self.assertEqual(m.ci_order(-586, -351, -821, "TWO_SIDED")["status"], "REVIEW")

    def test_point_outside_interval(self):
        self.assertEqual(m.ci_order(10.5, 9.9, 10.2, "TWO_SIDED")["status"], "REVIEW")

    def test_valid_interval(self):
        self.assertEqual(m.ci_order(1.0, 0.8, 1.2, "TWO_SIDED")["status"], "CONSISTENT")

    def test_interval_bad_input(self):
        self.assertEqual(m.ci_order("1.0", 0.8, 1.2, "TWO_SIDED")["status"], "INVALID")

    def test_crude_odds_ratio(self):
        self.assertEqual(m.crude_or(24, 43, 15, 53, 3.2, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True)["status"], "CONSISTENT")

    def test_crude_not_adjusted_estimator(self):
        self.assertEqual(m.crude_or(24, 43, 15, 53, 3.2, raw_estimator=False,
                                     population_match=True, endpoint_match=True, time_match=True)["status"], "NOT_COMPARABLE")

    def test_crude_or_warn_only(self):
        self.assertEqual(m.crude_or(24, 43, 15, 53, 1.2, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True)["status"], "REVIEW")

    def test_zero_event_abstains(self):
        self.assertEqual(m.crude_or(0, 43, 15, 53, 0.0, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True)["status"], "NOT_COMPARABLE")

    def test_fractional_count_invalid(self):
        self.assertEqual(m.crude_or(1.1, 43, 15, 53, 1.0, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True)["status"], "INVALID")

    def test_normal_z(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.0455, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=0, alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True, reported_p_text="P=.0455",
            source_input_precision="EXACT")["status"], "CONSISTENT")

    def test_injected_wrong_p_is_review(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.25, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=0, alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True, reported_p_text="P=.25",
            source_input_precision="EXACT")["status"], "REVIEW")

    def test_nonzero_null_benign(self):
        # P=0.0455 corresponds to (3 - H0:1)/1, not 3/1.
        self.assertEqual(m.p_from_normal_z(3, 1, 0.0455, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=1, alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True, reported_p_text="P=.0455",
            source_input_precision="EXACT")["status"], "CONSISTENT")

    def test_one_sided_benign(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.02275, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=0, alternative="GREATER",
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True, reported_p_text="P=.02275",
            source_input_precision="EXACT")["status"], "CONSISTENT")

    def test_ratio_with_log_se_abstains(self):
        # Raw OR and SE(log OR) must not be treated as same-scale.
        self.assertEqual(m.p_from_normal_z(1.5, 0.2, 0.0426, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=1, alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LOG_RATIO",
            test_identity_verified=True)["status"], "NOT_COMPARABLE")

    def test_log_ratio_correct_scale(self):
        import math
        self.assertEqual(m.p_from_normal_z(math.log(1.5), 0.2, 0.0426,
            test_name="NORMAL_Z", multiplicity="NONE", null_value=0,
            alternative="TWO_SIDED", estimate_scale="LOG_RATIO",
            se_scale="LOG_RATIO", test_identity_verified=True, reported_p_text="P=.0426",
            source_input_precision="EXACT")["status"], "CONSISTENT")

    def test_missing_null_abstains(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.0455, test_name="NORMAL_Z",
            multiplicity="NONE", alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True)["status"], "NOT_COMPARABLE")

    def test_unverified_test_identity_abstains(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.0455, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=0, alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LINEAR")["status"], "NOT_COMPARABLE")

    def test_missing_tail_abstains(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.0455, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=0,
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True)["status"], "NOT_COMPARABLE")

    def test_tukey_not_comparable(self):
        self.assertEqual(m.p_from_normal_z(2, 1, 0.15, test_name="NORMAL_Z", multiplicity="TUKEY")["status"], "NOT_COMPARABLE")

    def test_wrong_statistic_identity(self):
        self.assertEqual(m.statistic_identity("HETEROGENEITY_Q", "OVERALL_EFFECT")["status"], "REVIEW")

    def test_unknown_statistic_abstains(self):
        self.assertEqual(m.statistic_identity("UNKNOWN", "OVERALL_EFFECT")["status"], "NOT_COMPARABLE")

    def test_r_factor_shift(self):
        self.assertEqual(m.factor_shift([0, 1, 0], [1, 2, 1], verified_r_factor_conversion=True)["status"], "REVIEW")

    def test_code_not_available(self):
        self.assertEqual(m.factor_shift([0, 1], [1, 2], verified_r_factor_conversion=False)["status"], "NOT_COMPARABLE")

    def test_factor_noshift(self):
        self.assertEqual(m.factor_shift([0, 1], [0, 1], verified_r_factor_conversion=True)["status"], "CONSISTENT")



class PublishedPPrecisionTests(unittest.TestCase):
    """Injected and untouched synthetic witnesses, not held-out real-paper labels."""

    def _z(self, z, reported, printed, precision="EXACT", bounds=None):
        return m.p_from_normal_z(z, 1, reported, test_name="NORMAL_Z",
            multiplicity="NONE", null_value=0, alternative="TWO_SIDED",
            estimate_scale="LINEAR", se_scale="LINEAR",
            test_identity_verified=True, reported_p_text=printed,
            source_input_precision=precision, expected_p_bounds=bounds)

    def test_threshold_crossing_now_review(self):
        # Old absolute tolerance .01 incorrectly accepted P=.049 at z=1.89.
        self.assertEqual(self._z(1.89, .049, "P=.049")["status"], "REVIEW")

    def test_nearest_precision_benign(self):
        self.assertEqual(self._z(1.96, .05, "P=.05")["status"], "CONSISTENT")

    def test_less_than_benign(self):
        self.assertEqual(self._z(3.5, .001, "P<.001")["status"], "CONSISTENT")

    def test_less_than_incompatible(self):
        self.assertEqual(self._z(2.5, .001, "P<.001")["status"], "REVIEW")

    def test_unknown_source_precision_abstains(self):
        self.assertEqual(self._z(1.96, .05, "P=.05", None)["status"], "NOT_COMPARABLE")

    def test_verified_rounded_statistic_range_benign(self):
        self.assertEqual(self._z(1.94, .05, "P=.05", "P_BOUNDS_VERIFIED",
                                 (.049, .055))["status"], "CONSISTENT")

    def test_missing_source_rounding_range_abstains(self):
        self.assertEqual(self._z(1.94, .05, "P=.05", "P_BOUNDS_VERIFIED")
                         ["status"], "NOT_COMPARABLE")

    def test_ocr_ambiguous_abstains(self):
        self.assertEqual(self._z(1.96, .05, "P=O.O5")["status"], "NOT_COMPARABLE")

    def test_literal_numeric_conflict_invalid(self):
        self.assertEqual(self._z(1.96, .25, "P=.05")["status"], "INVALID")

    def test_rounded_zero_not_exact_claim(self):
        # .000 can result from numerical rounding; journal formatting is separate.
        self.assertEqual(self._z(3.5, 0, "P=.000")["status"], "CONSISTENT")


class GovernanceTests(unittest.TestCase):
    def test_stale_preprint(self):
        self.assertEqual(m.version("PREPRINT_STALE")["status"], "HOLD")

    def test_current_corrected(self):
        self.assertEqual(m.version("CORRECTED_LATEST")["status"], "CURRENT")

    def test_complete_candidate_is_not_confirmed(self):
        self.assertEqual(m.gate(candidate())["status"], "FLAG_CANDIDATE")

    def test_refuted_by_method_not_a_flag(self):
        self.assertEqual(m.gate(candidate(source_support="SUPPORTED", alternative_result="SUPPORTED"))["status"], "RECONCILED")

    def test_missing_refutation_holds(self):
        self.assertEqual(m.gate(candidate(alternative_locator=None))["status"], "HOLD")

    def test_unavailable_source_holds(self):
        self.assertEqual(m.gate(candidate(source_access="UNAVAILABLE"))["status"], "HOLD")

    def test_corrected_preprint_holds(self):
        self.assertEqual(m.gate(candidate(version="PREPRINT_STALE"))["status"], "HOLD")

    def test_unmatched_estimator_holds(self):
        self.assertEqual(m.gate(candidate(estimator_status="NOT_COMPARABLE"))["status"], "HOLD")

    def test_group_one_root_multiple_outputs(self):
        rows = [{"claim_id": "A", "root_cause_id": "R1"}, {"claim_id": "B", "root_cause_id": "R1"},
                {"claim_id": "C", "root_cause_id": "R2"}]
        summary = m.root_cause_summary(rows)
        self.assertEqual((summary["root_causes"], summary["affected_outputs"]), (2, 3))

    def test_all_claims_in_denominator(self):
        rows = [{"claim_id": "1", "prediction": "FLAG", "reference": "ERROR"},
                {"claim_id": "2", "prediction": "FLAG", "reference": "NO_ERROR"},
                {"claim_id": "3", "prediction": "NO_FLAG", "reference": "ERROR"},
                {"claim_id": "4", "prediction": "NO_FLAG", "reference": "NO_ERROR"},
                {"claim_id": "5", "prediction": "HOLD", "reference": "UNDETERMINED"},
                {"claim_id": "6", "prediction": "NO_FLAG", "reference": "UNDETERMINED"}]
        out = m.outcome_counts(rows)
        self.assertEqual(out["all_claims"], 6)
        self.assertEqual(out["adjudicated_nonabstained"], 4)
        self.assertEqual((out["TP"], out["FP"], out["FN"], out["TN"]), (1, 1, 1, 1))
        self.assertEqual((out["HOLD"], out["UNKNOWN_REFERENCE"]), (1, 1))
        self.assertEqual(out["false_alerts_per_100_adjudicated"], 25)

    def test_duplicate_claim_id_rejected(self):
        rows = [{"claim_id": "1", "prediction": "FLAG", "reference": "ERROR"}]*2
        with self.assertRaises(ValueError):
            m.outcome_counts(rows)


if __name__ == "__main__":
    unittest.main()
