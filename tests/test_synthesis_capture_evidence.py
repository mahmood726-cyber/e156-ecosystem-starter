"""Exercise the public source-capture command with synthetic JATS records."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from scripts import synthesis_capture_evidence as capture
from scripts import synthesis_preflight as preflight


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

    def test_incidental_or_contradictory_license_does_not_grant_access(self):
        declared = b'<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>'
        for invalid in (
            b'<license><license-p>All rights reserved. See <ext-link xlink:href="https://creativecommons.org/licenses/by/4.0/">another licence</ext-link>.</license-p></license>',
            b'<license license-type="all-rights-reserved" xlink:href="https://creativecommons.org/licenses/by/4.0/"/>',
        ):
            with self.subTest(invalid=invalid):
                code, result = self.run_capture(ARTICLE.replace(declared, invalid))
                self.assertEqual((code, result["status"]), (2, "HOLD"))

    def test_cell_markup_preserves_values_and_separation(self):
        payload = ARTICLE.replace(b"<td>Arm A</td><td>24</td>",
                                  b"<td>10<sup>5</sup></td><td>10<break/>20</td>")
        code, result = self.run_capture(payload)
        self.assertEqual(code, 0)
        cells = result["tables"][0]["rows"][1]["cells"]
        self.assertEqual([cell["text"] for cell in cells], ["10^{5}", "10 20"])

    def test_numeric_reference_stays_separate_from_the_value(self):
        payload = ARTICLE.replace(b"<td>24</td>", b'<td>10<xref ref-type="table-fn" rid="fn1">1</xref></td>')
        code, result = self.run_capture(payload)
        self.assertEqual(code, 0)
        self.assertEqual(result["tables"][0]["rows"][1]["cells"][1]["text"], "10[1]")

    def test_graphic_formula_requires_manual_review(self):
        payload = ARTICLE.replace(
            b"<td>24</td>",
            b'<td>10<inline-formula><alternatives><graphic xlink:href="formula.png"/></alternatives></inline-formula>20</td>',
        )
        code, result = self.run_capture(payload)
        self.assertEqual(code, 0)
        self.assertEqual(result["tables"][0]["status"], "MANUAL_REVIEW")
        self.assertNotIn("rows", result["tables"][0])

    def test_unhandled_semantic_styling_requires_manual_review(self):
        for cell in (
            b"<td>0.<overline>3</overline></td>",
            b"<td><strike>32</strike>24</td>",
            b'<td>10<styled-content style-type="superscript">5</styled-content></td>',
            b'<td>10<bold style="vertical-align: super">5</bold></td>',
        ):
            with self.subTest(cell=cell):
                code, result = self.run_capture(ARTICLE.replace(b"<td>24</td>", cell))
                self.assertEqual(code, 0)
                self.assertEqual(result["tables"][0]["status"], "MANUAL_REVIEW")
                self.assertNotIn("rows", result["tables"][0])

    def test_dated_licence_does_not_establish_applicability(self):
        payload = ARTICLE.replace(
            b'<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>',
            b'<license><license_ref xmlns="http://www.niso.org/schemas/ali/1.0/" start_date="9999-01-01">'
            b'https://creativecommons.org/licenses/by/4.0/</license_ref></license>',
        )
        code, result = self.run_capture(payload)
        self.assertEqual((code, result["status"]), (2, "HOLD"))
        self.assertIn("Dated", result["reason"])

    def test_redirect_and_unexpected_response_origin_hold(self):
        handler = capture.PmcRedirectHandler()
        for target in ("https://example.invalid/", "http://eutils.ncbi.nlm.nih.gov/"):
            with self.subTest(target=target), self.assertRaises(HTTPError):
                handler.redirect_request(Request(capture.EFETCH), None, 302, "Found", {}, target)
        with patch.object(capture, "build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.geturl.return_value = "https://example.invalid/"
            self.assertEqual(capture.retrieve_pmc_evidence("PMC123")["status"], "HOLD")
            response.read.assert_not_called()


class PmcIntakeTests(unittest.TestCase):
    def run_preflight(self, *, doi="10.1234/synthetic", version="PMC123.2", payload=ARTICLE, replay=True):
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
            command = [sys.executable, "-B", str(PREFLIGHT), "--prompt", str(PROMPT),
                       "--packet", str(packet), "--output-dir", str(root)]
            if replay:
                command += ["--pmc-xml", str(xml)]
            run = subprocess.run(command, capture_output=True, text=True, check=False)
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

    def test_packet_alone_cannot_enable_network(self):
        code, result, _ = self.run_preflight(replay=False)
        self.assertEqual(code, 2)
        self.assertIn("--pmc-live", result["pmc_evidence"]["reason"])
        self.assertNotIn("attempted_url", result["pmc_evidence"])

    def test_invalid_packet_cannot_trigger_even_enabled_network(self):
        digest = sha256(PROMPT.read_bytes()).hexdigest()
        packet = {
            "schema_version": "invalid",
            "run": {"prompt_sha256": digest},
            "document": {"pmcid": "PMC123", "identifier": "10.1234/synthetic", "version": "PMC123.2"},
        }
        with patch.object(capture, "retrieve_pmc_evidence") as retrieve:
            result = preflight.review_packet(packet, digest, "synthetic", pmc_live=True)
            retrieve.assert_not_called()
        self.assertFalse(result["intake_valid"])
        self.assertEqual(result["pmc_evidence"]["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
