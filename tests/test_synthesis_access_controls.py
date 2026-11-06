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

    def test_original_doi_must_bind_reviewed_source_and_obey_jama_hold(self):
        # Invented DOI suffixes only: no real journal material or network I/O.
        held_doi = "10.1001/synthetic-policy-fixture"
        for original_doi in (held_doi, "doi:" + held_doi,
                             "https://dx.doi.org/" + held_doi):
            with self.subTest(held_original=original_doi):
                source = {**SOURCE, "original_doi": original_doi}
                grant = {**PERMISSION, "original_doi": original_doi}
                manifest = {"schema": "source-permissions-v1", "permissions": [grant]}
                self.assertTrue(is_jama_source(source))
                self.assertEqual(assess_source(manifest, source, "CACHE_READ",
                                               on_date=TODAY)[0], "SOURCE_RIGHTS_HOLD")
                # The original identity in the reviewed grant also takes precedence.
                self.assertEqual(assess_source(manifest, SOURCE, "CACHE_READ",
                                               on_date=TODAY)[0], "SOURCE_RIGHTS_HOLD")
        same_source = {**SOURCE, "original_doi": SOURCE["doi"]}
        same_grant = {**PERMISSION, "original_doi": SOURCE["doi"]}
        matching = {"schema": "source-permissions-v1", "permissions": [same_grant]}
        self.assertEqual(assess_source(matching, same_source, "CACHE_READ",
                                       on_date=TODAY)[0], "ALLOW")
        # An extra asserted original identity is not independently reviewed.
        for src, grant in (
            (same_source, PERMISSION),
            (SOURCE, same_grant),
            ({**SOURCE, "original_doi": "10.7777/another-synthetic"}, same_grant),
            ({**SOURCE, "original_doi": "bad-doi"}, {**PERMISSION, "original_doi": "bad-doi"}),
            ({**SOURCE, "original_doi": ""}, {**PERMISSION, "original_doi": ""}),
        ):
            with self.subTest(unbound_original=(src.get("original_doi"), grant.get("original_doi"))):
                self.assertEqual(assess_source(
                    {"schema": "source-permissions-v1", "permissions": [grant]},
                    src, "CACHE_READ", on_date=TODAY)[0], "SOURCE_RIGHTS_HOLD")
        with TemporaryDirectory() as root:
            folder = Path(root)
            manifest_file = folder / "rights.json"
            manifest_file.write_text(json.dumps({
                "schema": "source-permissions-v1",
                "permissions": [{**PERMISSION, "original_doi": held_doi}]}))
            log = folder / "decisions.jsonl"
            log.touch()
            callback = Mock(return_value=b"synthetic-only")
            with self.assertRaises(PermissionError):
                execute_source_action({**SOURCE, "original_doi": held_doi},
                                      "CACHE_READ", callback,
                                      manifest_path=manifest_file,
                                      decision_log=log, on_date=TODAY)
            callback.assert_not_called()
            self.assertEqual(json.loads(log.read_text().splitlines()[0])["decision"],
                             "SOURCE_RIGHTS_HOLD")

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

    def test_network_fetch_requires_reviewed_absolute_url_before_action(self):
        # Invented source metadata only. A reviewed publication identity and
        # operation must not authorize an unspecified or non-network address.
        grant = dict(PERMISSION, operations=["NETWORK_FETCH"])
        manifest = {"schema": "source-permissions-v1", "permissions": [grant]}
        self.assertEqual(assess_source(manifest, SOURCE, "NETWORK_FETCH",
                                       on_date=TODAY)[0], "SOURCE_RIGHTS_HOLD")
        approved_url = "https://fictional.invalid/v2/approved.xml"
        grant["source_url"] = approved_url
        approved = {**SOURCE, "source_url": approved_url}
        self.assertEqual(assess_source(manifest, approved, "NETWORK_FETCH",
                                       on_date=TODAY)[0], "ALLOW")
        for invalid in ("", "/v2/approved.xml", "file:///tmp/synthetic.xml",
                        "ftp://fictional.invalid/v2.xml",
                        "https://reviewer@fictional.invalid/v2.xml",
                        "https://fictional.invalid:invalid/v2.xml"):
            with self.subTest(invalid=invalid):
                grant["source_url"] = invalid
                request = {**SOURCE, "source_url": invalid}
                self.assertEqual(assess_source(manifest, request, "NETWORK_FETCH",
                                               on_date=TODAY)[0], "SOURCE_RIGHTS_HOLD")
        with TemporaryDirectory() as root:
            p = Path(root)
            manifest_file = p / "permissions.json"
            manifest_file.write_text(json.dumps({"schema": "source-permissions-v1",
                                                  "permissions": [dict(PERMISSION, operations=["NETWORK_FETCH"])]}))
            log = p / "decisions.jsonl"
            log.touch()
            network_probe = Mock(return_value=b"synthetic-only")
            with self.assertRaises(PermissionError):
                execute_source_action(SOURCE, "NETWORK_FETCH", network_probe,
                                      manifest_path=manifest_file, decision_log=log,
                                      on_date=TODAY)
            network_probe.assert_not_called()
            self.assertEqual(json.loads(log.read_text().splitlines()[0])["decision"],
                             "SOURCE_RIGHTS_HOLD")

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


    def test_jama_trailing_dot_fqdn_hosts_fail_closed(self):
        # A terminal dot is the DNS absolute-name spelling of the same host.
        # All DOI suffixes and URL paths are synthetic; no URL is fetched.
        cases = (
            ("original_url", "jamanetwork.com."),
            ("source_url", "sub.jamanetwork.com."),
            ("original_url", "www.ama-assn.org."),
            ("source_url", "ama-assn.org."),
        )
        for field, host in cases:
            with self.subTest(identity_field=field, host=host):
                url = f"https://{host}/fictional-source"
                source = {**SOURCE, field: url}
                grant = {**PERMISSION, field: url}
                reviewed = {"schema": "source-permissions-v1", "permissions": [grant]}
                self.assertTrue(is_jama_source(source))
                self.assertEqual(assess_source(
                    reviewed, source, "CACHE_READ", on_date=TODAY)[0],
                    "SOURCE_RIGHTS_HOLD")

        # The preflight must stop the callback and append an actual HOLD receipt.
        with TemporaryDirectory() as root:
            folder = Path(root)
            url = "https://jamanetwork.com./fictional-source"
            source = {**SOURCE, "original_url": url}
            grant = {**PERMISSION, "original_url": url}
            manifest = folder / "rights.json"
            manifest.write_text(json.dumps({
                "schema": "source-permissions-v1", "permissions": [grant]}))
            log = folder / "decisions.jsonl"
            log.touch()
            callback = Mock(return_value=b"synthetic-only")
            with self.assertRaises(PermissionError):
                execute_source_action(source, "CACHE_READ", callback,
                                      manifest_path=manifest, decision_log=log,
                                      on_date=TODAY)
            callback.assert_not_called()
            self.assertEqual(json.loads(log.read_text().splitlines()[-1])["decision"],
                             "SOURCE_RIGHTS_HOLD")

        # A deceptive suffix on an unrelated synthetic host must not match.
        unrelated = "https://jamanetwork.com.fictional.invalid/fictional-source"
        source = {**SOURCE, "original_url": unrelated}
        grant = {**PERMISSION, "original_url": unrelated}
        reviewed = {"schema": "source-permissions-v1", "permissions": [grant]}
        self.assertFalse(is_jama_source(source))
        self.assertEqual(assess_source(reviewed, source, "CACHE_READ",
                                       on_date=TODAY)[0], "ALLOW")

    def test_resolver_alias_cannot_hide_jama_identity(self):
        # Invented DOIs: a resolver alias is still the same held publication.
        for doi in (
            "https://dx.doi.org/10.1001/synthetic-fixture",
            "http://dx.doi.org/10.1001/synthetic-fixture",
            "https://doi.org/10.1001/synthetic-fixture?reader=1",
        ):
            with self.subTest(doi=doi):
                self.assertTrue(is_jama_source({**SOURCE, "doi": doi}))
        self.assertFalse(is_jama_source({
            **SOURCE, "doi": "https://doi.org.untrusted.invalid/10.1001/synthetic-fixture"
        }))

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

    def test_log_aliases_hold_before_receipt_or_source_action(self):
        # A private append log cannot silently be a symlink, hardlink, or a
        # file reached through a symlinked parent directory. Synthetic only.
        with TemporaryDirectory() as root:
            base = Path(root)
            manifest = base / "permissions.json"
            manifest.write_text(json.dumps(MANIFEST))
            external = base / "unapproved-receipts.jsonl"
            external.write_text("synthetic sentinel\\n")
            aliases = []
            hardlink = base / "hardlink.jsonl"
            try:
                import os
                os.link(external, hardlink)
                aliases.append(hardlink)
            except (OSError, NotImplementedError):
                pass
            symlink = base / "symlink.jsonl"
            try:
                symlink.symlink_to(external)
                aliases.append(symlink)
            except (OSError, NotImplementedError):
                pass
            external_dir = base / "external"
            external_dir.mkdir()
            nested_log = external_dir / "log.jsonl"
            nested_log.write_text("nested sentinel\\n")
            aliased_dir = base / "indirect"
            try:
                aliased_dir.symlink_to(external_dir, target_is_directory=True)
                aliases.append(aliased_dir / "log.jsonl")
            except (OSError, NotImplementedError):
                pass
            self.assertTrue(aliases, "synthetic alias setup needs link support")
            for alias in aliases:
                with self.subTest(log=str(alias)):
                    before = (nested_log if alias == aliased_dir / "log.jsonl"
                              else external).read_bytes()
                    callback = Mock(return_value=b"synthetic")
                    with self.assertRaises(PermissionError):
                        execute_source_action(SOURCE, "CACHE_READ", callback,
                                              manifest_path=manifest,
                                              decision_log=alias, on_date=TODAY)
                    callback.assert_not_called()
                    self.assertEqual((nested_log if alias == aliased_dir / "log.jsonl"
                                      else external).read_bytes(), before)

    def test_permission_manifest_path_aliases_hold_before_source_action(self):
        # The rights manifest is a trust boundary. A symlink, hardlink,
        # or symlinked ancestor must not substitute another permission file,
        # even when it contains a syntactically reviewed synthetic grant.
        import os
        with TemporaryDirectory() as root:
            base = Path(root)
            trusted_dir = base / "trusted"
            trusted_dir.mkdir()
            trusted = trusted_dir / "rights.json"
            trusted.write_text(json.dumps(MANIFEST))
            decision_log = base / "decisions.jsonl"
            decision_log.touch()
            legitimate = Mock(return_value=b"synthetic")
            self.assertEqual(execute_source_action(
                SOURCE, "CACHE_READ", legitimate, manifest_path=trusted,
                decision_log=decision_log, on_date=TODAY), b"synthetic")
            legitimate.assert_called_once()

            aliases = []
            symlink = base / "rights-symlink.json"
            try:
                symlink.symlink_to(trusted)
                aliases.append(symlink)
            except (OSError, NotImplementedError):
                pass
            hardlink = base / "rights-hardlink.json"
            try:
                os.link(trusted, hardlink)
                aliases.append(hardlink)
            except (OSError, NotImplementedError):
                pass
            parent_link = base / "redirected-directory"
            try:
                parent_link.symlink_to(trusted_dir, target_is_directory=True)
                aliases.append(parent_link / "rights.json")
            except (OSError, NotImplementedError):
                pass
            if not aliases:
                self.skipTest("filesystem does not support manifest link fixtures")
            for alias in aliases:
                with self.subTest(manifest=alias.name):
                    probe = Mock(return_value=b"should-not-be-read")
                    with self.assertRaises(PermissionError):
                        execute_source_action(
                            SOURCE, "CACHE_READ", probe, manifest_path=alias,
                            decision_log=decision_log, on_date=TODAY)
                    probe.assert_not_called()
                    last = json.loads(decision_log.read_text().splitlines()[-1])
                    self.assertEqual(last["decision"], "SOURCE_RIGHTS_HOLD")

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



    def test_duplicate_json_keys_in_reviewed_manifest_fail_closed(self):
        # A JSON parser's last-wins handling of duplicate keys must not turn
        # a conflicting synthetic permission record into a reviewed grant.
        # No network, article fixtures, or real recipients are used.
        canonical = json.dumps(MANIFEST)
        variants = {
            "permission-status": canonical.replace(
                '"status": "REVIEWED_ALLOW"',
                '"status": "DENIED", "status": "REVIEWED_ALLOW"', 1),
            "operation-grant": canonical.replace(
                '"operations": ["CACHE_READ", "REPLAY"]',
                '"operations": [], "operations": ["CACHE_READ", "REPLAY"]', 1),
            "manifest-schema": canonical.replace(
                '"schema": "source-permissions-v1"',
                '"schema": "unknown", "schema": "source-permissions-v1"', 1),
        }
        with TemporaryDirectory() as root:
            folder = Path(root)
            manifest = folder / "permissions.json"
            log = folder / "access.jsonl"
            log.touch()
            for label, payload in variants.items():
                with self.subTest(duplicate=label):
                    self.assertNotEqual(payload, canonical)
                    manifest.write_text(payload, encoding="utf-8")
                    callback = Mock(return_value=b"synthetic-cache")
                    with self.assertRaises(PermissionError):
                        execute_source_action(SOURCE, "CACHE_READ", callback,
                                              manifest_path=manifest,
                                              decision_log=log, on_date=TODAY)
                    callback.assert_not_called()
                    receipt = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
                    self.assertEqual(receipt["decision"], "SOURCE_RIGHTS_HOLD")
            # A canonical, unambiguous reviewed fixture remains permitted.
            manifest.write_text(canonical, encoding="utf-8")
            callback = Mock(return_value=b"synthetic-cache")
            self.assertEqual(execute_source_action(
                SOURCE, "CACHE_READ", callback, manifest_path=manifest,
                decision_log=log, on_date=TODAY), b"synthetic-cache")
            callback.assert_called_once()


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

    def test_display_name_alias_on_all_recipient_routes(self):
        # The visible name alone can identify an excluded person even when
        # the mailbox is different from the known address or alias.
        for route in ("to", "cc", "bcc", "indirect_recipients"):
            for display_name in ("Fictional Researcher", "F. Researcher"):
                message = {route: [f'"{display_name}" <new-address@example.invalid>'],
                           "kind": "followup"}
                with self.subTest(route=route, display_name=display_name):
                    reasons = outgoing_blockers(message, self.EXCLUSIONS)
                    self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                    self.assertTrue(any("recipient/publication/thread exclusion" in x
                                        for x in reasons))
        unrelated = outgoing_blockers(
            {"to": ['"Different Invented Person" <new-address@example.invalid>']},
            self.EXCLUSIONS)
        self.assertEqual(unrelated, ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

    def test_multi_address_header_all_routes_fails_closed(self):
        # A recipient-list element can itself be an RFC 5322 address header,
        # with a second or later suppressed person. The first address must not
        # hide the second. Only invented names and mailboxes are used.
        headers = (
            'Allowed <allowed@example.invalid>, "Fictional Researcher" <new@example.invalid>',
            'Allowed <allowed@example.invalid>, "F. Researcher" <new@example.invalid>',
            'Allowed <allowed@example.invalid>, Coauthor <coauthor@example.invalid>',
            '"Another, Invented" <allowed@example.invalid>, "Fictional Researcher" <new@example.invalid>',
        )
        for route in ("to", "cc", "bcc", "indirect_recipients"):
            for header in headers:
                for kind in ("new", "retry", "followup", "queued_send"):
                    with self.subTest(route=route, header=header, kind=kind):
                        message = {route: [header], "kind": kind}
                        reasons = outgoing_blockers(message, self.EXCLUSIONS)
                        self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                        self.assertTrue(any("recipient/publication/thread exclusion" in x
                                            for x in reasons))
                        stub = Mock()
                        with self.assertRaises(PermissionError):
                            require_outgoing_allowed(message, self.EXCLUSIONS)
                        stub.assert_not_called()
        unrelated = outgoing_blockers(
            {"to": ['Allowed <allowed@example.invalid>, "Unrelated, Invented" <new@example.invalid>']},
            self.EXCLUSIONS)
        self.assertEqual(unrelated, ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

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


    def test_resolver_alias_cannot_hide_excluded_publication(self):
        # A publisher DOI exclusion must cover URL aliases in new/retry/follow-up
        # cases even if the recipient mailbox is previously unknown.
        for kind in ("new", "retry", "followup", "queued_send"):
            for field in ("doi", "related_dois"):
                value = "https://dx.doi.org/10.7777/fictional-publication"
                msg = {"to": ["unknown@example.invalid"], "kind": kind,
                       field: [value] if field == "related_dois" else value}
                with self.subTest(kind=kind, field=field):
                    blocked = outgoing_blockers(msg, self.EXCLUSIONS)
                    self.assertTrue(any("recipient/publication/thread exclusion" in reason
                                        for reason in blocked))
                    with self.assertRaises(PermissionError):
                        require_outgoing_allowed(msg, self.EXCLUSIONS)
        self.assertEqual(outgoing_blockers(
            {"to": ["unknown@example.invalid"],
             "doi": "https://doi.org.untrusted.invalid/10.7777/fictional-publication"},
            self.EXCLUSIONS),
            ["PROGRAMME_OUTGOING_QUERY_PAUSE",
             "CONTACT_BLOCKED_NO_CONTACT: malformed publication identifiers"])

    def test_mime_encoded_display_alias_in_all_recipient_fields(self):
        # RFC 2047 encoded words may appear in real address headers; use
        # invented names/mailboxes and never touch an outgoing transport.
        # Merely comparing getaddresses()' raw display text misses aliases.
        encoded = "=?utf-8?Q?Fictional_Researcher?="
        for route in ("to", "cc", "bcc", "indirect_recipients"):
            for kind in ("new", "retry", "followup", "queued_send"):
                message = {route: [f"{encoded} <alternate@example.invalid>"],
                           "kind": kind}
                with self.subTest(route=route, kind=kind):
                    reasons = outgoing_blockers(message, self.EXCLUSIONS)
                    self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                    self.assertTrue(any(
                        "CONTACT_BLOCKED_NO_CONTACT: recipient/publication/thread exclusion"
                        in reason for reason in reasons
                    ))
                    with self.assertRaises(PermissionError):
                        require_outgoing_allowed(message, self.EXCLUSIONS)
        unrelated = outgoing_blockers(
            {"to": ["=?utf-8?Q?Unrelated_Person?= <alternate@example.invalid>"]},
            self.EXCLUSIONS,
        )
        self.assertEqual(unrelated, ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

    def test_mime_encoded_standalone_recipient_name_and_exclusion_alias(self):
        # Separate recipient_names metadata does not necessarily contain a
        # formatted mailbox. Encoded aliases still must be matched, including
        # an unknown To address and a retry of a queued send.
        encoded = "=?utf-8?Q?Fictional_Researcher?="
        for kind in ("new", "retry", "followup", "queued_send"):
            message = {"to": ["different@example.invalid"],
                       "recipient_names": [encoded], "kind": kind}
            with self.subTest(kind=kind):
                reasons = outgoing_blockers(message, self.EXCLUSIONS)
                self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                self.assertIn(
                    "CONTACT_BLOCKED_NO_CONTACT: recipient/publication/thread exclusion",
                    reasons,
                )
                with self.assertRaises(PermissionError):
                    require_outgoing_allowed(message, self.EXCLUSIONS)

        encoded_exclusions = [{
            "names": [encoded], "emails": [], "aliases": [],
            "coauthors": [], "dois": [], "threads": [], "titles": [],
            "trial_families": [],
        }]
        for kind in ("new", "retry", "followup", "queued_send"):
            with self.subTest(exclusion_kind=kind):
                message = {"to": ["Fictional Researcher <unknown@example.invalid>"],
                           "kind": kind}
                reasons = outgoing_blockers(message, encoded_exclusions)
                self.assertIn(
                    "CONTACT_BLOCKED_NO_CONTACT: recipient/publication/thread exclusion",
                    reasons,
                )

        # An unrelated synthetic name must not manufacture a no-contact match.
        unrelated = {"to": ["unrelated@example.invalid"],
                     "recipient_names": ["=?utf-8?Q?Different_Person?="]}
        self.assertEqual(outgoing_blockers(unrelated, self.EXCLUSIONS),
                         ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

        malformed = "=?utf-8?B?////?="
        invalid_metadata = {"to": ["unrelated@example.invalid"],
                            "recipient_names": [malformed], "kind": "retry"}
        self.assertIn(
            "CONTACT_BLOCKED_NO_CONTACT: invalid recipient encoding",
            outgoing_blockers(invalid_metadata, self.EXCLUSIONS),
        )
        malformed_exclusions = [{
            "names": [malformed], "emails": [], "aliases": [],
            "coauthors": [], "dois": [], "threads": [], "titles": [],
            "trial_families": [],
        }]
        self.assertIn(
            "CONTACT_BLOCKED_NO_CONTACT: invalid exclusion encoding",
            outgoing_blockers({"to": ["unrelated@example.invalid"]},
                              malformed_exclusions),
        )

    def test_invalid_encoded_display_and_exclusion_hold(self):
        # Deliberately invalid UTF-8 encoded-word (synthetic), not a real
        # recipient. A decoding error must never turn into an implicit allow.
        invalid = "=?utf-8?B?////?= <alternate@example.invalid>"
        message = {"to": [invalid], "kind": "retry"}
        reasons = outgoing_blockers(message, self.EXCLUSIONS)
        self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
        self.assertIn("CONTACT_BLOCKED_NO_CONTACT: invalid recipient encoding", reasons)
        with self.assertRaises(PermissionError):
            require_outgoing_allowed(message, self.EXCLUSIONS)

        invalid_exclusions = [{
            "names": [invalid], "emails": [], "aliases": [], "coauthors": []
        }]
        reasons = outgoing_blockers({"to": ["other@example.invalid"]},
                                    invalid_exclusions)
        self.assertIn("CONTACT_BLOCKED_NO_CONTACT: invalid exclusion encoding", reasons)

    def test_related_threads_and_malformed_thread_metadata_fail_closed(self):
        # Invented Gmail-thread identifiers only. A resend can be linked to
        # multiple prior threads even when the active thread is a new ID.
        for kind in ("new", "retry", "followup", "queued_send"):
            msg = {"to": ["unlisted@example.invalid"], "kind": kind,
                   "thread_id": "new-synthetic-thread",
                   "related_thread_ids": ["other-synthetic-thread", "thread-fixture"]}
            with self.subTest(kind=kind):
                reasons = outgoing_blockers(msg, self.EXCLUSIONS)
                self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                self.assertIn(
                    "CONTACT_BLOCKED_NO_CONTACT: recipient/publication/thread exclusion",
                    reasons,
                )
                stub = Mock()
                with self.assertRaises(PermissionError):
                    require_outgoing_allowed(msg, self.EXCLUSIONS)
                stub.assert_not_called()

        for malformed in (
            {"thread_id": ["thread-fixture"]},
            {"thread_id": 72},
            {"related_thread_ids": "thread-fixture"},
            {"related_thread_ids": [None]},
        ):
            with self.subTest(malformed=malformed):
                msg = {"to": ["unlisted@example.invalid"], **malformed}
                reasons = outgoing_blockers(msg, self.EXCLUSIONS)
                self.assertTrue(any("CONTACT_BLOCKED_NO_CONTACT" in x for x in reasons))

        unrelated = {"to": ["unlisted@example.invalid"],
                     "thread_id": "other-synthetic-thread",
                     "related_thread_ids": ["unrelated-synthetic-thread"]}
        self.assertEqual(outgoing_blockers(unrelated, self.EXCLUSIONS),
                         ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

    def test_malformed_publication_values_cannot_disappear_from_matching(self):
        # Invented metadata only. A malformed primary or linked identifier
        # must not silently disappear from publication-level no-contact checks.
        # The programme pause is an independent safeguard, not proof the
        # publication exclusion was actually evaluated.
        malformed = (
            {"doi": ["10.7777/fictional-publication"]},
            {"doi": {"value": "10.7777/fictional-publication"}},
            {"doi": "https://untrusted-doi.invalid/10.7777/fictional-publication"},
            {"related_dois": ["not-a-doi"]},
            {"title": ["Synthetic STROKE Trial — analysis"]},
            {"title": "  "},
            {"trial_family": {"name": "Invented TRIAL Alpha"}},
            {"related_titles": ["  "]},
            {"related_trial_families": [""]},
        )
        for item in malformed:
            for kind in ("new", "retry", "followup", "queued_send"):
                with self.subTest(item=item, kind=kind):
                    message = {"to": ["unlisted@example.invalid"], "kind": kind, **item}
                    reasons = outgoing_blockers(message, self.EXCLUSIONS)
                    self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                    self.assertTrue(any(x.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                                        for x in reasons))
                    stub = Mock()
                    with self.assertRaises(PermissionError):
                        require_outgoing_allowed(message, self.EXCLUSIONS)
                    stub.assert_not_called()
        # A malformed private exclusion DOI is not an empty exclusion.
        exclusions = [{**self.EXCLUSIONS[0], "dois": ["not-a-doi"]}]
        reasons = outgoing_blockers({"to": ["unlisted@example.invalid"]}, exclusions)
        self.assertTrue(any(x.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                            for x in reasons))
        # Valid unrelated identifiers must not be spuriously classified as
        # a person/publication no-contact match.
        self.assertEqual(
            outgoing_blockers({"to": ["unlisted@example.invalid"],
                               "doi": "10.7777/another-synthetic-source",
                               "title": "Unrelated invented study",
                               "trial_family": "Other invented trial"}, self.EXCLUSIONS),
            ["PROGRAMME_OUTGOING_QUERY_PAUSE"],
        )

    def test_blank_suppression_values_and_recipients_fail_closed(self):
        # Invented-only metadata. A blank record in the private register must
        # not be silently discarded as though it contained no exclusions.
        for field in ("names", "aliases", "emails", "coauthors",
                      "dois", "threads", "titles", "trial_families"):
            for kind in ("new", "retry", "followup", "queued_send"):
                with self.subTest(field=field, kind=kind):
                    exclusion = {field: ["  \t "]}
                    reasons = outgoing_blockers(
                        {"to": ["unlisted@example.invalid"], "kind": kind},
                        [exclusion])
                    self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                    self.assertTrue(any(x.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                                        for x in reasons))
                    stub = Mock()
                    with self.assertRaises(PermissionError):
                        require_outgoing_allowed(
                            {"to": ["unlisted@example.invalid"], "kind": kind},
                            [exclusion])
                        stub()  # A blocked preflight cannot reach a transport.
                    stub.assert_not_called()
        # A transport recipient or standalone recipient-name field containing
        # only whitespace is likewise unknown, not a reviewed safe identity.
        for field in ("to", "cc", "bcc", "indirect_recipients", "recipient_names"):
            for kind in ("new", "retry", "followup", "queued_send"):
                with self.subTest(recipient_field=field, kind=kind):
                    msg = {"to": ["unlisted@example.invalid"], field: [" \t "],
                           "kind": kind}
                    reasons = outgoing_blockers(msg, self.EXCLUSIONS)
                    self.assertTrue(any(x.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                                        for x in reasons))
                    stub = Mock()
                    with self.assertRaises(PermissionError):
                        require_outgoing_allowed(msg, self.EXCLUSIONS)
                        stub()
                    stub.assert_not_called()
        # Negative control: a valid unrelated address and populated exclusion
        # must not be reported as an additional no-contact violation.
        self.assertEqual(outgoing_blockers(
            {"to": ["unlisted@example.invalid"]}, self.EXCLUSIONS),
            ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

    def test_transport_header_controls_fail_closed(self):
        # An untrusted address field containing CR/LF can be interpreted as
        # another header by a transport, while getaddresses may parse no
        # mailboxes at all. Invented names and domains only.
        poisoned = "Safe <safe@example.invalid>\r\nBcc: Excluded Test <alias@example.invalid>"
        exclusions = [{"names": ["Excluded Test"], "aliases": [],
                       "emails": [], "coauthors": []}]
        for kind in ("new", "retry", "followup", "queued_send"):
            for field in ("to", "cc", "bcc", "indirect_recipients",
                          "recipient_names"):
                with self.subTest(kind=kind, field=field):
                    message = {"to": ["safe@example.invalid"],
                               "kind": kind, field: [poisoned]}
                    reasons = outgoing_blockers(message, exclusions)
                    self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                    self.assertTrue(any(
                        reason.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                        for reason in reasons))
                    transport = Mock()
                    with self.assertRaises(PermissionError):
                        require_outgoing_allowed(message, exclusions)
                        transport()
                    transport.assert_not_called()
        # Encoded words must be inspected after RFC 2047 decoding too:
        # the raw header contains no literal CR/LF, but decoding restores it.
        encoded_poison = (
            "=?utf-8?B?U2FmZSA8c2FmZUBleGFtcGxlLmludmFsaWQ+"
            "DQpCY2M6IEV4Y2x1ZGVkIFRlc3QgPGFsaWFzQGV4YW1wbGUuaW52YWxpZD4=?="
        )
        for field in ("to", "cc", "bcc", "indirect_recipients",
                      "recipient_names"):
            with self.subTest(encoded_field=field):
                message = {"to": ["safe@example.invalid"], field: [encoded_poison]}
                reasons = outgoing_blockers(message, exclusions)
                self.assertTrue(any(
                    reason.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                    for reason in reasons))
        for field in ("names", "aliases", "emails", "coauthors"):
            with self.subTest(exclusion_field=field):
                invalid_exclusion = [{field: [poisoned]}]
                reasons = outgoing_blockers(
                    {"to": ["safe@example.invalid"]}, invalid_exclusion)
                self.assertTrue(any(
                    reason.startswith("CONTACT_BLOCKED_NO_CONTACT:")
                    for reason in reasons))
        # Negative control: a syntactically sound, nonexcluded address is
        # blocked by the programme pause alone.
        self.assertEqual(outgoing_blockers(
            {"to": ["Safe <safe@example.invalid>"]}, exclusions),
            ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

    def test_gmail_delivery_aliases_block_no_contact(self):
        # Entirely invented recipients. Consumer Gmail delivery ignores dots
        # and plus-tag suffixes; googlemail.com is an equivalent mailbox host.
        # An unrecognized alias must never evade the private contact block.
        exclusion = [{"emails": ["fictionalresearcher@gmail.com"]}]
        aliases = (
            "Fictional Researcher <fictional.researcher+queue@gmail.com>",
            "fictionalresearcher+retry@googlemail.com",
        )
        for kind in ("new", "retry", "followup", "queued_send"):
            for field in ("to", "cc", "bcc", "indirect_recipients"):
                for alias in aliases:
                    with self.subTest(kind=kind, field=field, alias=alias):
                        message = {"to": ["safe@example.invalid"], field: [alias],
                                   "kind": kind}
                        reasons = outgoing_blockers(message, exclusion)
                        self.assertIn("PROGRAMME_OUTGOING_QUERY_PAUSE", reasons)
                        self.assertIn(
                            "CONTACT_BLOCKED_NO_CONTACT: recipient/publication/thread exclusion",
                            reasons)
                        transport = Mock()
                        with self.assertRaises(PermissionError):
                            require_outgoing_allowed(message, exclusion)
                            transport()
                        transport.assert_not_called()
        # Negative controls: unrelated Gmail accounts and non-Gmail domains
        # must not be folded together merely because they contain a dot/tag.
        for unrelated in ("differentresearcher@gmail.com",
                          "fictional.researcher+queue@example.invalid"):
            self.assertEqual(
                outgoing_blockers({"to": [unrelated]}, exclusion),
                ["PROGRAMME_OUTGOING_QUERY_PAUSE"])

    def test_unavailable_exclusions_also_fail_closed(self):
        reasons=outgoing_blockers({"to":["other@example.invalid"]},None)
        self.assertTrue(any('exclusions unavailable' in x for x in reasons))

if __name__ == '__main__':
    unittest.main()