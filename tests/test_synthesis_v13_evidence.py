"""Synthetic tests only; no real publication, email or independent reviewer is verified."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "synthesis_v13_evidence",
    Path(__file__).resolve().parents[1] / "scripts" / "synthesis_v13_evidence.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def case(**changes):
    row = {
        "canonical_report_id": "synthetic:study-A",
        "current_version": "v2",
        "claim_locator": "Table 2, row A",
        "current_document_sha256": "a" * 64,
        "original_source_id": "synthetic:registry-A",
        "original_version": "v1",
        "original_locator": "Outcome 1",
        "original_source_sha256": "b" * 64,
        "analysis_identity": "Same ITT population, endpoint, window, estimator",
        "reconstruction_reference": "Synthetic workbook table A",
        "benign_explanation": "Different analysis population",
        "refutation_locator": "Synthetic source Methods paragraph",
        "root_scope_id": "synthetic:family-A",
        "root_cause_id": "root-1",
        "evidence_reference": "Synthetic record page 1",
        "current_claim_verified": True,
        "current_correction_status": "NO_RELEVANT_CORRECTION",
        "estimator_status": "MATCHED",
        "source_support": "CONTRADICTED",
        "benign_explanation_refuted": True,
        "severity": "S3",
        "maturity": "INDEPENDENTLY_ADJUDICATED",
        "investigator_id": "reviewer-A",
        "independent_verifier_id": "reviewer-B",
        "independent_adjudication_reference": "Synthetic masked verdict #1",
        "synthesis_discovery": True,
        "detection_record": "Synthetic timestamped discovery",
        "correspondence_status": "SENT",
        "sent_message_id": "synthetic-message-1",
        "recipient": "synthetic-author-A",
    }
    row.update(changes)
    return row


class EvidencePacketTests(unittest.TestCase):
    def test_complete_packet_is_only_ready_for_review(self):
        self.assertEqual(m.evidence_packet(case())["status"], "READY_FOR_INDEPENDENT_REVIEW")

    def test_missing_original_locator_holds(self):
        self.assertEqual(m.evidence_packet(case(original_locator=""))["status"], "HOLD")

    def test_invalid_source_hash_holds(self):
        self.assertEqual(m.evidence_packet(case(original_source_sha256="bad"))["status"], "HOLD")

    def test_uncertain_current_correction_holds(self):
        self.assertEqual(m.evidence_packet(case(current_correction_status="UNKNOWN"))["status"], "HOLD")

    def test_different_estimand_holds(self):
        self.assertEqual(m.evidence_packet(case(estimator_status="NOT_COMPARABLE"))["status"], "HOLD")

    def test_unrefuted_benign_explanation_holds(self):
        self.assertEqual(m.evidence_packet(case(benign_explanation_refuted=False))["status"], "HOLD")

    def test_no_automatic_error_verdict(self):
        self.assertNotIn("VERIFIED_ERROR", str(m.evidence_packet(case())))


class EmailedRootAccountingTests(unittest.TestCase):
    def test_one_attested_emailed_root(self):
        out = m.reconciliation_summary([case()])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 1)
        self.assertEqual(out["distinct_sent_messages"], 1)

    def test_same_root_multiple_outputs_deduplicated(self):
        out = m.reconciliation_summary([case(), case(claim_locator="Figure 3")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 1)
        self.assertEqual(out["duplicate_roots"], 1)

    def test_one_consolidated_email_can_cover_two_roots(self):
        out = m.reconciliation_summary([
            case(), case(root_cause_id="root-2", claim_locator="Table 3")
        ])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 2)
        self.assertEqual(out["distinct_sent_messages"], 1)

    def test_unsent_root_not_eligible(self):
        out = m.reconciliation_summary([case(correspondence_status="NOT_SENT")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)
        self.assertEqual(out["unqualified_or_unsent_records"], 1)

    def test_missing_sent_message_id_not_eligible(self):
        out = m.reconciliation_summary([case(sent_message_id="")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)

    def test_cosmetic_root_does_not_count(self):
        out = m.reconciliation_summary([case(severity="S2")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)

    def test_nonindependent_verifier_does_not_count(self):
        out = m.reconciliation_summary([case(independent_verifier_id="reviewer-A")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)

    def test_prior_published_correction_learning_not_new_discovery(self):
        out = m.reconciliation_summary([case(synthesis_discovery=False)])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)

    def test_author_confirmed_needs_confirmation_reference(self):
        out = m.reconciliation_summary([case(correspondence_status="AUTHOR_CONFIRMED")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)

    def test_published_correction_needs_notice_locator(self):
        out = m.reconciliation_summary([case(correspondence_status="CORRECTION_PUBLISHED")])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)

    def test_unknown_source_never_produces_verified_emailed_count(self):
        out = m.reconciliation_summary([case(current_claim_verified=False)])
        self.assertEqual(out["administratively_eligible_distinct_emailed_roots"], 0)
