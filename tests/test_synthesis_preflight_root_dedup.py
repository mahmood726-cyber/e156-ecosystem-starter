"""Invented IDs and statuses; no publication fixtures or participant records."""
import copy
import unittest
from scripts.synthesis_preflight_root_dedup import group_preflight_roots


class RootDedupContractTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(publication_id="synthetic:paper-1", source_version="v1",
                        root_scope_id="synthetic:family-1", root_cause_id="mapping-1",
                        affected_output_id="table1:event", source_support="CONTRADICTED",
                        maturity="REPRODUCED", disposition="FLAG",
                        human_adjudicated=False, author_confirmed=False)

    def row_with(self, **update):
        row = copy.deepcopy(self.row)
        row.update(update)
        return row

    def test_two_affected_outputs_one_root(self):
        result = group_preflight_roots([self.row, self.row_with(affected_output_id="abstract:event")])
        self.assertEqual(result["status"], "GROUPED")
        self.assertEqual(result["root_count"], 1)
        self.assertEqual(result["roots"][0]["affected_output_count"], 2)
        self.assertTrue(result["roots"][0]["all_source_reproduced"])
        self.assertFalse(result["roots"][0]["all_human_adjudicated"])
        self.assertEqual(result["certified_errors"], 0)

    def test_two_root_causes_not_conflated(self):
        other = self.row_with(root_cause_id="denominator-2", affected_output_id="table2:patients")
        self.assertEqual(group_preflight_roots([self.row, other])["root_count"], 2)

    def test_distinct_versions_do_not_conflate(self):
        other = self.row_with(source_version="v2")
        result = group_preflight_roots([self.row, other])
        self.assertEqual(result["root_count"], 2)

    def test_exact_replay_is_not_another_output(self):
        result = group_preflight_roots([self.row, copy.deepcopy(self.row)])
        self.assertEqual(result["root_count"], 1)
        self.assertEqual(result["roots"][0]["affected_output_count"], 1)

    def test_same_output_conflicting_root_is_held(self):
        other = self.row_with(root_cause_id="other-root")
        result = group_preflight_roots([self.row, other])
        self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
        self.assertIsNone(result["root_count"])

    def test_same_output_conflicting_confirmation_is_held(self):
        other = self.row_with(author_confirmed=True)
        result = group_preflight_roots([self.row, other])
        self.assertEqual(result["status"], "NOT_ENOUGH_INFO")

    def test_source_reproduced_not_human_or_author_confirmed(self):
        result = group_preflight_roots([self.row])
        root = result["roots"][0]
        self.assertTrue(root["all_source_reproduced"])
        self.assertFalse(root["all_human_adjudicated"])
        self.assertFalse(root["all_author_confirmed"])
        self.assertFalse(root["certified_error"])

    def test_human_and_author_fields_remain_separate(self):
        a = self.row_with(maturity="INDEPENDENTLY_ADJUDICATED", human_adjudicated=True,
                          human_receipt=self.human_receipt())
        b = self.row_with(affected_output_id="figure2:estimate", author_confirmed=True,
                          author_confirmation=self.author_receipt(affected_output_id="figure2:estimate"))
        result = group_preflight_roots([a,b])["roots"][0]
        self.assertFalse(result["all_human_adjudicated"])
        self.assertFalse(result["all_author_confirmed"])
        self.assertFalse(result["email_eligible"])

    def test_refutation_is_not_flag_or_certification(self):
        row = self.row_with(disposition="RECONCILED", source_support="SUPPORTED")
        result = group_preflight_roots([row])
        self.assertEqual(result["root_count"],1)
        self.assertEqual(result["roots"][0]["dispositions"], ["RECONCILED"])
        self.assertEqual(result["certified_errors"],0)

    def test_reconciled_and_flag_conflict_hold(self):
        row = self.row_with(disposition="RECONCILED", affected_output_id="text:claim")
        self.assertEqual(group_preflight_roots([self.row,row])["status"], "NOT_ENOUGH_INFO")

    def test_unknown_identity_and_nonboolean_hold(self):
        for update in ({"root_scope_id": "unknown"}, {"root_cause_id": "?"},
                       {"affected_output_id": ""}, {"human_adjudicated": "true"},
                       {"maturity": "PROVED"}, {"source_support": []},
                       {"disposition": {}}):
            with self.subTest(update=update):
                self.assertEqual(group_preflight_roots([self.row_with(**update)])["status"],
                                 "NOT_ENOUGH_INFO")

    def test_inconsistent_human_maturity_hold(self):
        a = self.row_with(maturity="INDEPENDENTLY_ADJUDICATED")
        self.assertEqual(group_preflight_roots([a])["status"], "NOT_ENOUGH_INFO")

    def test_empty_input_unambiguous_zero(self):
        result = group_preflight_roots([])
        self.assertEqual(result["status"], "GROUPED")
        self.assertEqual(result["root_count"],0)

    def test_invalid_container_hold(self):
        for bad in (None, "bad", {"a": "b"}, [self.row, "bad"]):
            with self.subTest(bad=bad):
                self.assertEqual(group_preflight_roots(bad)["status"], "NOT_ENOUGH_INFO")



    @staticmethod
    def human_receipt(**overrides):
        receipt = dict(
            reviewer_kind="independent_human", reviewer_id="synthetic:reviewer-2",
            investigator_id="synthetic:investigator-1",
            receipt_locator="private:synthetic-human-receipt",
            adjudicated_at="2026-01-02", conflict_check=True,
            publication_id="synthetic:paper-1", source_version="v1",
            root_scope_id="synthetic:family-1", root_cause_id="mapping-1",
            affected_output_id="table1:event",
        )
        receipt.update(overrides)
        return receipt

    @staticmethod
    def author_receipt(**overrides):
        receipt = dict(
            confirmation_kind="explicit_error_confirmation",
            confirmation_reference="private:synthetic-author-receipt",
            confirmed_at="2026-01-03", publication_id="synthetic:paper-1",
            source_version="v1", root_scope_id="synthetic:family-1",
            root_cause_id="mapping-1", affected_output_id="table1:event",
        )
        receipt.update(overrides)
        return receipt

    def test_human_adjudication_flag_without_scoped_receipt_holds(self):
        row = self.row_with(maturity="INDEPENDENTLY_ADJUDICATED",
                            human_adjudicated=True)
        result = group_preflight_roots([row])
        self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
        self.assertEqual(result["certified_errors"], 0)

    def test_author_confirmation_flag_without_receipt_holds(self):
        result = group_preflight_roots([self.row_with(author_confirmed=True)])
        self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
        self.assertEqual(result["certified_errors"], 0)

    def test_nonhuman_or_self_review_cannot_be_independent(self):
        for change in (dict(reviewer_kind="ai_model"),
                       dict(reviewer_id="synthetic:investigator-1"),
                       dict(conflict_check=False),
                       dict(receipt_locator="not_reported"),
                       dict(adjudicated_at="unknown"),
                       dict(adjudicated_at="2026-02-30")):
            with self.subTest(change=change):
                row = self.row_with(maturity="INDEPENDENTLY_ADJUDICATED",
                                    human_adjudicated=True,
                                    human_receipt=self.human_receipt(**change))
                self.assertEqual(group_preflight_roots([row])["status"],
                                 "NOT_ENOUGH_INFO")

    def test_author_acknowledgement_or_wrong_scope_is_not_confirmation(self):
        for change in (dict(confirmation_kind="acknowledged"),
                       dict(root_cause_id="another-root"),
                       dict(affected_output_id="figure2:different"),
                       dict(confirmation_reference="not_available"),
                       dict(confirmed_at="2026-02-30")):
            with self.subTest(change=change):
                row = self.row_with(author_confirmed=True,
                                    author_confirmation=self.author_receipt(**change))
                self.assertEqual(group_preflight_roots([row])["status"],
                                 "NOT_ENOUGH_INFO")

    def test_valid_separate_scoped_attestations_still_never_certify_error(self):
        row = self.row_with(
            maturity="INDEPENDENTLY_ADJUDICATED", human_adjudicated=True,
            author_confirmed=True, human_receipt=self.human_receipt(),
            author_confirmation=self.author_receipt())
        result = group_preflight_roots([row])
        self.assertEqual(result["status"], "GROUPED")
        self.assertTrue(result["roots"][0]["all_human_adjudicated"])
        self.assertTrue(result["roots"][0]["all_author_confirmed"])
        self.assertFalse(result["roots"][0]["certified_error"])
        self.assertEqual(result["certified_errors"], 0)
        self.assertFalse(result["email_eligible"])


    def test_normalized_unknown_root_and_receipt_id_aliases_hold(self):
        for key in ("root_scope_id", "root_cause_id", "affected_output_id"):
            for marker in ("not-reported", "NOT   REPORTED",
                           "source_limited", "not-available", "UnClEaR"):
                with self.subTest(key=key, marker=marker):
                    self.assertEqual(
                        group_preflight_roots([self.row_with(**{key: marker})])["status"],
                        "NOT_ENOUGH_INFO")
        row = self.row_with(maturity="INDEPENDENTLY_ADJUDICATED",
                            human_adjudicated=True,
                            human_receipt=self.human_receipt(receipt_locator="NOT   REPORTED"))
        self.assertEqual(group_preflight_roots([row])["status"], "NOT_ENOUGH_INFO")

    def test_legitimate_hyphenated_scope_and_underscored_output_pass(self):
        result = group_preflight_roots([
            self.row_with(root_scope_id="synthetic:family-1_v2",
                          affected_output_id="table1:unique_patient_count")])
        self.assertEqual(result["status"], "GROUPED")
        self.assertEqual(result["root_count"], 1)

    def test_source_unavailable_cannot_advance_to_reproduced_or_human_stage(self):
        # Synthetic evidence claiming a source was unavailable cannot
        # simultaneously mature to SOURCE_BACKED/REPRODUCED/ADJUDICATED.
        # A scoped human receipt does not repair missing source support.
        for support in ("SOURCE_UNAVAILABLE", "NOT_ENOUGH_INFO"):
            for maturity in ("SOURCE_BACKED", "REPRODUCED",
                             "INDEPENDENTLY_ADJUDICATED"):
                with self.subTest(support=support, maturity=maturity):
                    fields = dict(source_support=support, maturity=maturity)
                    if maturity == "INDEPENDENTLY_ADJUDICATED":
                        fields.update(human_adjudicated=True,
                                      human_receipt=self.human_receipt())
                    result = group_preflight_roots([self.row_with(**fields)])
                    self.assertEqual(result["status"], "NOT_ENOUGH_INFO")
                    self.assertEqual(result["certified_errors"], 0)
                    self.assertFalse(result["email_eligible"])

    def test_unknown_source_screened_hold_remains_legitimate_control(self):
        for support in ("SOURCE_UNAVAILABLE", "NOT_ENOUGH_INFO"):
            with self.subTest(support=support):
                result = group_preflight_roots([
                    self.row_with(source_support=support, maturity="SCREENED",
                                  disposition="HOLD")])
                self.assertEqual(result["status"], "GROUPED")
                self.assertFalse(result["roots"][0]["all_source_reproduced"])
                self.assertFalse(result["roots"][0]["certified_error"])

    def test_supported_source_reproduction_and_refutation_remain_valid(self):
        # Source-backed flags and independent refutations share the same
        # administrative maturity but neither certifies a scientific error.
        for support, disposition in (("CONTRADICTED", "FLAG"),
                                     ("SUPPORTED", "RECONCILED")):
            with self.subTest(support=support, disposition=disposition):
                result = group_preflight_roots([
                    self.row_with(source_support=support, maturity="REPRODUCED",
                                  disposition=disposition)])
                self.assertEqual(result["status"], "GROUPED")
                self.assertTrue(result["roots"][0]["all_source_reproduced"])
                self.assertEqual(result["certified_errors"], 0)

if __name__ == "__main__":
    unittest.main()
