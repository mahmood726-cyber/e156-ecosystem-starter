"""Bind reviewer-selected participant comparisons to exact PMC source cells."""
from __future__ import annotations

import re

if __package__:
    from scripts.synthesis_v13_nma_preflight import restricted_analysis_accounting
else:
    from synthesis_v13_nma_preflight import restricted_analysis_accounting


MAX_CHECKS = 40
COUNT = re.compile(r"(?:0|[1-9][0-9]{0,14}|[1-9][0-9]{0,2}(?:,[0-9]{3}){1,4})")
MISSING_LABELS = {"unknown", "n/a", "na", "not reported", "unclear", "not available",
                  "unavailable", "tbd", "not enough info", "source limited"}


def count_quotes(checks, *, corrections=False):
    quotes = set()
    def add(value):
        if isinstance(value, str) and 1 <= len(value) <= 500 and value.strip():
            quotes.add(" ".join(value.split()))
    for _, check in checks:
        spec = check.get("correction") if corrections and isinstance(check, dict) else check
        if not isinstance(spec, dict):
            continue
        add(spec.get("context_quote"))
        refs = [spec.get(k) for k in ("primary", "restricted", "reported", "original", "previous", "replacement")]
        for key in ("exclusion_counts", "current_occurrences", "arms"):
            entries = spec.get(key, [])
            if isinstance(entries, list):
                refs.extend(entry.get("count") if key == "arms" and isinstance(entry, dict) else entry
                            for entry in entries[:500])
        for ref in refs:
            if isinstance(ref, dict):
                add(ref.get("quote"))
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


def _count_ref(evidence, ref):
    if not isinstance(ref, dict) or "quote" not in ref:
        return _count_cell(evidence, ref)
    if not {"quote", "count_text"} <= set(ref) <= {"quote", "count_text", "locator"}:
        raise ValueError("A quoted count uses quote, count_text and an optional exact locator, without cell coordinates")
    if not isinstance(ref["quote"], str) or not 1 <= len(ref["quote"]) <= 500 or not ref["quote"].strip():
        raise ValueError("A count quote must contain 1 to 500 characters")
    quote, number = " ".join(ref["quote"].split()), ref["count_text"]
    matches = evidence.get("quote_bindings", {}).get(quote, [])
    if "locator" in ref:
        if not isinstance(ref["locator"], str) or not 1 <= len(ref["locator"]) <= 200:
            raise ValueError("The count locator must be an exact indexed source location")
        matches = [item for item in matches if item["locator"] == ref["locator"]]
    if len(matches) != 1 or matches[0]["count_safe"] is not True:
        raise ValueError("The quoted count has ambiguous, merged or unsupported source markup")
    source_binding = matches[0]
    binding = {"quote": quote, "locator": source_binding["locator"]}
    if not isinstance(number, str) or not COUNT.fullmatch(number):
        raise ValueError("count_text must be one exact nonnegative integer token")
    matches = list(re.finditer(r"(?<![\w.,+\-\u2212\u00b1])" + re.escape(number)
                              + r"(?![\w%+\-\u2212\u2013\u2014\u00b1]|[.,][0-9])", quote))
    if len(matches) != 1 or re.match(r"[\s*_]*(?:%|percent\b|percentage\b|per\s+cent\b)",
                                    quote[matches[0].end():], re.I):
        raise ValueError("The integer must occur once as a complete count token, not a percentage or range")
    offset = source_binding["quote_offset"]
    if type(offset) is not int or offset < 0:
        raise ValueError("A quoted count requires an unambiguous source text offset")
    return {**binding, "text": number, "participants": int(number.replace(",", "")),
            "token_start": matches[0].start(), "token_end": matches[0].end(),
            "source_token_start": offset + matches[0].start(), "source_token_end": offset + matches[0].end()}


def _reference_key(cell):
    """Canonical token identity also detects aliases using different excerpts."""
    return (cell["locator"], cell.get("source_token_start", 0), cell.get("source_token_end", len(cell["text"])))


def _label(spec, key):
    value = spec.get(key)
    label = " ".join(value.split()) if isinstance(value, str) else ""
    normalized = " ".join(label.casefold().replace("-", " ").replace("_", " ").split())
    if not label or len(value) > 200 or normalized in MISSING_LABELS:
        raise ValueError(f"An explicit reviewer-verified {key} is required")
    return label


