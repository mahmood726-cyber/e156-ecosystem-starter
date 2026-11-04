"""Synthetic NMA/IPD checks; no real trial or statistical replay is performed."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "synthesis_v13_nma_preflight",
    Path(__file__).resolve().parents[1] / "scripts" / "synthesis_v13_nma_preflight.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def effect(**changes):
    row = {
        "synthesis_id": "synthetic-NMA-A", "trial_family_id": "family-A",
        "cohort_id": "randomized-cohort-A", "endpoint": "mortality",
        "time_window": "day-30", "contrast_id": "A_vs_C",
        "source_version": "published-v1", "source_locator": "Table 2",
        "report_id": "report-1", "dependence_handling": "INDEPENDENT_UNCORRELATED",
        "same_cohort_source_verified": True, "included_as_independent_effect": True,
    }
    row.update(changes)
    return row


def contrast(**changes):
    row = {
        "trial_family_id": "family-A", "cohort_id": "randomized-cohort-A",
        "endpoint": "mortality", "time_window": "day-30",
        "control_arm_id": "control-C", "comparison_id": "A_vs_C",
        "analysis_model": "INDEPENDENT_UNCORRELATED",
        "source_locator": "Table 2", "control_identity_verified": True,
    }
    row.update(changes)
    return row


def replay(**changes):
    required = (
        "synthesis_id", "outcome", "source_version", "source_locator",
        "trial_family_matrix_reference", "original_event_data_reference",
        "endpoint_estimand_ledger_reference", "published_model_specification",
        "published_output_reference", "exact_replay_code_reference",
        "source_verified_extraction_receipt", "unique_population_receipt",
        "original_replay_result_reference", "corrected_replay_result_reference",
        "conclusion_sensitivity_reference", "rob2_reference", "rob_nma_reference",
        "transitivity_consistency_reference",
    )
    row = {k: f"synthetic-{k}" for k in required}
    row.update({
        "original_replay_completed": True,
        "corrected_replay_completed": True,
        "all_outcomes_verified": True,
    })
    row.update(changes)
    return row


class OverlapTests(unittest.TestCase):
    def test_repeated_independent_population_review(self):
        result = m.duplicate_trial_population([
            effect(), effect(report_id="report-2")
        ])
        self.assertEqual(result["status"], "REVIEW_CANDIDATE")

    def test_distinct_cohort_not_duplicate(self):
        result = m.duplicate_trial_population([
            effect(), effect(cohort_id="randomized-cohort-B", report_id="report-2")
        ])
        self.assertEqual(result["status"], "NO_FLAG")

    def test_different_endpoint_not_duplicate(self):
        result = m.duplicate_trial_population([
            effect(), effect(endpoint="hospitalization", report_id="report-2")
        ])
        self.assertEqual(result["status"], "NO_FLAG")

    def test_covariance_accounted_for_no_false_alarm(self):
        result = m.duplicate_trial_population([
            effect(dependence_handling="CORRELATION_ACCOUNTED_FOR"),
            effect(report_id="report-2", dependence_handling="CORRELATION_ACCOUNTED_FOR"),
        ])
        self.assertEqual(result["status"], "NO_FLAG")

    def test_mixed_three_reports_two_unaccounted_still_review(self):
        result = m.duplicate_trial_population([
            effect(), effect(report_id="report-2"),
            effect(report_id="report-3", dependence_handling="CORRELATION_ACCOUNTED_FOR"),
        ])
        self.assertEqual(result["status"], "REVIEW_CANDIDATE")

    def test_unknown_correlation_abstains(self):
        result = m.duplicate_trial_population([
            effect(), effect(report_id="report-2", dependence_handling="UNKNOWN"),
        ])
        self.assertEqual(result["status"], "HOLD")

    def test_unverified_cohort_identity_abstains(self):
        result = m.duplicate_trial_population([
            effect(), effect(report_id="report-2", same_cohort_source_verified=False),
        ])
        self.assertEqual(result["status"], "HOLD")


class SharedControlTests(unittest.TestCase):
    def test_shared_control_independent_model_candidate(self):
        result = m.shared_control_dependence([
            contrast(), contrast(comparison_id="B_vs_C"),
        ])
        self.assertEqual(result["status"], "REVIEW_CANDIDATE")

    def test_shared_control_covariance_accounted_for_is_clean(self):
        result = m.shared_control_dependence([
            contrast(analysis_model="CORRELATION_ACCOUNTED_FOR"),
            contrast(comparison_id="B_vs_C", analysis_model="CORRELATION_ACCOUNTED_FOR"),
        ])
        self.assertEqual(result["status"], "NO_FLAG")

    def test_different_control_arms_are_not_shared(self):
        result = m.shared_control_dependence([
            contrast(), contrast(comparison_id="B_vs_D", control_arm_id="control-D"),
        ])
        self.assertEqual(result["status"], "NO_FLAG")

    def test_two_unaccounted_contrasts_with_third_accounted_still_review(self):
        result = m.shared_control_dependence([
            contrast(), contrast(comparison_id="B_vs_C"),
            contrast(comparison_id="D_vs_C", analysis_model="CORRELATION_ACCOUNTED_FOR"),
        ])
        self.assertEqual(result["status"], "REVIEW_CANDIDATE")

    def test_unknown_model_abstains(self):
        result = m.shared_control_dependence([
            contrast(), contrast(comparison_id="B_vs_C", analysis_model="UNKNOWN"),
        ])
        self.assertEqual(result["status"], "HOLD")

    def test_control_identity_not_verified_abstains(self):
        result = m.shared_control_dependence([
            contrast(), contrast(comparison_id="B_vs_C", control_identity_verified=False),
        ])
        self.assertEqual(result["status"], "HOLD")


class RestrictedAccountingTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "source_version": "published-v1", "restriction_locator": "Methods, paragraph 2",
            "primary_locator": "Table 2, primary N", "restricted_locator": "Table 2, sensitivity N",
            "same_source_version_verified": True, "relationship": "RESTRICTION",
            "same_participant_count_basis_verified": True,
            "primary_participants": 100, "restricted_participants": 120,
        }

    def test_increased_count_returns_review_candidate_and_evidence(self):
        result = m.restricted_analysis_accounting(self.record)
        self.assertEqual(result["status"], "REVIEW_CANDIDATE")
        self.assertEqual(result["participant_excess"], 20)
        for locator in ("restriction_locator", "primary_locator", "restricted_locator"):
            self.assertEqual(result[locator], self.record[locator])

    def test_equal_or_smaller_count_does_not_flag(self):
        for count in (0, 99, 100):
            with self.subTest(count=count):
                row = dict(self.record, restricted_participants=count)
                self.assertEqual(m.restricted_analysis_accounting(row)["status"], "NO_FLAG")

    def test_expanded_analysis_is_not_comparable(self):
        row = dict(self.record, relationship="NOT_A_RESTRICTION")
        self.assertEqual(m.restricted_analysis_accounting(row)["status"], "NOT_COMPARABLE")

    def test_missing_or_mismatched_context_holds(self):
        for key, value in (("same_source_version_verified", False),
                           ("same_participant_count_basis_verified", False),
                           ("relationship", "UNKNOWN"), ("restriction_locator", ""),
                           ("primary_locator", ""), ("restricted_locator", "")):
            with self.subTest(key=key):
                row = dict(self.record, **{key: value})
                self.assertEqual(m.restricted_analysis_accounting(row)["status"], "HOLD")

    def test_non_integer_or_negative_counts_hold(self):
        for count in (True, 120.0, "120", -1, None):
            with self.subTest(count=count):
                row = dict(self.record, restricted_participants=count)
                self.assertEqual(m.restricted_analysis_accounting(row)["status"], "HOLD")


class ReplayReadinessTests(unittest.TestCase):
    def test_complete_receipts_not_a_replay_verdict(self):
        result = m.replay_readiness(replay())
        self.assertEqual(result["status"], "READY_FOR_INDEPENDENT_REVIEW")

    def test_missing_exact_replay_reference_holds(self):
        result = m.replay_readiness(replay(exact_replay_code_reference=""))
        self.assertEqual(result["status"], "HOLD")

    def test_original_replay_required_first(self):
        result = m.replay_readiness(replay(original_replay_completed=False))
        self.assertEqual(result["status"], "HOLD")

    def test_every_outcome_must_be_checked(self):
        result = m.replay_readiness(replay(all_outcomes_verified=False))
        self.assertEqual(result["status"], "HOLD")
