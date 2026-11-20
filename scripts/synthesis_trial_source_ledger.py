"""Source-to-cell crosswalk for Synthesis (experimental, offline, no model fitting).

Each reviewer-supplied meta-analysis row is linked to archived published and
primary-source quotations with checked file hashes and exact token offsets.
The script reuses synthesis_source_trial_view and v1.3 NMA preflight. It does
NOT authenticate trial identities, interpret table labels, or declare errors.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

MAX_ROWS = 200
SUPPORTED_TIERS = {"T1", "T2", "T3"}  # T4 = another synthesis; not a primary source


def _viewer():
    spec = importlib.util.spec_from_file_location(
        "synthesis_source_trial_view", Path(__file__).with_name("synthesis_source_trial_view.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("source evidence viewer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exact_binding(quote: str, binding: dict, expected) -> bool:
    """Check a reviewer-selected occurrence, never infer its scientific meaning."""
    if not isinstance(quote, str) or not isinstance(binding, dict):
        return False
    text, offset = binding.get("text"), binding.get("offset")
    if type(offset) is not int or offset < 0 or not isinstance(text, str) or not text:
        return False
    if quote[offset:offset + len(text)] != text:
        return False
    if type(expected) is int:
        if expected < 0 or text not in {str(expected), format(expected, ",")}:
            return False
        # Avoid binding a decimal, signed number, large integer or neighbouring token.
        before = quote[offset - 1] if offset else ""
        after = quote[offset + len(text):offset + len(text) + 1]
        return before not in "0123456789.,−-" and after not in "0123456789.,"
    if isinstance(expected, str):
        if text != expected:
            return False
        before = quote[offset - 1] if offset else ""
        after = quote[offset + len(text):offset + len(text) + 1]
        return not (before.isalnum() or after.isalnum())
    return False


def _bindings_for(case: dict):
    comparison = case.get("comparison", {})
    kind = comparison.get("kind") if isinstance(comparison, dict) else None
    if kind in {"integer_count", "variance_label"}:
        return [
            ("published_value", "published", comparison.get("published")),
            ("primary_value", "primary", comparison.get("primary")),
        ]
    if kind == "count_percentage":
        return [
            ("published_count", "published", comparison.get("published_count")),
            ("published_denominator", "published", comparison.get("published_denominator")),
            ("published_percentage", "published", comparison.get("published_percentage")),
            ("primary_count", "primary", comparison.get("primary_count")),
            ("primary_denominator", "primary", comparison.get("primary_denominator")),
        ]
    return []


def _hold(row_id: str, reason: str, earlier: dict | None = None) -> dict:
    out = dict(earlier or {})
    out.update(case_id=row_id, status="HOLD", reason=reason,
               calculation=out.get("calculation", "NOT_RUN"))
    out.setdefault("evidence", {})
    return out


def review_ledger(packet: dict, root: Path) -> dict:
    """Review scoped statements only; all cohort identities are human-attested."""
    if not isinstance(packet, dict) or packet.get("ledger_version") != "0.1":
        raise ValueError("ledger_version must be 0.1")
    synthesis_id = packet.get("synthesis_id")
    rows = packet.get("rows")
    if not isinstance(synthesis_id, str) or not synthesis_id.strip():
        raise ValueError("synthesis_id required")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("rows must be a nonempty bounded list")
    viewer = _viewer()
    outcomes = []
    duplicate_rows = []
    seen = set()
    for i, row in enumerate(rows):
        row_id = row.get("row_id") if isinstance(row, dict) else None
        if not isinstance(row_id, str) or not row_id.strip():
            row_id = f"UNIDENTIFIED-{i+1}"
        if row_id in seen:
            outcomes.append(_hold(row_id, "duplicate row_id; row identities must be unique"))
            continue
        seen.add(row_id)
        if not isinstance(row, dict):
            outcomes.append(_hold(row_id, "row must be a mapping"))
            continue
        case = row.get("case")
        if not isinstance(case, dict):
            outcomes.append(_hold(row_id, "missing source-viewer case"))
            continue
        case = {**case, "case_id": row_id}
        checked = viewer.evaluate_case(case, root)
        # Even when viewer has enough material to screen, trial *source* identity
        # and exact field occurrences must be explicitly supplied and bound.
        if not all(k in checked.get("evidence", {}) for k in ("published", "primary")):
            outcomes.append(_hold(row_id, "both archived source excerpts required", checked))
            continue
        tier = row.get("source_tier")
        if tier not in SUPPORTED_TIERS:
            outcomes.append(_hold(row_id, "primary evidence tier T1/T2/T3 required; prior syntheses T4 are unverified", checked))
            continue
        trial_key = row.get("trial_key")
        if not isinstance(trial_key, str) or not trial_key.strip():
            outcomes.append(_hold(row_id, "typed trial key missing", checked))
            continue
        if row.get("trial_key_type") not in {"REGISTRY", "DOI", "OTHER_SOURCE_ID"}:
            outcomes.append(_hold(row_id, "trial key type unknown", checked))
            continue
        if row.get("trial_key_type") == "REGISTRY":
            # Not a registry lookup or an existence check; merely NCT syntax.
            if not re.fullmatch(r"NCT[0-9]{8}", trial_key):
                outcomes.append(_hold(row_id, "registry key syntax unrecognised; use a properly sourced OTHER_SOURCE_ID if applicable", checked))
                continue
        if row.get("trial_key_source_checked") is not True:
            outcomes.append(_hold(row_id, "trial key source identity not reviewer-checked", checked))
            continue
        primary_quote = checked["evidence"]["primary"]["quote"]
        if not _exact_binding(primary_quote, row.get("trial_key_binding"), trial_key):
            outcomes.append(_hold(row_id, "trial identifier not bound to exact primary quotation offset", checked))
            continue
        bindings = row.get("bindings")
        required = _bindings_for(case)
        if not required or not isinstance(bindings, dict):
            outcomes.append(_hold(row_id, "supported source-cell bindings missing", checked))
            continue
        bad = [
            name for name, side, value in required
            if not _exact_binding(checked["evidence"][side]["quote"], bindings.get(name), value)
        ]
        if bad:
            outcomes.append(_hold(row_id, "unbound or ambiguous source-cell offsets: " + ", ".join(bad), checked))
            continue
        identity = case.get("contexts", {})
        primary_identity = identity.get("primary", {}) if isinstance(identity, dict) else {}
        if trial_key != row.get("trial_key") or not isinstance(primary_identity, dict):
            outcomes.append(_hold(row_id, "primary identity unavailable", checked))
            continue
        analysis = row.get("analysis")
        if not isinstance(analysis, dict):
            outcomes.append(_hold(row_id, "analysis inclusion and dependence record missing", checked))
            continue
        if not all(isinstance(analysis.get(k), str) and analysis[k].strip() for k in
                   ("report_id", "contrast_id", "dependence_handling")):
            outcomes.append(_hold(row_id, "analysis identity or dependence method incomplete", checked))
            continue
        if analysis.get("included_as_independent_effect") not in (True, False) or \
                analysis.get("same_cohort_source_verified") not in (True, False):
            outcomes.append(_hold(row_id, "analysis inclusion/cohort overlap attestations missing", checked))
            continue
        if analysis["dependence_handling"] not in (
            "INDEPENDENT_UNCORRELATED", "CORRELATION_ACCOUNTED_FOR", "UNKNOWN"
        ):
            outcomes.append(_hold(row_id, "unrecognised dependence handling", checked))
            continue
        duplicate_rows.append({
            "synthesis_id": synthesis_id,
            "trial_family_id": primary_identity.get("trial_family_id"),
            "cohort_id": primary_identity.get("cohort_id"),
            "endpoint": primary_identity.get("endpoint"),
            "time_window": primary_identity.get("time_window"),
            "contrast_id": analysis["contrast_id"],
            "source_version": checked["evidence"]["primary"]["version"],
            "source_locator": checked["evidence"]["primary"]["locator"],
            "report_id": analysis["report_id"],
            "dependence_handling": analysis["dependence_handling"],
            "same_cohort_source_verified": analysis["same_cohort_source_verified"],
            "included_as_independent_effect": analysis["included_as_independent_effect"],
        })
        checked["trial_key"] = trial_key
        checked["source_tier"] = tier
        checked["identity_attestation"] = "REVIEWER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"
        outcomes.append(checked)
    duplicate = (
        viewer.duplicate_preflight(duplicate_rows) if duplicate_rows
        else {"status": "HOLD", "reason": "no fully source-bound rows eligible for overlap preflight"}
    )
    counts = {state: sum(1 for row in outcomes if row["status"] == state)
              for state in ("HOLD", "NOT_COMPARABLE", "REVIEW_CANDIDATE", "NO_SCOPED_DIFFERENCE")}
    return {
        "scope": "supervised source-to-cell ledger; no model reproduction or accuracy claim",
        "synthesis_id": synthesis_id,
        "rows": outcomes,
        "counts": counts,
        "duplicate_preflight": duplicate,
        "certified": False,
    }


def to_viewer_report(report: dict) -> dict:
    """Render through existing safe HTML view, without new presentation logic."""
    return {"cases": report["rows"], "duplicate_preflight": report["duplicate_preflight"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--html-out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        report = review_ledger(packet, args.source_root)
        viewer = _viewer()
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(viewer.render_html(to_viewer_report(report)), encoding="utf-8")
        # Persist source locators and row statuses, not raw private quotes, in JSON.
        public_rows = [{k: row.get(k) for k in ("case_id", "status", "reason", "trial_key",
                                                "source_tier", "calculation")}
                       for row in report["rows"]]
        args.json_out.write_text(json.dumps({
            "synthesis_id": report["synthesis_id"], "rows": public_rows,
            "counts": report["counts"], "duplicate_preflight": report["duplicate_preflight"],
            "certified": False,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, "Ledger input/output refused: " + str(exc) + "\n")
    print(json.dumps({"rows": len(report["rows"]), "counts": report["counts"],
                      "duplicate_preflight": report["duplicate_preflight"].get("status"),
                      "certified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
