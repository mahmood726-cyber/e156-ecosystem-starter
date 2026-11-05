"""Source-rights boundary tests. All identifiers and payloads are synthetic."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

from scripts import synthesis_source_rights as rights
from scripts import synthesis_capture_evidence as capture


NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def entry(resource="pmc:PMC123", doi="10.1234/synthetic", digest=None):
    source = {
        "resource": resource, "doi": doi, "journal": "Synthetic Journal",
        "publisher": "Synthetic Publisher", "identity_verified": True,
        "identity_evidence": {"ref": "synthetic:metadata", "sha256": "a" * 64},
        "permission": {
            "basis": "explicit_permission", "reviewed_by": "synthetic reviewer",
            "reviewed_at": "2026-11-04T00:00:00Z", "expires_at": "2027-01-01T00:00:00Z",
            "operations": ["acquire", "process", "replay"],
            "evidence": [{"ref": "synthetic:permission", "sha256": "b" * 64}],
            "restrictions_checked": True, "conditions_satisfied": True,
        },
    }
    if digest is not None:
        source["content_sha256"] = digest
    return source


class SourceRightsTests(unittest.TestCase):
    def test_verified_permission_allows_only_covered_operation(self):
        source = entry()
        self.assertEqual(rights.evaluate(source, "acquire", now=NOW)["status"], "ALLOW")
        source["permission"]["operations"] = ["process"]
        self.assertEqual(rights.evaluate(source, "acquire", now=NOW)["status"], "HOLD")

    def test_jama_hold_overrides_licence_and_mirrors(self):
        for metadata in (
            {"doi": "https://doi.org/10.1001/JAMA.2099.synthetic"},
            {"resource": "https://jamanetwork.com/journals/synthetic/fullarticle/0"},
            {"resource": "https://mirror.invalid/?url=https%3A%2F%2Fsub.jamanetwork.com%2Fa"},
            {"resource": "file:///cache/old.xml", "journal": "JAMA Network Open"},
            {"resource": "pmc:PMC123", "publisher": "American Medical Association"},
            {"journal": "Archives of Internal Medicine"},
        ):
            with self.subTest(metadata=metadata):
                source = dict(entry(), **metadata)
                source["permission"]["basis"] = "licence"
                decision = rights.evaluate(source, "replay", now=NOW)
                self.assertEqual((decision["status"], decision["reason_code"]),
                                 ("DENY", "JAMA_PROGRAMME_HOLD"))

    def test_missing_ambiguous_or_stale_evidence_holds(self):
        for field, value in (("identity_verified", False), ("identity_evidence", {}),
                             ("journal", ""), ("doi", ""), ("publisher", "")):
            source = entry(); source[field] = value
            self.assertEqual(rights.evaluate(source, "process", now=NOW)["status"], "HOLD")
        for field, value in (("basis", "publicly_readable"), ("evidence", []),
                             ("reviewed_by", ""), ("expires_at", "2026-11-04T00:00:00Z"),
                             ("reviewed_at", "2026-11-06T00:00:00Z"),
                             ("restrictions_checked", False), ("conditions_satisfied", False)):
            source = entry(); source["permission"][field] = value
            self.assertEqual(rights.evaluate(source, "process", now=NOW)["status"], "HOLD")

    def test_manual_reading_is_not_an_automated_permission(self):
        self.assertEqual(rights.evaluate(entry(), "manual_read", now=NOW)["status"], "HOLD")

    def test_unrelated_domain_or_citation_is_not_automatically_jama(self):
        source = entry("https://jamanetwork.com.example.invalid/synthetic")
        source["note"] = "cites a JAMA paper"
        self.assertEqual(rights.evaluate(source, "process", now=NOW)["status"], "ALLOW")

    def test_manifest_and_audit_are_required_and_preserve_prior_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "rights.json"; log = root / "audit.jsonl"
            source = entry()
            manifest.write_text(json.dumps({"sources": [source]}))
            log.write_text('{"historical":true}\n')
            with patch.dict(os.environ, {"SYNTHESIS_RIGHTS_MANIFEST": str(manifest),
                                         "SYNTHESIS_RIGHTS_LOG": str(log)}):
                receipt = rights.authorize(source["resource"], "acquire", doi=source["doi"], now=NOW)
                rows = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual(rows[0], {"historical": True})
                self.assertEqual(rows[-1]["decision_id"], receipt["decision_id"])
                self.assertEqual(rows[-1]["manifest_sha256"], sha256(manifest.read_bytes()).hexdigest())
                self.assertIn("policy_sha256", rows[-1])
                self.assertEqual(rows[-1]["evidence"], source["permission"]["evidence"])
                with patch.dict(os.environ, {"SYNTHESIS_RIGHTS_LOG": str(root)}):
                    with self.assertRaises(rights.RightsError):
                        rights.authorize(source["resource"], "acquire", now=NOW)

    def test_duplicate_grants_and_doi_mismatch_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "rights.json"
            with patch.dict(os.environ, {"SYNTHESIS_RIGHTS_MANIFEST": str(manifest),
                                         "SYNTHESIS_RIGHTS_LOG": str(root / "log")}):
                manifest.write_text(json.dumps({"sources": [entry(), entry()]}))
                with self.assertRaises(rights.RightsError): rights.authorize("pmc:PMC123", "acquire", now=NOW)
                manifest.write_text(json.dumps({"sources": [entry()]}))
                with self.assertRaises(rights.RightsError):
                    rights.authorize("pmc:PMC123", "acquire", doi="10.1234/other", now=NOW)

    def test_missing_permission_prevents_network_and_cached_xml_reads(self):
        with patch.dict(os.environ, {"SYNTHESIS_RIGHTS_MANIFEST": "", "SYNTHESIS_RIGHTS_LOG": ""}), \
             patch.object(capture, "build_opener") as network, patch.object(capture, "_read_xml") as disk:
            for xml in (None, Path("synthetic-cache.xml")):
                result = capture.retrieve_pmc_evidence("PMC123", doi="10.1234/synthetic", xml=xml)
                self.assertEqual(result["status"], "HOLD")
            network.assert_not_called(); disk.assert_not_called()

    def test_jama_identity_blocks_before_network_without_a_grant(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "SYNTHESIS_RIGHTS_MANIFEST": "", "SYNTHESIS_RIGHTS_LOG": str(Path(tmp) / "log")}), \
             patch.object(capture, "build_opener") as network:
            result = capture.retrieve_pmc_evidence("PMC123", doi="10.1001/jama.2099.synthetic")
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(json.loads((Path(tmp) / "log").read_text())["reason_code"], "JAMA_PROGRAMME_HOLD")
            network.assert_not_called()

    def test_cached_bytes_must_match_the_approved_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = root / "packet.json"; data.write_text("synthetic")
            source = entry(data.as_uri(), digest="0" * 64)
            source["lineage"] = [entry()]
            manifest = root / "rights.json"; manifest.write_text(json.dumps({"sources": [source]}))
            with patch.dict(os.environ, {"SYNTHESIS_RIGHTS_MANIFEST": str(manifest),
                                         "SYNTHESIS_RIGHTS_LOG": str(root / "log")}):
                with self.assertRaises(rights.RightsError): rights.read_authorized(data, now=NOW)
                self.assertEqual(json.loads((root / "log").read_text().splitlines()[-1])["reason_code"],
                                 "CONTENT_DIGEST_MISMATCH")

    def test_mixed_lineage_cannot_inherit_permission_from_its_container(self):
        source = entry("file:///synthetic/batch.json")
        source["lineage"] = [entry(), dict(entry(), journal="JAMA Psychiatry")]
        result = rights.evaluate(source, "process", now=NOW)
        self.assertEqual((result["status"], result["reason_code"]), ("DENY", "JAMA_PROGRAMME_HOLD"))

    def test_real_gate_accepts_only_exact_authorized_synthetic_xml(self):
        from source_rights_fixtures import synthetic_env
        from test_synthesis_capture_evidence import ARTICLE
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); xml = root / "source.xml"; xml.write_bytes(ARTICLE)
            with patch.dict(os.environ, synthetic_env(root)):
                result = capture.retrieve_pmc_evidence("PMC123", doi="10.1234/synthetic", xml=xml)
                self.assertEqual(result["status"], "CAPTURED")
                self.assertIn("source_rights_decision_id", result)

    def test_preflight_holds_before_scientific_processing(self):
        from scripts import synthesis_preflight as preflight
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "SYNTHESIS_RIGHTS_MANIFEST": "", "SYNTHESIS_RIGHTS_LOG": str(Path(tmp) / "log")}), \
             patch.object(preflight, "review_packet") as process:
            code = preflight.main(["--prompt", "synthetic-prompt", "--packet", "synthetic-packet", "--output-dir", tmp])
            self.assertEqual(code, 2)
            process.assert_not_called()

    def test_downloader_rechecks_cached_permissions_and_refuses_redirect_following(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import scicoqa_retrieve_sources as retrieval
        asset = {"url": "https://example.invalid/synthetic.pdf", "relative_path": "cached.pdf", "kind": "paper"}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "SYNTHESIS_RIGHTS_MANIFEST": "", "SYNTHESIS_RIGHTS_LOG": str(Path(tmp) / "log")}), \
             patch.object(retrieval.subprocess, "run") as network, \
             patch.object(retrieval, "validate_payload") as parse:
            cached = Path(tmp) / "cached.pdf"; cached.write_bytes(b"synthetic cache")
            result = retrieval.retrieve(asset, Path(tmp), 1, 1024, {"status": "RETRIEVED"})
            self.assertEqual(result["status"], "HOLD")
            network.assert_not_called(); parse.assert_not_called()
        from urllib.error import HTTPError
        from urllib.request import Request
        with self.assertRaises(HTTPError):
            capture.PmcRedirectHandler().redirect_request(Request(capture.EFETCH), None, 302, "Found", {},
                                                         capture.EFETCH + "?id=synthetic-other")

    def test_model_submission_needs_its_own_fresh_permission(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import scicoqa_paired_benchmark as benchmark
        import scicoqa_paired_inference as inference
        manifest, prompts = benchmark.make_prompts(
            [{"case_id": "synthetic", "paper_family_id": "synthetic", "split": "synthetic",
              "paper_version": "fixture", "code_commit": "a" * 40, "paper_text": "synthetic", "code_text": "pass"}],
            "${paper} ${code}", "${paper} ${code}", "synthetic", "synthetic", {"temperature": 0}, "b" * 40)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "SYNTHESIS_RIGHTS_MANIFEST": "", "SYNTHESIS_RIGHTS_LOG": str(Path(tmp) / "log")}), \
             patch.object(inference.subprocess, "run") as model:
            with self.assertRaises((rights.RightsError, ValueError)):
                inference.execute(manifest, prompts, ["synthetic-model"])
            model.assert_not_called()

    def test_audit_discard_device_is_not_a_log(self):
        if os.name == "posix":
            with self.assertRaises(rights.RightsError):
                rights.record({"status": "ALLOW"}, log_path="/dev/null")

    def test_derived_files_and_model_prompts_require_lineage(self):
        for resource in ("file:///synthetic/context.jsonl", "sha256:" + "c" * 64):
            source = entry(resource)
            self.assertEqual(rights.evaluate(source, "process", now=NOW)["reason_code"], "LINEAGE_REQUIRED")

    def test_fresh_model_grants_allow_synthetic_calls_and_record_each(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import subprocess
        import scicoqa_paired_benchmark as benchmark
        import scicoqa_paired_inference as inference
        manifest, prompts = benchmark.make_prompts(
            [{"case_id": "synthetic", "paper_family_id": "synthetic", "split": "synthetic",
              "paper_version": "fixture", "code_commit": "a" * 40, "paper_text": "synthetic", "code_text": "pass"}],
            "baseline ${paper} ${code}", "candidate ${paper} ${code}", "synthetic", "synthetic",
            {"temperature": 0}, "b" * 40)
        sources = []
        for rows in prompts.values():
            for row in rows:
                source = entry("sha256:" + benchmark.digest(row["prompt"]))
                source["permission"]["expires_at"] = "2099-01-01T00:00:00Z"
                source["permission"]["operations"].append("model_submit")
                source["lineage"] = [entry()]
                source["lineage"][0]["permission"]["expires_at"] = "2099-01-01T00:00:00Z"
                source["lineage"][0]["permission"]["operations"].append("model_submit")
                sources.append(source)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); grant = root / "grants.json"; grant.write_text(json.dumps({"sources": sources}))
            with patch.dict(os.environ, {"SYNTHESIS_RIGHTS_MANIFEST": str(grant), "SYNTHESIS_RIGHTS_LOG": str(root / "log")}), \
                 patch.object(inference.subprocess, "run", return_value=subprocess.CompletedProcess(
                     ["synthetic"], 0, "discrepancies: []", "")) as model:
                predictions, _ = inference.execute(manifest, prompts, ["synthetic"])
                self.assertEqual((len(predictions), model.call_count), (2, 2))
                self.assertEqual(len((root / "log").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
