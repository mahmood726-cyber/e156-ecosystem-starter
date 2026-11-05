"""Conservative root-cause grouping of *caller-supplied* preflight observations.

Pure metadata contract: no article access, source authentication, scientific
adjudication, or eligibility for correspondence. Frozen v1.1/v1.2 unchanged.
"""
from __future__ import annotations

import re
from datetime import date
from collections.abc import Mapping, Sequence
from typing import Any

ROOT_KEYS = ("publication_id", "source_version", "root_scope_id", "root_cause_id")
REQUIRED = ROOT_KEYS + ("affected_output_id", "source_support", "maturity",
                        "disposition", "human_adjudicated", "author_confirmed")
SUPPORT = frozenset({"SUPPORTED", "CONTRADICTED", "OVERGENERALIZED",
                     "UNSUPPORTED_CITATION", "SOURCE_UNAVAILABLE", "NOT_ENOUGH_INFO"})
MATURITY = ("SCREENED", "SOURCE_BACKED", "REPRODUCED", "INDEPENDENTLY_ADJUDICATED")
DISPOSITIONS = frozenset({"FLAG", "RECONCILED", "DISCUSSION", "HOLD", "NO_FLAG"})
UNKNOWN = frozenset({
    "", "unknown", "unverified", "not_applicable", "not_reported",
    "not_specified", "not_available", "source_limited", "unavailable",
    "none", "null", "missing", "n/a", "na", "unclear", "undetermined",
    "tbd", "?",
})


def _valid_identifier(value: Any) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    # A repeated spelling of UNKNOWN is never a valid scope or receipt ID.
    # Preserve original identifiers for grouping: normalize only to reject
    # placeholders, not to equate unrelated outputs or trial families.
    normalized = re.sub(r"[\\s_-]+", "_", value.casefold())
    return normalized not in UNKNOWN


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _receipt_matches_scope(receipt: Any, record: Mapping[str, Any]) -> bool:
    return (isinstance(receipt, Mapping)
            and all(receipt.get(key) == record[key]
                    for key in ROOT_KEYS + ("affected_output_id",)))


def _human_receipt_valid(record: Mapping[str, Any]) -> bool:
    receipt = record.get("human_receipt")
    return (
        _receipt_matches_scope(receipt, record)
        and receipt.get("reviewer_kind") == "independent_human"
        and _valid_identifier(receipt.get("reviewer_id"))
        and _valid_identifier(receipt.get("investigator_id"))
        and receipt["reviewer_id"] != receipt["investigator_id"]
        and _valid_identifier(receipt.get("receipt_locator"))
        and _valid_date(receipt.get("adjudicated_at"))
        and receipt.get("conflict_check") is True
    )


def _author_receipt_valid(record: Mapping[str, Any]) -> bool:
    receipt = record.get("author_confirmation")
    return (
        _receipt_matches_scope(receipt, record)
        and receipt.get("confirmation_kind") == "explicit_error_confirmation"
        and _valid_identifier(receipt.get("confirmation_reference"))
        and _valid_date(receipt.get("confirmed_at"))
    )


