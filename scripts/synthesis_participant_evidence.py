"""Bind reviewer-selected participant comparisons to exact PMC source cells."""
from __future__ import annotations

import re

if __package__:
    from scripts.synthesis_v13_nma_preflight import restricted_analysis_accounting
else:
    from synthesis_v13_nma_preflight import restricted_analysis_accounting


MAX_CHECKS = 40
COUNT = re.compile(r"(?:0|[1-9][0-9]{0,14}|[1-9][0-9]{0,2}(?:,[0-9]{3}){1,4})")


def count_quotes(checks, *, corrections=False):
    quotes = set()
    for _, check in checks:
        spec = check.get("correction") if corrections and isinstance(check, dict) else check
        quote = spec.get("context_quote") if isinstance(spec, dict) else None
        if isinstance(quote, str) and 1 <= len(quote) <= 500 and quote.strip():
            quotes.add(" ".join(quote.split()))
    return sorted(quotes)


def _context(evidence, spec):
    quote = spec.get("context_quote")
    if not isinstance(quote, str) or not 1 <= len(quote) <= 500:
        raise ValueError("A source context quote of at most 500 characters is required")
    quote = " ".join(quote.split())
    locations = evidence.get("quote_locations", {}).get(quote, [])
    if len(locations) != 1:
        raise ValueError("The context quote must resolve to one source location")
    return {"quote": quote, "locator": locations[0]}


def _count_cell(evidence, ref):
    if not isinstance(ref, dict) or any(type(ref.get(key)) is not int or ref[key] < 1
                                        for key in ("table", "row", "cell")):
        raise ValueError("Counts require positive one-based table, row and physical cell coordinates")
    table_number, row_number, cell_number = (ref[key] for key in ("table", "row", "cell"))
    locator = f"body table-wrap {table_number} row {row_number} cell {cell_number}"
    try:
        table = evidence["tables"][table_number - 1]
        if table["status"] != "STRUCTURED":
            raise ValueError(f"{locator} belongs to a table requiring manual review")
        cell = table["rows"][row_number - 1]["cells"][cell_number - 1]
    except (IndexError, OverflowError) as exc:
        raise ValueError(f"{locator} does not exist") from exc
    if cell["rowspan"] != "1" or cell["colspan"] != "1" or not COUNT.fullmatch(cell["text"]):
        raise ValueError(f"{locator} must be an unmerged cell with one plain participant count")
    return {"locator": locator, "jats_table_id": table["jats_id"], "text": cell["text"],
            "participants": int(cell["text"].replace(",", ""))}


def _label(spec, key):
    value = spec.get(key)
    if (not isinstance(value, str) or not value.strip() or len(value) > 200
            or value.strip().casefold() in {"unknown", "n/a", "na", "not reported", "unclear"}):
        raise ValueError(f"An explicit reviewer-verified {key} is required")
    return " ".join(value.split())


def _restricted(evidence, spec, context):
    cells = {key: _count_cell(evidence, spec.get(key)) for key in ("primary", "restricted")}
    if cells["primary"]["locator"] == cells["restricted"]["locator"]:
        raise ValueError("The primary and restricted analyses must refer to different cells")
    return {"cells": cells, **restricted_analysis_accounting({
        "relationship": "RESTRICTION", "source_version": evidence["source"]["version"],
        "same_source_version_verified": True, "same_participant_count_basis_verified": True,
        "restriction_locator": context["locator"],
        "primary_locator": cells["primary"]["locator"], "restricted_locator": cells["restricted"]["locator"],
        "primary_participants": cells["primary"]["participants"],
        "restricted_participants": cells["restricted"]["participants"],
    })}


