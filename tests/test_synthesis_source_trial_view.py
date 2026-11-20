"""Synthetic-only tests of the supervised source/trial viewer; not accuracy evidence."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "synthesis_source_trial_view",
    Path(__file__).resolve().parents[1] / "scripts" / "synthesis_source_trial_view.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceTrialViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.left = "Synthetic manuscript reports 14 events. <script>alert(1)</script>"
        self.right = "Synthetic original source records 12 events."
        self.packet = {
            "cases": [self._case()],
        }

    def _snapshot(self, name, quote):
        path = self.root / name
        path.write_text("HEADER\n" + quote + "\nFOOTER", encoding="utf-8")
        return {
            "path": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "version": "invented-source-v1",
            "locator": "invented Table 1",
            "quote": quote,
        }

    def _case(self):
        identity = {
            "trial_family_id": "SYNTHETIC-FAMILY",
            "cohort_id": "SYNTHETIC-COHORT",
            "population": "invented adults",
            "intervention": "therapy A",
            "comparator": "placebo",
            "endpoint": "invented outcome",
            "time_window": "day 30",
            "analysis_set": "intention-to-treat",
            "effect_measure": "event count",
            "estimand": "crude count",
            "statistic_id": "treatment arm events",
        }
        return {
            "case_id": "invented-case",
            "claim_version_status": "CURRENT_UNCORRECTED",
            "published": self._snapshot("published.txt", self.left),
            "primary": self._snapshot("source.txt", self.right),
            "contexts": {"published": identity.copy(), "primary": identity.copy()},
            "comparison": {"kind": "integer_count", "published": 14, "primary": 12},
            "refutation": {
                "alternative": "Maybe different follow-up",
                "checked_against": "invented Table 1 and Methods",
                "result": "NOT_SUPPORTED",
            },
        }

    def test_verified_quotes_generate_candidate_not_confirmed_error(self):
        report = module.evaluate_packet(self.packet, self.root)
        case = report["cases"][0]
        self.assertEqual(case["status"], "REVIEW_CANDIDATE")
        self.assertIn("14 - source 12 = 2", case["calculation"])

    def test_html_displays_both_sources_and_escapes_untrusted_text(self):
        html = module.render_html(module.evaluate_packet(self.packet, self.root))
        self.assertIn("Published claim", html)
        self.assertIn("Original source", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("SHA-256", html)

    def test_missing_original_snapshot_holds(self):
        self.packet["cases"][0]["primary"]["sha256"] = "0" * 64
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "HOLD")
        self.assertIn("SHA-256", case["reason"])

    def test_context_mismatch_is_not_comparable_not_error(self):
        self.packet["cases"][0]["contexts"]["primary"]["time_window"] = "day 60"
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "NOT_COMPARABLE")

    def test_unknown_context_holds_even_if_numbers_mismatch(self):
        self.packet["cases"][0]["contexts"]["primary"]["cohort_id"] = "unknown"
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "HOLD")

    def test_unrefuted_difference_is_hold(self):
        self.packet["cases"][0]["refutation"]["result"] = "UNTESTED"
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "HOLD")

    def test_matching_count_does_not_certify_article(self):
        self.packet["cases"][0]["comparison"]["primary"] = 14
        self.packet["cases"][0]["primary"] = self._snapshot(
            "source-agree.txt", "Synthetic original source records 14 events."
        )
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "NO_SCOPED_DIFFERENCE")

    def test_sd_se_discrepancy_is_review_candidate(self):
        self.packet["cases"][0]["published"] = self._snapshot(
            "published-label.txt", "Synthetic report labels uncertainty SD."
        )
        self.packet["cases"][0]["primary"] = self._snapshot(
            "source-label.txt", "Synthetic source labels uncertainty SE."
        )
        self.packet["cases"][0]["comparison"] = {
            "kind": "variance_label", "published": "SD", "primary": "SE",
        }
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "REVIEW_CANDIDATE")
        self.assertIn("source label SE", case["calculation"])

    def test_bad_quote_abstains(self):
        self.packet["cases"][0]["primary"]["quote"] = "quotation not present"
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "HOLD")

    def test_file_outside_source_root_is_rejected(self):
        self.packet["cases"][0]["primary"]["path"] = "../exfiltrate.txt"
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "HOLD")

    def test_missing_page_image_is_not_rendered_as_verified(self):
        html = module.render_html(module.evaluate_packet(self.packet, self.root))
        self.assertIn("No page image supplied", html)
        self.assertNotIn("<img", html)

    def test_duplicate_preflight_reuses_existing_conservative_detector(self):
        row = {
            "synthesis_id": "synthetic-meta", "trial_family_id": "family-A",
            "cohort_id": "shared-cohort", "endpoint": "mortality",
            "time_window": "day 30", "contrast_id": "A vs B",
            "source_version": "v1", "source_locator": "Table 2",
            "report_id": "report-one", "dependence_handling": "INDEPENDENT_UNCORRELATED",
            "same_cohort_source_verified": True, "included_as_independent_effect": True,
        }
        self.packet["duplicate_effects"] = [row, {**row, "report_id": "report-two"}]
        report = module.evaluate_packet(self.packet, self.root)
        self.assertEqual(report["duplicate_preflight"]["status"], "REVIEW_CANDIDATE")

    def test_duplicate_unverified_overlap_holds(self):
        row = {
            "synthesis_id": "synthetic-meta", "trial_family_id": "family-A",
            "cohort_id": "shared-cohort", "endpoint": "mortality",
            "time_window": "day 30", "contrast_id": "A vs B",
            "source_version": "v1", "source_locator": "Table 2",
            "report_id": "report-one", "dependence_handling": "INDEPENDENT_UNCORRELATED",
            "same_cohort_source_verified": False, "included_as_independent_effect": True,
        }
        self.packet["duplicate_effects"] = [row, {**row, "report_id": "report-two"}]
        report = module.evaluate_packet(self.packet, self.root)
        self.assertEqual(report["duplicate_preflight"]["status"], "HOLD")

    def test_unbound_numeric_payload_holds(self):
        # A copied/mistyped count not present in the quoted source is not evidence.
        self.packet["cases"][0]["comparison"]["published"] = 99
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "HOLD")
        self.assertIn("not anchored", case["reason"])

    def test_partial_digit_match_does_not_bind(self):
        case = self.packet["cases"][0]
        case["published"] = self._snapshot("partial.txt", "Synthetic report says 142 events")
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")

    def test_ishikawa_notice_is_historical_not_new_error(self):
        # From published correction DOI 10.1007/s00737-026-01767-2.
        # The local snippets are transcribed *fixtures*, not raw original sources.
        case = self.packet["cases"][0]
        case["published"] = self._snapshot("ishikawa-old.txt",
            "In the original version, 76,242 controls were stated.")
        case["primary"] = self._snapshot("ishikawa-new.txt",
            "The correction states 7,624 controls.")
        case["comparison"] = {"kind": "integer_count",
                              "published": 76242, "primary": 7624}
        case["claim_version_status"] = "HISTORICAL_CORRECTED"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("historical correction", out["reason"])

    def test_aqeel_notice_is_historical_not_independent_recount(self):
        # From DOI 10.3390/nu12051263; no trial-level recount is supplied.
        case = self.packet["cases"][0]
        case["published"] = self._snapshot("aqeel-old.txt",
            "The original abstract gave 352 participants.")
        case["primary"] = self._snapshot("aqeel-new.txt",
            "The correction states 332 participants.")
        case["comparison"] = {"kind": "integer_count",
                              "published": 352, "primary": 332}
        case["claim_version_status"] = "HISTORICAL_CORRECTED"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")

    def test_benralizumab_2_of_67_percent_error_is_missed_by_count_only(self):
        # DOI 10.1038/s41591-026-04425-3: historic 2 (1.5%) -> 2 (3.0%).
        # This is an intentionally limited count-only comparison; no claim of
        # successful identification of the wrong percentage may be made.
        case = self.packet["cases"][0]
        case["published"] = self._snapshot("hes-old.txt", "2 (1.5%)")
        case["primary"] = self._snapshot("hes-new.txt", "2 (3.0%)")
        case["comparison"] = {"kind": "integer_count", "published": 2, "primary": 2}
        case["claim_version_status"] = "HISTORICAL_CORRECTED"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "NO_SCOPED_DIFFERENCE")
        self.assertIn("no other claims assessed", out["reason"])

    def test_brooklyn_signed_ci_correction_not_implemented(self):
        # DOI 10.1038/s41591-026-04405-7, historical upper bound -2.0 to 2.0.
        case = self.packet["cases"][0]
        case["published"] = self._snapshot("brooklyn-old.txt", "95% CI to -2.0%")
        case["primary"] = self._snapshot("brooklyn-new.txt", "95% CI to 2.0%")
        case["comparison"] = {"kind": "signed_ci_limit",
                              "published": -2.0, "primary": 2.0}
        case["claim_version_status"] = "HISTORICAL_CORRECTED"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("only integer_count or variance_label supported", out["reason"])

    def test_unverified_claim_version_never_produces_candidate(self):
        case = self.packet["cases"][0]
        case.pop("claim_version_status")
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("current uncorrected", out["reason"])


    def _percentage_case(self, printed="1.5%", count=2, denominator=67,
                         source_count=2, source_denominator=67):
        case = self.packet["cases"][0]
        case["published"] = self._snapshot(
            "percentage-paper.txt",
            f"Synthetic manuscript: {count} ({printed}) of {denominator} participants."
        )
        case["primary"] = self._snapshot(
            "percentage-source.txt",
            f"Synthetic source: {source_count} of {source_denominator} participants."
        )
        case["contexts"]["published"]["denominator_basis"] = "synthetic treated population"
        case["contexts"]["primary"]["denominator_basis"] = "synthetic treated population"
        case["contexts"]["published"]["effect_measure"] = "raw participant percentage"
        case["contexts"]["primary"]["effect_measure"] = "raw participant percentage"
        case["contexts"]["published"]["estimand"] = "unweighted participants with event"
        case["contexts"]["primary"]["estimand"] = "unweighted participants with event"
        case["comparison"] = {
            "kind": "count_percentage",
            "published_count": count,
            "published_denominator": denominator,
            "primary_count": source_count,
            "primary_denominator": source_denominator,
            "published_percentage": printed,
            "percentage_method": "RAW_UNWEIGHTED_PERSON_FRACTION",
            "raw_fraction_source_verified": True,
            "denominator_basis_source_verified": True,
        }
        return case

    def test_raw_fraction_inconsistent_percentage_review_candidate(self):
        self._percentage_case(printed="1.5%", count=2, denominator=67)
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "REVIEW_CANDIDATE")
        self.assertIn("100 * 2 / 67 percent", case["calculation"])

    def test_raw_fraction_matching_percentage_no_scoped_difference(self):
        self._percentage_case(printed="3.0%", count=2, denominator=67)
        case = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(case["status"], "NO_SCOPED_DIFFERENCE")

    def test_correct_historical_benralizumab_notice_is_not_reopened(self):
        # Notice DOI 10.1038/s41591-026-04425-3; transcribed fixture only.
        case = self._percentage_case(printed="1.5%", count=2, denominator=67)
        case["claim_version_status"] = "HISTORICAL_CORRECTED"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("historical correction", out["reason"])

    def test_percentage_missing_source_denominator_holds(self):
        case = self._percentage_case()
        case["primary"] = self._snapshot("missing-denom.txt", "Synthetic source recorded 2 participants.")
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("primary denominator", out["reason"])

    def test_percentage_mismatched_source_denominator_holds(self):
        self._percentage_case(printed="1.5%", count=2, denominator=67,
                              source_count=2, source_denominator=70)
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("source count or denominator differs", out["reason"])

    def test_percentage_incompatible_denominator_basis_not_comparable(self):
        case = self._percentage_case()
        case["contexts"]["primary"]["denominator_basis"] = "synthetic completers"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "NOT_COMPARABLE")

    def test_percentage_weighted_or_km_basis_holds(self):
        for method in ("KAPLAN_MEIER", "WEIGHTED", "UNKNOWN"):
            with self.subTest(method=method):
                case = self._percentage_case()
                case["comparison"]["percentage_method"] = method
                out = module.evaluate_packet(self.packet, self.root)["cases"][0]
                self.assertEqual(out["status"], "HOLD")

    def test_percentage_missing_raw_source_attestation_holds(self):
        case = self._percentage_case()
        case["comparison"]["denominator_basis_source_verified"] = False
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")

    def test_percentage_exact_rounding_halfway_is_conservative(self):
        # 1/200 is exactly 0.5%; printed 1% may reflect ties-away rounding.
        self._percentage_case(printed="1%", count=1, denominator=200)
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "NO_SCOPED_DIFFERENCE")

    def test_percentage_zero_count_and_full_count(self):
        for count, pct in ((0, "0.0%"), (67, "100.0%")):
            with self.subTest(pct=pct):
                self._percentage_case(printed=pct, count=count, denominator=67,
                                      source_count=count)
                out = module.evaluate_packet(self.packet, self.root)["cases"][0]
                self.assertEqual(out["status"], "NO_SCOPED_DIFFERENCE")

    def test_percentage_reported_over_100_holds(self):
        self._percentage_case(printed="101.0%", count=67, denominator=67)
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("outside 0 to 100", out["reason"])

    def test_percentage_wrong_literal_not_bound_holds(self):
        case = self._percentage_case()
        case["comparison"]["published_percentage"] = "2.0%"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("not anchored", out["reason"])

    def test_percentage_missing_benign_explanation_holds(self):
        case = self._percentage_case()
        case["refutation"]["result"] = "UNTESTED"
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")

    def test_percentage_negative_population_count_holds(self):
        case = self._percentage_case()
        case["comparison"]["primary_count"] = -2
        out = module.evaluate_packet(self.packet, self.root)["cases"][0]
        self.assertEqual(out["status"], "HOLD")

    def test_cli_writes_offline_review_html(self):
        packet = self.root / "packet.json"
        packet.write_text(json.dumps(self.packet), encoding="utf-8")
        output = self.root / "private" / "viewer.html"
        self.assertEqual(module.main(["--packet", str(packet), "--source-root",
                                      str(self.root), "--html-out", str(output)]), 0)
        self.assertTrue(output.is_file())
        self.assertIn("Experimental reviewer aid", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