def _restricted(evidence, spec, context):
    cells = {key: _count_ref(evidence, spec.get(key)) for key in ("primary", "restricted")}
    if _reference_key(cells["primary"]) == _reference_key(cells["restricted"]):
        raise ValueError("The primary and restricted analyses must refer to different source count tokens")
    bound = restricted_analysis_accounting({
        "relationship": "RESTRICTION", "source_version": evidence["source"]["version"],
        "same_source_version_verified": True, "same_participant_count_basis_verified": True,
        "restriction_locator": context["locator"],
        "primary_locator": cells["primary"]["locator"], "restricted_locator": cells["restricted"]["locator"],
        "primary_participants": cells["primary"]["participants"],
        "restricted_participants": cells["restricted"]["participants"],
    })
    result = {"cells": cells, **bound, "comparison_status": bound["status"], "accounting_status": "HOLD"}
    if bound["status"] != "NO_FLAG":
        return result
    result.update(status="HOLD", reason="A count within its parent bound does not verify exclusion accounting")
    exclusions = spec.get("exclusion_counts")
    if (not isinstance(exclusions, list) or not 1 <= len(exclusions) <= 500
            or spec.get("exclusions_disjoint_verified") is not True
            or spec.get("exclusions_exhaustive_verified") is not True):
        return result
    bindings = [_count_ref(evidence, ref) for ref in exclusions]
    used = {_reference_key(cell) for cell in cells.values()}
    for cell in bindings:
        if _reference_key(cell) in used:
            raise ValueError("Exclusions must use distinct source count tokens, separate from parent and restricted counts")
        used.add(_reference_key(cell))
    expected = cells["primary"]["participants"] - sum(cell["participants"] for cell in bindings)
    if expected < 0:
        raise ValueError("Exclusion counts exceed the verified parent; review the ledger")
    difference = cells["restricted"]["participants"] - expected
    result.update(status="REVIEW_CANDIDATE" if difference else "NO_FLAG", accounting_status="CHECKED",
                  reason="Reported restricted count differs from parent minus exclusions" if difference
                  else "Reported restricted count matches the reviewer-mapped disjoint, exhaustive exclusion ledger",
                  accounting={"exclusions": bindings, "expected_restricted": expected, "difference": difference,
                              "formula": "parent - sum(exclusions); difference = reported - expected"})
    return result


def _unique_arms(evidence, spec):
    reported = _count_ref(evidence, spec.get("reported"))
    arms = spec.get("arms")
    if not isinstance(arms, list) or not 2 <= len(arms) <= 500:
        raise ValueError("Supply a complete mapping of 2 to 500 source-backed trial arm entries")
    unique = {}
    locations = {_reference_key(reported): None}
    bindings = []
    for arm in arms:
        if not isinstance(arm, dict):
            raise ValueError("An arm entry must identify its trial, cohort, arm and source cell")
        identity = {key: _label(arm, key) for key in ("trial", "cohort", "arm")}
        key = tuple(value.casefold() for value in identity.values())
        cell = _count_ref(evidence, arm.get("count"))
        location = _reference_key(cell)
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
            result["replacement"] = _count_ref(entry, spec["replacement"])
        if "previous" in spec:
            result["previous_as_reproduced_in_notice"] = _count_ref(entry, spec["previous"])
        return result
    except ValueError as exc:
        return {"status": "HOLD", "reason": str(exc)}


def _revision_sweep(evidence, spec, replacement):
    refs, unchecked = spec.get("current_occurrences"), spec.get("unchecked_locations")
    if (not isinstance(refs, list) or not 1 <= len(refs) <= 500 or not isinstance(unchecked, list)
            or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in unchecked)
            or len(unchecked) > 500):
        return {"status": "HOLD", "reason": "Map current occurrences and list unchecked locations explicitly",
                "coverage": "REVIEWER_SELECTED_ONLY"}
    occurrences = []
    used = set()
    for ref in refs:
        try:
            cell = _count_ref(evidence, ref)
            if _reference_key(cell) in used:
                raise ValueError("A correction sweep must map distinct source count tokens")
            used.add(_reference_key(cell))
            occurrences.append({**cell, "status": "MATCH" if cell["participants"] == replacement["participants"] else "DIFFERS"})
        except ValueError as exc:
            occurrences.append({"status": "HOLD", "reason": str(exc)})
    status = ("REVIEW_CANDIDATE" if any(c["status"] == "DIFFERS" for c in occurrences)
              else "HOLD" if unchecked or any(c["status"] == "HOLD" for c in occurrences) else "MATCH")
    return {"status": status, "occurrences": occurrences, "unchecked_locations": unchecked,
            "coverage": "REVIEWER_SELECTED_ONLY", "replacement": replacement}


def participant_count_finding(claim_id, spec, evidence):
    finding = {"claim_id": claim_id, "count_validity": "NOT_INDEPENDENTLY_VERIFIED"}
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
            prior = (_count_ref(evidence, spec["original"]) if from_article
                     else correction["previous_as_reproduced_in_notice"])
            replacement = correction["replacement"]
            if from_notice and _reference_key(prior) == _reference_key(replacement):
                raise ValueError("The original and replacement must use distinct source count tokens")
            if from_article:
                finding["original"] = prior
            if prior["participants"] == replacement["participants"]:
                finding.update(status="MATCH", reason="The two selected participant counts agree")
            else:
                finding.update(status="PUBLISHED_CORRECTION",
                               reason="The two reviewer-mapped counts differ across the original and replacement cells")
            finding["revision_sweep"] = _revision_sweep(evidence, spec, replacement)
            return finding
        finding["context"] = _context(evidence, spec)
        if kind == "RESTRICTED":
            finding.update(_restricted(evidence, spec, finding["context"]))
        elif kind == "UNIQUE_ARMS":
            finding.update(_unique_arms(evidence, spec))
        else:
            raise ValueError("Unknown participant count check kind")
        if finding.get("comparison_status", finding["status"]) == "NO_FLAG" and correction:
            reason = ("Requested correction evidence is unresolved" if correction["status"] == "HOLD"
                      else "A source-bound correction requires review of the original-only comparison")
            finding.update(status="HOLD", comparison_status="NO_FLAG", reason=reason)
    except ValueError as exc:
        finding.update(status="HOLD", reason=str(exc))
    return finding