def _unique_arms(evidence, spec):
    reported = _count_cell(evidence, spec.get("reported"))
    arms = spec.get("arms")
    if not isinstance(arms, list) or not 2 <= len(arms) <= 500:
        raise ValueError("Supply a complete mapping of 2 to 500 source-backed trial arm entries")
    unique = {}
    locations = {reported["locator"]: None}
    bindings = []
    for arm in arms:
        if not isinstance(arm, dict):
            raise ValueError("An arm entry must identify its trial, cohort, arm and source cell")
        identity = {key: _label(arm, key) for key in ("trial", "cohort", "arm")}
        key = tuple(value.casefold() for value in identity.values())
        cell = _count_cell(evidence, arm.get("count"))
        location = cell["locator"]
        if locations.get(location, key) != key:
            raise ValueError("One count cell cannot represent different arms or the reported total")
        locations[location] = key
        count = cell["participants"]
        shared = arm.get("shared_control") is True
        if key in unique and (not shared or unique[key] != (count, True)):
            raise ValueError("Repeated arms require an explicitly mapped shared control with matching counts")
        unique[key] = count, shared
        bindings.append({**identity, "shared_control": shared, "count": cell})
    if len(unique) < 2:
        raise ValueError("At least two distinct source-backed arms are required")
    total = sum(count for count, _ in unique.values())
    excess = reported["participants"] - total
    return {"status": "REVIEW_CANDIDATE" if excess else "NO_FLAG",
            "reason": ("Reported participants differ from the verified distinct-arm sum" if excess
                       else "Reported participants equal the verified distinct-arm sum"),
            "cells": {"reported": reported, "arms": bindings}, "unique_participants": total,
            "participant_excess": excess, "distinct_arms": len(unique)}


def _correction(evidence, spec):
    try:
        if not isinstance(spec, dict) or spec.get("same_claim_verified") is not True:
            raise ValueError("Reviewers must identify the same claim in the published correction")
        matches = [entry for entry in evidence.get("linked_corrections", []) if entry["status"] == "CAPTURED"
                   and entry["source"]["pmcid"] == spec.get("pmcid")
                   and entry["source"]["snapshot_sha256"] == spec.get("snapshot_sha256")]
        matches = {entry["source"]["snapshot_sha256"]: entry for entry in matches}
        if len(matches) != 1:
            raise ValueError("The correction must match a verified linked PMC snapshot and digest")
        entry = next(iter(matches.values()))
        result = {"status": "SOURCE_BOUND", "source": entry["source"], "context": _context(entry, spec)}
        if "replacement" in spec:
            result["replacement"] = _count_cell(entry, spec["replacement"])
        if "previous" in spec:
            result["previous_as_reproduced_in_notice"] = _count_cell(entry, spec["previous"])
        return result
    except ValueError as exc:
        return {"status": "HOLD", "reason": str(exc)}


def participant_count_finding(claim_id, spec, evidence):
    finding = {"claim_id": claim_id}
    try:
        if not evidence or evidence["status"] != "CAPTURED":
            raise ValueError("A valid open-access PMC snapshot is required")
        if not isinstance(spec, dict) or spec.get("scope_verified") is not True:
            raise ValueError("A reviewer must verify analysis relationship, arm coverage and comparable denominators")
        source = evidence["source"]
        if spec.get("snapshot_sha256") != source["snapshot_sha256"]:
            raise ValueError("Participant cell coordinates must bind the exact source snapshot SHA-256")
        finding["source"] = source
        finding["analysis"] = {key: _label(spec, key) for key in ("outcome", "timepoint", "basis")}
        correction = _correction(evidence, spec["correction"]) if "correction" in spec else {}
        if correction:
            finding["correction"] = correction
        kind = spec.get("kind")
        if kind == "PUBLISHED_CORRECTION":
            if correction.get("status") != "SOURCE_BOUND":
                raise ValueError("A published replacement requires a source-bound correction")
            from_article = "original" in spec
            from_notice = "previous_as_reproduced_in_notice" in correction
            if from_article == from_notice or "replacement" not in correction:
                raise ValueError("Supply one original count cell and one replacement count cell")
            prior = (_count_cell(evidence, spec["original"]) if from_article
                     else correction["previous_as_reproduced_in_notice"])
            replacement = correction["replacement"]
            if from_notice and prior["locator"] == replacement["locator"]:
                raise ValueError("The original and replacement must use distinct source cells")
            if from_article:
                finding["original"] = prior
            if prior["participants"] == replacement["participants"]:
                finding.update(status="MATCH", reason="The two selected participant counts agree")
            else:
                finding.update(status="PUBLISHED_CORRECTION",
                               reason="The two reviewer-mapped counts differ across the original and replacement cells")
            return finding
        finding["context"] = _context(evidence, spec)
        if kind == "RESTRICTED":
            finding.update(_restricted(evidence, spec, finding["context"]))
        elif kind == "UNIQUE_ARMS":
            finding.update(_unique_arms(evidence, spec))
        else:
            raise ValueError("Unknown participant count check kind")
        if finding["status"] == "NO_FLAG" and correction.get("status") == "HOLD":
            finding.update(status="HOLD", comparison_status="NO_FLAG", reason="Requested correction evidence is unresolved")
    except ValueError as exc:
        finding.update(status="HOLD", reason=str(exc))
    return finding
