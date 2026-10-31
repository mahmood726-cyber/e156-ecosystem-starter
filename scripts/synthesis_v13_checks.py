"""Synthesis v1.3 experimental, deterministic candidate gates.

This module does not read research papers, verify medical conclusions, send
messages, or certify scientific errors. It extends rather than replaces the
separate v1.1 preflight module; all outputs require source-based review.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re
from typing import Mapping, Sequence, Any

ESTIMATOR_FIELDS = (
    "population", "endpoint", "time_window", "effect_measure", "estimand",
    "model", "adjustment", "multiplicity", "missingness", "censoring",
    "variance_method", "test_statistic_identity",
)
SEVERITIES = {"S1", "S2", "S3", "S4", "S5"}


def result(status: str, reason: str, **extra: Any) -> dict:
    return {"status": status, "reason": reason, **extra}


def finite(value: Any) -> float:
    if type(value) not in (float, int):
        raise ValueError("not a numeric value")
    try:
        n = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("numeric input out of range") from exc
    if not math.isfinite(n):
        raise ValueError("nonfinite input")
    return n


def nonnegative_count(value: Any) -> int:
    n = finite(value)
    if n < 0 or not n.is_integer():
        raise ValueError("counts must be nonnegative integers")
    return int(n)


def compatible(left: Mapping, right: Mapping, fields: Sequence[str] = ESTIMATOR_FIELDS) -> dict:
    """Unknown or differing analysis definitions cannot support a numerical allegation."""
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return result("INVALID", "signatures must be mappings")
    if not fields or any(f not in ESTIMATOR_FIELDS for f in fields):
        return result("INVALID", "unknown required estimator field")
    unknown = [k for k in fields if left.get(k) in (None, "", "UNKNOWN")
               or right.get(k) in (None, "", "UNKNOWN")]
    if unknown:
        return result("NOT_COMPARABLE", "estimator signature incomplete", fields=unknown)
    mismatch = [k for k in fields if left[k] != right[k]]
    if mismatch:
        return result("NOT_COMPARABLE", "different estimators, endpoints or populations", fields=mismatch)
    return result("MATCHED", "required estimator fields match")


def ci_order(estimate: Any, lower: Any, upper: Any, interval_type: str) -> dict:
    if interval_type not in {"TWO_SIDED", "ONE_SIDED_LOWER", "ONE_SIDED_UPPER"}:
        return result("NOT_COMPARABLE", "interval definition not established")
    try:
        e, lo, hi = finite(estimate), finite(lower), finite(upper)
    except ValueError as exc:
        return result("INVALID", str(exc))
    if lo > hi:
        return result("REVIEW", "confidence interval bounds reversed")
    if interval_type == "TWO_SIDED" and not lo <= e <= hi:
        return result("REVIEW", "estimate outside reported two-sided interval")
    return result("CONSISTENT", "interval ordering compatible")


def crude_or(a: Any, n1: Any, c: Any, n0: Any, reported: Any, *,
             raw_estimator: bool, population_match: bool, endpoint_match: bool,
             time_match: bool, tolerance: Any = 0.02) -> dict:
    if not all(x is True for x in (raw_estimator, population_match, endpoint_match, time_match)):
        return result("NOT_COMPARABLE", "exact unadjusted 2x2 analysis identity not established")
    try:
        a, n1, c, n0 = map(nonnegative_count, (a, n1, c, n0))
        claimed, tol = finite(reported), finite(tolerance)
        if not n1 or not n0 or a > n1 or c > n0 or claimed < 0 or tol < 0:
            raise ValueError("invalid 2x2 table, reported ratio or tolerance")
    except ValueError as exc:
        return result("INVALID", str(exc))
    if min(a, n1-a, c, n0-c) == 0:
        return result("NOT_COMPARABLE", "zero cell requires declared correction/exact method")
    expected = a * (n0-c) / ((n1-a)*c)
    delta = abs(expected-claimed)
    return result("CONSISTENT" if delta <= tol else "REVIEW",
                  "crude OR within tolerance" if delta <= tol else "arithmetic discrepancy requiring source check",
                  expected=expected, reported=claimed, difference=delta)



_P_LITERAL_RE = re.compile(
    r"^\s*(?:[pP]\s*)?(<=|>=|<|>|=|≤|≥)?\s*((?:\d+(?:\.\d+)?|\.\d+))\s*$"
)


def _printed_p_comparison(expected: float, reported: float, literal: str | None,
                          source_input_precision: str | None,
                          expected_p_bounds: Sequence[float] | None) -> dict:
    """Conservative printed-P compatibility; never certifies a paper error.

    Exact inputs must be source-verified. For rounded test statistics, externally
    verified P bounds must reflect *all* compatible source rounding values.
    """
    if not isinstance(literal, str):
        return result("NOT_COMPARABLE", "verbatim published P notation unavailable")
    match = _P_LITERAL_RE.fullmatch(literal)
    if not match:
        return result("NOT_COMPARABLE", "P notation/OCR not reliably parsed")
    comparator, value_text = match.groups()
    comparator = comparator or "="
    value = float(value_text)
    if not 0 <= value <= 1:
        return result("INVALID", "reported P outside [0,1]")
    if abs(value - reported) > 1e-12:
        return result("INVALID", "source P text and numeric supplied P disagree")
    if source_input_precision == "EXACT":
        lo = hi = expected
    elif source_input_precision == "P_BOUNDS_VERIFIED":
        if not isinstance(expected_p_bounds, (tuple, list)) or len(expected_p_bounds) != 2:
            return result("NOT_COMPARABLE", "rounded source-statistic P bounds unverified")
        try:
            lo, hi = map(finite, expected_p_bounds)
        except ValueError as exc:
            return result("INVALID", str(exc))
        if not 0 <= lo <= expected <= hi <= 1:
            return result("INVALID", "P bounds must contain recomputation and lie in [0,1]")
    else:
        return result("NOT_COMPARABLE", "source statistic precision not established")

    if comparator == "=":
        if "." not in value_text:
            return result("NOT_COMPARABLE", "equality has no published decimal precision")
        half = 0.5 * 10 ** (-len(value_text.split(".")[1]))
        low = max(0.0, value - half)
        high = min(1.0, value + half)
        overlap = hi >= low and (lo < high or high == 1.0 and lo <= high)
    elif comparator in ("<", "<=", "≤"):
        overlap = lo < value if comparator == "<" else lo <= value
    else:
        overlap = hi > value if comparator == ">" else hi >= value

    return result("CONSISTENT" if overlap else "REVIEW",
                  "P notation compatible with verified reporting precision"
                  if overlap else "P notation outside verified precision range; check sources",
                  reported_literal=literal, recomputed_p_range=(lo, hi))


def p_from_normal_z(estimate: Any, se: Any, reported: Any, *,
                    test_name: str, multiplicity: str, null_value: Any = None,
                    alternative: str | None = None, estimate_scale: str | None = None,
                    se_scale: str | None = None, test_identity_verified: bool = False,
                    reported_p_text: str | None = None,
                    source_input_precision: str | None = None,
                    expected_p_bounds: Sequence[float] | None = None) -> dict:
    """Compare an identified normal-z P with its exact *published notation*.

    No P comparison is attempted without source-verbatim notation and verified
    exact inputs or a source-derived interval covering printed-statistic rounding.
    """
    if test_name != "NORMAL_Z" or multiplicity != "NONE":
        return result("NOT_COMPARABLE", "adjusted, t-based or alternative P-value method")
    if test_identity_verified is not True:
        return result("NOT_COMPARABLE", "published test-statistic identity unverified")
    if null_value is None or alternative not in {"TWO_SIDED", "GREATER", "LESS"}:
        return result("NOT_COMPARABLE", "null hypothesis or test direction unknown")
    if estimate_scale not in {"LINEAR", "LOG_RATIO"} or se_scale != estimate_scale:
        return result("NOT_COMPARABLE", "estimate and SE scales not established as identical")
    try:
        est, err, p, null = map(finite, (estimate, se, reported, null_value))
        if err <= 0 or not 0 <= p <= 1:
            raise ValueError("invalid SE or P")
    except ValueError as exc:
        return result("INVALID", str(exc))
    z = (est - null) / err
    if alternative == "TWO_SIDED":
        expected = math.erfc(abs(z) / math.sqrt(2))
    elif alternative == "GREATER":
        expected = 0.5 * math.erfc(z / math.sqrt(2))
    else:
        expected = 0.5 * math.erfc(-z / math.sqrt(2))
    check = _printed_p_comparison(expected, p, reported_p_text,
                                  source_input_precision, expected_p_bounds)
    return {**check, "expected": expected, "reported": p, "null_value": null,
            "alternative": alternative, "scale": estimate_scale}


def statistic_identity(reported_source: str, expected_source: str) -> dict:
    """TOPCHILD-type error: Q-test P mistakenly attached to pooled effect."""
    if not reported_source or not expected_source or "UNKNOWN" in {reported_source, expected_source}:
        return result("NOT_COMPARABLE", "P-value source statistic unknown")
    return result("CONSISTENT" if reported_source == expected_source else "REVIEW",
                  "statistic identity matches" if reported_source == expected_source else "P value belongs to different test")


def factor_shift(original: Any, observed: Any, *, verified_r_factor_conversion: bool) -> dict:
    if verified_r_factor_conversion is not True:
        return result("NOT_COMPARABLE", "paper-time code conversion unverified")
    if not isinstance(original, list) or not isinstance(observed, list) or len(original) != len(observed) or not original:
        return result("INVALID", "nonempty equal-length category vectors required")
    if any(type(x) is not int for x in original+observed):
        return result("INVALID", "noninteger category labels")
    if set(original) != {0, 1}:
        return result("NOT_COMPARABLE", "not a binary 0/1 factor")
    if observed == [v+1 for v in original]:
        return result("REVIEW", "verified factor-to-integer shift; investigate affected results")
    return result("CONSISTENT" if observed == original else "REVIEW",
                  "no numeric shift" if observed == original else "unexpected recoding needs review")


def cross_document(left: Any, right: Any, left_sig: Mapping, right_sig: Mapping,
                   required_fields: Sequence[str], tolerance: Any = 0) -> dict:
    match = compatible(left_sig, right_sig, required_fields)
    if match["status"] != "MATCHED":
        return match
    try:
        x, y, tol = finite(left), finite(right), finite(tolerance)
        if tol < 0:
            raise ValueError("negative tolerance")
    except ValueError as exc:
        return result("INVALID", str(exc))
    return result("CONSISTENT" if abs(x-y) <= tol else "REVIEW",
                  "matched document values agree" if abs(x-y) <= tol else "matched source values disagree")


def version(status: str) -> dict:
    if status in {"PREPRINT_STALE", "MANUSCRIPT_STALE", "UNKNOWN"}:
        return result("HOLD", "verify final typeset article and corrections")
    if status in {"FINAL_CURRENT", "CORRECTED_LATEST"}:
        return result("CURRENT", "known publication edition")
    return result("INVALID", "unknown version state")


def gate(record: Mapping) -> dict:
    """At most a source-backed flag *candidate*, never a confirmed error."""
    if not isinstance(record, Mapping):
        return result("INVALID", "candidate must be a mapping")
    if record.get("severity") not in SEVERITIES or version(record.get("version", "UNKNOWN"))["status"] != "CURRENT":
        return result("HOLD", "severity or current publication version not established")
    if record.get("source_access") != "ACCESSIBLE" or not record.get("source_locator"):
        return result("HOLD", "source access or exact locator incomplete")
    if record.get("source_support") == "SUPPORTED" and record.get("alternative_result") == "SUPPORTED":
        return result("RECONCILED", "documented benign explanation")
    if record.get("source_support") != "CONTRADICTED":
        return result("HOLD", "source does not establish contradiction")
    if record.get("maturity") not in {"SOURCE_BACKED", "REPRODUCED", "INDEPENDENTLY_ADJUDICATED"}:
        return result("HOLD", "insufficient evidence maturity")
    if not record.get("alternative") or not record.get("alternative_locator") or record.get("alternative_result") != "REFUTED":
        return result("HOLD", "benign explanation not tested or remains plausible")
    if record.get("estimator_status") != "MATCHED" or not record.get("root_cause_id"):
        return result("HOLD", "analysis identity or root-cause record incomplete")
    return result("FLAG_CANDIDATE", "source-backed, refuted candidate; independent adjudication required")


def root_cause_summary(rows: Sequence[Mapping]) -> dict:
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        cid, rid = row.get("claim_id"), row.get("root_cause_id")
        if not isinstance(cid, str) or not cid:
            raise ValueError("each affected output needs a claim ID")
        if rid is not None:
            if not isinstance(rid, str) or not rid:
                raise ValueError("invalid root cause ID")
            groups[rid].add(cid)
    return {"root_causes": len(groups), "affected_outputs": sum(map(len, groups.values())),
            "groups": {k: sorted(v) for k, v in sorted(groups.items())}}


def outcome_counts(rows: Sequence[Mapping]) -> dict:
    """Synthetic bookkeeping only; caller-supplied references are not validated.

    Report conditional performance on non-abstained, labelled claims separately
    from automatic flag recall on *all* labelled errors, including abstentions.
    Preserve unknown references and distinguish their predictions. No score is a
    held-out estimate without independent, masked sampling and adjudication.
    """
    names = {("FLAG", "ERROR"): "TP", ("FLAG", "NO_ERROR"): "FP",
             ("NO_FLAG", "NO_ERROR"): "TN", ("NO_FLAG", "ERROR"): "FN"}
    counts = {k: 0 for k in (
        "TP", "FP", "TN", "FN", "HOLD", "UNKNOWN_REFERENCE",
        "HOLD_ERROR", "HOLD_NO_ERROR", "HOLD_UNDETERMINED",
        "FLAG_UNDETERMINED", "NO_FLAG_UNDETERMINED"
    )}
    seen: set[str] = set()
    for row in rows:
        cid, pred, truth = row.get("claim_id"), row.get("prediction"), row.get("reference")
        if not isinstance(cid, str) or not cid or cid in seen:
            raise ValueError("claim IDs must be unique and nonempty")
        seen.add(cid)
        if pred not in {"FLAG", "NO_FLAG", "HOLD"} or truth not in {"ERROR", "NO_ERROR", "UNDETERMINED"}:
            raise ValueError("unknown prediction or adjudication label")
        if pred == "HOLD":
            counts["HOLD"] += 1
            counts[{"ERROR": "HOLD_ERROR", "NO_ERROR": "HOLD_NO_ERROR",
                    "UNDETERMINED": "HOLD_UNDETERMINED"}[truth]] += 1
        elif truth == "UNDETERMINED":
            counts["UNKNOWN_REFERENCE"] += 1
            counts[pred + "_UNDETERMINED"] += 1
        else:
            counts[names[(pred, truth)]] += 1

    n_nonabstained_labelled = sum(counts[k] for k in ("TP", "FP", "TN", "FN"))
    n_labelled = n_nonabstained_labelled + counts["HOLD_ERROR"] + counts["HOLD_NO_ERROR"]
    n_known_error = counts["TP"] + counts["FN"] + counts["HOLD_ERROR"]
    n_unknown = counts["UNKNOWN_REFERENCE"] + counts["HOLD_UNDETERMINED"]
    ratio = lambda a, b: a / b if b else None
    conditional_recall = ratio(counts["TP"], counts["TP"] + counts["FN"])
    return {
        **counts,
        "all_claims": len(rows),
        "adjudicated_nonabstained": n_nonabstained_labelled,
        "reference_known_claims": n_labelled,
        "reference_undetermined_total": n_unknown,
        "known_error_claims": n_known_error,
        "known_no_error_claims": counts["FP"] + counts["TN"] + counts["HOLD_NO_ERROR"],
        "sensitivity": conditional_recall,  # legacy: excludes abstained known errors
        "conditional_sensitivity_nonabstained": conditional_recall,
        "flag_recall_including_abstentions": ratio(counts["TP"], n_known_error),
        "precision": ratio(counts["TP"], counts["TP"] + counts["FP"]),
        "specificity": ratio(counts["TN"], counts["TN"] + counts["FP"]),
        "false_alerts_per_100_adjudicated":
            100 * counts["FP"] / n_nonabstained_labelled if n_nonabstained_labelled else None,
        "false_alerts_per_100_reference_known":
            100 * counts["FP"] / n_labelled if n_labelled else None,
        "abstention_rate": ratio(counts["HOLD"], len(rows)),
        "nonabstention_coverage": ratio(len(rows) - counts["HOLD"], len(rows)),
        "reference_label_coverage": ratio(n_labelled, len(rows)),
        "warning": ("Bookkeeping only; labels supplied by caller. Legacy sensitivity and "
                    "false_alerts_per_100_adjudicated exclude holds. For parity use "
                    "flag_recall_including_abstentions and report reference coverage, "
                    "abstentions, paper-level unchanged controls and clustered intervals. "
                    "Independent masked adjudication and complete sampling required.")
    }
