"""Synthetic, offline regression tests; no research-performance claims."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scicoqa_paired_benchmark.py"
spec = importlib.util.spec_from_file_location("scicoqa_paired_benchmark", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

UPSTREAM = "  prompts: |\n  discrepancy_generation: |\n    Paper ${paper}\n    Code ${code}\n  other: |\n    bad\n"
BASE = "Paper ${paper}\nCode ${code}\n"
CANDIDATE = "Carefully check ${paper}\nversus ${code}\n"
SHA = "a" * 40


def context(cid, split="real"):
    return {"case_id": cid, "paper_family_id": "family-" + cid,
            "split": split, "paper_version": "https://arxiv.org/pdf/testv1.pdf",
            "code_commit": SHA, "paper_text": "Paper mentions L2 normalization",
            "code_text": "def normalize(x): return sum(abs(x))"}


def prepared(rows):
    return m.make_prompts(rows, BASE, CANDIDATE, "fixed-model", "exact-revision", {"temperature": 0}, SHA)


def prediction(manifest, cid, arm, status, findings):
    c = next(x for x in manifest["cases"] if x["case_id"] == cid)
    return {"case_id": cid, "arm": arm, "manifest_sha256": m.digest(m.canonical(manifest)),
            "rendered_prompt_sha256": c["rendered_prompt_sha256"][arm],
            "model": manifest["model"], "model_revision": manifest["model_revision"],
            "decoding_config": manifest["decoding_config"], "status": status,
            "findings": [{"finding_id": f, "text": "Model finding"} for f in findings]}


def review(cid, refs, base_matches=None, synth_matches=None, base_false=None, synth_false=None):
    base_matches = base_matches or []
    synth_matches = synth_matches or []
    base_false = base_false or []
    synth_false = synth_false or []
    return {"case_id": cid, "review_state": "COMPLETE", "reference_ids": refs,
            "independently_adjudicated": True, "reviewer_count": 2,
            "by_arm": {"baseline": {"matches": base_matches, "false_positive_ids": base_false,
                                    "unresolved_ids": [], "review_minutes": 1},
                       "synthesis": {"matches": synth_matches, "false_positive_ids": synth_false,
                                     "unresolved_ids": [], "review_minutes": 2}}}


class PairPreparationTests(unittest.TestCase):
    def test_family_id_is_required_and_frozen(self):
        c = context("C1")
        c["paper_family_id"] = "same-paper"
        manifest, _ = prepared([c])
        self.assertEqual(manifest["cases"][0]["paper_family_id"], "same-paper")
        del c["paper_family_id"]
        with self.assertRaises(m.BenchmarkError):
            prepared([c])

    def test_verbatim_plain_and_same_underlying_inputs(self):
        manifest, out = prepared([context("C1")])
        self.assertEqual(out["baseline"][0]["prompt"], BASE.replace("${paper}", context("C1")["paper_text"]).replace("${code}", context("C1")["code_text"]))
        self.assertIn(context("C1")["code_text"], out["synthesis"][0]["prompt"])
        self.assertEqual(manifest["cases"][0]["code_sha256"], m.digest(context("C1")["code_text"]))
        self.assertNotEqual(out["baseline"][0]["rendered_prompt_sha256"], out["synthesis"][0]["rendered_prompt_sha256"])

    def test_preparation_rejects_label_leak_and_wrong_commit(self):
        c = context("C1")
        c["reference_ids"] = ["hidden"]
        with self.assertRaises(m.BenchmarkError):
            prepared([c])
        c = context("C1")
        c["code_commit"] = "main"
        with self.assertRaises(m.BenchmarkError):
            prepared([c])

    def test_upstream_yaml_literal(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "prompts.yaml"
            p.write_text(UPSTREAM, encoding="utf-8")
            self.assertEqual(m.upstream_plain_prompt(p), BASE)


class ScoreTests(unittest.TestCase):
    def test_real_and_synthetic_denominators_remain_separate(self):
        manifest, _ = prepared([context("R", "real"), context("S", "synthetic")])
        preds = [prediction(manifest, cid, arm, "COMPLETE", ["f"] if arm == hit else [])
                 for cid, hit in [("R", "baseline"), ("S", "synthesis")] for arm in m.ARMS]
        reviews = [review("R", ["r"], [{"finding_id": "f", "reference_id": "r"}]),
                   review("S", ["r"], synth_matches=[{"finding_id": "f", "reference_id": "r"}])]
        result = m.score(manifest, preds, reviews)
        key = "full_reference_recall_including_abstentions_and_failures"
        self.assertEqual(result["arms"]["baseline"][key]["value"], 0.5)
        self.assertEqual(result["by_split"]["real"]["arms"]["baseline"][key]["value"], 1)
        self.assertEqual(result["by_split"]["synthetic"]["arms"]["baseline"][key]["value"], 0)
        self.assertEqual(result["by_split"]["synthetic"]["paired"]["synthesis_only_reference_detections"], 1)
        self.assertIn("secondary", result["aggregate_role"])

    def test_paired_reference_recall_with_abstention_and_false_alert(self):
        manifest, _ = prepared([context("A"), context("B"), context("C")])
        preds = [prediction(manifest, "A", "baseline", "COMPLETE", ["b1"]),
                 prediction(manifest, "A", "synthesis", "COMPLETE", ["s1"]),
                 prediction(manifest, "B", "baseline", "ABSTAIN", []),
                 prediction(manifest, "B", "synthesis", "COMPLETE", ["s2"]),
                 prediction(manifest, "C", "baseline", "COMPLETE", ["b3"]),
                 prediction(manifest, "C", "synthesis", "COMPLETE", [])]
        reviews = [review("A", ["R1"], [{"finding_id": "b1", "reference_id": "R1"}],
                          [{"finding_id": "s1", "reference_id": "R1"}]),
                   review("B", ["R2"], synth_matches=[{"finding_id": "s2", "reference_id": "R2"}]),
                   review("C", [], base_false=["b3"])]
        scored = m.score(manifest, preds, reviews)
        self.assertEqual(scored["reference_error_count"], 2)
        self.assertEqual(scored["arms"]["baseline"]["full_reference_recall_including_abstentions_and_failures"]["value"], 0.5)
        self.assertEqual(scored["arms"]["synthesis"]["full_reference_recall_including_abstentions_and_failures"]["value"], 1.0)
        self.assertEqual(scored["paired"]["synthesis_only_reference_detections"], 1)
        self.assertEqual(scored["arms"]["baseline"]["false_alerts_per_100_verified_clean_cases"]["value"], 100.0)
        self.assertEqual(scored["arms"]["baseline"]["abstained_cases"], 1)
        self.assertIsNone(scored["paired"]["confidence_interval"])

    def test_unreviewed_reference_cases_cannot_be_falsely_clean(self):
        manifest, _ = prepared([context("A")])
        preds = [prediction(manifest, "A", a, "COMPLETE", ["f1"]) for a in m.ARMS]
        unknown = {"case_id": "A", "review_state": "UNKNOWN", "reference_ids": [],
                   "by_arm": {a: {"matches": [], "false_positive_ids": [], "unresolved_ids": ["f1"],
                                  "review_minutes": 1} for a in m.ARMS}}
        result = m.score(manifest, preds, [unknown])
        self.assertEqual(result["unknown_reference_case_count"], 1)
        self.assertEqual(result["verified_clean_case_count"], 0)
        self.assertIsNone(result["arms"]["baseline"]["adjudicated_flag_precision_excluding_unresolved"]["value"])

    def test_rejects_unadjudicated_or_partial_finding_ledger(self):
        manifest, _ = prepared([context("A")])
        preds = [prediction(manifest, "A", a, "COMPLETE", ["f1"]) for a in m.ARMS]
        controls = review("A", [], base_false=["f1"], synth_false=["f1"])
        controls["independently_adjudicated"] = False
        with self.assertRaises(m.BenchmarkError):
            m.score(manifest, preds, [controls])
        controls["independently_adjudicated"] = True
        controls["by_arm"]["baseline"]["false_positive_ids"] = []
        with self.assertRaises(m.BenchmarkError):
            m.score(manifest, preds, [controls])

    def test_missing_arm_cannot_dilute_denominator(self):
        manifest, _ = prepared([context("A")])
        preds = [prediction(manifest, "A", "baseline", "FAILED", [])]
        with self.assertRaises(m.BenchmarkError):
            m.score(manifest, preds, [review("A", ["R1"])])


if __name__ == "__main__":
    unittest.main()
