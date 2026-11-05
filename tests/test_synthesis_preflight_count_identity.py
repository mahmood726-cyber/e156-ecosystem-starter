"""Deterministic synthetic witnesses and benign controls only."""

import copy
import unittest

from scripts.synthesis_preflight_count_identity import compare_raw_counts


class CountIdentityTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "publication_id": "synthetic:study-A", "source_result_id": "result:1",
            "data_version": "snapshot-1", "source_version": "current-v1",
            "count_basis": "unique_participants", "denominator_basis": "randomized",
            "analysis_cell_id": "overall",
            "population": "intention-to-treat", "endpoint": "hospitalisation",
            "time_window": "52-weeks", "effect_measure": "raw_count",
            "estimand": "participants_with_event", "model": "not_applicable",
            "adjustment": "not_applicable", "multiplicity": "not_applicable",
            "missingness": "not_applicable", "censoring": "not_applicable",
            "variance_method": "not_applicable", "test_statistic_identity": "not_applicable",
            "locator": "synthetic table 1, row 1", "source_sha256": "a" * 64,
            "value": 12,
        }

    def compare(self, **overrides):
        right = copy.deepcopy(self.source)
        right.update(overrides)
        return compare_raw_counts(self.source, right)

    def test_equal_matched_counts_are_negative_control(self):
        result = self.compare(locator="synthetic abstract")
        self.assertEqual(result["status"], "CONSISTENT")
        self.assertEqual(result["disposition"], "NO_FLAG")
        self.assertFalse(result["certified_error"])

    def test_source_reproduced_difference_is_not_certified(self):
        result = self.compare(value=15)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["difference"], -3)
        self.assertEqual(result["maturity"], "SCREENED")
        self.assertTrue(result["arithmetic_reproduced"])
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["human_adjudicated"])
        self.assertFalse(result["author_confirmed"])
        self.assertFalse(result["email_eligible"])

    def test_distinct_arm_or_stratum_cells_are_not_same_result(self):
        # Same paper, endpoint, and estimator; different treatment arms
        # legitimately have different raw counts, not an error candidate.
        result = self.compare(analysis_cell_id="treatment-arm", value=15)
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertEqual(result["disposition"], "HOLD")
        self.assertIn("analysis_cell_id", result["mismatched_fields"])
        self.assertFalse(result["arithmetic_reproduced"])
        self.assertFalse(result["certified_error"])

    def test_missing_or_placeholder_analysis_cell_cannot_be_compared(self):
        for cell in (None, "", "not_reported", "unknown"):
            with self.subTest(cell=cell):
                self.assertEqual(
                    self.compare(analysis_cell_id=cell, value=15)["status"],
                    "NOT_ENOUGH_INFO",
                )
        left = copy.deepcopy(self.source)
        right = copy.deepcopy(left)
        del right["analysis_cell_id"]
        self.assertEqual(compare_raw_counts(left, right)["status"], "NOT_ENOUGH_INFO")

    def test_matched_analysis_cell_preserves_legitimate_comparison(self):
        result = self.compare(analysis_cell_id="overall", value=15)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["difference"], -3)
        self.assertFalse(result["certified_error"])

    def test_patient_versus_recurrent_events_is_not_comparable(self):
        result = self.compare(count_basis="events", value=15)
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertIn("count_basis", result["mismatched_fields"])

    def test_distinct_followup_and_endpoints_hold(self):
        for key, value in (("time_window", "26-weeks"), ("endpoint", "death"),
                           ("population", "per-protocol")):
            with self.subTest(key=key):
                self.assertEqual(self.compare(**{key:value})["status"], "NOT_COMPARABLE")

    def test_different_source_revision_or_analysis_does_not_flag(self):
        for key, value in (("source_version", "revised-v2"),
                           ("data_version", "snapshot-2"),
                           ("source_result_id", "result:2"),
                           ("model", "adjusted-cox"),
                           ("denominator_basis", "observed")):
            with self.subTest(key=key):
                self.assertEqual(self.compare(**{key:value}, value=99)["status"], "NOT_COMPARABLE")

    def test_missing_estimator_signature_fails_closed(self):
        right=copy.deepcopy(self.source)
        del right["variance_method"]
        result=compare_raw_counts(self.source, right)
        self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
        self.assertEqual(result["disposition"], "HOLD")

    def test_unknown_identity_fails_closed(self):
        self.assertEqual(self.compare(estimand="unknown")["status"], "NOT_ENOUGH_INFO")

    def test_missing_or_malformed_provenance_fails_closed(self):
        self.assertEqual(self.compare(source_sha256="bad")["status"], "NOT_ENOUGH_INFO")
        self.assertEqual(self.compare(locator="")["status"], "NOT_ENOUGH_INFO")

    def test_exact_large_integer_count_not_float_rounded(self):
        source=copy.deepcopy(self.source)
        source["value"]=2**53+1
        other=copy.deepcopy(source)
        other["value"]=2**53
        result=compare_raw_counts(source,other)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["difference"], 1)

    def test_float_boolean_and_negative_counts_fail_closed(self):
        for value in (12.0, True, -1):
            with self.subTest(value=value):
                self.assertEqual(self.compare(value=value)["status"], "NOT_ENOUGH_INFO")

    def test_repeated_trial_family_is_distinct_count_basis(self):
        self.assertEqual(self.compare(count_basis="trial_families", value=12)["status"], "NOT_COMPARABLE")

    def test_bad_container_fails_closed(self):
        self.assertEqual(compare_raw_counts([], self.source)["status"], "NOT_ENOUGH_INFO")


    def test_placeholder_core_identities_refuse_even_if_both_sides_agree(self):
        # Same placeholder on both sides is not a verified matching endpoint.
        for key in ("publication_id", "source_result_id", "data_version",
                    "source_version", "denominator_basis", "population",
                    "endpoint", "time_window", "effect_measure", "estimand",
                    "locator"):
            for marker in ("not_applicable", "N/A", " none ", "not specified",
                           "missing", "undetermined", "tbd", "?"):
                with self.subTest(key=key, marker=marker):
                    left = copy.deepcopy(self.source)
                    left[key] = marker
                    right = copy.deepcopy(left)
                    right["value"] = 15
                    result = compare_raw_counts(left, right)
                    self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                    self.assertEqual(result["disposition"], "HOLD")
                    self.assertFalse(result["arithmetic_reproduced"])
                    self.assertFalse(result["certified_error"])

    def test_explicit_nonapplicable_statistical_methods_are_valid_control(self):
        # A raw count needs endpoint identity but not an inferential model.
        result = self.compare(value=15, model="not_applicable",
                              adjustment="not_applicable",
                              variance_method="not_applicable")
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["difference"], -3)
        self.assertFalse(result["certified_error"])


    def test_normalized_unreported_core_aliases_refuse(self):
        # Before this guard, identical unknown markers produced REVIEW for
        # divergent counts, despite absent endpoint/result/version evidence.
        for key in ("endpoint", "source_version", "locator"):
            for marker in ("not_reported", "not-reported", "NOT   REPORTED",
                           "source_limited", "not-available", "UNCLEAR",
                           "unavailable"):
                with self.subTest(key=key, marker=marker):
                    left = copy.deepcopy(self.source)
                    left[key] = marker
                    right = copy.deepcopy(left)
                    right["value"] = 15
                    result = compare_raw_counts(left, right)
                    self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                    self.assertFalse(result["arithmetic_reproduced"])
                    self.assertFalse(result["certified_error"])

    def test_missing_noncore_method_is_not_accepted_as_known(self):
        for marker in ("not_reported", "not-reported", "source_limited", "unclear"):
            with self.subTest(marker=marker):
                left = copy.deepcopy(self.source)
                left["variance_method"] = marker
                right = copy.deepcopy(left)
                right["value"] = 15
                self.assertEqual(compare_raw_counts(left, right)["status"],
                                 "NOT_ENOUGH_INFO")

    def test_actual_no_model_method_markers_are_valid_controls(self):
        # A raw count can explicitly have no inferential method; unlike a
        # missing endpoint, this is not a reason to claim unknown identity.
        for marker in ("not_applicable", "N/A", "none"):
            with self.subTest(marker=marker):
                left = copy.deepcopy(self.source)
                for key in ("model", "adjustment", "variance_method"):
                    left[key] = marker
                right = copy.deepcopy(left)
                right["value"] = 15
                result = compare_raw_counts(left, right)
                self.assertEqual(result["status"], "REVIEW")
                self.assertFalse(result["source_authenticated"])
                self.assertFalse(result["human_adjudicated"])
                self.assertFalse(result["author_confirmed"])


    def test_same_locator_with_divergent_source_digests_abstains(self):
        # Two allegedly identical source locations and versions with
        # different bytes do not establish an authenticated comparison.
        for next_value in (12, 15):
            with self.subTest(next_value=next_value):
                right = copy.deepcopy(self.source)
                right["source_sha256"] = "b" * 64
                right["value"] = next_value
                result = compare_raw_counts(self.source, right)
                self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                self.assertFalse(result["arithmetic_reproduced"])
                self.assertFalse(result["certified_error"])

    def test_distinct_locators_may_have_distinct_source_digests(self):
        # PDF versus HTML or abstract versus supplement can have different
        # raw bytes; differing locators stay an explicitly reviewable case.
        right = copy.deepcopy(self.source)
        right.update(locator="synthetic alternate representation",
                     source_sha256="b" * 64, value=15)
        result = compare_raw_counts(self.source, right)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["difference"], -3)
        self.assertFalse(result["source_authenticated"])

    def test_same_locator_and_identical_digest_retains_exact_count_checks(self):
        self.assertEqual(self.compare(value=15)["status"], "REVIEW")
        self.assertEqual(self.compare(value=12)["status"], "CONSISTENT")


if __name__ == "__main__":
    unittest.main()