def group_preflight_roots(observations: Any) -> dict[str, Any]:
    """Group identical source-version/root keys; preserve all affected outputs.

    Duplicate outputs with conflicting statements and contradictory dispositions
    are held rather than counted as separate confirmed roots. Everything is a
    preflight record, not an authenticated error or human-adjudicated finding.
    """
    held = {"status": "NOT_ENOUGH_INFO", "disposition": "HOLD", "roots": [],
            "root_count": None, "certified_errors": 0, "email_eligible": False}
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return {**held, "reason": "observations must be a sequence of mappings"}
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    seen_outputs: dict[tuple[str, str, str], tuple[str, ...]] = {}
    for index, record in enumerate(observations):
        if not isinstance(record, Mapping):
            return {**held, "reason": f"record {index}: expected mapping"}
        if any(not _valid_identifier(record.get(k)) for k in ROOT_KEYS + ("affected_output_id",)):
            return {**held, "reason": f"record {index}: missing or ambiguous root/output identity"}
        if (not isinstance(record.get("source_support"), str)
                or not isinstance(record.get("maturity"), str)
                or not isinstance(record.get("disposition"), str)
                or record["source_support"] not in SUPPORT
                or record["maturity"] not in MATURITY
                or record["disposition"] not in DISPOSITIONS
                or type(record.get("human_adjudicated")) is not bool
                or type(record.get("author_confirmed")) is not bool):
            return {**held, "reason": f"record {index}: unknown evidence status or boolean"}
        # Booleans alone do not evidence human independence or explicit author
        # agreement. Exact dated, conflict-checked, scope-bound private receipt
        # metadata are required before either status may be reported. Even these
        # caller-supplied declarations are NOT authenticated by this helper.
        if record["human_adjudicated"]:
            if (record["maturity"] != "INDEPENDENTLY_ADJUDICATED"
                    or not _human_receipt_valid(record)):
                return {**held, "reason": f"record {index}: independent human receipt missing, invalid or mismatched"}
        elif (record["maturity"] == "INDEPENDENTLY_ADJUDICATED"
              or record.get("human_receipt") is not None):
            return {**held, "reason": f"record {index}: human maturity or receipt contradicts status"}
        if record["author_confirmed"]:
            if not _author_receipt_valid(record):
                return {**held, "reason": f"record {index}: explicit author-confirmation receipt missing, invalid or mismatched"}
        elif record.get("author_confirmation") is not None:
            return {**held, "reason": f"record {index}: author receipt contradicts status"}
        key = tuple(record[k] for k in ROOT_KEYS)
        output = record["affected_output_id"]
        # The same output within a publication/version must not be counted
        # under two different roots without an explicit subsequent review.
        output_key = (key[0], key[1], output)
        if output_key in seen_outputs and seen_outputs[output_key] != key:
            return {**held, "reason": f"record {index}: output assigned conflicting roots"}
        seen_outputs[output_key] = key
        evidence = (record["source_support"], record["maturity"],
                    record["disposition"], record["human_adjudicated"],
                    record["author_confirmed"])
        group = groups.setdefault(key, {"outputs": {}, "evidence": []})
        if output in group["outputs"]:
            if group["outputs"][output] != evidence:
                return {**held, "reason": f"record {index}: conflicting repeated output evidence"}
            continue  # exact replay, not another affected output
        group["outputs"][output] = evidence
        group["evidence"].append(evidence)
    roots = []
    for key, group in sorted(groups.items()):
        evidence = group["evidence"]
        dispositions = {entry[2] for entry in evidence}
        # Reconciled and flagged states cannot silently coexist in a root.
        if "RECONCILED" in dispositions and "FLAG" in dispositions:
            return {**held, "reason": "root contains conflicting FLAG and RECONCILED states"}
        ranks = [MATURITY.index(e[1]) for e in evidence]
        roots.append({
            "root_key": dict(zip(ROOT_KEYS, key)),
            "affected_output_ids": sorted(group["outputs"]),
            "affected_output_count": len(group["outputs"]),
            "minimum_maturity": MATURITY[min(ranks)],
            "all_source_reproduced": all(r >= MATURITY.index("REPRODUCED") for r in ranks),
            "all_human_adjudicated": all(e[3] for e in evidence),
            "all_author_confirmed": all(e[4] for e in evidence),
            "dispositions": sorted(dispositions),
            "certified_error": False,  # no tool-based human/scientific certification
            "email_eligible": False,
            "attestations_authenticated": False,
        })
    return {"status": "GROUPED", "disposition": "HOLD", "roots": roots,
            "root_count": len(roots), "certified_errors": 0, "email_eligible": False,
            "reason": "synthetic-safe administrative grouping, not independent verification"}
