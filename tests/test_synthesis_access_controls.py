"""Synthetic source-permission and no-contact enforcement tests; no transports."""
from datetime import date, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from synthesis_access_controls import (assess_source, is_jama_source, source_preflight,
    outgoing_blockers, require_outgoing_allowed, execute_source_action)

TODAY = date(2026, 11, 5)
SOURCE = {"doi": "10.7777/synthetic-study", "version": "v2",
          "resource_ref": "synthetic-cache-v2", "access_route": "LOCAL_FIXTURE",
          "original_journal": "Invented Medical Journal", "original_publisher": "Fictional Press",
          "original_url": "https://fictional.invalid/study"}
PERMISSION = {"doi": SOURCE["doi"], "version": SOURCE["version"],
              "resource_ref": SOURCE["resource_ref"], "access_route": SOURCE["access_route"],
              "status": "REVIEWED_ALLOW", "reviewer": "Synthetic Reviewer",
              "reviewed_on": "2026-11-04", "expires_on": "2026-11-06",
              "original_journal": SOURCE["original_journal"], "original_publisher": SOURCE["original_publisher"],
              "original_url": SOURCE["original_url"],
              "evidence_reference": "synthetic-evidence-record", "evidence_sha256": "a" * 64,
              "conditions_satisfied": True, "operations": ["CACHE_READ", "REPLAY"]}
MANIFEST = {"schema": "source-permissions-v1", "permissions": [PERMISSION]}


