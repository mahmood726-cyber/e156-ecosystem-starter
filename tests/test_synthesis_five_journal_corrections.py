"""Synthetic contract tests plus source-indexed corpus smoke checks.

The pilot file is retrospective development material, not a held-out benchmark.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.synthesis_five_journal_corrections import (
    normalize_doi, summarize, validate_notice,
)

OA_CORPUS = (
    Path(__file__).resolve().parents[1]
    / "research/correction_learning/five_journals/20261103/notices-oa-review-v2.json"
)

CORPUS = (
    Path(__file__).resolve().parents[1]
    / "research/correction_learning/five_journals/20261103/notices-pilot-v1.json"
)


class FiveJournalCorrectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(CORPUS.read_text(encoding="utf-8"))

    def test_pilot_has_exact_source_depth(self):
        result = summarize(self.rows)
        self.assertEqual(result["total_distinct_notice_records"], 12)
        self.assertEqual(result["full_primary_notices"], 8)
        self.assertEqual(result["indexed_excerpt_only"], 4)
        self.assertEqual(result["remaining_to_full_notice_target"], 992)
        self.assertEqual(result["duplicate_rows_removed"], 0)

    def test_exact_main_journal_boundaries(self):
        result = summarize(self.rows)["by_journal"]
        self.assertEqual(result["The Lancet"]["full_primary_notice"], 3)
        self.assertEqual(result["Nature"]["full_primary_notice"], 2)
        self.assertEqual(result["Circulation"]["full_primary_notice"], 3)
        self.assertEqual(result["New England Journal of Medicine"]["full_primary_notice"], 0)
        self.assertEqual(result["JACC"]["full_primary_notice"], 0)

    def test_notice_article_claim_units_are_not_interchangeable(self):
        result = summarize(self.rows)
        self.assertEqual(result["referenced_article_entries_not_unique_papers"], 15)
        self.assertEqual(result["notice_described_change_entries_not_error_roots"], 28)
        self.assertNotIn("confirmed_errors", result)
        self.assertNotIn("scientific_accuracy", result)
        multi = next(row for row in self.rows
                     if row["notice_doi"].lower() ==
                     "10.1016/s0140-6736(21)00398-6")
        self.assertEqual(len(multi["articles"]), 4)

    def test_every_source_record_validates(self):
        for row in self.rows:
            with self.subTest(row=row["notice_doi"]):
                validate_notice(row)

    def test_doi_aliases_case_fold_without_changing_identity(self):
        self.assertEqual(
            normalize_doi("https://doi.org/10.1161/CIR.0000000000001338"),
            "10.1161/cir.0000000000001338",
        )
        self.assertEqual(normalize_doi("DOI:10.1038/NATURE19804"),
                         "10.1038/nature19804")

    def test_identical_duplicate_not_double_counted(self):
        row = deepcopy(self.rows[0])
        result = summarize([row, deepcopy(row)])
        self.assertEqual(result["total_distinct_notice_records"], 1)
        self.assertEqual(result["full_primary_notices"], 1)
        self.assertEqual(result["duplicate_rows_removed"], 1)

    def test_conflicting_duplicate_refused(self):
        row = deepcopy(self.rows[0])
        other = deepcopy(row)
        other["notice_body_locator"] = "different source location"
        with self.assertRaisesRegex(ValueError, "conflicting entries"):
            summarize([row, other])

    def test_related_journal_not_inadvertently_included(self):
        for false_journal in ("Nature Communications", "JACC: Cardiovascular Imaging",
                              "The Lancet Oncology", "Circulation Research"):
            row = deepcopy(self.rows[0])
            row["journal"] = false_journal
            with self.subTest(journal=false_journal), self.assertRaises(ValueError):
                validate_notice(row)

    def test_full_notice_requires_entire_publisher_source(self):
        row = deepcopy(self.rows[0])
        row["notice_body_locator"] = ""
        with self.assertRaisesRegex(ValueError, "body locator"):
            validate_notice(row)
        row = deepcopy(self.rows[0])
        row["primary_notice_read_entirely"] = False
        with self.assertRaisesRegex(ValueError, "unread"):
            validate_notice(row)
        row = deepcopy(self.rows[0])
        row["source_format"] = "SEARCH_RESULT"
        with self.assertRaisesRegex(ValueError, "publisher"):
            validate_notice(row)

    def test_indexed_excerpt_cannot_claim_full_credit(self):
        row = deepcopy(self.rows[8])
        row["primary_notice_read_entirely"] = True
        with self.assertRaisesRegex(ValueError, "non-full"):
            validate_notice(row)
        self.assertEqual(summarize([self.rows[8]])["full_primary_notices"], 0)

    def test_publisher_https_domain_gate(self):
        for wrong_url in ("http://www.thelancet.com/a", "https://thelancet.example.org/a",
                          "https://evil.example/www.thelancet.com/a"):
            row = deepcopy(self.rows[0])
            row["primary_notice_url"] = wrong_url
            with self.subTest(url=wrong_url), self.assertRaisesRegex(ValueError, "publisher"):
                validate_notice(row)

    def test_bad_evidence_fields_fail_closed(self):
        row = deepcopy(self.rows[0])
        del row["articles"][0]["changes"][0]["current_vor_state"]
        with self.assertRaisesRegex(ValueError, "Version-of-Record"):
            validate_notice(row)
        row = deepcopy(self.rows[0])
        row["articles"][0]["changes"][0]["mechanism"] = "INSPECTED_AND_CONFIRMED"
        with self.assertRaisesRegex(ValueError, "mechanism"):
            validate_notice(row)
        row = deepcopy(self.rows[0])
        row["observed_on"] = "2026-02-30"
        with self.assertRaisesRegex(ValueError, "date"):
            validate_notice(row)

    def test_invalid_targets_and_invalid_dois(self):
        with self.assertRaises(ValueError):
            summarize([], target=0)
        with self.assertRaises(ValueError):
            summarize([], target=True)
        for invalid in ("not a doi", "https://doi.org/10.1038/example?x=1", ""):
            with self.subTest(doi=invalid), self.assertRaises(ValueError):
                normalize_doi(invalid)



class OpenOriginalEvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(OA_CORPUS.read_text(encoding="utf-8"))

    def test_oa_pair_count_is_separate_from_notice_count(self):
        stats = summarize(self.rows)
        self.assertEqual(stats["total_distinct_notice_records"], 12)
        self.assertEqual(stats["full_primary_notices"], 8)
        self.assertEqual(stats["full_notices_paired_with_public_original_claim"], 3)
        self.assertEqual(stats["remaining_to_oa_paired_target"], 997)
        self.assertEqual(stats["original_article_spans_rechecked"], 4)
        self.assertEqual(stats["original_full_text_located_without_claim_recheck"], 1)

    def test_every_original_access_record_validates(self):
        for row in self.rows:
            with self.subTest(doi=row["notice_doi"]):
                validate_notice(row)
                for article in row["articles"]:
                    self.assertIn("original_access", article)

    def test_original_full_text_location_alone_not_paired_credit(self):
        row = next(r for r in self.rows if r["notice_doi"].lower() ==
                   "10.1161/cir.0000000000001345")
        self.assertEqual(row["articles"][0]["original_access"]["status"],
                         "FREE_FULL_TEXT_IDENTIFIED")
        self.assertEqual(summarize([row])["full_notices_paired_with_public_original_claim"], 0)

    def test_indexed_notice_with_original_source_span_not_paired_credit(self):
        row = next(r for r in self.rows if r["notice_doi"].lower() ==
                   "10.1016/j.jacc.2024.05.033")
        self.assertEqual(row["articles"][0]["original_access"]["status"],
                         "SOURCE_SPAN_RECHECKED")
        self.assertEqual(summarize([row])["full_notices_paired_with_public_original_claim"], 0)
        self.assertIn("PMC_AUTHOR_MANUSCRIPT",
                      row["articles"][0]["original_access"]["source_version"])

    def test_unsubstantiated_oa_claim_fails_closed(self):
        source = next(r for r in self.rows if r["notice_doi"].lower() ==
                      "10.1161/cir.0000000000001338")
        for field in ("full_text_url", "source_version", "source_locator",
                      "observed_on", "comparison_note", "access_basis"):
            bad = deepcopy(source)
            del bad["articles"][0]["original_access"][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_notice(bad)

    def test_false_open_original_metadata_cannot_win_credit(self):
        row = deepcopy(self.rows[0])
        row["articles"][0]["original_access"] = {"status": "SOURCE_SPAN_RECHECKED"}
        with self.assertRaises(ValueError):
            validate_notice(row)
        row = deepcopy(self.rows[0])
        row["articles"][0]["original_access"] = {"status": "NOT_CHECKED",
                                                "full_text_url": "https://example.org"}
        with self.assertRaises(ValueError):
            validate_notice(row)

    def test_public_article_requires_exact_host_and_not_a_license_inference(self):
        row = next(r for r in self.rows if r["notice_doi"].lower() ==
                   "10.1038/s41586-025-09938-4")
        with self.assertRaisesRegex(ValueError, "full-text host"):
            other = deepcopy(row)
            other["articles"][0]["original_access"]["full_text_url"] = "https://nature.com.attacker.example/a"
            validate_notice(other)
        with self.assertRaisesRegex(ValueError, "licence"):
            other = deepcopy(row)
            other["articles"][0]["original_access"]["access_basis"] = "CC_BY_CONFIRMED"
            validate_notice(other)

    def test_legacy_notice_pilot_never_implies_original_review(self):
        legacy = json.loads(CORPUS.read_text(encoding="utf-8"))
        stats = summarize(legacy)
        self.assertEqual(stats["full_notices_paired_with_public_original_claim"], 0)


if __name__ == "__main__":
    unittest.main()
