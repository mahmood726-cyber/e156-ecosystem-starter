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
    base.update({"value_unit": "1", "value_representation": "RAW_RATIO",
                 "value_identity_verified": True})
    base.update(overrides)
    return base


def candidate(**overrides):
    base = {"severity": "S3", "version": "FINAL_CURRENT", "source_access": "ACCESSIBLE",
            "source_locator": "Table 2", "source_support": "CONTRADICTED",
            "maturity": "SOURCE_BACKED", "alternative": "different population",
            "alternative_locator": "Methods 2.1", "alternative_result": "REFUTED",
            "estimator_status": "MATCHED", "root_cause_id": "CODE-001",
            "current_claim_verified": True,
            "current_correction_status": "NO_RELEVANT_CORRECTION"}
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

    def test_crossdocument_population_mismatch_fails_closed(self):
        # Before this gate, requesting endpoint alone would falsely flag a
        # mismatch between ITT and per-protocol numerators.
        out = m.cross_document(40, 50, sig(population="ITT"),
                               sig(population="per-protocol"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("population", out["fields"])

    def test_crossdocument_timepoint_mismatch_fails_closed(self):
        out = m.cross_document(40, 50, sig(time_window="30 days"),
                               sig(time_window="90 days"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("time_window", out["fields"])

    def test_crossdocument_estimand_mismatch_fails_closed(self):
        out = m.cross_document(40, 50, sig(estimand="treatment policy"),
                               sig(estimand="hypothetical"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("estimand", out["fields"])

    def test_crossdocument_measure_mismatch_fails_closed(self):
        out = m.cross_document(40, 50, sig(effect_measure="risk ratio"),
                               sig(effect_measure="risk difference"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("effect_measure", out["fields"])

    def test_crossdocument_missing_core_field_fails_closed(self):
        self.assertEqual(m.cross_document(
            40, 50, sig(population="UNKNOWN"), sig(), ("endpoint",)
        )["status"], "NOT_COMPARABLE")

    def test_crossdocument_extra_requested_field_remains_binding(self):
        out = m.cross_document(40, 50, sig(adjustment="none"),
                               sig(adjustment="site-stratified"),
                               ("endpoint", "adjustment"))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("adjustment", out["fields"])

    def test_crossdocument_empty_requested_fields_invalid(self):
        self.assertEqual(m.cross_document(40, 50, sig(), sig(), ())["status"],
                         "INVALID")

    def test_crossdocument_equivalent_physical_units_abstain(self):
        # 1 mg/L equals 1000 micrograms/L: raw values are NOT disagreeing claims.
        left = sig(effect_measure="mean serum concentration",
                   value_unit="mg/L", value_representation="RAW")
        right = sig(effect_measure="mean serum concentration",
                    value_unit="micrograms/L", value_representation="RAW")
        out = m.cross_document(1, 1000, left, right, ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("value_unit", out["fields"])

    def test_crossdocument_raw_vs_log_ratio_abstains(self):
        import math
        left = sig(value_representation="RAW_RATIO")
        right = sig(value_representation="LOG_RATIO")
        out = m.cross_document(2, math.log(2), left, right, ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("value_representation", out["fields"])

    def test_crossdocument_unverified_numeric_identity_abstains(self):
        self.assertEqual(m.cross_document(
            1, 2, sig(value_identity_verified=False), sig(), ("endpoint",)
        )["status"], "NOT_COMPARABLE")

    def test_crossdocument_missing_unit_abstains(self):
        self.assertEqual(m.cross_document(
            1, 2, sig(value_unit=None), sig(), ("endpoint",)
        )["status"], "NOT_COMPARABLE")

    def test_crossdocument_unknown_representation_abstains(self):
        self.assertEqual(m.cross_document(
            1, 2, sig(value_representation="UNKNOWN"), sig(), ("endpoint",)
        )["status"], "NOT_COMPARABLE")

    def test_crossdocument_real_injected_mismatch_still_review(self):
        left = sig(effect_measure="mean serum concentration",
                   value_unit="mg/L", value_representation="RAW")
        right = sig(effect_measure="mean serum concentration",
                    value_unit="mg/L", value_representation="RAW")
        self.assertEqual(m.cross_document(1, 2, left, right, ("endpoint",))
                         ["status"], "REVIEW")

    def test_crossdocument_clean_physical_match_remains_consistent(self):
        left = sig(effect_measure="mean serum concentration",
                   value_unit="mg/L", value_representation="RAW")
        right = sig(effect_measure="mean serum concentration",
                    value_unit="mg/L", value_representation="RAW")
        self.assertEqual(m.cross_document(1, 1, left, right, ("endpoint",))
                         ["status"], "CONSISTENT")


    def test_crossdocument_crude_vs_adjusted_benign(self):
        # Same endpoint/population/time, but two legitimate analysis models.
        out = m.cross_document(0.75, 0.68, sig(adjustment="none"),
                               sig(adjustment="site and age"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("adjustment", out["fields"])

    def test_crossdocument_model_mismatch_benign(self):
        out = m.cross_document(0.75, 0.68, sig(model="log-binomial"),
                               sig(model="Poisson robust"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("model", out["fields"])

    def test_crossdocument_multiplicity_adjustment_benign(self):
        out = m.cross_document(0.75, 0.68, sig(multiplicity="none"),
                               sig(multiplicity="Holm"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("multiplicity", out["fields"])

    def test_crossdocument_missingness_mismatch_benign(self):
        out = m.cross_document(0.75, 0.68, sig(missingness="complete case"),
                               sig(missingness="multiple imputation"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("missingness", out["fields"])

    def test_crossdocument_censoring_mismatch_benign(self):
        out = m.cross_document(0.12, 0.15, sig(censoring="administrative"),
                               sig(censoring="IPCW"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("censoring", out["fields"])

    def test_crossdocument_variance_mismatch_benign(self):
        out = m.cross_document(0.75, 0.68, sig(variance_method="sandwich"),
                               sig(variance_method="cluster robust"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("variance_method", out["fields"])

    def test_crossdocument_statistic_identity_mismatch_benign(self):
        out = m.cross_document(0.75, 0.68, sig(test_statistic_identity="primary RR"),
                               sig(test_statistic_identity="subgroup RR"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("test_statistic_identity", out["fields"])

    def test_crossdocument_unknown_adjustment_abstains(self):
        out = m.cross_document(0.75, 0.68, sig(adjustment="UNKNOWN"),
                               sig(adjustment="none"), ("endpoint",))
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("adjustment", out["fields"])

    def test_crossdocument_complete_identity_injected_discrepancy(self):
        # A deliberate synthetic mismatch still enters REVIEW, not a paper verdict.
        out = m.cross_document(0.75, 0.68, sig(), sig(), ("endpoint",))
        self.assertEqual(out["status"], "REVIEW")

    def test_crossdocument_complete_identity_clean_match(self):
        out = m.cross_document(0.75, 0.75, sig(), sig(), ("endpoint",))
        self.assertEqual(out["status"], "CONSISTENT")



def or_inputs(literal):
    """Synthetic attestations, NOT authenticated source evidence."""
    return dict(source_effect_measure="UNADJUSTED_ODDS_RATIO",
                effect_measure_verified=True, source_counts_verified=True,
                reported_or_text=literal, reported_rounding_rule="NEAREST_DECIMAL",
                reported_precision_verified=True)


class DeterministicTests(unittest.TestCase):
    def test_ci_reversal(self):
        self.assertEqual(m.ci_order(-586, -351, -821, "TWO_SIDED")["status"], "REVIEW")

    def test_point_outside_interval(self):
        # Deliberately injected discrepancy with method, signature and exactness verified.
        self.assertEqual(m.ci_order(10.5, 9.9, 10.2, "TWO_SIDED",
            ci_method="WALD_LINEAR", estimator_signature_matched=True,
            source_input_precision="EXACT")["status"], "REVIEW")

    def test_ci_unknown_method_abstains(self):
        # Old logic would falsely label this a discrepancy without CI method evidence.
        self.assertEqual(m.ci_order(10.5, 9.9, 10.2, "TWO_SIDED")["status"],
                         "NOT_COMPARABLE")

    def test_ci_bootstrap_bca_benign_challenger(self):
        # A non-Wald interval cannot be challenged using the Wald-linear gate.
        self.assertEqual(m.ci_order(1.0, 1.08, 1.20, "TWO_SIDED",
            ci_method="BOOTSTRAP_BCA", estimator_signature_matched=True,
            source_input_precision="EXACT")["status"], "NOT_COMPARABLE")

    def test_ci_rounded_source_abstains(self):
        # Apparent printed bound conflict may disappear with source rounding.
        self.assertEqual(m.ci_order(10.205, 10.21, 11.0, "TWO_SIDED",
            ci_method="WALD_LINEAR", estimator_signature_matched=True,
            source_input_precision="ROUNDED")["status"], "NOT_COMPARABLE")

    def test_ci_mismatched_estimand_abstains(self):
        self.assertEqual(m.ci_order(10.5, 9.9, 10.2, "TWO_SIDED",
            ci_method="WALD_LINEAR", estimator_signature_matched=False,
            source_input_precision="EXACT")["status"], "NOT_COMPARABLE")

    def test_ci_known_wald_clean_control(self):
        self.assertEqual(m.ci_order(10.0, 9.0, 11.0, "TWO_SIDED",
            ci_method="WALD_LINEAR", estimator_signature_matched=True,
            source_input_precision="EXACT")["status"], "CONSISTENT")

    def test_valid_interval(self):
        self.assertEqual(m.ci_order(1.0, 0.8, 1.2, "TWO_SIDED")["status"], "CONSISTENT")

    def test_interval_bad_input(self):
        self.assertEqual(m.ci_order("1.0", 0.8, 1.2, "TWO_SIDED")["status"], "INVALID")

    def test_crude_odds_ratio(self):
        self.assertEqual(m.crude_or(24, 43, 15, 53, 3.2, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True, **or_inputs("3.2"))["status"], "CONSISTENT")

    def test_crude_not_adjusted_estimator(self):
        self.assertEqual(m.crude_or(24, 43, 15, 53, 3.2, raw_estimator=False,
                                     population_match=True, endpoint_match=True, time_match=True, **or_inputs("3.2"))["status"], "NOT_COMPARABLE")

    def test_crude_or_warn_only(self):
        self.assertEqual(m.crude_or(24, 43, 15, 53, 1.2, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True, **or_inputs("1.2"))["status"], "REVIEW")

    def test_zero_event_abstains(self):
        self.assertEqual(m.crude_or(0, 43, 15, 53, 0.0, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True, **or_inputs("0.0"))["status"], "NOT_COMPARABLE")

    def test_fractional_count_invalid(self):
        self.assertEqual(m.crude_or(1.1, 43, 15, 53, 1.0, raw_estimator=True,
                                     population_match=True, endpoint_match=True, time_match=True, **or_inputs("1.0"))["status"], "INVALID")

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

    def test_r_factor_shift_alone_does_not_establish_paper_error(self):
        # R's factor codes are normally 1-based. Merely observing a shift is
        # not proof of a discrepancy with the article or affected output.
        self.assertEqual(m.factor_shift([0, 1, 0], [1, 2, 1],
                         verified_r_factor_conversion=True)["status"], "NOT_COMPARABLE")

    def test_code_not_available(self):
        self.assertEqual(m.factor_shift([0, 1], [1, 2], verified_r_factor_conversion=False)["status"], "NOT_COMPARABLE")

    def test_factor_noshift(self):
        self.assertEqual(m.factor_shift([0, 1], [0, 1], verified_r_factor_conversion=True)["status"], "CONSISTENT")



class PaperCodeFactorFidelityTests(unittest.TestCase):
    """Synthetic paper-code contrasts; none represent a verified journal error."""

    @staticmethod
    def evidence(**overrides):
        # Fabricated test provenance: paper version, specific source span,
        # paper-time code line and affected output are ALL only caller-attested.
        args = dict(verified_r_factor_conversion=True,
                    paper_claim_code_conflict_verified=True,
                    paper_source_locator="Synthetic VoR Methods sec 2; Table 3 row 1",
                    code_source_locator="Synthetic commit abc123 analysis.R:18",
                    analysis_identity_verified=True, affected_output_verified=True)
        args.update(overrides)
        return args

    def test_injected_source_backed_difference_is_review_candidate(self):
        # Deliberately planted: exact paper says outcome remains binary 0/1;
        # attested code numeric factor codes are used in incompatible output.
        out = m.factor_shift([0, 1, 0], [1, 2, 1], **self.evidence())
        self.assertEqual(out["status"], "REVIEW")

    def test_harmless_factor_level_display_is_not_a_paper_claim(self):
        # A common legal R representation; no asserted affected-result conflict.
        args = self.evidence(paper_claim_code_conflict_verified=False,
                             affected_output_verified=False)
        self.assertEqual(m.factor_shift([0, 1, 0], [1, 2, 1], **args)["status"],
                         "NOT_COMPARABLE")

    def test_paper_code_conflict_without_affected_output_abstains(self):
        args = self.evidence(affected_output_verified=False)
        self.assertEqual(m.factor_shift([0, 1], [1, 2], **args)["status"],
                         "NOT_COMPARABLE")

    def test_different_analysis_or_version_abstains(self):
        args = self.evidence(analysis_identity_verified=False)
        self.assertEqual(m.factor_shift([0, 1], [1, 2], **args)["status"],
                         "NOT_COMPARABLE")

    def test_missing_paper_span_abstains(self):
        args = self.evidence(paper_source_locator="  ")
        self.assertEqual(m.factor_shift([0, 1], [1, 2], **args)["status"],
                         "NOT_COMPARABLE")

    def test_missing_code_span_abstains(self):
        args = self.evidence(code_source_locator=None)
        self.assertEqual(m.factor_shift([0, 1], [1, 2], **args)["status"],
                         "NOT_COMPARABLE")

    def test_other_recoding_requires_paper_code_evidence_too(self):
        # Downstream numbers changed; without a paper conflict this remains
        # a code observation, not a proven publication discrepancy.
        self.assertEqual(m.factor_shift([0, 1, 0], [2, 1, 2],
                         verified_r_factor_conversion=True)["status"],
                         "NOT_COMPARABLE")
        self.assertEqual(m.factor_shift([0, 1, 0], [2, 1, 2],
                         **self.evidence())["status"], "REVIEW")

    def test_unmodified_factor_data_remains_benign(self):
        self.assertEqual(m.factor_shift([0, 1, 0], [0, 1, 0],
                         verified_r_factor_conversion=True)["status"],
                         "CONSISTENT")

    def test_invalid_category_inputs_still_invalid(self):
        self.assertEqual(m.factor_shift([0, True], [1, 2],
                         verified_r_factor_conversion=True)["status"], "INVALID")

    def test_nonbinary_source_abstains(self):
        self.assertEqual(m.factor_shift([0, 2], [1, 3],
                         verified_r_factor_conversion=True)["status"],
                         "NOT_COMPARABLE")


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

    def test_stale_claim_in_corrected_vor_reconciles(self):
        # Injected historical claim; current publisher correction removes it.
        out = m.gate(candidate(
            version="CORRECTED_LATEST", current_claim_verified=False,
            current_correction_status="RESOLVED_IN_PUBLISHED_VERSION",
            correction_locator="Current VoR correction notice, Table 2, test DOI",
            correction_source_verified=True))
        self.assertEqual(out["status"], "RECONCILED")

    def test_current_claim_in_corrected_vor_still_reviewable(self):
        # An injected contradiction persists after a different correction.
        out = m.gate(candidate(
            version="CORRECTED_LATEST", current_claim_verified=True,
            current_correction_status="CORRECTION_REVIEWED_CLAIM_PERSISTS"))
        self.assertEqual(out["status"], "FLAG_CANDIDATE")

    def test_unchecked_current_claim_holds(self):
        self.assertEqual(m.gate(candidate(current_claim_verified=False))["status"], "HOLD")

    def test_unknown_correction_history_holds(self):
        self.assertEqual(m.gate(candidate(current_correction_status="UNKNOWN"))["status"], "HOLD")

    def test_claimed_correction_without_source_holds(self):
        self.assertEqual(m.gate(candidate(
            version="CORRECTED_LATEST", current_claim_verified=False,
            current_correction_status="RESOLVED_IN_PUBLISHED_VERSION",
            correction_locator="unverified note",
            correction_source_verified=False))["status"], "HOLD")

    def test_claimed_correction_without_exact_locator_holds(self):
        self.assertEqual(m.gate(candidate(
            version="CORRECTED_LATEST", current_claim_verified=False,
            current_correction_status="RESOLVED_IN_PUBLISHED_VERSION",
            correction_locator="", correction_source_verified=True))["status"], "HOLD")

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

    def test_abstained_known_errors_not_hidden_from_flag_recall(self):
        # Injected known error deliberately held; one genuine flag alone does not
        # imply 100% automatic recall across known errors.
        rows = [{"claim_id": "a", "prediction": "FLAG", "reference": "ERROR"},
                {"claim_id": "b", "prediction": "HOLD", "reference": "ERROR"},
                {"claim_id": "c", "prediction": "NO_FLAG", "reference": "NO_ERROR"},
                {"claim_id": "d", "prediction": "HOLD", "reference": "NO_ERROR"},
                {"claim_id": "e", "prediction": "HOLD", "reference": "UNDETERMINED"},
                {"claim_id": "f", "prediction": "FLAG", "reference": "UNDETERMINED"}]
        out = m.outcome_counts(rows)
        self.assertEqual(out["sensitivity"], 1.0)  # legacy conditional metric
        self.assertEqual(out["flag_recall_including_abstentions"], .5)
        self.assertEqual(out["HOLD_ERROR"], 1)
        self.assertEqual(out["HOLD_NO_ERROR"], 1)
        self.assertEqual(out["HOLD_UNDETERMINED"], 1)
        self.assertEqual(out["FLAG_UNDETERMINED"], 1)
        self.assertEqual(out["reference_undetermined_total"], 2)
        self.assertEqual(out["reference_known_claims"], 4)
        self.assertAlmostEqual(out["reference_label_coverage"], 4/6)

    def test_false_alert_denominators_disclose_clean_abstentions(self):
        # One injected false alert plus two benign claims, one held.
        rows = [{"claim_id": "a", "prediction": "FLAG", "reference": "NO_ERROR"},
                {"claim_id": "b", "prediction": "HOLD", "reference": "NO_ERROR"},
                {"claim_id": "c", "prediction": "NO_FLAG", "reference": "NO_ERROR"}]
        out = m.outcome_counts(rows)
        self.assertEqual(out["false_alerts_per_100_adjudicated"], 50.0)
        self.assertAlmostEqual(out["false_alerts_per_100_reference_known"], 100/3)
        self.assertAlmostEqual(out["nonabstention_coverage"], 2/3)

    def test_unknown_references_do_not_imply_zero_performance(self):
        rows = [{"claim_id": "a", "prediction": "FLAG", "reference": "UNDETERMINED"},
                {"claim_id": "b", "prediction": "HOLD", "reference": "UNDETERMINED"}]
        out = m.outcome_counts(rows)
        self.assertIsNone(out["precision"])
        self.assertIsNone(out["flag_recall_including_abstentions"])
        self.assertIsNone(out["false_alerts_per_100_reference_known"])
        self.assertEqual(out["reference_undetermined_total"], 2)
        self.assertEqual(out["reference_label_coverage"], 0.0)

    def test_all_known_errors_held_not_counted_as_detected(self):
        rows = [{"claim_id": "a", "prediction": "HOLD", "reference": "ERROR"},
                {"claim_id": "b", "prediction": "NO_FLAG", "reference": "NO_ERROR"}]
        out = m.outcome_counts(rows)
        self.assertIsNone(out["sensitivity"])
        self.assertEqual(out["flag_recall_including_abstentions"], 0.0)
        self.assertEqual(out["known_error_claims"], 1)

    def test_duplicate_claim_id_rejected(self):
        rows = [{"claim_id": "1", "prediction": "FLAG", "reference": "ERROR"}]*2
        with self.assertRaises(ValueError):
            m.outcome_counts(rows)



class CleanPaperControlMetricTests(unittest.TestCase):
    """Synthetic bookkeeping only; labels are NOT independent human adjudications."""

    @staticmethod
    def paper(pid, ids, status="CLEAN_UNCHANGED", complete=True):
        return {"paper_id": pid, "claim_ids": ids, "control_status": status,
                "inventory_complete": complete}

    @staticmethod
    def claim(pid, cid, prediction, reference="NO_ERROR"):
        return {"paper_id": pid, "claim_id": cid,
                "prediction": prediction, "reference": reference}

    def test_injected_positive_and_clean_benign_control(self):
        papers = [self.paper("inj", ["a"], "OTHER"),
                  self.paper("clean", ["b", "c"])]
        claims = [self.claim("inj", "a", "FLAG", "ERROR"),
                  self.claim("clean", "b", "NO_FLAG"),
                  self.claim("clean", "c", "HOLD")]
        out = m.unchanged_control_false_alerts(papers, claims)
        self.assertEqual(out["eligible_complete_clean_papers"], 1)
        self.assertEqual(out["false_alert_papers_per_100_clean_papers"], 0)
        self.assertEqual(out["eligible_clean_claims"], 2)

    def test_flag_count_and_any_alert_paper_rates_diverge(self):
        papers = [self.paper("a", ["a1", "a2"]), self.paper("b", ["b1"])]
        claims = [self.claim("a", "a1", "FLAG"),
                  self.claim("a", "a2", "FLAG"),
                  self.claim("b", "b1", "NO_FLAG")]
        out = m.unchanged_control_false_alerts(papers, claims)
        self.assertEqual(out["false_alert_papers_per_100_clean_papers"], 50)
        self.assertEqual(out["false_alert_flags_per_100_clean_papers"], 100)
        self.assertAlmostEqual(out["false_alert_flags_per_100_clean_claims"], 200/3)

    def test_missing_claim_holds_paper_out_of_denominator(self):
        out = m.unchanged_control_false_alerts(
            [self.paper("a", ["1", "2"])],
            [self.claim("a", "1", "NO_FLAG")])
        self.assertEqual(out["held_clean_papers"], 1)
        self.assertIsNone(out["false_alert_papers_per_100_clean_papers"])

    def test_unknown_or_genuine_error_reference_is_not_clean(self):
        papers = [self.paper("a", ["1"]), self.paper("b", ["2"])]
        claims = [self.claim("a", "1", "FLAG", "UNDETERMINED"),
                  self.claim("b", "2", "NO_FLAG", "ERROR")]
        out = m.unchanged_control_false_alerts(papers, claims)
        self.assertEqual(out["held_clean_papers"], 2)
        self.assertEqual(out["eligible_complete_clean_papers"], 0)

    def test_incomplete_inventory_and_unknown_controls_not_silent_negatives(self):
        papers = [self.paper("a", ["1"]),
                  self.paper("b", ["2"], complete=False),
                  self.paper("c", ["3"], status="UNKNOWN")]
        claims = [self.claim("a", "1", "FLAG"),
                  self.claim("b", "2", "NO_FLAG"),
                  self.claim("c", "3", "NO_FLAG")]
        out = m.unchanged_control_false_alerts(papers, claims)
        self.assertEqual(out["declared_clean_unchanged_papers"], 2)
        self.assertEqual(out["held_clean_papers"], 1)
        self.assertEqual(out["false_alert_papers_per_100_clean_papers"], 100)


    def test_one_false_flag_with_three_abstentions_exposes_rate_gap(self):
        # Synthetic injection: one known false flag, three clean claims held.
        p = [self.paper("a", ["1", "2", "3", "4"])]
        c = [self.claim("a", "1", "FLAG")] + [
            self.claim("a", k, "HOLD") for k in ("2", "3", "4")]
        out = m.unchanged_control_false_alerts(p, c)
        self.assertEqual(out["eligible_clean_claims"], 4)
        self.assertEqual(out["eligible_clean_nonabstained_claims"], 1)
        self.assertEqual(out["eligible_clean_abstained_claims"], 3)
        self.assertEqual(out["eligible_clean_papers_with_abstentions"], 1)
        self.assertEqual(out["false_alert_flags_per_100_clean_claims"], 25)
        self.assertEqual(out["false_alert_flags_per_100_nonabstained_clean_claims"], 100)
        self.assertEqual(out["abstentions_per_100_clean_claims"], 75)
        self.assertEqual(out["clean_papers_with_abstentions_per_100"], 100)

    def test_same_operational_false_rate_without_holds_is_distinct(self):
        # Benign comparison: no held claims with the same single false flag.
        p = [self.paper("a", ["1", "2", "3", "4"])]
        c = [self.claim("a", "1", "FLAG")] + [
            self.claim("a", k, "NO_FLAG") for k in ("2", "3", "4")]
        out = m.unchanged_control_false_alerts(p, c)
        self.assertEqual(out["false_alert_flags_per_100_clean_claims"], 25)
        self.assertEqual(out["false_alert_flags_per_100_nonabstained_clean_claims"], 25)
        self.assertEqual(out["eligible_clean_abstained_claims"], 0)
        self.assertEqual(out["clean_papers_with_abstentions_per_100"], 0)

    def test_all_held_clean_claims_do_not_imply_good_conditional_precision(self):
        p = [self.paper("a", ["1", "2"])]
        c = [self.claim("a", "1", "HOLD"), self.claim("a", "2", "HOLD")]
        out = m.unchanged_control_false_alerts(p, c)
        self.assertEqual(out["false_alert_flags_per_100_clean_claims"], 0)
        self.assertIsNone(out["false_alert_flags_per_100_nonabstained_clean_claims"])
        self.assertEqual(out["abstentions_per_100_clean_claims"], 100)

    def test_incomplete_or_unknown_control_excluded_from_abstention_counts(self):
        p = [self.paper("a", ["1"], complete=False),
             self.paper("b", ["2"], status="UNKNOWN"),
             self.paper("c", ["3"])]
        c = [self.claim("a", "1", "HOLD"),
             self.claim("b", "2", "HOLD"),
             self.claim("c", "3", "NO_FLAG")]
        out = m.unchanged_control_false_alerts(p, c)
        self.assertEqual(out["held_clean_papers"], 1)
        self.assertEqual(out["eligible_clean_claims"], 1)
        self.assertEqual(out["eligible_clean_abstained_claims"], 0)
        self.assertEqual(out["false_alert_flags_per_100_nonabstained_clean_claims"], 0)

    def test_empty_clean_corpus_has_unknown_abstention_rates(self):
        out = m.unchanged_control_false_alerts([], [])
        self.assertIsNone(out["abstentions_per_100_clean_claims"])
        self.assertIsNone(out["clean_papers_with_abstentions_per_100"])
        self.assertIsNone(out["false_alert_flags_per_100_nonabstained_clean_claims"])

    def test_duplicate_claim_rejected(self):
        paper = [self.paper("a", ["1"])]
        claim = self.claim("a", "1", "NO_FLAG")
        with self.assertRaises(ValueError):
            m.unchanged_control_false_alerts(paper, [claim, claim])

    def test_no_eligible_control_has_undefined_rate(self):
        out = m.unchanged_control_false_alerts([], [])
        self.assertIsNone(out["false_alert_papers_per_100_clean_papers"])
        self.assertEqual(out["eligible_complete_clean_papers"], 0)




class CrudeORPrecisionTests(unittest.TestCase):
    def test_benign_one_decimal_rounding_old_false_alert(self):
        # 35/100 vs 20/100: exact OR=2.153846..., correctly printed as 2.2.
        # Old absolute tolerance 0.02 would incorrectly REVIEW.
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.2,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **or_inputs("2.2"))["status"], "CONSISTENT")

    def test_injected_two_decimal_inaccuracy_old_tolerance_missed(self):
        # Correct OR=2.153846... -> 2.15, not the injected 2.17.
        # Old absolute tolerance 0.02 incorrectly accepted this report.
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.17,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **or_inputs("2.17"))["status"], "REVIEW")

    def test_risk_ratio_is_not_a_crude_odds_ratio(self):
        # 35/100 divided by 20/100 gives RR=1.75, a legitimate alternate
        # estimand; comparing it against crude OR=2.153846 is inappropriate.
        evidence = or_inputs("1.75")
        evidence["source_effect_measure"] = "RISK_RATIO"
        self.assertEqual(m.crude_or(35, 100, 20, 100, 1.75,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **evidence)["status"], "NOT_COMPARABLE")

    def test_missing_source_effect_measure_abstains(self):
        evidence = or_inputs("2.17")
        evidence["source_effect_measure"] = None
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.17,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **evidence)["status"], "NOT_COMPARABLE")

    def test_unknown_rounding_rule_abstains(self):
        evidence = or_inputs("2.17")
        evidence["reported_rounding_rule"] = "UNKNOWN"
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.17,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **evidence)["status"], "NOT_COMPARABLE")

    def test_ocr_ambiguous_literal_abstains(self):
        evidence = or_inputs("2,l7")
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.17,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **evidence)["status"], "NOT_COMPARABLE")

    def test_source_literal_numeric_mismatch_is_invalid(self):
        evidence = or_inputs("2.15")
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.17,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **evidence)["status"], "INVALID")

    def test_fixed_tolerance_override_cannot_bypass_precision(self):
        self.assertEqual(m.crude_or(35, 100, 20, 100, 2.17,
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, tolerance=0.2, **or_inputs("2.17"))["status"],
            "NOT_COMPARABLE")



class ExactIntegerPrecisionTests(unittest.TestCase):
    """Controlled numeric witnesses, not blinded or real-paper findings."""

    @staticmethod
    def count_sig():
        return sig(effect_measure="EVENT_COUNT", test_statistic_identity="COUNT",
                   value_unit="participants", value_representation="INTEGER_COUNT")

    def test_injected_large_one_count_discrepancy_no_longer_hidden(self):
        # IEEE-754 float(2**53+1) == float(2**53): old code said CONSISTENT.
        x, y = 2**53 + 1, 2**53
        self.assertEqual(m.cross_document(
            x, y, self.count_sig(), self.count_sig(), ("endpoint",))["status"],
            "REVIEW")

    def test_untouched_large_identical_integer_counts_remain_consistent(self):
        x = 2**53 + 1
        self.assertEqual(m.cross_document(
            x, x, self.count_sig(), self.count_sig(), ("endpoint",))["status"],
            "CONSISTENT")

    def test_exact_integer_tolerance_one_allows_one_count_difference(self):
        self.assertEqual(m.cross_document(
            2**53+1, 2**53, self.count_sig(), self.count_sig(),
            ("endpoint",), tolerance=1)["status"], "CONSISTENT")

    def test_exact_integer_tolerance_one_still_detects_two_counts(self):
        self.assertEqual(m.cross_document(
            2**53+2, 2**53, self.count_sig(), self.count_sig(),
            ("endpoint",), tolerance=1)["status"], "REVIEW")

    def test_lossy_mixed_float_and_exact_integer_abstains(self):
        self.assertEqual(m.cross_document(
            float(2**53), 2**53+1, self.count_sig(), self.count_sig(),
            ("endpoint",))["status"], "NOT_COMPARABLE")

    def test_large_float_pair_abstains_even_if_equal(self):
        self.assertEqual(m.cross_document(
            float(2**53), float(2**53), self.count_sig(), self.count_sig(),
            ("endpoint",))["status"], "NOT_COMPARABLE")

    def test_small_float_comparisons_preserved(self):
        s = sig(value_unit="1", value_representation="RAW_RATIO")
        self.assertEqual(m.cross_document(
            0.75, 0.75, s, s, ("endpoint",))["status"], "CONSISTENT")
        self.assertEqual(m.cross_document(
            0.75, 0.68, s, s, ("endpoint",))["status"], "REVIEW")

    def test_negative_exact_integer_tolerance_invalid(self):
        self.assertEqual(m.cross_document(
            10, 10, self.count_sig(), self.count_sig(),
            ("endpoint",), tolerance=-1)["status"], "INVALID")

    def test_boolean_input_still_invalid(self):
        self.assertEqual(m.cross_document(
            True, 1, self.count_sig(), self.count_sig(),
            ("endpoint",))["status"], "INVALID")


class CrudeORExactCountTests(unittest.TestCase):
    """Synthetic regression, not a human-adjudicated research claim."""

    @staticmethod
    def large_counts():
        # Native integer inputs: every limb matters. True OR is exactly 3.
        base = 2**53
        return base+1, base+2, base+1, base+4

    @staticmethod
    def check(counts, shown):
        return m.crude_or(*counts, float(shown),
            raw_estimator=True, population_match=True, endpoint_match=True,
            time_match=True, **or_inputs(shown))

    def test_correct_large_integer_or_no_longer_false_alert(self):
        # Prior float(count) gate turned genuine OR 3 into computed OR 2.
        self.assertEqual(self.check(self.large_counts(), "3.0")["status"], "CONSISTENT")

    def test_injected_wrong_or_no_longer_false_negative(self):
        # A deliberately misprinted 2.0 previously agreed with lossy count arithmetic.
        self.assertEqual(self.check(self.large_counts(), "2.0")["status"], "REVIEW")

    def test_native_large_integer_count_is_exact(self):
        self.assertEqual(m.nonnegative_count(2**53+1), 2**53+1)

    def test_large_floating_count_abstains(self):
        a, n1, c, n0 = self.large_counts()
        out = self.check((float(a), n1, c, n0), "3.0")
        self.assertEqual(out["status"], "NOT_COMPARABLE")
        self.assertIn("precision", out["reason"])

    def test_even_large_floating_count_abstains(self):
        a, n1, c, n0 = self.large_counts()
        self.assertEqual(self.check((a, float(n1), c, n0), "3.0")["status"],
                         "NOT_COMPARABLE")

    def test_safe_float_counts_remain_accepted(self):
        self.assertEqual(self.check((35.0, 100.0, 20.0, 100.0), "2.15")["status"],
                         "CONSISTENT")

    def test_fractional_counts_remain_invalid(self):
        self.assertEqual(self.check((35.5, 100, 20, 100), "2.15")["status"],
                         "INVALID")

    def test_negative_counts_remain_invalid(self):
        self.assertEqual(self.check((-1, 100, 20, 100), "2.15")["status"],
                         "INVALID")

    def test_bool_counts_remain_invalid(self):
        self.assertEqual(self.check((True, 100, 20, 100), "2.15")["status"],
                         "INVALID")

    def test_zero_cell_still_abstains(self):
        self.assertEqual(self.check((0, 100, 20, 100), "2.15")["status"],
                         "NOT_COMPARABLE")


if __name__ == "__main__":
    unittest.main()