class SourceRightsTests(unittest.TestCase):
    def test_exact_reviewed_fixture_allowed(self):
        self.assertEqual(assess_source(MANIFEST, SOURCE, 'CACHE_READ', on_date=TODAY)[0], 'ALLOW')

    def test_unreviewed_expired_future_unknown_permissions_hold(self):
        variants = [None, {}, {"schema":"source-permissions-v1", "permissions":[]},
                    {"schema":"source-permissions-v1", "permissions":[dict(PERMISSION,status="UNREVIEWED")]},
                    {"schema":"source-permissions-v1", "permissions":[dict(PERMISSION,expires_on="2026-11-04")]},
                    {"schema":"source-permissions-v1", "permissions":[dict(PERMISSION,reviewed_on="2026-11-06")]},
                    {"schema":"source-permissions-v1", "permissions":[dict(PERMISSION,conditions_satisfied=False)]},
                    {"schema":"source-permissions-v1", "permissions":[dict(PERMISSION,evidence_sha256="unknown")]},
                    {"schema":"source-permissions-v1", "permissions":[PERMISSION,PERMISSION]}]
        for m in variants:
            with self.subTest(manifest=m):
                self.assertEqual(assess_source(m, SOURCE, 'CACHE_READ', on_date=TODAY)[0], 'SOURCE_RIGHTS_HOLD')

    def test_original_publication_identity_requires_exact_reviewed_match_before_io(self):
        for changes in ({"original_journal": "Different Fictional Journal"},
                        {"original_publisher": "Unreviewed Publisher"},
                        {"original_url": "https://other.invalid/replaced"},
                        {"original_journal": None},
                        {"original_publisher": "  "},
                        {"original_url": None}):
            with self.subTest(changes=changes):
                changed = {**SOURCE, **changes}
                self.assertEqual(assess_source(MANIFEST, changed, 'CACHE_READ', on_date=TODAY)[0],
                                 'SOURCE_RIGHTS_HOLD')
        with TemporaryDirectory() as root:
            p = Path(root)
            manifest = p / 'rights.json'; manifest.write_text(json.dumps(MANIFEST))
            log = p / 'decisions.jsonl'; log.touch()
            probe = Mock(return_value=b'synthetic fixture')
            with self.assertRaises(PermissionError):
                execute_source_action({**SOURCE, 'original_publisher': 'Unreviewed Publisher'},
                                      'CACHE_READ', probe, manifest_path=manifest,
                                      decision_log=log, on_date=TODAY)
            probe.assert_not_called()
            self.assertEqual(json.loads(log.read_text().splitlines()[0])['decision'],
                             'SOURCE_RIGHTS_HOLD')

    def test_wrong_version_route_resource_and_operation_hold(self):
        for changes in ({"version":"v3"}, {"access_route":"OTHER_MIRROR"},
                        {"resource_ref":"different-cache"}, {"doi":"10.7777/other"},
                        {"doi":None}):
            with self.subTest(changes=changes):
                self.assertEqual(assess_source(MANIFEST,{**SOURCE,**changes},'CACHE_READ',on_date=TODAY)[0], 'SOURCE_RIGHTS_HOLD')
        for op in ('NETWORK_FETCH','EXTRACT','MODEL_SUBMISSION','SOME_OTHER_ACTION'):
            self.assertEqual(assess_source(MANIFEST,SOURCE,op,on_date=TODAY)[0], 'SOURCE_RIGHTS_HOLD')

    def test_jama_original_identity_held_even_from_mirror_and_reviewed_entry(self):
        for changes in ({"doi":"10.1001/synthetic-fixture"},
                        {"original_journal":"JAMA Network Open"},
                        {"original_journal":"Archives of Synthetic Medicine"},
                        {"original_publisher":"American Medical Association"},
                        {"original_url":"https://jamanetwork.com/journals/test"},
                        {"source_url":"https://jama.ama-assn.org/test"},
                        {"original_url":"https://archinte.ama-assn.org/test"},
                        {"original_journal":"Journal of the American Medical Association"}):
            source = {**SOURCE, **changes, "source_url": changes.get("source_url", "https://mirror.invalid/test")}
            with self.subTest(changes=changes):
                self.assertTrue(is_jama_source(source))
                self.assertEqual(assess_source(MANIFEST,source,'CACHE_READ',on_date=TODAY)[0], 'SOURCE_RIGHTS_HOLD')

    def test_log_missing_blocks_before_any_operation(self):
        with TemporaryDirectory() as root:
            p=Path(root); manifest=p/'manifest.json'; manifest.write_text(json.dumps(MANIFEST))
            decision=source_preflight(SOURCE,'CACHE_READ',manifest_path=manifest,decision_log=p/'missing.jsonl',on_date=TODAY)
            self.assertEqual(decision['decision'],'SOURCE_RIGHTS_HOLD')

    def test_append_only_log_includes_manifest_and_policy_hash(self):
        with TemporaryDirectory() as root:
            p=Path(root); manifest=p/'manifest.json'; manifest.write_text(json.dumps(MANIFEST))
            log=p/'decisions.jsonl'; log.touch()
            allow=source_preflight(SOURCE,'CACHE_READ',manifest_path=manifest,decision_log=log,on_date=TODAY)
            self.assertEqual(allow['decision'],'ALLOW')
            denied=source_preflight(SOURCE,'NETWORK_FETCH',manifest_path=manifest,decision_log=log,on_date=TODAY)
            self.assertEqual(denied['decision'],'SOURCE_RIGHTS_HOLD')
            lines=[json.loads(x) for x in log.read_text().splitlines()]
            self.assertEqual([x['decision'] for x in lines], ['ALLOW','SOURCE_RIGHTS_HOLD'])
            self.assertEqual(len(lines[0]['manifest_sha256']),64)
            self.assertEqual(len(lines[0]['policy_sha256']),64)
            self.assertEqual(lines[0]['evidence_reference'], PERMISSION['evidence_reference'])
            self.assertEqual(lines[0]['evidence_sha256'], PERMISSION['evidence_sha256'])
            self.assertEqual(lines[0]['reviewer'], PERMISSION['reviewer'])
            self.assertEqual(lines[0]['access_route'], SOURCE['access_route'])
            self.assertNotIn('evidence_reference', lines[1])

    def test_missing_manifest_or_log_never_reaches_cache_or_network_callback(self):
        with TemporaryDirectory() as root:
            p = Path(root)
            manifest = p / "rights.json"
            manifest.write_text(json.dumps(MANIFEST))
            log = p / "decisions.jsonl"
            probe = Mock(return_value=b"synthetic bytes")
            for kwargs in (dict(manifest_path=None, decision_log=log),
                           dict(manifest_path=manifest, decision_log=p / "missing.jsonl")):
                with self.subTest(kwargs=kwargs), self.assertRaises(PermissionError):
                    execute_source_action(SOURCE, "CACHE_READ", probe, on_date=TODAY, **kwargs)
                probe.assert_not_called()
            log.touch()
            self.assertEqual(execute_source_action(SOURCE, "CACHE_READ", probe,
                manifest_path=manifest, decision_log=log, on_date=TODAY), b"synthetic bytes")
            probe.assert_called_once()


    def test_unreviewed_mirror_and_lineage_cannot_reuse_a_grant(self):
        # A permission for one exact source must not authorize a different
        # mirror, prior extraction, or derived input with unchecked ancestry.
        variants = (
            {"source_url": "https://unreviewed-mirror.invalid/fixture.xml"},
            {"origin_urls": ["https://other-source.invalid/fixture.xml"]},
            {"lineage": [{"doi": "10.1001/synthetic-ancestor"}]},
            {"lineage": [{"doi": "10.8888/synthetic-unreviewed-parent"}]},
            {"content_kind": "derived"},
        )
        for changes in variants:
            with self.subTest(changes=changes):
                changed = {**SOURCE, **changes}
                self.assertEqual(
                    assess_source(MANIFEST, changed, "CACHE_READ", on_date=TODAY)[0],
                    "SOURCE_RIGHTS_HOLD",
                )
        approved_url = "https://fictional.invalid/reviewed-mirror/fixture.xml"
        grant = dict(PERMISSION, source_url=approved_url)
        scoped_manifest = dict(MANIFEST, permissions=[grant])
        reviewed_source = dict(SOURCE, source_url=approved_url)
        self.assertEqual(
            assess_source(scoped_manifest, reviewed_source, "CACHE_READ", on_date=TODAY)[0],
            "ALLOW",
        )
        self.assertEqual(
            assess_source(scoped_manifest, SOURCE, "CACHE_READ", on_date=TODAY)[0],
            "SOURCE_RIGHTS_HOLD",
        )
        self.assertEqual(
            assess_source(scoped_manifest, {**reviewed_source,
                "source_url": "https://fictional.invalid/other-path/fixture.xml"},
                "CACHE_READ", on_date=TODAY)[0],
            "SOURCE_RIGHTS_HOLD",
        )
        with TemporaryDirectory() as root:
            base = Path(root)
            manifest = base / "rights.json"
            manifest.write_text(json.dumps(scoped_manifest))
            log = base / "decisions.jsonl"
            log.touch()
            probe = Mock(return_value=b"synthetic-only")
            with self.assertRaises(PermissionError):
                execute_source_action({**reviewed_source,
                    "source_url": "https://fictional.invalid/other-path/fixture.xml"},
                    "CACHE_READ", probe, manifest_path=manifest,
                    decision_log=log, on_date=TODAY)
            probe.assert_not_called()
            self.assertEqual(json.loads(log.read_text().splitlines()[0])["decision"],
                             "SOURCE_RIGHTS_HOLD")



