"""Source-attested Synthesis v1.3 evidence packet and correspondence accounting.

Development utility only: it validates declarations and bookkeeping, not the
contents of publications, independent reviewers, email delivery, or error truth.
Never export case records or identifiers from private working ledgers to GitHub.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
SUBSTANTIVE = {"S3", "S4", "S5"}
SENT_STATES = {
    "SENT", "ACKNOWLEDGED", "AUTHOR_CONFIRMED", "AUTHOR_DISAGREED",
    "CORRECTION_REQUESTED", "CORRECTION_PUBLISHED", "UNRESOLVED",
}
CURRENT_STATES = {"NO_RELEVANT_CORRECTION", "CORRECTION_REVIEWED_CLAIM_PERSISTS"}


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evidence_packet(record: Mapping) -> dict:
    """Check evidence receipt *completeness*, not whether an error exists.

    The verifier identity, DOI/arXiv identifier, source paths and hashes are
    caller supplied. A complete packet is only READY_FOR_INDEPENDENT_REVIEW.
    It is never itself a publication-error finding or permission to email.
    """
    if not isinstance(record, Mapping):
        return {"status": "INVALID", "reason": "record is not a mapping"}
    required = (
        "canonical_report_id", "current_version", "claim_locator",
        "current_document_sha256", "original_source_id", "original_version",
        "original_locator", "original_source_sha256", "analysis_identity",
        "reconstruction_reference", "benign_explanation", "refutation_locator",
        "root_scope_id", "root_cause_id", "evidence_reference",
    )
    missing = [k for k in required if not _nonblank(record.get(k))]
    if missing:
        return {"status": "HOLD", "reason": "evidence fields missing", "fields": missing}
    for field in ("current_document_sha256", "original_source_sha256"):
        if SHA256.fullmatch(record[field]) is None:
            return {"status": "HOLD", "reason": "source SHA-256 format invalid", "field": field}
    if (record.get("current_claim_verified") is not True
            or record.get("current_correction_status") not in CURRENT_STATES
            or record.get("estimator_status") != "MATCHED"
            or record.get("source_support") != "CONTRADICTED"
            or record.get("benign_explanation_refuted") is not True):
        return {"status": "HOLD", "reason": "source/version/analysis/refutation gate incomplete"}
    if record.get("severity") not in {"S1", "S2", *SUBSTANTIVE}:
        return {"status": "HOLD", "reason": "severity not assessed"}
    return {
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "reason": "caller-supplied evidence packet complete; no truth authenticated",
        "root_key": (record["root_scope_id"], record["root_cause_id"]),
    }


def reconciliation_summary(records: Sequence[Mapping]) -> dict:
    """Deduplicated *administrative* count, never independent truth validation.

    Count only source-matched, independently adjudicated substantive root
    records with an attested actual sent-message ID. A caller can lie or err;
    evidence must be independently checked against the source and sent folder.
    """
    if not isinstance(records, (list, tuple)):
        raise ValueError("records must be a finite sequence")
    seen_roots: set[tuple[str, str]] = set()
    seen_messages: set[str] = set()
    eligible = duplicates = holds = sent_unqualified = 0
    reasons: dict[str, int] = {}
    for item in records:
        packet = evidence_packet(item)
        if packet["status"] != "READY_FOR_INDEPENDENT_REVIEW":
            holds += 1
            key = packet["reason"]
            reasons[key] = reasons.get(key, 0) + 1
            continue
        if (item.get("severity") not in SUBSTANTIVE
                or item.get("maturity") != "INDEPENDENTLY_ADJUDICATED"
                or not _nonblank(item.get("independent_verifier_id"))
                or not _nonblank(item.get("independent_adjudication_reference"))
                or not _nonblank(item.get("investigator_id"))
                or item.get("independent_verifier_id") == item.get("investigator_id")
                or item.get("synthesis_discovery") is not True
                or not _nonblank(item.get("detection_record"))):
            holds += 1
            reasons["substantive independent adjudication not attested"] = (
                reasons.get("substantive independent adjudication not attested", 0) + 1)
            continue
        if item.get("correspondence_status") not in SENT_STATES:
            sent_unqualified += 1
            continue
        if (not _nonblank(item.get("sent_message_id"))
                or not _nonblank(item.get("recipient"))
                or (item.get("correspondence_status") == "AUTHOR_CONFIRMED"
                    and not _nonblank(item.get("author_confirmation_reference")))
                or (item.get("correspondence_status") == "CORRECTION_PUBLISHED"
                    and not _nonblank(item.get("published_correction_locator")))):
            sent_unqualified += 1
            continue
        root = packet["root_key"]
        if root in seen_roots:
            duplicates += 1
            continue
        # One consolidated email may document several independently checked
        # roots. Count roots and distinct messages on separate axes.
        seen_roots.add(root)
        seen_messages.add(item["sent_message_id"])
        eligible += 1
    return {
        "records": len(records),
        "administratively_eligible_distinct_emailed_roots": eligible,
        "duplicate_roots": duplicates,
        "distinct_sent_messages": len(seen_messages),
        "held_records": holds,
        "unqualified_or_unsent_records": sent_unqualified,
        "hold_reasons": dict(sorted(reasons.items())),
        "warning": ("Caller attestations are unauthenticated; this is not a validated "
                    "scientific error count, independent source check or proof of delivery. "
                    "Do not put private evidence, addresses or message IDs in the repository."),
    }
