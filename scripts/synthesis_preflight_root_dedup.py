"""Conservative root-cause grouping of *caller-supplied* preflight observations.

Pure metadata contract: no article access, source authentication, scientific
adjudication, or eligibility for correspondence. Frozen v1.1/v1.2 unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

ROOT_KEYS = ("publication_id", "source_version", "root_scope_id", "root_cause_id")
REQUIRED = ROOT_KEYS + ("affected_output_id", "source_support", "maturity",
                        "disposition", "human_adjudicated", "author_confirmed")
SUPPORT = frozenset({"SUPPORTED", "CONTRADICTED", "OVERGENERALIZED",
                     "UNSUPPORTED_CITATION", "SOURCE_UNAVAILABLE", "NOT_ENOUGH_INFO"})
MATURITY = ("SCREENED", "SOURCE_BACKED", "REPRODUCED", "INDEPENDENTLY_ADJUDICATED")
DISPOSITIONS = frozenset({"FLAG", "RECONCILED", "DISCUSSION", "HOLD", "NO_FLAG"})
UNKNOWN = frozenset({"", "unknown", "unverified", "not_applicable", "not reported",
                     "not_reported", "none", "null", "missing", "tbd", "?"})


def _valid_identifier(value: Any) -> bool:
    return (isinstance(value, str) and value == value.strip()
            and value.strip().casefold() not in UNKNOWN)


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
        # An independent adjudication state cannot be created by flagging a
        # source as REPRODUCED: explicit human status remains mandatory.
        if (record["maturity"] == "INDEPENDENTLY_ADJUDICATED"
                and not record["human_adjudicated"]):
            return {**held, "reason": f"record {index}: maturity contradicts human status"}
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
        })
    return {"status": "GROUPED", "disposition": "HOLD", "roots": roots,
            "root_count": len(roots), "certified_errors": 0, "email_eligible": False,
            "reason": "synthetic-safe administrative grouping, not independent verification"}
