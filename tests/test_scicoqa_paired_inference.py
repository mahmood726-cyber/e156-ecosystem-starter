"""Offline smoke tests only; simulated model output is not scientific validation."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scicoqa_paired_benchmark import make_prompts, BenchmarkError
from scicoqa_paired_inference import execute, parse_yaml


class PairedModelRunnerTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.prompts = make_prompts(
            [{"case_id": "synthetic-1", "paper_family_id": "fixture-family", "split": "synthetic",
              "paper_version": "fixture-v1",
              "code_commit": "a" * 40,
              "paper_text": "Paper describes method A.",
              "code_text": "def method(): return 'B'"}],
            "Compare ${paper} and ${code}.",
            "Check ${paper} against ${code}.",
            "fixture-model", "fixture-revision",
            {"temperature": 0}, "b" * 40)

    def test_parses_standard_yaml_and_zero(self):
        self.assertEqual(parse_yaml("discrepancies: []"), [])
        self.assertEqual(parse_yaml("discrepancies:\n  - method A differs"), [
            {"finding_id": "F1", "text": "method A differs"}])
        with self.assertRaises(BenchmarkError):
            parse_yaml("I found a serious error.")

    def test_two_arms_are_accounted(self):
        command = [sys.executable, "-c", "print('discrepancies: []')"]
        preds, raw = execute(self.manifest, self.prompts, command)
        self.assertEqual(len(preds), 2)
        self.assertEqual([p["arm"] for p in preds], ["baseline", "synthesis"])
        self.assertTrue(all(p["status"] == "COMPLETE" and not p["findings"] for p in preds))
        self.assertEqual(len(raw), 2)

    def test_preambles_trailers_and_invalid_empty_documents_abstain(self):
        for text in ["I cannot review this.\ndiscrepancies: []",
                     "discrepancies: []\nExtra explanation", "discrepancies:",
                     "discrepancies:\n  - null", "discrepancies:\n  - key: value",
                     "```yaml\ndiscrepancies: []\n```\nMore text"]:
            with self.subTest(text=text), self.assertRaises(BenchmarkError):
                parse_yaml(text)
        self.assertEqual(parse_yaml("```yaml\ndiscrepancies: []\n```"), [])
        command = [sys.executable, "-c", "print('Refusal\\ndiscrepancies: []')"]
        preds, _ = execute(self.manifest, self.prompts, command)
        self.assertTrue(all(p["status"] == "ABSTAIN" for p in preds))

    def test_timeout_preserves_partial_stdout_stderr_and_hash(self):
        from scicoqa_paired_benchmark import digest
        from unittest.mock import patch
        import subprocess
        partial = "discrepancies:\n  - partial output"
        exc = subprocess.TimeoutExpired("fixture", 1, output=partial.encode(), stderr=b"diagnostic")
        with patch("scicoqa_paired_inference.subprocess.run", side_effect=exc):
            preds, raw = execute(self.manifest, self.prompts, ["fixture"], timeout=1)
        self.assertTrue(all(p["status"] == "FAILED" for p in preds))
        self.assertTrue(all(p["findings"] == [] for p in preds))
        self.assertEqual(raw[0]["raw_response"], partial)
        self.assertEqual(raw[0]["stderr"], "diagnostic")
        self.assertEqual(raw[0]["raw_response_sha256"], digest(partial))
        self.assertGreaterEqual(raw[0]["latency_seconds"], 0)

    def test_checkpoint_preserves_first_call_if_later_call_is_interrupted(self):
        from unittest.mock import patch
        import subprocess
        saved = []
        success = subprocess.CompletedProcess(["fixture"], 0, "discrepancies: []", "")
        with patch("scicoqa_paired_inference.subprocess.run", side_effect=[success, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                execute(self.manifest, self.prompts, ["fixture"],
                        on_result=lambda p, r: saved.append((p, r)))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][0]["status"], "COMPLETE")

    def test_missing_arm_is_rejected(self):
        with self.assertRaises(BenchmarkError):
            execute(self.manifest, {"baseline": self.prompts["baseline"], "synthesis": []},
                    [sys.executable, "-c", "print('discrepancies: []')"])

    def test_failed_command_is_visible(self):
        preds, _ = execute(self.manifest, self.prompts, [
            sys.executable, "-c", "import sys; sys.exit(1)"])
        self.assertEqual([p["status"] for p in preds], ["FAILED", "FAILED"])


if __name__ == "__main__":
    unittest.main()
