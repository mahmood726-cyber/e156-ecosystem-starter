#!/usr/bin/env python3
"""Summarise private Synthesis journal audit records without exporting case IDs.

The output contains aggregates only. No source assertion or human adjudication
is created by this program; status labels must be supported by the input ledger.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path


DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
ACCESS = {"ACCESSIBLE_VOR", "SOURCE_LIMITED", "BLOCKED"}
ROOT_STATUS = {
    "PROVISIONAL", "SOURCE_VERIFIED", "AUTHOR_CONFIRMED",
    "PUBLISHED_CORRECTION", "REFUTED", "UNRESOLVED",
}
VERIFIED = {"SOURCE_VERIFIED", "AUTHOR_CONFIRMED", "PUBLISHED_CORRECTION"}
AUDIT_OUTCOMES = {"NOT_AUDITED", "NEGATIVE", "CANDIDATE", "VERIFIED", "INCONCLUSIVE"}


class LedgerError(ValueError):
    """The audit ledger is malformed or cannot justify a reported numerator."""


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{field} must be a nonempty string")
    return value.strip()


def _ids(row: dict, field: str) -> set[str]:
    values = row.get(field, [])
    if not isinstance(values, list):
        raise LedgerError(f"{field} must be a list")
    output = [_nonempty(v, field) for v in values]
    if len(set(output)) != len(output):
        raise LedgerError(f"duplicate {field} within one record")
    return set(output)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def summarise(records: list[dict]) -> dict:
    """Aggregate one reconciled record per DOI; preserve unknown denominators."""
    if not isinstance(records, list):
        raise LedgerError("top level must be a JSON list")
    seen_dois: set[str] = set()
    by_journal: dict[str, list[dict]] = defaultdict(list)
    all_verified: set[tuple[str, str]] = set()
    all_discovered: set[tuple[str, str]] = set()
    all_sent: set[str] = set()
    all_replies: set[str] = set()
    all_corrections: set[str] = set()
    for position, row in enumerate(records):
        if not isinstance(row, dict):
            raise LedgerError(f"record {position} must be an object")
        doi = _nonempty(row.get("doi"), "doi").lower()
        if not DOI.fullmatch(doi):
            raise LedgerError(f"invalid DOI in record {position}")
        if doi in seen_dois:
            raise LedgerError(f"duplicate DOI {doi}; reconcile owners before reporting")
        seen_dois.add(doi)
        journal = _nonempty(row.get("journal"), "journal")
        family = _nonempty(row.get("family_id"), "family_id")
        access = row.get("access")
        if access not in ACCESS:
            raise LedgerError(f"invalid access for {doi}")
        if access == "ACCESSIBLE_VOR":
            for field in ("source_version", "retrieval_path", "source_locator"):
                _nonempty(row.get(field), field)
        else:
            _nonempty(row.get("stop_point"), "stop_point")
        audited = row.get("deep_audit")
        if not isinstance(audited, bool):
            raise LedgerError(f"deep_audit must be a boolean for {doi}")
        if audited and access != "ACCESSIBLE_VOR":
            raise LedgerError(f"deep audit cannot be complete without accessible VOR: {doi}")
        outcome = row.get("audit_outcome")
        if outcome not in AUDIT_OUTCOMES:
            raise LedgerError(f"invalid/missing audit_outcome for {doi}")
        if audited == (outcome == "NOT_AUDITED"):
            raise LedgerError(f"audit_outcome contradicts deep_audit for {doi}")
        seconds = row.get("review_seconds")
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds) or seconds < 0):
            raise LedgerError(f"review_seconds must be finite and nonnegative for {doi}")
        roots = row.get("root_causes", [])
        if not isinstance(roots, list):
            raise LedgerError(f"root_causes must be a list for {doi}")
        root_ids: set[str] = set()
        verified: set[tuple[str, str]] = set()
        discovered: set[tuple[str, str]] = set()
        acknowledged: set[tuple[str, str]] = set()
        published: set[tuple[str, str]] = set()
        for root in roots:
            if not isinstance(root, dict):
                raise LedgerError("root cause must be an object")
            root_id = _nonempty(root.get("root_id"), "root_id")
            if root_id in root_ids:
                raise LedgerError(f"duplicate root in {doi}")
            root_ids.add(root_id)
            status = root.get("status")
            if status not in ROOT_STATUS:
                raise LedgerError(f"invalid root status in {doi}")
            key = (family, root_id)
            if status in VERIFIED:
                if not audited:
                    raise LedgerError(f"verified root without accessible deep audit in {doi}")
                _nonempty(root.get("evidence_locator"), "evidence_locator")
                _nonempty(root.get("source_reference"), "source_reference")
                verified.add(key)
                if not isinstance(root.get("synthesis_discovery"), bool):
                    raise LedgerError(f"synthesis_discovery must be explicit for verified root in {doi}")
                if root["synthesis_discovery"]:
                    _nonempty(root.get("detection_record"), "detection_record")
                    discovered.add(key)
            if status == "AUTHOR_CONFIRMED":
                _nonempty(root.get("confirmation_reference"), "confirmation_reference")
                acknowledged.add(key)
            if status == "PUBLISHED_CORRECTION":
                _nonempty(root.get("correction_reference"), "correction_reference")
                published.add(key)
        if outcome == "VERIFIED" and not verified:
            raise LedgerError(f"VERIFIED audit has no verified roots in {doi}")
        if outcome == "NEGATIVE" and any(r.get("status") not in {"REFUTED"} for r in roots):
            raise LedgerError(f"NEGATIVE audit contains unresolved or verified roots in {doi}")
        if outcome != "VERIFIED" and verified:
            raise LedgerError(f"verified root requires VERIFIED audit outcome in {doi}")
        sent, replied, corrections = (_ids(row, k) for k in
                                      ("sent_ids", "reply_ids", "correction_ids"))
        all_sent.update(sent)
        all_replies.update(replied)
        all_corrections.update(corrections)
        all_verified.update(verified)
        all_discovered.update(discovered)
        by_journal[journal].append({
            "access": access, "audited": audited, "seconds": seconds,
            "verified": verified, "discovered": discovered,
            "acknowledged": acknowledged,
            "published": published, "sent": sent, "replied": replied,
            "corrections": corrections, "negative": outcome == "NEGATIVE",
        })

    summaries: dict[str, dict] = {}
    for journal, rows in sorted(by_journal.items()):
        accessible = sum(r["access"] == "ACCESSIBLE_VOR" for r in rows)
        audited = sum(r["audited"] for r in rows)
        roots = set().union(*(r["verified"] for r in rows))
        discovered = set().union(*(r["discovered"] for r in rows))
        confirmed = set().union(*(r["acknowledged"] for r in rows))
        corrected = set().union(*(r["published"] for r in rows))
        sent = set().union(*(r["sent"] for r in rows))
        replied = set().union(*(r["replied"] for r in rows))
        seconds = sum(r["seconds"] for r in rows)
        summaries[journal] = {
            "screened_unique_dois": len(rows),
            "accessible_vor": accessible,
            "source_limited": sum(r["access"] == "SOURCE_LIMITED" for r in rows),
            "blocked": sum(r["access"] == "BLOCKED" for r in rows),
            "deep_audits": audited,
            "explicit_negative_audits": sum(r["negative"] for r in rows),
            "source_verified_unique_roots": len(roots),
            "verified_synthesis_discoveries": len(discovered),
            "author_confirmed_unique_roots": len(confirmed),
            "published_corrected_unique_roots": len(corrected),
            "sent_messages": len(sent), "replied_messages": len(replied),
            "verified_discoveries_per_100_accessible": _rate(len(discovered), accessible),
            "verified_discoveries_per_100_deep_audits": _rate(len(discovered), audited),
            "review_hours": round(seconds / 3600, 2),
            "verified_discoveries_per_reviewer_hour": (
                round(len(discovered) * 3600 / seconds, 2) if seconds else None
            ),
        }
    return {
        "schema": "synthesis-journal-yield-v1",
        "note": "Aggregates from supplied evidence labels, not independent adjudication. Cross-journal roots are not additive.",
        "portfolio_unique_dois": len(seen_dois),
        "portfolio_unique_source_verified_roots": len(all_verified),
        "portfolio_unique_verified_synthesis_discoveries": len(all_discovered),
        "portfolio_unique_sent_ids": len(all_sent),
        "portfolio_unique_reply_ids": len(all_replies),
        "portfolio_unique_correction_ids": len(all_corrections),
        "journals": summaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="private reconciled JSON list, one item per DOI")
    args = parser.parse_args()
    try:
        result = summarise(json.loads(args.ledger.read_text(encoding="utf-8")))
    except (LedgerError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
