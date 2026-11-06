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


    def test_nonprintable_identity_characters_refuse_arithmetic_comparison(self):
        # Invisible or control characters must not silently become matching
        # evidence identities: all records here are purely synthetic.
        for field, bad in (
            ("publication_id", "synthetic:paper-\u200bA"),
            ("source_result_id", "result:\u202e1"),
            ("source_version", "snapshot-\u20601"),
            ("endpoint", "hospital\u200bisation"),
            ("analysis_cell_id", "arm-\u200b1"),
            ("locator", "synthetic table\x00 row"),
            ("model", "not_applicable\u2060"),
        ):
            with self.subTest(field=field):
                left = copy.deepcopy(self.source)
                left[field] = bad
                right = copy.deepcopy(left)
                right["value"] = 15
                result = compare_raw_counts(left, right)
                self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                self.assertEqual(result["disposition"], "HOLD")
                self.assertFalse(result["arithmetic_reproduced"])
                self.assertFalse(result["certified_error"])

    def test_noncanonical_unicode_result_identifiers_hold(self):
        # NFD and NFC spellings can alias after downstream canonicalization.
        # Repeated decomposed metadata must not be accepted as a matched
        # source identity merely because both inputs use the same spelling.
        for field, decomposed in (
            ("publication_id", "synthetic:e\u0301tude"),
            ("source_result_id", "re\u0301sultat:1"),
            ("source_version", "re\u0301vision:1"),
            ("analysis_cell_id", "bras:re\u0301gional"),
            ("population", "re\u0301gion"),
            ("endpoint", "re\u0301admission"),
            ("locator", "synthetic table: re\u0301sultat"),
        ):
            with self.subTest(field=field):
                left = copy.deepcopy(self.source)
                left[field] = decomposed
                right = copy.deepcopy(left)
                right["value"] = 15
                result = compare_raw_counts(left, right)
                self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                self.assertEqual(result["disposition"], "HOLD")
                self.assertFalse(result["arithmetic_reproduced"])
                self.assertFalse(result["certified_error"])

    def test_printable_unicode_identity_remains_comparable(self):
        # Do not reject genuine printable international identifiers.
        left = copy.deepcopy(self.source)
        left["publication_id"] = "synthetic:étude-1"
        left["endpoint"] = "réadmission"
        right = copy.deepcopy(left)
        right["value"] = 15
        result = compare_raw_counts(left, right)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["difference"], -3)
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["certified_error"])


    def test_optional_denominator_size_must_match_for_same_result(self):
        # Both records claim randomized denominators, but the actual cohort
        # sizes differ. A raw-count difference is NOT a reproduced issue.
        for right_count in (12, 15):
            with self.subTest(right_count=right_count):
                left = copy.deepcopy(self.source)
                left["analysis_denominator_n"] = 100
                right = copy.deepcopy(left)
                right.update(analysis_denominator_n=120, value=right_count)
                result = compare_raw_counts(left, right)
                self.assertEqual(result["status"], "NOT_COMPARABLE")
                self.assertIn("analysis_denominator_n", result["mismatched_fields"])
                self.assertFalse(result["arithmetic_reproduced"])
                self.assertFalse(result["certified_error"])

    def test_partial_or_invalid_denominator_size_abstains(self):
        # Absence on only one side, floats, bools and zero cannot silently
        # be interpreted as a verified cohort size.
        for denominator in (None, 0, -1, 100.0, True):
            with self.subTest(denominator=denominator):
                left = copy.deepcopy(self.source)
                right = copy.deepcopy(left)
                left["analysis_denominator_n"] = 100
                right["analysis_denominator_n"] = denominator
                right["value"] = 15
                result = compare_raw_counts(left, right)
                self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                self.assertFalse(result["arithmetic_reproduced"])
        left = copy.deepcopy(self.source)
        right = copy.deepcopy(left)
        right["analysis_denominator_n"] = 100
        self.assertEqual(compare_raw_counts(left, right)["status"],
                         "NOT_ENOUGH_INFO")

    def test_unique_participant_count_above_denominator_abstains(self):
        # With a supplied exact cohort size, more unique participants than
        # the cohort is an invalid input, not a plausible REVIEW finding.
        left = copy.deepcopy(self.source)
        left.update(analysis_denominator_n=100, value=101)
        right = copy.deepcopy(left)
        right["value"] = 99
        result = compare_raw_counts(left, right)
        self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
        self.assertFalse(result["arithmetic_reproduced"])
        self.assertFalse(result["certified_error"])

    def test_matched_cohort_and_recurrent_event_controls(self):
        # A matched denominator does not obstruct a legitimate comparison.
        self.assertEqual(
            self.compare(analysis_denominator_n=100)["status"],
            "NOT_ENOUGH_INFO",  # one-sided field is not sufficient
        )
        left = copy.deepcopy(self.source)
        left["analysis_denominator_n"] = 100
        right = copy.deepcopy(left)
        right["value"] = 15
        self.assertEqual(compare_raw_counts(left, right)["status"], "REVIEW")
        right["value"] = 12
        self.assertEqual(compare_raw_counts(left, right)["status"], "CONSISTENT")
        # Recurrent events may exceed the number of enrolled individuals.
        left.update(count_basis="events", estimand="recurrent_events", value=120)
        right = copy.deepcopy(left)
        right["value"] = 125
        self.assertEqual(compare_raw_counts(left, right)["status"], "REVIEW")



    def test_padded_source_identity_cannot_support_raw_count_review(self):
        # An identity may be nonempty but still ambiguous if its first or
        # last character is whitespace. Both synthetic records use the same
        # invalid identity; repetition must not promote it to a comparison.
        for field in ("publication_id", "source_result_id", "data_version",
                      "source_version", "denominator_basis", "analysis_cell_id",
                      "population", "endpoint", "time_window", "effect_measure",
                      "estimand", "locator"):
            for padded in (" " + self.source[field],
                           self.source[field] + " ", "\u00a0" + self.source[field]):
                with self.subTest(field=field, padded=repr(padded)):
                    left = copy.deepcopy(self.source)
                    left[field] = padded
                    right = copy.deepcopy(left)
                    right["value"] = 15
                    result = compare_raw_counts(left, right)
                    self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                    self.assertEqual(result["disposition"], "HOLD")
                    self.assertFalse(result["arithmetic_reproduced"])
                    self.assertFalse(result["certified_error"])

    def test_internal_spaces_in_result_labels_remain_valid(self):
        # Human-readable endpoint and population labels often contain spaces.
        # Boundary whitespace refusal must not invalidate such labels.
        left = copy.deepcopy(self.source)
        left["population"] = "adult outpatient population"
        left["endpoint"] = "first hospital admission"
        left["locator"] = "synthetic table 1 row 3"
        right = copy.deepcopy(left)
        right["value"] = 15
        result = compare_raw_counts(left, right)
        self.assertEqual(result["status"], "REVIEW")
        self.assertTrue(result["arithmetic_reproduced"])
        self.assertFalse(result["certified_error"])


    def test_opt_in_trial_family_membership_rejects_duplicates(self):
        # Synthetic aliases of the same family must never count twice.
        for members in (
            ["fam-A", "fam-A"], ["fam-A", "FAM-a"],
            ["Fam-①", "Fam-1"], ["unknown", "fam-B"],
        ):
            with self.subTest(members=members):
                left = copy.deepcopy(self.source)
                left.update(count_basis="trial_families", value=2,
                            trial_family_ids=members)
                right = copy.deepcopy(left)
                result = compare_raw_counts(left, right)
                self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                self.assertEqual(result["disposition"], "HOLD")
                self.assertFalse(result["arithmetic_reproduced"])
                self.assertFalse(result["certified_error"])

    def test_opt_in_trial_family_membership_requires_consistent_sets(self):
        left = copy.deepcopy(self.source)
        left.update(count_basis="trial_families", value=2,
                    trial_family_ids=["fam-A", "fam-B"])
        right = copy.deepcopy(left)
        right["trial_family_ids"] = ["fam-A", "fam-C"]
        result = compare_raw_counts(left, right)
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertIn("trial_family_ids", result["mismatched_fields"])
        self.assertFalse(result["certified_error"])
        del right["trial_family_ids"]
        self.assertEqual(compare_raw_counts(left, right)["status"],
                         "NOT_ENOUGH_INFO")
        right["trial_family_ids"] = ["fam-A", "fam-B"]
        right["value"] = 3  # stated family count contradicts membership
        self.assertEqual(compare_raw_counts(left, right)["status"],
                         "NOT_ENOUGH_INFO")
        right["value"] = 2
        right["trial_family_ids"] = "fam-A,fam-B"  # not an ID sequence
        self.assertEqual(compare_raw_counts(left, right)["status"],
                         "NOT_ENOUGH_INFO")

    def test_opt_in_trial_family_valid_membership_negative_control(self):
        left = copy.deepcopy(self.source)
        left.update(count_basis="trial_families", value=2,
                    trial_family_ids=["fam-A", "fam-B"])
        right = copy.deepcopy(left)
        right["trial_family_ids"] = ["fam-B", "fam-A"]
        result = compare_raw_counts(left, right)
        self.assertEqual(result["status"], "CONSISTENT")
        self.assertEqual(result["difference"], 0)
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["certified_error"])
        # A membership manifest supplied for event counts is not interpretable.
        right = copy.deepcopy(self.source)
        right["trial_family_ids"] = ["fam-A", "fam-B"]
        self.assertEqual(compare_raw_counts(self.source, right)["status"],
                         "NOT_ENOUGH_INFO")


if __name__ == "__main__":
    unittest.main()