class ContactTests(unittest.TestCase):
    EXCLUSIONS=[{"names":["Fictional Researcher"],"aliases":["F. Researcher"],
                 "emails":["fictional@example.invalid"],"coauthors":["coauthor@example.invalid"],
                 "dois":["10.7777/fictional-publication"],"threads":["thread-fixture"],
                 "titles":["Synthetic STROKE Trial — analysis"], "trial_families":["Invented TRIAL Alpha"]}]

    def test_global_pause_blocks_new_replies_drafts_followups_retries(self):
        stub=Mock()
        for kind in ('new','reply','draft','followup','retry','reminder','resend','escalation','queued_send'):
            msg={"to":["unlisted@example.invalid"],"cc":[],"bcc":[],"kind":kind}
            with self.subTest(kind=kind), self.assertRaises(PermissionError):
                require_outgoing_allowed(msg, [])
            stub.assert_not_called()

    def test_alias_coauthor_bcc_indirect_thread_and_doi_match(self):
        messages=[{"to":["fictional@example.invalid"]},
                  {"to":["other@example.invalid"],"recipient_names":["F. Researcher"]},
                  {"bcc":["COAUTHOR@example.invalid"]},
                  {"indirect_recipients":["fictional@example.invalid"]},
                  {"to":["other@example.invalid"],"doi":"10.7777/fictional-publication"},
                  {"to":["other@example.invalid"],"thread_id":"thread-fixture"},
                  {"to":["Fictional Researcher <fictional@example.invalid>"]},
                  {"cc":["Dr Someone <coauthor@example.invalid>"]},
                  {"to":["other@example.invalid"],"title":"synthetic-stroke trial: ANALYSIS"},
                  {"to":["other@example.invalid"],"related_titles":["SYNTHETIC stroke trial analysis"]},
                  {"to":["other@example.invalid"],"trial_family":"Invented-Trial ALPHA"},
                  {"to":["other@example.invalid"],"related_trial_families":["Invented TRIAL Alpha"]}]
        for m in messages:
            with self.subTest(msg=m):
                blocked=outgoing_blockers(m,self.EXCLUSIONS)
                self.assertIn('PROGRAMME_OUTGOING_QUERY_PAUSE',blocked)
                self.assertTrue(any(x.startswith('CONTACT_BLOCKED_NO_CONTACT: recipient/publication') for x in blocked))

    def test_malformed_publication_and_exclusion_lists_fail_closed(self):
        malformed_messages = (
            {"to":["other@example.invalid"],"related_dois":"10.7777/fictional-publication"},
            {"to":["other@example.invalid"],"related_titles":[None]},
            {"to":["other@example.invalid"],"related_trial_families":{"bad":"shape"}},
            {"to":["other@example.invalid"],"recipient_names":[42]},
        )
        for msg in malformed_messages:
            with self.subTest(msg=msg):
                self.assertTrue(any("CONTACT_BLOCKED_NO_CONTACT" in reason
                                    for reason in outgoing_blockers(msg,self.EXCLUSIONS)))
        malformed_exclusions = [{**self.EXCLUSIONS[0], "titles":"not-list"},
                                {**self.EXCLUSIONS[0], "emails":[None]}]
        for entry in malformed_exclusions:
            self.assertTrue(any("CONTACT_BLOCKED_NO_CONTACT: malformed exclusion" in reason
                                for reason in outgoing_blockers({"to":["other@example.invalid"]},[entry])))

    def test_unavailable_exclusions_also_fail_closed(self):
        reasons=outgoing_blockers({"to":["other@example.invalid"]},None)
        self.assertTrue(any('exclusions unavailable' in x for x in reasons))

if __name__ == '__main__':
    unittest.main()