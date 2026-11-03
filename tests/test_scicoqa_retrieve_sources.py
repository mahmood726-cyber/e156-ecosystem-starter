"""Retrieval integrity tests use in-memory fixtures, never benchmark observations."""
import io
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scicoqa_retrieve_sources import inventory, retrieve, sha256, validate_payload, BenchmarkError


class RetrievalTests(unittest.TestCase):
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
            response = io.BytesIO(b"<html>Access denied</html>")
            response.headers = {}
            asset = {"asset_id": "fixture", "kind": "paper", "url": "https://example.org/paper.pdf",
                     "relative_path": "assets/fixture.pdf"}
            with patch("scicoqa_retrieve_sources.urllib.request.urlopen", return_value=response):
                result = retrieve(asset, Path(tmp), 1, 1024)
            self.assertEqual(result["status"], "FAILED")
            self.assertFalse((Path(tmp) / asset["relative_path"]).exists())
            self.assertFalse(list(Path(tmp).rglob("*.part")))

    def test_pdf_receipt_hash_and_cache_tamper_detection(self):
        with TemporaryDirectory() as tmp:
            data = b"%PDF-1.4\nfixture bytes only"
            response = io.BytesIO(data)
            response.headers = {"Content-Length": str(len(data))}
            asset = {"asset_id": "fixture", "kind": "paper", "url": "https://example.org/paper.pdf",
                     "relative_path": "assets/fixture.pdf"}
            with patch("scicoqa_retrieve_sources.urllib.request.urlopen", return_value=response):
                result = retrieve(asset, Path(tmp), 1, 1024)
            self.assertEqual(result["status"], "RETRIEVED")
            self.assertEqual(result["sha256"], sha256(data))
            self.assertEqual(retrieve(asset, Path(tmp), 1, 1024, result), result)
            (Path(tmp) / asset["relative_path"]).write_bytes(b"tampered")
            with self.assertRaises(BenchmarkError):
                retrieve(asset, Path(tmp), 1, 1024, result)

    def test_archive_root_must_match_exact_commit(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                item = tarfile.TarInfo("repo-" + "b" * 40 + "/file.py")
                item.size = 4
                archive.addfile(item, io.BytesIO(b"pass"))
            with self.assertRaises(BenchmarkError):
                validate_payload(path, {"kind": "code", "code_commit": "a" * 40})


if __name__ == "__main__":
    unittest.main()
