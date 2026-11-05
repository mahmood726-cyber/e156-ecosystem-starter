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
        self.assertEqual(result["maturity"], "REPRODUCED")
        self.assertFalse(result["human_adjudicated"])
        self.assertFalse(result["author_confirmed"])
        self.assertFalse(result["email_eligible"])

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


if __name__ == "__main__":
    unittest.main()
