"""Synthetic-only tests of the supervised source/trial viewer; not accuracy evidence."""
import hashlib
import importlib.util
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_signed_and_embedded_counts_hold_without_candidate(self):
        for prefix, suffix in (("-", ""), ("−", ""), ("+", ""),
                               ("", "e1"), ("", "_000"), ("arm", "")):
            with self.subTest(prefix=prefix, suffix=suffix):
                case = self._case()
                case["published"] = self._snapshot(
                    "published.txt", f"Synthetic count {prefix}14{suffix} events")
                case["primary"] = self._snapshot(
                    "source.txt", f"Synthetic count {prefix}12{suffix} events")
                self.assertEqual(module.evaluate_case(case, self.root)["status"], "HOLD")

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

    def test_cli_refuses_output_aliases_before_evaluation_and_preserves_inputs(self):
        packet = self.root / "packet.json"
        packet.write_text(json.dumps(self.packet), encoding="utf-8")
        source = self.root / self.packet["cases"][0]["primary"]["path"]
        previous = self.root / "previous.html"
        previous.write_text("previous private report", encoding="utf-8")
        linked = self.root / "linked-source.txt"
        os.link(source, linked)
        targets = [packet, source, previous, linked]
        if os.name == "nt":
            targets.append(source.with_name(source.name.upper()))
        for target in targets:
            before = target.read_bytes()
            with self.subTest(target=target.name), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(module, "evaluate_packet", side_effect=AssertionError("must preflight first")):
                with self.assertRaises(SystemExit) as error:
                    module.main(["--packet", str(packet), "--source-root", str(self.root),
                                 "--html-out", str(target)])
                self.assertEqual(error.exception.code, 2)
            self.assertEqual(target.read_bytes(), before)

    def test_cli_does_not_create_a_missing_declared_source_as_output(self):
        missing = self.root / "missing-source.txt"
        self.packet["cases"][0]["primary"]["path"] = missing.name
        packet = self.root / "packet.json"
        packet.write_text(json.dumps(self.packet), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), \
                patch.object(module, "evaluate_packet", side_effect=AssertionError("must preflight first")):
            with self.assertRaises(SystemExit) as error:
                module.main(["--packet", str(packet), "--source-root", str(self.root),
                             "--html-out", str(missing)])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(missing.exists())




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

    def test_complete_integer_tokens_and_grouping(self):
        for text, value in (("5", 5), ("1,000", 1000)):
            quote = f"Count ({text}) participants"
            self.assertTrue(ledger._exact_binding(
                quote, {"text": text, "offset": quote.index(text)}, value))
        for token in ("5e1", "5_000", "5arms", "arm5", "-5", "−5", "+5", "5.0", "15"):
            quote = f"Count={token} participants"
            with self.subTest(token=token):
                self.assertFalse(ledger._exact_binding(
                    quote, {"text": "5", "offset": quote.index("5")}, 5))

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

    def test_selected_percentage_cannot_borrow_a_valid_occurrence_elsewhere(self):
        for invalid in ("-1.5%", "−1.5%", "+1.5%", "±1.5%", "11.5%", "1.5%%"):
            with self.subTest(invalid=invalid):
                row = self._row()
                key = row["trial_key"]
                pub = f"Review {key}: 2/67 ({invalid}) participants; other endpoint 1.5% of people."
                pri = f"{key} source reports 2 of 67 participants."
                row["case"]["published"] = self._snapshot("percentage-review.txt", pub)
                row["case"]["primary"] = self._snapshot("percentage-source.txt", pri)
                for context in row["case"]["contexts"].values():
                    context.update(denominator_basis="observed people",
                                   effect_measure="raw participant percentage",
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
                self.assertEqual(self._review(row)["rows"][0]["status"], "HOLD")
                row["bindings"]["published_percentage"]["offset"] = pub.rindex("1.5%")
                self.assertEqual(self._review(row)["rows"][0]["status"], "REVIEW_CANDIDATE")

    def test_malformed_row_membership_fields_hold_and_retain_following_row(self):
        for field in ("source_tier", "trial_key_type"):
            for invalid in ([], {}, None, 42):
                with self.subTest(field=field, invalid=invalid):
                    bad, good = self._row("bad"), self._row("good")
                    bad[field] = invalid
                    report = self._review(bad, good)
                    self.assertEqual([r["case_id"] for r in report["rows"]], ["bad", "good"])
                    self.assertEqual([r["status"] for r in report["rows"]], ["HOLD", "REVIEW_CANDIDATE"])
                    self.assertEqual(report["counts"]["HOLD"], 1)

    def test_malformed_comparison_kind_holds_and_retains_following_row(self):
        malformed = [{"kind": value} for value in ([], {}, None, 42)] + [[], None, 42]
        for comparison in malformed:
            with self.subTest(comparison=comparison):
                bad, good = self._row("bad"), self._row("good")
                bad["case"]["comparison"] = comparison
                report = self._review(bad, good)
                self.assertEqual([r["case_id"] for r in report["rows"]], ["bad", "good"])
                self.assertEqual([r["status"] for r in report["rows"]], ["HOLD", "REVIEW_CANDIDATE"])
                self.assertEqual(report["counts"]["HOLD"], 1)

    def test_cli_preflights_all_outputs_and_preserves_existing_sources(self):
        row = self._row()
        packet = self.root / "packet.json"
        packet.write_text(json.dumps({"ledger_version": "0.1", "synthesis_id": "invented",
                                      "rows": [row]}), encoding="utf-8")
        source = self.root / row["case"]["primary"]["path"]
        html_out = self.root / "review.html"
        for second in (packet, source, html_out, self.root / "unused" / ".." / html_out.name):
            before = {p: p.read_bytes() for p in (packet, source)}
            with self.subTest(second=str(second)), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(ledger, "review_ledger", side_effect=AssertionError("preflight first")):
                with self.assertRaises(SystemExit) as error:
                    ledger.main(["--packet", str(packet), "--source-root", str(self.root),
                                 "--html-out", str(html_out), "--json-out", str(second)])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(html_out.exists())
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data)

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
        publication = "Analysis used Paule-Mandel and floored Knapp-Hartung. Reported pooled OR: 0.80 (95% CI 0.60 to 1.05)."
        self.packet = {
            "schema_version": "0.1",
            "claim_version_status": "CURRENT_UNCORRECTED",
            "analysis": self.analysis,
            "publication": {
                "snapshot": self._snapshot("meta.txt", publication),
                "model": paired.METHOD, "published_method_source_checked": True,
                "method_quote": "Paule-Mandel and floored Knapp-Hartung",
                "published_variance_floor_source_verified": True,
                "variance_floor_quote": "floored Knapp-Hartung",
                "pooled_or_text": "0.80",
                "pooled_or_binding": {"text": "0.80", "offset": publication.index("0.80")},
                "ci_low_text": "0.60",
                "ci_low_binding": {"text": "0.60", "offset": publication.index("0.60")},
                "ci_high_text": "1.05",
                "ci_high_binding": {"text": "1.05", "offset": publication.index("1.05")},
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
        if not run_engine:
            return paired.check_replay(self.packet, self.root)
        # Fake engine exercises orchestration only, not real pooling correctness
        # or trust in the separately pinned external meta-starter-kit source.
        import types
        def make_effect(name, tE, tN, cE, cN, nct=None):
            return types.SimpleNamespace(tE=tE, name=name)
        def fake_pool(effects, scale):
            if scale != "OR":
                raise ValueError("unsupported")
            point = 0.8 if sum(e.tE for e in effects) == 10 else 0.9
            return types.SimpleNamespace(k=len(effects), pooled=point,
                ci_low=0.60, ci_high=1.05, tau2=0.01, i2=10.0)
        toy = types.SimpleNamespace(binary_effect=make_effect, pool_effects=fake_pool)
        with patch.object(paired, "_engine_at", return_value=toy):
            return paired.check_replay(self.packet, self.root,
                engine_path=self.fake_engine, engine_sha256=self.engine_digest)

    def test_preflight_without_engine_does_not_claim_model_replay(self):
        result = self._replay(False)
        self.assertEqual(result["status"], "READY_FOR_PINNED_ENGINE")
        self.assertEqual(result["model_fit"], "NOT_RUN")
        self.assertFalse(result["scientific_error_confirmed"])

    def test_exponent_count_blocks_before_engine_loading(self):
        row = self.trials[0]
        text = row["published_extraction"]["quote"].replace("tE=5", "tE=5e1")
        row["published_extraction"] = self._snapshot("exponent.txt", text)
        for field, value in row["original"].items():
            row["original_bindings"][field]["offset"] = text.index(field + "=") + len(field) + 1
        with patch.object(paired, "_engine_at") as load:
            result = paired.check_replay(self.packet, self.root,
                engine_path=self.fake_engine, engine_sha256=self.engine_digest)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["model_fit"], "NOT_RUN")
        load.assert_not_called()

    def test_unicode_signed_publication_value_holds(self):
        pub = self.packet["publication"]
        text = pub["snapshot"]["quote"].replace("0.80", "−0.80")
        pub["snapshot"] = self._snapshot("signed.txt", text)
        for field in ("pooled_or", "ci_low", "ci_high"):
            pub[field + "_binding"]["offset"] = text.index(pub[field + "_text"])
        self.assertEqual(self._replay(False)["status"], "HOLD")

    def test_failed_correction_preserves_original_and_execution_receipt(self):
        import types
        calls = []
        def pool(effects, scale):
            calls.append(scale)
            if len(calls) == 2:
                raise ValueError("synthetic corrected fit failed")
            return types.SimpleNamespace(k=len(effects), pooled=.8, ci_low=.60,
                                         ci_high=1.05, tau2=.01, i2=10.0)
        toy = types.SimpleNamespace(binary_effect=lambda *args, **kwargs: object(), pool_effects=pool)
        with patch.object(paired, "_engine_at", return_value=toy):
            result = paired.check_replay(self.packet, self.root,
                engine_path=self.fake_engine, engine_sha256=self.engine_digest)
        self.assertEqual(calls, ["OR", "OR"])
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["model_fit"], "ACTUALLY_EXECUTED")
        self.assertEqual(result["published_replay"]["pooled"], .8)
        self.assertEqual(result["corrected_replay"], "FAILED")
        self.assertEqual(result["replay_stages"], {"published": "COMPLETED", "corrected": "FAILED"})
        self.assertEqual(result["external_engine_sha256"], self.engine_digest)
        self.assertNotIn("delta_pooled_or", result)

    def test_failed_original_records_attempt_and_never_corrects(self):
        import types
        toy = types.SimpleNamespace(binary_effect=lambda *args, **kwargs: None)
        with patch.object(paired, "_engine_at", return_value=toy):
            result = paired.check_replay(self.packet, self.root,
                engine_path=self.fake_engine, engine_sha256=self.engine_digest)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["model_fit"], "EXECUTION_ATTEMPTED")
        self.assertEqual(result["replay_stages"], {"published": "FAILED", "corrected": "NOT_RUN"})
        self.assertEqual(result["corrected_replay"], "NOT_RUN")

    def test_verified_source_executes_instead_of_timestamp_valid_bytecode(self):
        import os
        import py_compile
        source = b"probe='SOURCE'\ndef binary_effect(): pass\ndef pool_effects(): pass\n"
        cached = source.replace(b"SOURCE", b"CACHED")
        self.fake_engine.write_bytes(cached)
        timestamp = self.fake_engine.stat().st_mtime
        py_compile.compile(str(self.fake_engine), doraise=True)
        self.fake_engine.write_bytes(source)
        os.utime(self.fake_engine, (timestamp, timestamp))
        blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        with patch.object(paired, "SUPPORTED_ENGINE_GIT_BLOB_SHA1", blob):
            actual = paired._engine_at(self.fake_engine, hashlib.sha256(source).hexdigest())
        self.assertEqual(actual.probe, "SOURCE")

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

    def test_published_interval_mismatch_blocks_corrected_fit(self):
        pub = self.packet["publication"]
        pub["ci_high_text"] = "1.06"
        txt = pub["snapshot"]["quote"].replace("1.05", "1.06")
        pub["snapshot"] = self._snapshot("meta.txt", txt)
        pub["ci_high_binding"]["text"] = "1.06"
        out = self._replay()
        self.assertEqual(out["status"], "PUBLISHED_REPLAY_MISMATCH")
        self.assertIn("ci_high", out["reason"])
        self.assertEqual(out["corrected_replay"], "NOT_RUN")

    def test_published_or_cannot_bind_suffix_of_larger_decimal(self):
        pub = self.packet["publication"]
        text = pub["snapshot"]["quote"].replace("0.80", "10.80")
        pub["snapshot"] = self._snapshot("meta.txt", text)
        pub["pooled_or_binding"]["offset"] = text.index("10.80") + 1
        out = self._replay(False)
        self.assertEqual(out["status"], "HOLD")
        self.assertTrue("not bound" in out["reason"] or "larger" in out["reason"])

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

    def test_unverified_variance_floor_blocks_before_replay(self):
        self.packet["publication"]["published_variance_floor_source_verified"] = False
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("variance-floor", result["reason"])

    def test_variance_floor_quote_must_be_in_original_paper(self):
        self.packet["publication"]["variance_floor_quote"] = "not found in publication"
        result = self._replay()
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("not bound to report", result["reason"])

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

    def test_exact_engine_source_pin_is_checked(self):
        self.assertEqual(
            paired.SUPPORTED_ENGINE_GIT_BLOB_SHA1,
            "768aeb1e8dd892f388dffe6c636293be92a74107",
        )
        # User-selected SHA-256 alone is insufficient to substitute a fake file.
        result = paired.check_replay(self.packet, self.root,
                      engine_path=self.fake_engine, engine_sha256=self.engine_digest)
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("pinned Git blob", result["reason"])

    def test_engine_unavailable_does_not_execute(self):
        result = paired.check_replay(self.packet, self.root,
                engine_path=self.root / "missing" / "engine.py",
                engine_sha256=self.engine_digest)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["scientific_error_confirmed"])


class OutputPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_complete_utf8_outputs_are_published_without_temporary_files(self):
        first, second = self.root / "view.html", self.root / "receipt.json"
        module._publish_outputs([(first, "private café"), (second, "{\"complete\": true}\n")])
        self.assertEqual(first.read_bytes(), "private café".encode("utf-8"))
        self.assertEqual(json.loads(second.read_text(encoding="utf-8")), {"complete": True})
        self.assertEqual(set(self.root.iterdir()), {first, second})

    def test_cli_existing_and_dangling_symlink_outputs_are_refused(self):
        source = self.root / "private-source.txt"
        source.write_text("original private source", encoding="utf-8")
        existing = self.root / "existing-source-link.txt"
        try:
            existing.symlink_to(source)
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege unavailable; required on Ubuntu")
            raise
        missing = self.root / "missing-source.txt"
        dangling = self.root / "dangling-source-link.txt"
        dangling.symlink_to(missing)
        packet = self.root / "packet.json"
        packet.write_text("{}", encoding="utf-8")
        base = ["--packet", str(packet), "--source-root", str(self.root)]
        other = self.root / "receipt.json"
        for destination in (existing, dangling):
            for tool, evaluator, arguments in (
                (module, "evaluate_packet", [*base, "--html-out", str(destination)]),
                (ledger, "review_ledger", [*base, "--html-out", str(destination),
                                           "--json-out", str(other)]),
                (paired, "check_replay", [*base, "--out", str(destination)]),
            ):
                with self.subTest(tool=tool.__name__, destination=destination.name), \
                        contextlib.redirect_stderr(io.StringIO()), \
                        patch.object(tool, evaluator, side_effect=AssertionError("must preflight first")):
                    with self.assertRaises(SystemExit) as error:
                        tool.main(arguments)
                    self.assertEqual(error.exception.code, 2)
                self.assertEqual(source.read_text(encoding="utf-8"), "original private source")
                self.assertTrue(existing.is_symlink())
                self.assertTrue(dangling.is_symlink())
                self.assertFalse(missing.exists())
                self.assertFalse(other.exists())

    def test_second_output_race_preserves_competing_file_and_rolls_back_first(self):
        for name, parent_alias in (("ordinary", False), ("normalized-parent", True)):
            with self.subTest(path_form=name):
                actual_root = self.root / name
                actual_root.mkdir()
                # The redundant parent segment exercises normalization on every
                # platform, including hosts without Windows 8.3 short names.
                requested_root = actual_root / ".." / name if parent_alias else actual_root
                first, second = requested_root / "view.html", requested_root / "receipt.json"
                second_identity = second.resolve()
                real_link = os.link
                injected = []
                def raced_link(source, destination):
                    if Path(destination).resolve() == second_identity:
                        injected.append(str(destination))
                        Path(destination).write_text("another process owns this", encoding="utf-8")
                    return real_link(source, destination)
                with patch.object(module.os, "link", side_effect=raced_link):
                    with self.assertRaises(ValueError):
                        module._publish_outputs([(first, "private view"), (second, "private receipt")])
                self.assertEqual(len(injected), 1, "competing-file race must actually execute")
                self.assertFalse(first.exists())
                self.assertEqual(second.read_text(encoding="utf-8"), "another process owns this")
                self.assertEqual(set(actual_root.resolve().iterdir()), {second_identity})

    def test_staging_failure_leaves_no_published_output(self):
        first, second = self.root / "view.html", self.root / "receipt.json"
        real_fsync = os.fsync
        calls = 0
        def failed_sync(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected write failure")
            return real_fsync(fd)
        with patch.object(module.os, "fsync", side_effect=failed_sync):
            with self.assertRaises(ValueError):
                module._publish_outputs([(first, "private view"), (second, "private receipt")])
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
