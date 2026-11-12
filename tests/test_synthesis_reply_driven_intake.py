"""Invented development cases for repeated values, scale limits and reply coverage.

No correspondence, paper identifiers or held-out labels are used here.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import synthesis_case_state as case
from test_synthesis_intake_evidence import XML, CONTEXT, PROMPT, ROOT, audit, identity, matched, packet, record, scalar
from test_synthesis_case_state import event, log, reply


def source(*paragraphs):
    addition = "".join("<p>" + p + "</p>" for p in paragraphs).encode()
    return XML.replace(b"</sec>", addition + b"</sec>")


def value_record(quote, number, *, role="estimate", unit="points", version="final-v2"):
    result = identity()
    result.pop("count_basis")
    result.update(data_version=version, effect_measure="mean score", estimand="observed mean",
                  comparison_id="synthetic-arm-A-score")
    return {"value": scalar(quote, number, role, unit), "identity": result,
            "definition": {"quote": CONTEXT}, "scope_verified": True}


def scalar_pair(left="2.46", right="2.64", **extra):
    a, b = f"Table mean {left} points.", f"Prose mean {right} points."
    raw = source(a, b)
    return raw, {"id": "REPEAT", "kind": "MATCHED_SCALARS", "snapshot_sha256": sha256(raw).hexdigest(),
                 "left": value_record(a, left), "right": value_record(b, right), **extra}


def registered(number, point, question_kind="CLARIFICATION"):
    return event(number, "POINT_REGISTERED", claim_id="C1", point_id=point,
                 original_question_reference="PRIVATE_SENTINEL_QUESTION", question_kind=question_kind)


class ReplyDrivenIntakeTests(unittest.TestCase):
    def finding(self, raw, check):
        return audit(check, payload=raw)["evidence_findings"][0]

    def test_same_result_stale_value_is_review_candidate_with_both_source_tokens(self):
        raw, check = scalar_pair()
        finding = self.finding(raw, check)
        self.assertEqual(finding["status"], "REVIEW_CANDIDATE")
        self.assertEqual(finding["left"]["binding"]["lexeme"], "2.46")
        self.assertEqual(finding["right"]["binding"]["lexeme"], "2.64")
        self.assertFalse(finding["comparability"]["scope_authenticated"])
        self.assertEqual(audit(check, payload=raw)["ledger"][0]["effective"], "HOLD")

    def test_final_and_interim_or_different_definitions_are_not_automatic_errors(self):
        raw, check = scalar_pair()
        for field, replacement in (("data_version", "interim-v1"), ("endpoint", "temporary-or-permanent-stop"),
                                   ("comparison_id", "synthetic-arm-B-score"), ("time_window", "other visit"),
                                   ("population", "restricted"), ("model", "different model")):
            with self.subTest(field=field):
                candidate = deepcopy(check); candidate["right"]["identity"][field] = replacement
                finding = self.finding(raw, candidate)
                self.assertEqual(finding["status"], "HOLD")
                self.assertEqual(finding["comparability"]["status"], "NOT_COMPARABLE")

    def test_missing_scope_definition_identity_or_role_holds(self):
        raw, check = scalar_pair()
        mutations = []
        bad = deepcopy(check); bad["left"]["scope_verified"] = False; mutations.append(bad)
        bad = deepcopy(check); bad["left"]["definition"] = {"quote": "Absent definition"}; mutations.append(bad)
        bad = deepcopy(check); del bad["left"]["identity"]["data_version"]; mutations.append(bad)
        bad = deepcopy(check); bad["right"]["value"]["role"] = "upper"; mutations.append(bad)
        bad = deepcopy(check); bad["right"]["identity"]["source_version"] = "PMC123.1"; mutations.append(bad)
        for bad in mutations:
            self.assertEqual(self.finding(raw, bad)["status"], "HOLD")

    def test_same_or_legitimately_rounded_values_pass_only_this_comparison(self):
        for left, right in (("2.46", "2.46"), ("2.46", "2.5"), ("-2.46", "-2.5"), ("2.460", "2.46")):
            with self.subTest(left=left, right=right):
                raw, check = scalar_pair(left, right)
                self.assertEqual(self.finding(raw, check)["status"], "NO_FLAG")

    def test_unknown_tie_policy_holds_and_explicit_policy_is_preserved(self):
        raw, check = scalar_pair("2.45", "2.4")
        self.assertEqual(self.finding(raw, check)["status"], "HOLD")
        check["rounding"] = "HALF_EVEN"
        self.assertEqual(self.finding(raw, check)["status"], "NO_FLAG")
        check["rounding"] = "HALF_UP"
        self.assertEqual(self.finding(raw, check)["status"], "REVIEW_CANDIDATE")

    def test_count_percent_unknown_rounding_policy_does_not_allege_a_tie_error(self):
        raw = source("Synthetic fraction 1 of 16 eligible participants (6.2%).")
        quote = "Synthetic fraction 1 of 16 eligible participants (6.2%)."
        check = {"id": "TIE", "kind": "COUNT_PERCENT", "snapshot_sha256": sha256(raw).hexdigest(),
                 "numerator": record(quote, "1"), "denominator": record(quote, "16"),
                 "percentage": scalar(quote, "6.2", "percentage", "percent")}
        self.assertEqual(self.finding(raw, check)["status"], "HOLD")
        check["rounding"] = "HALF_EVEN"
        self.assertEqual(self.finding(raw, check)["status"], "NO_FLAG")
        check["rounding"] = "HALF_UP"
        self.assertEqual(self.finding(raw, check)["status"], "REVIEW_CANDIDATE")

    def test_unambiguous_count_percent_rounding_error_still_flags(self):
        quote = "Synthetic fraction 28 of 37 eligible participants (75.8%)."
        raw = source(quote)
        check = {"id": "ROUND", "kind": "COUNT_PERCENT", "snapshot_sha256": sha256(raw).hexdigest(),
                 "numerator": record(quote, "28"), "denominator": record(quote, "37"),
                 "percentage": scalar(quote, "75.8", "percentage", "percent")}
        finding = self.finding(raw, check)
        self.assertEqual(finding["status"], "REVIEW_CANDIDATE")
        self.assertEqual(finding["rounded_percent"], "75.7")

    def test_explicit_scale_bounds_catch_decimal_displacement(self):
        raw = source("Scale limits are 0 to 7 points.", "Observed score 42 points.")
        check = {"id": "SCALE", "kind": "BOUNDED_VALUE", "snapshot_sha256": sha256(raw).hexdigest(),
                 "scope_verified": True, "scope_context": {"quote": "Scale limits are 0 to 7 points."},
                 "value": scalar("Observed score 42 points.", "42", "value", "points"),
                 "minimum": scalar("Scale limits are 0 to 7 points.", "0", "value", "points"),
                 "maximum": scalar("Scale limits are 0 to 7 points.", "7", "value", "points")}
        self.assertEqual(self.finding(raw, check)["status"], "REVIEW_CANDIDATE")
        raw = raw.replace(b"42 points", b"4.2 points")
        check["snapshot_sha256"] = sha256(raw).hexdigest()
        check["value"] = scalar("Observed score 4.2 points.", "4.2", "value", "points")
        self.assertEqual(self.finding(raw, check)["status"], "NO_FLAG")
        check["minimum"], check["maximum"] = check["maximum"], check["minimum"]
        self.assertEqual(self.finding(raw, check)["status"], "HOLD")

    def test_registered_unanswered_point_keeps_case_open(self):
        events = [registered(1, "P1"), registered(2, "P2"),
                  reply(3, "P1", "RESOLVED_ENQUIRY")]
        result = audit(matched(), log(events))
        summary = result["private_case_summary"]["claims"][0]
        self.assertEqual((summary["point_count"], summary["pending_point_count"], summary["unanswered_point_count"]), (2, 1, 1))
        self.assertEqual(result["ledger"][0]["effective"], "HOLD")
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))

    def test_registered_question_cannot_become_false_positive_error_allegation(self):
        events = [registered(1, "P1"), reply(2, outcome="FALSE_POSITIVE_ALLEGATION")]
        result = audit(matched(), log(events))
        self.assertFalse(result["intake_valid"])
        events[0]["question_kind"] = "ERROR_ALLEGATION"
        result = audit(matched(), log(events))
        self.assertTrue(result["intake_valid"])
        self.assertEqual(result["private_case_summary"]["claims"][0]["point_outcomes"], ["FALSE_POSITIVE_ALLEGATION"])

    def test_source_inspection_alone_and_editorial_closure_do_not_answer_registered_question(self):
        events = [registered(1, "P1"), reply(2, outcome="SOURCE_RECHECKED"),
                  event(3, "CORRECTION_STATUS", claim_id="C1", point_id="P1", status="DECLINED_OR_UNAVAILABLE",
                        evidence_reference="PRIVATE_SENTINEL_EDITORIAL")]
        result = audit(matched(), log(events))
        self.assertTrue(result["intake_valid"])
        self.assertEqual(result["private_case_summary"]["claims"][0]["pending_point_count"], 1)
        self.assertEqual(result["ledger"][0]["effective"], "HOLD")

    def test_classified_reply_requires_recheck_and_cannot_reclassify_original_question(self):
        events = [registered(1, "P1", "ERROR_ALLEGATION"), reply(2, outcome="RESOLVED_ENQUIRY")]
        self.assertFalse(audit(matched(), log(events))["intake_valid"])
        events[1]["outcome"] = "VERSION_LIMITED"
        del events[1]["source_recheck_reference"]
        self.assertFalse(audit(matched(), log(events))["intake_valid"])

    def test_scalar_denominator_contract_cannot_hide_incompatibility(self):
        raw, check = scalar_pair()
        for side in ("left", "right"):
            check[side]["identity"].update(analysis_denominator_n=20, analysis_denominator_unit="unique_participants")
        check["right"]["identity"]["analysis_denominator_n"] = 19
        self.assertEqual(self.finding(raw, check)["status"], "HOLD")
        for side in ("left", "right"): check[side]["identity"]["analysis_denominator_unit"] = "unknown-unit"
        self.assertEqual(self.finding(raw, check)["status"], "HOLD")

    def test_all_registered_points_resolve_independently_and_editorial_status_is_separate(self):
        events = [registered(1, "P1"), registered(2, "P2"),
                  reply(3, "P1", "RESOLVED_ENQUIRY"), reply(4, "P2", "VERSION_LIMITED"),
                  event(5, "CORRECTION_STATUS", claim_id="C1", point_id="P2", status="DECLINED_OR_UNAVAILABLE",
                        evidence_reference="PRIVATE_SENTINEL_EDITORIAL")]
        result = audit(matched(), log(events))
        self.assertTrue(result["intake_valid"])
        summary = result["private_case_summary"]["claims"][0]
        self.assertEqual(summary["pending_point_count"], 0)
        self.assertEqual(summary["correction_statuses"], ["DECLINED_OR_UNAVAILABLE"])
        self.assertFalse(summary["publication_independently_verified"])
        self.assertFalse(result["private_case_summary"]["email_eligible"])

    def test_registration_is_stable_and_invalid_history_cannot_be_appended(self):
        original = log([registered(1, "P1")])
        for mutation in (registered(2, "P1"), reply(2)):
            if mutation["type"] == "REPLY_POINT": mutation["original_question_reference"] = "different question"
            with self.assertRaises(ValueError): case.append_event(original, mutation)
        self.assertEqual(len(original["events"]), 1)

    def test_normal_cli_combines_scalar_evidence_with_unanswered_point_hold(self):
        raw, check = scalar_pair("2.46", "2.5")
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder); xml = parent / "article.xml"; xml.write_bytes(raw)
            p = parent / "packet.json"; p.write_text(json.dumps(packet(check)), encoding="utf-8")
            state_path = parent / "private-state.json"
            state_path.write_text(json.dumps(log([registered(1, "P1")])), encoding="utf-8")
            output = parent / "receipt"
            run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/synthesis_preflight.py"),
                                  "--packet", str(p), "--prompt", str(PROMPT), "--pmc-xml", str(xml),
                                  "--private-case-state", str(state_path), "--output-dir", str(output)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["evidence_findings"][0]["status"], "NO_FLAG")
            self.assertEqual(receipt["ledger"][0]["effective"], "HOLD")
            self.assertNotIn("PRIVATE_SENTINEL", (output / "receipt.json").read_text() + (output / "report.md").read_text())


if __name__ == "__main__": unittest.main()
