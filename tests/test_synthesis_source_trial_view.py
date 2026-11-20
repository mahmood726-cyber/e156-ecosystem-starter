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
        self.assertIn("only integer_count, variance_label or count_percentage supported", out["reason"])

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
        self._percentage_case(printed="1%", count=1, denominator=200,
                              source_count=1, source_denominator=200)
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




ledger_spec = importlib.util.spec_from_file_location(
    "synthesis_trial_source_ledger",
    Path(__file__).resolve().parents[1] / "scripts" / "synthesis_trial_source_ledger.py",
)
ledger = importlib.util.module_from_spec(ledger_spec)
ledger_spec.loader.exec_module(ledger)


class TrialSourceLedgerTests(unittest.TestCase):
    """Source-to-cell crosswalk fixtures are invented, not clinical findings."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _snapshot(self, filename, quote):
        path = self.root / filename
        path.write_text("ARCHIVED TEST\n" + quote + "\nEND\n", encoding="utf-8")
        return {
            "path": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "version": "synthetic-source-v1", "locator": "invented Table 1",
            "quote": quote,
        }

    def _row(self, row_id="R1", count=4, source_count=2, report_id="report-1",
             cohort_id="cohort-A", trial_key="SYNTHETIC-TRIAL-001"):
        published_quote = f"Review lists {count} events for {trial_key} at day 30."
        primary_quote = f"{trial_key} primary report records {source_count} events at day 30."
        keys = dict(
            trial_family_id="synthetic-family-A", cohort_id=cohort_id,
            population="invented adults ITT", intervention="invented A",
            comparator="invented C", endpoint="invented mortality",
            time_window="day 30", analysis_set="ITT", effect_measure="event count",
            estimand="raw people count", statistic_id="treatment arm events",
        )
        return {
            "row_id": row_id, "trial_key": trial_key, "trial_key_type": "OTHER_SOURCE_ID",
            "trial_key_source_checked": True,
            "trial_key_binding": {"text": trial_key, "offset": primary_quote.index(trial_key)},
            "source_tier": "T1",
            "case": {
                "claim_version_status": "CURRENT_UNCORRECTED",
                "published": self._snapshot(f"{row_id}-review.txt", published_quote),
                "primary": self._snapshot(f"{row_id}-primary.txt", primary_quote),
                "contexts": {"published": dict(keys), "primary": dict(keys)},
                "comparison": {"kind": "integer_count", "published": count,
                               "primary": source_count},
                "refutation": {"alternative": "possible different analysis population",
                               "checked_against": "invented trial Methods",
                               "result": "NOT_SUPPORTED"},
            },
            "bindings": {
                "published_value": {"text": str(count),
                                    "offset": published_quote.index(f"{count} events")},
                "primary_value": {"text": str(source_count),
                                  "offset": primary_quote.index(f"{source_count} events")},
            },
            "analysis": {
                "report_id": report_id, "contrast_id": "A_vs_C",
                "included_as_independent_effect": True,
                "same_cohort_source_verified": True,
                "dependence_handling": "INDEPENDENT_UNCORRELATED",
            },
        }

    def _review(self, *rows):
        return ledger.review_ledger({
            "ledger_version": "0.1", "synthesis_id": "synthetic-synthesis-A",
            "rows": list(rows),
        }, self.root)

    def test_quoted_difference_is_review_only(self):
        report = self._review(self._row())
        self.assertFalse(report["certified"])
        self.assertEqual(report["rows"][0]["status"], "REVIEW_CANDIDATE")
        self.assertEqual(report["rows"][0]["trial_key"], "SYNTHETIC-TRIAL-001")

    def test_matched_count_not_paper_certification(self):
        report = self._review(self._row(count=4, source_count=4))
        self.assertEqual(report["rows"][0]["status"], "NO_SCOPED_DIFFERENCE")
        self.assertFalse(report["certified"])

    def test_missing_trial_identity_source_holds(self):
        row = self._row()
        row["trial_key_source_checked"] = False
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_wrong_trial_identity_offset_holds(self):
        row = self._row()
        row["trial_key_binding"]["offset"] += 1
        out = self._review(row)
        self.assertEqual(out["rows"][0]["status"], "HOLD")
        self.assertIn("trial identifier", out["rows"][0]["reason"])

    def test_unbound_source_count_holds(self):
        row = self._row()
        row["bindings"]["primary_value"]["offset"] += 1
        out = self._review(row)
        self.assertEqual(out["rows"][0]["status"], "HOLD")
        self.assertIn("source-cell offsets", out["rows"][0]["reason"])

    def test_secondary_meta_source_is_not_a_primary_recheck(self):
        row = self._row()
        row["source_tier"] = "T4"
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_unknown_cohort_holds(self):
        row = self._row()
        row["case"]["contexts"]["primary"]["cohort_id"] = "unknown"
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_distinct_timepoint_not_comparable(self):
        row = self._row()
        row["case"]["contexts"]["primary"]["time_window"] = "day 60"
        self.assertEqual(self._review(row)["rows"][0]["status"], "NOT_COMPARABLE")

    def test_historical_corrected_claim_not_new_flag(self):
        row = self._row()
        row["case"]["claim_version_status"] = "HISTORICAL_CORRECTED"
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_duplicate_row_id_holds_only_repeated_row(self):
        report = self._review(self._row(), self._row())
        self.assertEqual(report["rows"][0]["status"], "REVIEW_CANDIDATE")
        self.assertEqual(report["rows"][1]["status"], "HOLD")
        self.assertIn("duplicate row_id", report["rows"][1]["reason"])

    def test_duplicate_trial_family_preflight_reused(self):
        report = self._review(self._row(), self._row(
            row_id="R2", report_id="report-2"))
        self.assertEqual(report["duplicate_preflight"]["status"], "REVIEW_CANDIDATE")
        self.assertEqual(report["counts"]["REVIEW_CANDIDATE"], 2)

    def test_unverified_overlap_abstains_in_duplicate_preflight(self):
        row = self._row()
        row["analysis"]["same_cohort_source_verified"] = False
        report = self._review(row, self._row(row_id="R2", report_id="report-2"))
        self.assertEqual(report["duplicate_preflight"]["status"], "HOLD")

    def test_absent_primary_file_holds(self):
        row = self._row()
        (self.root / row["case"]["primary"]["path"]).unlink()
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_unregistered_trial_key_format_requires_attested_other_id(self):
        row = self._row()
        row["trial_key_type"] = "REGISTRY"
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_bounded_input_refuses_empty_and_oversized(self):
        with self.assertRaises(ValueError):
            self._review()
        with self.assertRaises(ValueError):
            self._review(*[{} for _ in range(ledger.MAX_ROWS + 1)])

    def test_quoted_percentage_cells_have_exact_offsets(self):
        row = self._row()
        key = row["trial_key"]
        pub = f"Review {key}: 2/67 (1.5%) participants."
        pri = f"{key} source reports 2 of 67 participants."
        row["case"]["published"] = self._snapshot("pct-review.txt", pub)
        row["case"]["primary"] = self._snapshot("pct-source.txt", pri)
        row["case"]["contexts"]["primary"].update(
            denominator_basis="observed people", effect_measure="raw participant percentage",
            estimand="unweighted participants with outcome")
        row["case"]["contexts"]["published"].update(
            denominator_basis="observed people", effect_measure="raw participant percentage",
            estimand="unweighted participants with outcome")
        row["case"]["comparison"] = {
            "kind": "count_percentage", "published_count": 2,
            "published_denominator": 67, "published_percentage": "1.5%",
            "primary_count": 2, "primary_denominator": 67,
            "percentage_method": "RAW_UNWEIGHTED_PERSON_FRACTION",
            "raw_fraction_source_verified": True,
            "denominator_basis_source_verified": True,
        }
        row["trial_key_binding"] = {"text": key, "offset": pri.index(key)}
        row["bindings"] = {
            "published_count": {"text": "2", "offset": pub.index("2/67")},
            "published_denominator": {"text": "67", "offset": pub.index("67")},
            "published_percentage": {"text": "1.5%", "offset": pub.index("1.5%")},
            "primary_count": {"text": "2", "offset": pri.index("2 of")},
            "primary_denominator": {"text": "67", "offset": pri.index("67")},
        }
        report = self._review(row)
        self.assertEqual(report["rows"][0]["status"], "REVIEW_CANDIDATE")
        row["bindings"]["published_denominator"]["offset"] += 1
        self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")

    def test_cli_writes_private_html_and_sanitised_json(self):
        packet = self.root / "ledger.json"
        packet.write_text(json.dumps({
            "ledger_version": "0.1", "synthesis_id": "synthetic-synthesis-A",
            "rows": [self._row()],
        }), encoding="utf-8")
        html_out = self.root / "out" / "private.html"
        json_out = self.root / "out" / "receipt.json"
        rc = ledger.main([
            "--packet", str(packet), "--source-root", str(self.root),
            "--html-out", str(html_out), "--json-out", str(json_out),
        ])
        self.assertEqual(rc, 0)
        self.assertIn("Published claim", html_out.read_text(encoding="utf-8"))
        data = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertFalse(data["certified"])
        self.assertNotIn("quote", data["rows"][0])
        self.assertIn("sha256", data["rows"][0]["source_snapshots"]["primary"])
        self.assertIn("locator", data["rows"][0]["source_snapshots"]["published"])
        self.assertNotIn("ARCHIVED TEST", json.dumps(data))




paired_spec = importlib.util.spec_from_file_location(
    "synthesis_paired_model_replay",
    Path(__file__).resolve().parents[1] / "scripts" / "synthesis_paired_model_replay.py",
)
paired = importlib.util.module_from_spec(paired_spec)
paired_spec.loader.exec_module(paired)


class PairedModelReplayTests(unittest.TestCase):
    """Invented cells and a deliberately fake pooling adapter test only the gates."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.analysis = {
            "population": "invented adults",
            "endpoint": "invented day-30 outcome",
            "time_window": "day 30",
            "analysis_set": "ITT",
            "intervention": "synthetic agent A",
            "comparator": "synthetic control C",
            "effect_measure": "OR",
            "estimand": "UNADJUSTED_TWO_ARM_LOG_OR",
        }
        self.trials = [self._trial("SYN-T-A", 5, 6),
                       self._trial("SYN-T-B", 5, 5)]
        publication = "Analysis used Paule-Mandel and floored Knapp-Hartung. Reported pooled OR: 0.80."
        self.packet = {
            "schema_version": "0.1",
            "claim_version_status": "CURRENT_UNCORRECTED",
            "analysis": self.analysis,
            "publication": {
                "snapshot": self._snapshot("meta.txt", publication),
                "model": paired.METHOD, "published_method_source_checked": True,
                "method_quote": "Paule-Mandel and floored Knapp-Hartung",
                "pooled_or_text": "0.80",
                "pooled_or_binding": {"text": "0.80", "offset": publication.index("0.80")},
                "trial_set_complete_source_checked": True,
            },
            "trials": self.trials,
        }
        self.fake_engine = self.root / "engine.py"
        self.fake_engine.write_text(
            "from types import SimpleNamespace\n"
            "def binary_effect(name,tE,tN,cE,cN,nct=None):\n"
            "    return SimpleNamespace(tE=tE, name=name)\n"
            "def pool_effects(effects, scale):\n"
            "    if scale != 'OR': raise ValueError('not OR')\n"
            "    p = 0.8 if sum(e.tE for e in effects)==10 else 0.9\n"
            "    return SimpleNamespace(k=len(effects), pooled=p, ci_low=0.60,\n"
            "        ci_high=1.05, tau2=0.01, i2=10.0)\n",
            encoding="utf-8",
        )
        self.engine_digest = hashlib.sha256(self.fake_engine.read_bytes()).hexdigest()

    def _snapshot(self, name, quote):
        file = self.root / name
        file.write_text(quote, encoding="utf-8")
        return {
            "path": name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "version": "synthetic-v1", "locator": "invented table",
            "quote": quote,
        }

    def _trial(self, key, original_events, corrected_events):
        original = {"tE": original_events, "tN": 50, "cE": 7, "cN": 55}
        corrected = {**original, "tE": corrected_events}
        published = f"{key} published tE={original['tE']} tN=50 cE=7 cN=55 participants."
        primary = f"{key} primary tE={corrected['tE']} tN=50 cE=7 cN=55 participants."
        def bindings(text, values):
            return {field: {"text": str(values[field]),
                            "offset": text.index(str(values[field]), text.index(field + "="))}
                    for field in paired.CELL_FIELDS}
        return {
            "trial_key": key, "trial_family_id": key + "-family",
            "trial_identity_source_checked": True, "source_tier": "T1",
            "independent_trial_source_verified": True,
            "analysis": dict(self.analysis),
            "published_extraction": self._snapshot(key + "-pub.txt", published),
            "primary_trial": self._snapshot(key + "-primary.txt", primary),
            "trial_key_binding": {"text": key, "offset": primary.index(key)},
            "original": original, "corrected": corrected,
            "original_bindings": bindings(published, original),
            "corrected_bindings": bindings(primary, corrected),
            "correction_source_checked": True, "correction_rationale": "invented count transcription",
        }

    def _replay(self, run_engine=True):
        return paired.check_replay(
            self.packet, self.root,
            engine_path=self.fake_engine if run_engine else None,
            engine_sha256=self.engine_digest if run_engine else None,
        )

    def test_preflight_without_engine_does_not_claim_model_replay(self):
        result = self._replay(False)
        self.assertEqual(result["status"], "READY_FOR_PINNED_ENGINE")
        self.assertEqual(result["model_fit"], "NOT_RUN")
        self.assertFalse(result["scientific_error_confirmed"])

    def test_published_first_then_corrected_same_engine_interface(self):
        result = self._replay()
        self.assertEqual(result["status"], "PAIRED_MODEL_REPLAYED_FOR_REVIEW")
        self.assertEqual(result["published_replay"]["pooled"], 0.8)
        self.assertEqual(result["corrected_replay"]["pooled"], 0.9)
        self.assertAlmostEqual(result["delta_pooled_or"], 0.1)
        self.assertEqual(result["conclusion_impact"], "NOT_ASSESSED")
        self.assertEqual(result["external_engine_sha256"], self.engine_digest)

    def test_original_replay_mismatch_stops_before_correction(self):
        self.packet["publication"]["pooled_or_text"] = "0.79"
        pub = self.packet["publication"]
        txt = pub["snapshot"]["quote"].replace("0.80", "0.79")
        pub["snapshot"] = self._snapshot("meta.txt", txt)
        pub["pooled_or_binding"]["text"] = "0.79"
        result = self._replay()
        self.assertEqual(result["status"], "PUBLISHED_REPLAY_MISMATCH")
        self.assertEqual(result["corrected_replay"], "NOT_RUN")

    def test_corrected_rows_unchanged_do_not_claim_changed_effect(self):
        a = self.trials[0]
        a["corrected"] = dict(a["original"])
        a["primary_trial"] = self._snapshot("SYN-T-A-primary.txt",
                        "SYN-T-A primary tE=5 tN=50 cE=7 cN=55 participants.")
        a["corrected_bindings"]["tE"] = {"text": "5", "offset": a["primary_trial"]["quote"].index("tE=5") + 3}
        result = self._replay()
        self.assertEqual(result["status"], "ORIGINAL_REPLAY_MATCHED_NO_INPUT_CHANGE")
        self.assertEqual(result["corrected_replay"], "NOT_RUN")

    def test_no_primary_cell_source_blocks(self):
        self.trials[0]["corrected_bindings"]["tE"]["offset"] += 1
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("counts not bound", result["reason"])

    def test_aliasing_two_arm_cells_blocks(self):
        self.trials[0]["corrected_bindings"]["cN"] = dict(self.trials[0]["corrected_bindings"]["tN"])
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("distinct physical tokens", result["reason"])

    def test_duplicate_trial_families_block(self):
        self.trials[1]["trial_family_id"] = self.trials[0]["trial_family_id"]
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("duplicate trial", result["reason"])

    def test_wrong_analysis_definition_blocks(self):
        self.trials[1]["analysis"]["time_window"] = "day 60"
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("analysis population", result["reason"])

    def test_zero_cell_requires_appropriate_published_correction_method(self):
        self.trials[0]["original"]["tE"] = 0
        pub = self.trials[0]["published_extraction"]
        pub["quote"] = pub["quote"].replace("tE=5", "tE=0")
        self.trials[0]["published_extraction"] = self._snapshot("SYN-T-A-pub.txt", pub["quote"])
        self.trials[0]["original_bindings"]["tE"] = {
            "text": "0", "offset": pub["quote"].index("tE=0") + 3}
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("zero cell", result["reason"])

    def test_mismatched_engine_hash_blocks_without_execution(self):
        result = paired.check_replay(self.packet, self.root,
                      engine_path=self.fake_engine, engine_sha256="0" * 64)
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("SHA-256", result["reason"])

    def test_model_not_supported_blocks(self):
        self.packet["publication"]["model"] = "REML"
        self.assertEqual(self._replay()["status"], "HOLD")

    def test_historical_correction_stays_on_hold(self):
        self.packet["claim_version_status"] = "HISTORICAL_CORRECTED"
        self.assertEqual(self._replay()["status"], "HOLD")

    def test_unchecked_trial_set_completeness_blocks(self):
        self.packet["publication"]["trial_set_complete_source_checked"] = False
        self.assertEqual(self._replay()["status"], "HOLD")

    def test_missing_correction_source_review_blocks(self):
        self.trials[0]["correction_source_checked"] = False
        self.assertEqual(self._replay()["status"], "HOLD")

    def test_prior_meta_not_primary_source_blocks(self):
        self.trials[0]["source_tier"] = "T4"
        self.assertEqual(self._replay()["status"], "HOLD")

    def test_published_or_requires_exact_quote_location(self):
        self.packet["publication"]["pooled_or_binding"]["offset"] += 1
        self.assertEqual(self._replay()["status"], "HOLD")

    def test_engine_unavailable_does_not_execute(self):
        result = paired.check_replay(self.packet, self.root,
                engine_path=self.root / "missing" / "engine.py",
                engine_sha256=self.engine_digest)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["scientific_error_confirmed"])


if __name__ == "__main__":
    unittest.main()
