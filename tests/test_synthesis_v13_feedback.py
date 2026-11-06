"""Synthetic response-review contracts; no real emails or publication verdicts."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "synthesis_v13_checks",
    Path(__file__).resolve().parents[1] / "scripts" / "synthesis_v13_checks.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def review(**changes):
    row = dict(claim_id="synthetic:point-A", original_claim_reference="private original A",
               reply_reference="private response A", original_claim_reviewed=True,
               reply_reviewed=True, same_claim_verified=True,
               original_item_kind="CLARIFICATION_REQUEST", outcome="EXPLANATION_SUPPORTED",
               sources_rechecked=True, counterevidence_checked=True,
               source_version="synthetic current v2", source_locator="Table A, footnote",
               recheck_reference="private source comparison A", calculation_kind="NOT_NEEDED")
    row.update(changes)
    return row


def candidate(**changes):
    row = dict(claim_id="synthetic:point-A", severity="S3", version="FINAL_CURRENT",
               source_access="ACCESSIBLE", source_locator="synthetic Table A",
               current_claim_verified=True, current_correction_status="NO_RELEVANT_CORRECTION",
               source_support="CONTRADICTED", maturity="SOURCE_BACKED",
               alternative="synthetic benign explanation", alternative_locator="source footnote",
               alternative_result="REFUTED", estimator_status="MATCHED", root_cause_id="root-A")
    row.update(changes)
    return row


class FeedbackReviewTests(unittest.TestCase):
    def test_author_denial_alone_cannot_suppress_or_uphold_a_candidate(self):
        self.assertEqual(m.gate(candidate(correspondence_status="AUTHOR_DISAGREED"))["status"], "HOLD")

    def test_resolved_question_is_not_a_false_positive_allegation(self):
        out = m.feedback_recheck(review())
        self.assertEqual(out["status"], "RECONCILED")
        self.assertEqual(out["feedback_outcome"], "RESOLVED_ENQUIRY")
        self.assertEqual(out["evidence_basis"], "REVIEWER_ATTESTATION_ONLY")

    def test_refuted_allegation_has_separate_recorded_outcome(self):
        out = m.feedback_recheck(review(original_item_kind="ERROR_ALLEGATION"))
        self.assertEqual(out["feedback_outcome"], "FALSE_POSITIVE_RECORDED")

    def test_missing_evidence_or_unread_original_never_resolves(self):
        for field in ("claim_id", "original_claim_reference", "reply_reference", "source_version",
                      "source_locator", "recheck_reference"):
            with self.subTest(field=field):
                self.assertEqual(m.feedback_recheck(review(**{field: "UNKNOWN"}))["status"], "HOLD")
        for field in ("original_claim_reviewed", "reply_reviewed", "same_claim_verified",
                      "sources_rechecked", "counterevidence_checked"):
            for value in (False, "true", 1, None):
                with self.subTest(field=field, value=value):
                    self.assertEqual(m.feedback_recheck(review(**{field: value}))["status"], "HOLD")

    def test_uncertainty_remains_held(self):
        self.assertEqual(m.feedback_recheck(review(outcome="UNRESOLVED"))["status"], "HOLD")

    def test_methodological_preference_is_not_an_error_verdict(self):
        self.assertEqual(m.gate(candidate(feedback_review=review(
            outcome="METHODOLOGICAL_DISCUSSION")))["status"], "DISCUSSION")

    def test_old_version_is_separate_from_false_positive(self):
        out = m.feedback_recheck(review(outcome="VERSION_RESOLVED"))
        self.assertEqual(out["status"], "RECONCILED")
        self.assertEqual(out["feedback_outcome"], "VERSION_LIMITED")

    def test_supported_explanation_blocks_reflagging(self):
        self.assertEqual(m.gate(candidate(feedback_review=review()))["status"], "RECONCILED")

    def test_different_point_or_whole_thread_cannot_close_a_candidate(self):
        for value in (None, [], "all points correct", review(claim_id="synthetic:point-B")):
            with self.subTest(value=value):
                self.assertEqual(m.gate(candidate(feedback_review=value))["status"], "HOLD")

    def test_upheld_concern_still_needs_the_existing_gates(self):
        reviewed = review(outcome="CONCERN_PERSISTS")
        self.assertEqual(m.gate(candidate(feedback_review=reviewed))["status"], "FLAG_CANDIDATE")
        self.assertEqual(m.gate(candidate(feedback_review=reviewed,
                                         estimator_status="NOT_COMPARABLE"))["status"], "HOLD")

    def test_claimed_code_execution_needs_replay_artifacts(self):
        code = review(calculation_kind="CODE", calculation_executed=True,
                      input_reference="synthetic inputs", script_reference="synthetic script",
                      raw_output_reference="synthetic stdout")
        self.assertEqual(m.feedback_recheck(code)["status"], "RECONCILED")
        for field in ("input_reference", "script_reference", "raw_output_reference"):
            with self.subTest(field=field):
                self.assertEqual(m.feedback_recheck({**code, field: ""})["status"], "HOLD")
        self.assertEqual(m.feedback_recheck({**code, "calculation_executed": False})["status"], "HOLD")

    def test_manual_working_and_unknown_calculation_status(self):
        self.assertEqual(m.feedback_recheck(review(calculation_kind="MANUAL"))["status"], "HOLD")
        self.assertEqual(m.feedback_recheck(review(calculation_kind="MANUAL",
                            working_reference="synthetic inputs and arithmetic"))["status"], "RECONCILED")
        self.assertEqual(m.feedback_recheck(review(calculation_kind="UNKNOWN"))["status"], "HOLD")

    def test_invalid_outcome_and_original_item_kind_fail_closed(self):
        self.assertEqual(m.feedback_recheck(review(outcome="AUTHOR_SAYS_CORRECT"))["status"], "HOLD")
        self.assertEqual(m.feedback_recheck(review(original_item_kind="WHOLE_THREAD"))["status"], "HOLD")
        self.assertEqual(m.feedback_recheck(None)["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
