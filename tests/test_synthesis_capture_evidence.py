"""Exercise the public source-capture command with synthetic JATS records."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "synthesis_capture_evidence.py"
PREFLIGHT = SCRIPT.with_name("synthesis_preflight.py")
PROMPT = SCRIPT.parents[1] / "docs" / "SYNTHESIS-PREFLIGHT-v1.1.md"
ARTICLE = b"""<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front><article-meta>
    <article-id pub-id-type="pmcid">PMC123</article-id>
    <article-id pub-id-type="pmcid-ver">PMC123.2</article-id>
    <article-id pub-id-type="doi">10.1234/synthetic</article-id>
    <permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>
    <related-article related-article-type="correction-forward" ext-link-type="pmc" xlink:href="PMC124"/>
  </article-meta></front>
  <body><sec id="results"><title>Results</title><p>Counts by arm.</p>
    <table-wrap id="counts"><label>Table 1</label><caption><p>Trial counts</p></caption>
      <table><thead><tr><th colspan="2">Counts</th></tr></thead>
        <tbody><tr><td>Arm A</td><td>24</td></tr></tbody></table>
      <table-wrap-foot><p>Participants with an observed outcome.</p></table-wrap-foot>
    </table-wrap>
    <table-wrap id="image-table"><graphic xlink:href="table2.png"/></table-wrap>
    <supplementary-material id="supplement"><media xlink:href="appendix.pdf"/></supplementary-material>
  </sec></body>
</article>"""


class CaptureEvidenceTests(unittest.TestCase):
    def run_capture(self, payload=ARTICLE, doi="10.1234/synthetic"):
        with tempfile.TemporaryDirectory() as folder:
            xml = Path(folder) / "response.xml"
            xml.write_bytes(payload)
            run = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "PMC123", "--doi", doi, "--xml", str(xml)],
                capture_output=True, text=True, check=False,
            )
        return run.returncode, json.loads(run.stdout)

    def test_capture_binds_tables_and_links_to_exact_snapshot(self):
        payload = b"<pmc-articleset>" + ARTICLE + b"</pmc-articleset>"
        code, result = self.run_capture(payload)
        self.assertEqual(code, 0)
        self.assertEqual(result["capture_mode"], "ARCHIVED_XML")
        self.assertEqual(result["source"]["snapshot_sha256"], sha256(payload).hexdigest())
        self.assertEqual(result["source"]["version"], "PMC123.2")
        self.assertEqual(result["sections"][0]["jats_id"], "results")
        table, image_table = result["tables"]
        self.assertEqual((table["jats_id"], table["status"]), ("counts", "STRUCTURED"))
        self.assertEqual(table["rows"][0]["cells"][0]["colspan"], "2")
        self.assertEqual(table["rows"][1]["cells"][1]["text"], "24")
        self.assertEqual(table["footnotes"], "Participants with an observed outcome.")
        self.assertEqual(image_table["status"], "MANUAL_REVIEW")
        self.assertEqual(result["correction_links"][0]["target"], "PMC124")
        self.assertEqual(result["supplement_links"][0]["targets"], ["appendix.pdf"])

    def test_identifier_mismatch_does_not_emit_evidence(self):
        code, result = self.run_capture(doi="10.1234/different")
        self.assertEqual((code, result["status"]), (2, "HOLD"))
        self.assertNotIn("tables", result)

    def test_ambiguous_or_wrong_version_holds(self):
        for payload in (ARTICLE.replace(b"PMC123.2", b"PMC124.2"),
                        b"<pmc-articleset>" + ARTICLE * 2 + b"</pmc-articleset>"):
            with self.subTest(payload_length=len(payload)):
                code, result = self.run_capture(payload)
                self.assertEqual((code, result["status"]), (2, "HOLD"))

    def test_unlicensed_or_truncated_response_holds(self):
        for payload in (ARTICLE.replace(b"licenses/by/", b"licenses/by-nc/"), ARTICLE[:-12]):
            with self.subTest(payload_length=len(payload)):
                code, result = self.run_capture(payload)
                self.assertEqual((code, result["status"]), (2, "HOLD"))


class PmcIntakeTests(unittest.TestCase):
    def run_preflight(self, *, doi="10.1234/synthetic", version="PMC123.2", payload=ARTICLE):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            xml = root / "response.xml"
            if payload is not None:
                xml.write_bytes(payload)
            packet = root / "packet.json"
            packet.write_text(json.dumps({
                "schema_version": "1.1",
                "run": {"run_id": "synthetic-pmc-intake", "model_id": "none", "model_provider": "manual",
                        "tool_versions": {}, "prompt_sha256": sha256(PROMPT.read_bytes()).hexdigest()},
                "document": {"pmcid": "PMC123", "identifier": doi, "version": version},
                "sources": [],
                "claims": [{"id": "C1", "text": "Synthetic claim", "locator": "Table 1", "source_ids": [],
                            "source_support": "SUPPORTED", "evidence_maturity": "SCREENED",
                            "priority": "P4", "proposed_disposition": "NO_FLAG"}],
            }), encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-B", str(PREFLIGHT), "--prompt", str(PROMPT), "--packet", str(packet),
                 "--output-dir", str(root), "--pmc-xml", str(xml)],
                capture_output=True, text=True, check=False,
            )
            result = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(result["input_sha256"], sha256(packet.read_bytes()).hexdigest())
            return run.returncode, result, (root / "report.md").read_text(encoding="utf-8")

    def test_normal_intake_binds_capture_to_receipt(self):
        code, result, report = self.run_preflight()
        self.assertEqual(code, 0)
        self.assertTrue(result["intake_valid"])
        self.assertEqual(result["ledger"][0]["effective"], "NO_FLAG")
        evidence = result["pmc_evidence"]
        self.assertEqual(evidence["source"]["snapshot_sha256"], sha256(ARTICLE).hexdigest())
        self.assertEqual(evidence["tables"][0]["jats_id"], "counts")
        self.assertIn("PMC123.2", report)

    def test_wrong_doi_or_version_holds_review(self):
        for override in ({"doi": "10.1234/different"}, {"version": "PMC123.1"}):
            with self.subTest(override=override):
                code, result, _ = self.run_preflight(**override)
                self.assertEqual(code, 2)
                self.assertFalse(result["intake_valid"])
                self.assertEqual(result["ledger"][0]["effective"], "HOLD")
                self.assertNotIn("tables", result["pmc_evidence"])

    def test_failed_retrieval_is_logged_and_holds_review(self):
        code, result, _ = self.run_preflight(payload=None)
        self.assertEqual(code, 2)
        self.assertEqual(result["pmc_evidence"]["status"], "HOLD")
        self.assertEqual(result["ledger"][0]["effective"], "HOLD")
        self.assertIn("PMC_EVIDENCE_HOLD", [problem["code"] for problem in result["problems"]])


if __name__ == "__main__":
    unittest.main()
