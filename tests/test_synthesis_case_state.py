"""Private-state contracts use invented references, never correspondence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import synthesis_case_state as state
from test_synthesis_intake_evidence import audit, matched, packet, XML, ROOT, PROMPT


def event(number, kind="REPLY_POINT", **values):
    return {"event_id": f"event-{number}", "type": kind, "recorded_at": f"2026-01-01T00:00:{number:02d}Z", **values}


def log(events):
    return {"schema_version": "synthesis-case-state/1", "document": packet(matched())["document"], "events": events}


def reply(number=1, point="P1", outcome="UNRESOLVED"):
    return event(number, claim_id="C1", point_id=point, outcome=outcome,
                 original_question_reference="PRIVATE_SENTINEL_QUESTION", reply_reference="PRIVATE_SENTINEL_REPLY",
                 source_recheck_reference="PRIVATE_SENTINEL_RECHECK", reviewer_reference="PRIVATE_SENTINEL_REVIEWER")


class CaseStateTests(unittest.TestCase):
    def test_unresolved_point_holds_claim_and_receipts_redact_private_references(self):
        result = audit(matched(), log([reply()]))
        self.assertEqual(result["ledger"][0]["effective"], "HOLD")
        self.assertTrue(result["private_case_summary"]["claims"][0]["reply_pending"])
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
        self.assertNotIn("PRIVATE_SENTINEL", __import__("scripts.synthesis_preflight", fromlist=["_markdown"])._markdown(result))

    def test_mixed_reply_points_and_correction_request_do_not_clear_unresolved_point(self):
        events = [reply(outcome="SOURCE_RECHECKED"), reply(2, "P2"),
                  event(3, "CORRECTION_STATUS", claim_id="C1", point_id="P1", status="REQUESTED",
                        evidence_reference="PRIVATE_SENTINEL_CORRECTION")]
        result = audit(matched(), log(events))
        summary = result["private_case_summary"]["claims"][0]
        self.assertEqual((summary["point_count"], summary["pending_point_count"]), (2, 1))
        self.assertEqual(summary["correction_statuses"], ["REQUESTED"])
        self.assertFalse(summary["publication_independently_verified"])
        self.assertEqual(result["ledger"][0]["effective"], "HOLD")

    def test_pause_release_does_not_release_other_pause_or_authorise_email(self):
        pause = lambda n, p: event(n, "CONTACT_PAUSE", pause_id=p, scope="DOCUMENT",
                                  source_reference="PRIVATE_SENTINEL_PAUSE", reason="Synthetic pause", release_condition="Explicit release")
        events = [pause(1, "a"), pause(2, "b"), event(3, "CONTACT_RELEASE", pause_id="a",
                 release_authorised=True, source_reference="PRIVATE_SENTINEL_RELEASE")]
        result = audit(matched(), log(events))
        self.assertTrue(result["private_case_summary"]["contact_paused"])
        self.assertFalse(result["private_case_summary"]["email_eligible"])
        self.assertEqual(result["ledger"][0]["effective"], "NO_FLAG")

    def test_invalid_dates_ids_document_or_claim_hold_globally(self):
        good = log([reply()])
        cases = []
        bad = deepcopy(good); bad["events"].append(reply()); cases.append(bad)
        bad = deepcopy(good); bad["document"]["version"] = "different"; cases.append(bad)
        bad = deepcopy(good); bad["events"][0]["claim_id"] = "absent"; cases.append(bad)
        bad = deepcopy(good); bad["events"][0]["recorded_at"] = "not a date"; cases.append(bad)
        for bad in cases:
            result = audit(matched(), bad)
            self.assertFalse(result["intake_valid"])
            self.assertEqual(result["ledger"][0]["effective"], "HOLD")

    def test_cli_append_preserves_history_refuses_duplicate_and_normal_intake_redacts(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder); path = parent / "private" / "state.json"
            script = ROOT / "scripts/synthesis_case_state.py"
            run = subprocess.run([sys.executable, "-B", str(script), "--state", str(path), "--init",
                                  "--identifier", "10.1234/synthetic", "--version", "PMC123.2"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            request = parent / "event.json"; request.write_text(json.dumps(reply()), encoding="utf-8")
            command = [sys.executable, "-B", str(script), "--state", str(path), "--event", str(request)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            previous = path.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(path.read_bytes(), previous)
            self.assertTrue((path.parent / ".gitignore").is_file())
            xml = parent / "article.xml"; xml.write_bytes(XML)
            p = parent / "packet.json"; p.write_text(json.dumps(packet(matched())), encoding="utf-8")
            out = parent / "receipt"
            run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/synthesis_preflight.py"), "--packet", str(p),
                                  "--prompt", str(PROMPT), "--pmc-xml", str(xml), "--output-dir", str(out),
                                  "--private-case-state", str(path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            receipt = json.loads((out / "receipt.json").read_text())
            self.assertEqual(receipt["ledger"][0]["effective"], "HOLD")
            self.assertNotIn("PRIVATE_SENTINEL", (out / "receipt.json").read_text() + (out / "report.md").read_text() + run.stdout)


if __name__ == "__main__": unittest.main()
