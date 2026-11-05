"""Retrieval integrity tests use in-memory fixtures, never benchmark observations."""
import io
import json
from pathlib import Path
import sys
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scicoqa_retrieve_sources import inventory, retrieve, sha256, validate_payload, BenchmarkError


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        mocked_gate = patch("scicoqa_retrieve_sources.authorize", return_value={"status": "ALLOW"})
        mocked_gate.start()
        self.addCleanup(mocked_gate.stop)
        synthetic_bytes = patch("scicoqa_retrieve_sources.read_authorized",
                                side_effect=lambda path, **kwargs: Path(path).read_bytes())
        synthetic_bytes.start()
        self.addCleanup(synthetic_bytes.stop)

    @staticmethod
    def downloader(payload):
        def run(command, **kwargs):
            Path(command[command.index("--output") + 1]).write_bytes(payload)
            return subprocess.CompletedProcess(command, 0, "", "")
        return run

    def test_main_resumes_an_empty_receipt_without_network(self):
        from scicoqa_retrieve_sources import main
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "retrieval.jsonl").touch()
            with patch("sys.argv", ["retrieve", "--dataset-dir", str(root), "--output", str(root)]), \
                    patch("scicoqa_retrieve_sources.inventory", return_value=([], {})):
                main()
            self.assertTrue((root / "inventory.json").is_file())

    def test_inventory_deduplicates_shared_sources_without_exposing_answers(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = {"paper_url_versioned": "https://arxiv.org/pdf/fixturev1.pdf",
                   "code_url_versioned": "https://github.com/fixture/repo/tree/" + "a" * 40,
                   "discrepancy_description_gpt": "DO NOT INCLUDE THIS LABEL"}
            for split in ("real", "synthetic"):
                (root / f"scicoqa-{split}-v1.1.jsonl").write_text(json.dumps(row) + "\n")
            assets, datasets = inventory(root, verify_hashes=False)
            self.assertEqual(len(assets), 2)
            self.assertTrue(all(a["splits"] == ["real", "synthetic"] for a in assets))
            self.assertNotIn("DO NOT INCLUDE", json.dumps([assets, datasets]))
            with self.assertRaises(BenchmarkError):
                inventory(root)

    def test_html_is_not_accepted_as_a_paper_and_partial_is_removed(self):
        with TemporaryDirectory() as tmp:
            payload = b"<html>Access denied</html>"
            asset = {"asset_id": "fixture", "kind": "paper", "url": "https://example.org/paper.pdf",
                     "relative_path": "assets/fixture.pdf"}
            with patch("scicoqa_retrieve_sources.subprocess.run", side_effect=self.downloader(payload)):
                result = retrieve(asset, Path(tmp), 1, 1024)
            self.assertEqual(result["status"], "FAILED")
            self.assertFalse((Path(tmp) / asset["relative_path"]).exists())
            self.assertFalse(list(Path(tmp).rglob("*.part")))

    def test_pdf_receipt_hash_and_cache_tamper_detection(self):
        with TemporaryDirectory() as tmp:
            data = b"%PDF-1.4\nfixture bytes only"
            payload = data
            asset = {"asset_id": "fixture", "kind": "paper", "url": "https://example.org/paper.pdf",
                     "relative_path": "assets/fixture.pdf"}
            with patch("scicoqa_retrieve_sources.subprocess.run", side_effect=self.downloader(payload)):
                result = retrieve(asset, Path(tmp), 1, 1024)
            self.assertEqual(result["status"], "RETRIEVED")
            self.assertEqual(result["sha256"], sha256(data))
            self.assertEqual(retrieve(asset, Path(tmp), 1, 1024, result), result)
            (Path(tmp) / asset["relative_path"]).write_bytes(b"tampered")
            with self.assertRaises(BenchmarkError):
                retrieve(asset, Path(tmp), 1, 1024, result)

    def test_arxiv_abstract_resolves_the_same_explicit_edition(self):
        with TemporaryDirectory() as tmp:
            payload = b"%PDF-1.4\nfixture"
            asset = {"asset_id": "fixture", "kind": "paper",
                     "url": "https://arxiv.org/abs/2106.05234v5",
                     "relative_path": "assets/fixture.pdf"}
            with patch("scicoqa_retrieve_sources.subprocess.run", side_effect=self.downloader(payload)) as get:
                result = retrieve(asset, Path(tmp), 1, 1024)
            self.assertEqual(get.call_args.args[0][-1], "https://arxiv.org/pdf/2106.05234v5.pdf")
            self.assertEqual(result["url"], asset["url"])
            self.assertEqual(result["status"], "RETRIEVED")

    def test_archive_root_must_match_exact_commit(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                item = tarfile.TarInfo("repo-" + "b" * 40 + "/file.py")
                item.size = 4
                archive.addfile(item, io.BytesIO(b"pass"))
            with self.assertRaises(BenchmarkError):
                validate_payload(path, {"kind": "code", "code_commit": "a" * 40})

    def test_hard_download_timeout_is_recorded_and_partial_removed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            part = root / "assets/fixture.pdf.part"
            part.write_bytes(b"partial")
            asset = {"asset_id": "fixture", "kind": "paper", "url": "https://example.org/paper.pdf",
                     "relative_path": "assets/fixture.pdf"}
            with patch("scicoqa_retrieve_sources.subprocess.run",
                       side_effect=subprocess.TimeoutExpired("curl", 6)):
                result = retrieve(asset, root, 1, 1024)
            self.assertEqual(result["status"], "FAILED")
            self.assertIn("TimeoutExpired", result["error"])
            self.assertFalse(part.exists())


if __name__ == "__main__":
    unittest.main()

