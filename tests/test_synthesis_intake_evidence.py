"""Normal-intake contracts using wholly synthetic OA JATS and private metadata."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import synthesis_preflight as preflight

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "docs/SYNTHESIS-PREFLIGHT-v1.1.md"
XML = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<article-id pub-id-type="pmcid">PMC123</article-id><article-id pub-id-type="pmcid-ver">PMC123.2</article-id>
<article-id pub-id-type="doi">10.1234/synthetic</article-id><permissions>
<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>
</article-meta></front><body><sec><title>Synthetic results</title>
<p>One synthetic trial, arm A, endpoint E at visit V; raw observed participants.</p>
<p>Randomised population: 36 participants. Treated population: 32 participants.</p>
<p>Four not treated: exclusion count 4. The restricted count is 32.</p>
<p>Response count 8 of 32 treated participants (25.0%).</p>
<p>Same treated count: 32 participants.</p>
<p>Mean difference -1.4 units; two-sided reported interval -2.6 to -0.2 units.</p>
<p>Stale mean difference -0.8 units.</p>
<p>Raw percentage label and raw scale. Interval method: reported two-sided.</p>
</sec></body></article>'''
SHA = sha256(XML).hexdigest()
CONTEXT = "One synthetic trial, arm A, endpoint E at visit V; raw observed participants."


def ref(quote, number):
    return {"quote": quote, "count_text": number}


def scalar(quote, number, role="estimate", unit="units"):
    return {"quote": quote, "number_text": number, "role": role,
            "unit": unit, "scale": "raw"}


def identity(population="treated"):
    return {"source_result_id": "synthetic-E-V-A", "data_version": "synthetic-v1",
            "count_basis": "unique_participants", "denominator_basis": population,
            "analysis_cell_id": "arm-A", "population": population, "endpoint": "E",
            "time_window": "V", "effect_measure": "raw count", "estimand": "observed count",
            **{k: "not_applicable" for k in ("model", "adjustment", "multiplicity", "missingness",
                                              "censoring", "variance_method", "test_statistic_identity")}}


def record(quote, number, population="treated"):
    return {"count": ref(quote, number), "identity": identity(population),
            "definition": {"quote": CONTEXT}, "scope_verified": True}


def packet(check):
    return {"schema_version": "1.1", "run": {"run_id": "synthetic-evidence", "model_id": "none",
            "model_provider": "manual", "tool_versions": {}, "prompt_sha256": sha256(PROMPT.read_bytes()).hexdigest()},
            "document": {"pmcid": "PMC123", "identifier": "10.1234/synthetic", "version": "PMC123.2"},
            "sources": [], "claims": [{"id": "C1", "text": "Synthetic scoped claim", "locator": "Results",
            "source_ids": [], "source_support": "SUPPORTED", "evidence_maturity": "SCREENED", "priority": "P4",
            "proposed_disposition": "NO_FLAG", "evidence_checks": [check]}]}


def matched():
    return {"id": "MATCH", "kind": "MATCHED_COUNTS", "snapshot_sha256": SHA,
            "left": record("Treated population: 32 participants.", "32"),
            "right": record("Same treated count: 32 participants.", "32")}


def audit(check, private_state=None, payload=XML):
    p = packet(check)
    with tempfile.TemporaryDirectory() as folder:
        xml = Path(folder) / "article.xml"
        xml.write_bytes(payload)
        return preflight.review_packet(p, p["run"]["prompt_sha256"], sha256(json.dumps(p).encode()).hexdigest(),
                                       pmc_xml=xml, private_case_state=private_state)


class IntakeEvidenceTests(unittest.TestCase):
    def finding(self, check):
        return audit(check)["evidence_findings"][0]

    def test_matched_counts_bind_definitions_and_source_identity(self):
        result = audit(matched())
        finding = result["evidence_findings"][0]
        self.assertEqual(finding["status"], "NO_FLAG")
        self.assertEqual(finding["identity"]["status"], "CONSISTENT")
        self.assertEqual(finding["left"]["source_sha256"], SHA)
        self.assertEqual(finding["left"]["definition"]["quote"], CONTEXT)
        self.assertEqual(result["ledger"][0]["effective"], "NO_FLAG")

    def test_different_or_missing_populations_cannot_raise_an_error(self):
        check = matched()
        check["left"] = record("Randomised population: 36 participants.", "36", "randomised")
        finding = self.finding(check)
        self.assertEqual((finding["status"], finding["identity"]["status"]), ("HOLD", "NOT_COMPARABLE"))
        del check["right"]["identity"]["population"]
        self.assertEqual(self.finding(check)["status"], "HOLD")

    def test_unsupported_definition_and_stale_snapshot_hold(self):
        for mutation in ("definition", "snapshot"):
            check = matched()
            if mutation == "definition": check["left"]["definition"] = {"quote": "Absent definition."}
            else: check["snapshot_sha256"] = "0" * 64
            self.assertEqual(self.finding(check)["status"], "HOLD")

    def test_censored_count_cannot_be_treated_as_exact(self):
        payload = XML.replace(b"Treated population: 32 participants.", b"Treated population: &lt;32 participants.")
        check = matched(); check["snapshot_sha256"] = sha256(payload).hexdigest()
        check["left"]["count"]["quote"] = "Treated population: <32 participants."
        self.assertEqual(audit(check, payload=payload)["evidence_findings"][0]["status"], "HOLD")

    def test_excerpt_cannot_hide_a_percent_sign_outside_the_quote(self):
        payload = XML.replace(b"</sec>", b"<p>Synthetic percentage 17 %.</p></sec>")
        check = matched(); check["snapshot_sha256"] = sha256(payload).hexdigest()
        check["left"]["count"] = ref("17", "17")
        self.assertEqual(audit(check, payload=payload)["evidence_findings"][0]["status"], "HOLD")

    def test_restricted_accounting_requires_identity_and_complete_exclusions(self):
        check = {"id": "SUBSET", "kind": "STRICT_SUBSET", "relationship": "STRICT_SUBSET", "snapshot_sha256": SHA,
                 "primary": record("Randomised population: 36 participants.", "36", "randomised"),
                 "restricted": record("The restricted count is 32.", "32"),
                 "exclusions": [record("exclusion count 4.", "4", "excluded")],
                 "exclusions_disjoint_verified": True, "exclusions_exhaustive_verified": True}
        finding = self.finding(check)
        self.assertEqual((finding["status"], finding["expected_restricted"]), ("NO_FLAG", 32))
        incomplete = deepcopy(check); del incomplete["exclusions"]
        self.assertEqual(self.finding(incomplete)["status"], "HOLD")
        for relation in ("REMATCHED", "DIFFERENT_RISK_SET", "UNKNOWN"):
            bad = deepcopy(check); bad["relationship"] = relation
            self.assertEqual(self.finding(bad)["status"], "HOLD")
        bad = deepcopy(check); bad["restricted"]["identity"]["time_window"] = "other visit"
        self.assertEqual(self.finding(bad)["status"], "HOLD")

    def test_restricted_wrong_smaller_count_is_a_candidate(self):
        check = {"id": "SUBSET", "kind": "STRICT_SUBSET", "relationship": "STRICT_SUBSET", "snapshot_sha256": SHA,
                 "primary": record("Randomised population: 36 participants.", "36", "randomised"),
                 "restricted": record("Response count 8 of 32 treated participants (25.0%).", "8"),
                 "exclusions": [record("exclusion count 4.", "4", "excluded")],
                 "exclusions_disjoint_verified": True, "exclusions_exhaustive_verified": True}
        self.assertEqual(self.finding(check)["status"], "REVIEW_CANDIDATE")

    def test_legacy_count_arithmetic_cannot_bypass_source_bound_identity(self):
        p = packet(matched()); del p["claims"][0]["evidence_checks"]
        p["claims"][0]["participant_count_check"] = {
            "kind": "RESTRICTED", "context_quote": CONTEXT, "scope_verified": True,
            "outcome": "E", "timepoint": "V", "basis": "participants", "snapshot_sha256": SHA,
            "primary": ref("Randomised population: 36 participants.", "36"),
            "restricted": ref("The restricted count is 32.", "32"),
            "exclusion_counts": [ref("exclusion count 4.", "4")],
            "exclusions_disjoint_verified": True, "exclusions_exhaustive_verified": True}
        with tempfile.TemporaryDirectory() as folder:
            xml = Path(folder) / "a.xml"; xml.write_bytes(XML)
            result = preflight.review_packet(p, p["run"]["prompt_sha256"], SHA, pmc_xml=xml)
        finding = result["participant_count_findings"][0]
        self.assertEqual((finding["status"], finding["decision_status"]), ("NO_FLAG", "HOLD"))
        self.assertEqual(result["ledger"][0]["effective"], "HOLD")

    def test_count_percent_uses_source_denominator_and_printed_precision(self):
        check = {"id": "PCT", "kind": "COUNT_PERCENT", "snapshot_sha256": SHA,
                 "numerator": record("Response count 8 of 32 treated participants (25.0%).", "8"),
                 "denominator": record("Treated population: 32 participants.", "32"),
                 "percentage": scalar("Response count 8 of 32 treated participants (25.0%).", "25.0", "percentage", "percent")}
        finding = self.finding(check)
        self.assertEqual((finding["status"], finding["computed_percent"]), ("NO_FLAG", "25"))
        check["denominator"] = record("Randomised population: 36 participants.", "36", "randomised")
        self.assertEqual(self.finding(check)["status"], "HOLD")

    def interval(self):
        quote = "Mean difference -1.4 units; two-sided reported interval -2.6 to -0.2 units."
        return {"id": "CI", "kind": "INTERVAL", "snapshot_sha256": SHA,
                "estimate": scalar(quote, "-1.4"), "lower": scalar(quote, "-2.6", "lower"),
                "upper": scalar(quote, "-0.2", "upper"), "effect_measure": "mean difference",
                "method": "reported_two_sided", "method_context": {"quote": "Interval method: reported two-sided."},
                "scope_verified": True}

    def test_signed_intervals_preserve_lexemes_and_roles(self):
        finding = self.finding(self.interval())
        self.assertEqual(finding["status"], "NO_FLAG")
        self.assertEqual(finding["values"]["upper"]["lexeme"], "-0.2")
        self.assertEqual(finding["values"]["upper"]["role"], "upper")
        self.assertFalse(finding["interval_method_validated"])

    def test_partial_sign_invented_value_and_different_unit_hold(self):
        for key, value in (("number_text", "0.2"), ("number_text", "-0.3"), ("unit", "different units")):
            check = self.interval(); check["upper"][key] = value
            self.assertEqual(self.finding(check)["status"], "HOLD")

    def test_excerpt_cannot_hide_a_sign_outside_the_selected_quote(self):
        check = self.interval()
        check["upper"].update(quote="0.2 units.", number_text="0.2")
        self.assertEqual(self.finding(check)["status"], "HOLD")
        check = self.interval(); check["upper"].update(quote="0.2 units.", number_text="0.2")
        payload = XML.replace(b"to -0.2 units.", b"to - 0.2 units.")
        check["snapshot_sha256"] = sha256(payload).hexdigest()
        self.assertEqual(audit(check, payload=payload)["evidence_findings"][0]["status"], "HOLD")

    def test_reversed_interval_is_a_candidate_without_reconstructing_the_model(self):
        check = self.interval()
        check["lower"]["number_text"], check["upper"]["number_text"] = "-0.2", "-2.6"
        self.assertEqual(self.finding(check)["status"], "REVIEW_CANDIDATE")

    def sweep(self):
        return {"id": "SWEEP", "kind": "REVISION_SWEEP", "snapshot_sha256": SHA,
                "expected": scalar("Mean difference -1.4 units; two-sided reported interval -2.6 to -0.2 units.", "-1.4"),
                "occurrences": [{"id": "abstract", "root_id": "copy", "ref": scalar("Stale mean difference -0.8 units.", "-0.8")}],
                "dependencies": [{"id": "external-figure", "locator": "External synthetic figure", "status": "UNINSPECTED"}]}

    def test_revision_sweep_keeps_stale_and_uninspected_dependencies(self):
        finding = self.finding(self.sweep())
        self.assertEqual(finding["status"], "REVIEW_CANDIDATE")
        self.assertEqual(finding["occurrences"][0]["status"], "STALE")
        self.assertEqual(finding["coverage"], "REVIEWER_SELECTED_ONLY")
        self.assertEqual(finding["dependencies"][0]["status"], "UNINSPECTED")
        self.assertEqual(finding["root_groups"]["root_count"], 1)

    def test_dependency_cycle_duplicate_token_and_missing_coverage_hold(self):
        check = self.sweep(); del check["dependencies"]
        self.assertEqual(self.finding(check)["status"], "HOLD")
        check = self.sweep(); check["occurrences"].append({**check["occurrences"][0], "id": "duplicate"})
        self.assertEqual(self.finding(check)["status"], "HOLD")
        check = self.sweep(); check["dependencies"] = [
            {"id": "a", "locator": "a", "status": "UNINSPECTED", "depends_on": ["b"]},
            {"id": "b", "locator": "b", "status": "UNINSPECTED", "depends_on": ["a"]}]
        self.assertEqual(self.finding(check)["status"], "HOLD")

    def test_matching_sweep_retains_uninspected_dependency_hold(self):
        check = self.sweep(); check["occurrences"][0]["ref"] = deepcopy(check["expected"])
        self.assertEqual(self.finding(check)["status"], "HOLD")
        check["dependencies"] = []
        self.assertEqual(self.finding(check)["status"], "NO_FLAG")

    def test_arbitrary_unit_is_not_accepted_even_when_all_roles_agree(self):
        check = self.interval()
        for role in ("estimate", "lower", "upper"): check[role]["unit"] = "invented units"
        self.assertEqual(self.finding(check)["status"], "HOLD")

    def test_invalid_root_identity_cannot_clear_a_matching_sweep(self):
        check = self.sweep(); check["occurrences"][0].update(root_id="copy\u200d", ref=deepcopy(check["expected"]))
        check["dependencies"] = []
        self.assertEqual(self.finding(check)["status"], "HOLD")

    def test_oversized_or_malformed_checks_fail_closed(self):
        for bad in (None, [matched()] * 41, {"not": "a list"}):
            p = packet(matched()); p["claims"][0]["evidence_checks"] = bad
            with tempfile.TemporaryDirectory() as folder:
                xml = Path(folder) / "a.xml"; xml.write_bytes(XML)
                result = preflight.review_packet(p, p["run"]["prompt_sha256"], SHA, pmc_xml=xml)
            self.assertFalse(result["intake_valid"])
            self.assertEqual(result["ledger"][0]["effective"], "HOLD")
        check = matched(); check["id"] = ["invalid"]
        self.assertFalse(audit(check)["intake_valid"])

    def test_documented_demo_runs_through_normal_cli(self):
        fixture = ROOT / "examples/synthesis_intake_demo"
        with tempfile.TemporaryDirectory() as folder:
            run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/synthesis_preflight.py"),
                                  "--prompt", str(PROMPT), "--packet", str(fixture / "packet.json"),
                                  "--pmc-xml", str(fixture / "article.xml"), "--output-dir", folder],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads((Path(folder) / "receipt.json").read_text())
            self.assertEqual([f["status"] for f in result["evidence_findings"]],
                             ["NO_FLAG", "NO_FLAG", "NO_FLAG", "NO_FLAG", "REVIEW_CANDIDATE"])
            self.assertEqual(result["ledger"][0]["effective"], "HOLD")
            self.assertIn("UNINSPECTED", (Path(folder) / "report.md").read_text())


if __name__ == "__main__": unittest.main()
