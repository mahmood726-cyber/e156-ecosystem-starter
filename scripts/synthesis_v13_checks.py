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

# Always compare the minimum target question before cross-document numeric flags.
# Caller-chosen narrow fields are additive, never a bypass of clinical identity.
CROSS_DOCUMENT_CORE_FIELDS = ("population", "endpoint", "time_window",
                              "effect_measure", "estimand")
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


def ci_order(estimate: Any, lower: Any, upper: Any, interval_type: str, *,
             ci_method: str | None = None,
             estimator_signature_matched: bool = False,
             source_input_precision: str | None = None) -> dict:
    """Geometric interval check only; never a confirmed scientific error.

    An out-of-range estimate is reviewable only when independent source
    inspection confirms an exact, same-estimand Wald-linear interval.
    Bootstrap/adjusted/unidentified intervals and rounded printed inputs
    must not be treated as arithmetic contradictions.
    """
    if interval_type not in {"TWO_SIDED", "ONE_SIDED_LOWER", "ONE_SIDED_UPPER"}:
        return result("NOT_COMPARABLE", "interval definition not established")
    try:
        e, lo, hi = finite(estimate), finite(lower), finite(upper)
    except ValueError as exc:
        return result("INVALID", str(exc))
    if lo > hi:
        return result("REVIEW", "confidence interval bounds reversed")
    if interval_type == "TWO_SIDED" and not lo <= e <= hi:
        if ci_method != "WALD_LINEAR" or estimator_signature_matched is not True:
            return result("NOT_COMPARABLE",
                          "CI method or point/interval estimator identity unverified")
        if source_input_precision != "EXACT":
            return result("NOT_COMPARABLE", "published estimate or CI bounds may be rounded")
        return result("REVIEW",
                      "verified same-estimand Wald-linear estimate outside CI; check source")
    return result("CONSISTENT", "interval ordering compatible")


def crude_or(a: Any, n1: Any, c: Any, n0: Any, reported: Any, *,
             raw_estimator: bool, population_match: bool, endpoint_match: bool,
             time_match: bool, tolerance: Any = None,
             source_effect_measure: str | None = None,
             effect_measure_verified: bool = False,
             source_counts_verified: bool = False,
             reported_or_text: str | None = None,
             reported_rounding_rule: str | None = None,
             reported_precision_verified: bool = False) -> dict:
    """Unadjusted, uncorrected 2x2 OR only, with source-attested print precision.

    No numerical disagreement is inferred from an RR/adjusted estimate, from a
    fixed arbitrary tolerance or from ambiguous printed rounding. Exact data
    provenance is external; a REVIEW is never a verdict about the article.
    """
    if not all(x is True for x in
               (raw_estimator, population_match, endpoint_match, time_match)):
        return result("NOT_COMPARABLE", "exact unadjusted 2x2 analysis identity not established")
    if source_effect_measure != "UNADJUSTED_ODDS_RATIO" or effect_measure_verified is not True:
        return result("NOT_COMPARABLE", "published effect measure not verified as crude odds ratio")
    if source_counts_verified is not True:
        return result("NOT_COMPARABLE", "source 2x2 event counts not independently checked")
    if tolerance is not None:
        return result("NOT_COMPARABLE", "fixed numeric tolerance cannot replace published precision")
    if (reported_precision_verified is not True
            or reported_rounding_rule != "NEAREST_DECIMAL"
            or not isinstance(reported_or_text, str)):
        return result("NOT_COMPARABLE", "published OR precision/rounding not verified")
    literal = reported_or_text.strip()
    if not re.fullmatch(r"(?:\d+\.\d+|\.\d+)", literal):
        return result("NOT_COMPARABLE", "published OR literal or OCR is ambiguous")
    try:
        a, n1, c, n0 = map(nonnegative_count, (a, n1, c, n0))
        claimed = finite(reported)
        if not n1 or not n0 or a > n1 or c > n0 or claimed < 0:
            raise ValueError("invalid 2x2 table or reported ratio")
    except ValueError as exc:
        return result("INVALID", str(exc))
    from decimal import Decimal
    printed = Decimal(literal)
    if printed != Decimal(str(claimed)):
        return result("INVALID", "source OR text and numeric OR disagree")
    if min(a, n1 - a, c, n0 - c) == 0:
        return result("NOT_COMPARABLE", "zero cell requires declared correction/exact method")
    numerator, denominator = a * (n0 - c), (n1 - a) * c
    places = len(literal.split(".")[1])
    half_step = Decimal(5).scaleb(-places - 1)
    low, high = max(Decimal(0), printed - half_step), printed + half_step
    # Include exact halfway ties conservatively: journal ties-to-even vs
    # ties-away conventions may differ. Decimal*integer avoids float tolerance.
    overlaps = low * denominator <= numerator <= high * denominator
    expected = numerator / denominator
    return result("CONSISTENT" if overlaps else "REVIEW",
                  "crude OR compatible with verified displayed rounding"
                  if overlaps else "crude OR incompatible with printed precision; check source",
                  expected=expected, reported=claimed, difference=abs(expected - claimed),
                  printed_rounding_interval=(float(low), float(high)))


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
    """Compare numbers only after matching a minimum clinical estimand identity.

    A caller listing only endpoint/test fields cannot override population,
    timepoint, effect measure or estimand checks. Explicit, source-attested
    numeric unit and representation must also match; no automatic conversion.
    These attestations are not independently verified by this software.
    Provenance and current-source identity still require external inspection;
    REVIEW is never a paper verdict.
    """
    if not isinstance(required_fields, (list, tuple)) or not required_fields or any(
            field not in ESTIMATOR_FIELDS for field in required_fields):
        return result("INVALID", "unknown or empty requested identity fields")
    fields = tuple(dict.fromkeys((*CROSS_DOCUMENT_CORE_FIELDS, *required_fields)))
    match = compatible(left_sig, right_sig, fields)
    if match["status"] != "MATCHED":
        return match
    # Source-matched estimands can still contain physically equivalent numbers
    # in different units (mg vs micrograms) or different representations
    # (raw ratio vs log ratio, proportion vs percentage). No implicit
    # conversions or comparison without source-verified value identity.
    if (left_sig.get("value_identity_verified") is not True
            or right_sig.get("value_identity_verified") is not True):
        return result("NOT_COMPARABLE", "source unit/representation identity unverified")
    value_fields = ("value_unit", "value_representation")
    unknown = [name for name in value_fields
               if any(not isinstance(sig.get(name), str)
                      or not sig.get(name).strip()
                      or sig.get(name).strip().upper() == "UNKNOWN"
                      for sig in (left_sig, right_sig))]
    if unknown:
        return result("NOT_COMPARABLE", "numeric value identity incomplete", fields=unknown)
    differing = [name for name in value_fields
                 if left_sig[name] != right_sig[name]]
    if differing:
        return result("NOT_COMPARABLE", "different numeric units/representations; verify conversion",
                      fields=differing)
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
    # Source support is version-scoped: a valid contradiction in an earlier
    # edition must not be flagged against a subsequently corrected article.
    correction = record.get("current_correction_status")
    if correction == "RESOLVED_IN_PUBLISHED_VERSION":
        if (record.get("correction_source_verified") is True
                and isinstance(record.get("correction_locator"), str)
                and record["correction_locator"].strip()):
            return result("RECONCILED", "verified published correction resolves prior claim")
        return result("HOLD", "published correction lacks verified exact locator")
    if record.get("current_claim_verified") is not True:
        return result("HOLD", "exact disputed claim not verified in current published version")
    if correction not in {"NO_RELEVANT_CORRECTION", "CORRECTION_REVIEWED_CLAIM_PERSISTS"}:
        return result("HOLD", "current correction/claim status not independently established")
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
def unchanged_control_false_alerts(papers: Sequence[Mapping], claims: Sequence[Mapping]) -> dict:
    """Bookkeep false flags on explicitly clean, unchanged control papers.

    A declared unchanged paper is NOT automatically a clean paper: an unmodified
    publication may contain genuine errors. This function trusts supplied labels
    and must not be described as independent verification or held-out accuracy.
    Incomplete inventories and unresolved truth hold papers out of the rate.
    """
    if not isinstance(papers, (list, tuple)) or not isinstance(claims, (list, tuple)):
        raise ValueError("paper and claim manifests must be sequences")
    paper_map = {}
    for p in papers:
        if not isinstance(p, Mapping):
            raise ValueError("paper manifest entries must be mappings")
        pid = p.get("paper_id")
        if not isinstance(pid, str) or not pid or pid in paper_map:
            raise ValueError("paper IDs must be nonempty and unique")
        if p.get("control_status") not in {"CLEAN_UNCHANGED", "OTHER", "UNKNOWN"}:
            raise ValueError("unknown control status")
        paper_map[pid] = p
    by_paper: dict[str, dict[str, Mapping]] = defaultdict(dict)
    seen = set()
    for c in claims:
        if not isinstance(c, Mapping):
            raise ValueError("claim entries must be mappings")
        pid, cid = c.get("paper_id"), c.get("claim_id")
        if pid not in paper_map or not isinstance(cid, str) or not cid or cid in seen:
            raise ValueError("orphaned, duplicate or empty claim ID")
        seen.add(cid)
        if c.get("prediction") not in {"FLAG", "NO_FLAG", "HOLD"}:
            raise ValueError("unknown prediction")
        if c.get("reference") not in {"ERROR", "NO_ERROR", "UNDETERMINED"}:
            raise ValueError("unknown reference")
        by_paper[pid][cid] = c
    declared = eligible = held = alert_papers = false_flags = evaluated_claims = 0
    hold_reasons = defaultdict(int)
    for pid, p in paper_map.items():
        if p["control_status"] != "CLEAN_UNCHANGED":
            continue
        declared += 1
        ids = p.get("claim_ids")
        if (p.get("inventory_complete") is not True or not isinstance(ids, (list, tuple))
                or not ids or any(not isinstance(c, str) or not c for c in ids)
                or len(set(ids)) != len(ids) or set(ids) != set(by_paper[pid])):
            held += 1
            hold_reasons["claim_inventory_missing_or_incomplete"] += 1
            continue
        entries = list(by_paper[pid].values())
        if any(c["reference"] != "NO_ERROR" for c in entries):
            held += 1
            hold_reasons["clean_reference_unresolved_or_contradicted"] += 1
            continue
        eligible += 1
        evaluated_claims += len(entries)
        n_false = sum(c["prediction"] == "FLAG" for c in entries)
        false_flags += n_false
        alert_papers += bool(n_false)
    rate = lambda n, d: 100 * n / d if d else None
    return {
        "declared_clean_unchanged_papers": declared,
        "eligible_complete_clean_papers": eligible,
        "held_clean_papers": held,
        "hold_reasons": dict(sorted(hold_reasons.items())),
        "eligible_clean_claims": evaluated_claims,
        "false_alert_flags": false_flags,
        "clean_papers_with_at_least_one_false_alert": alert_papers,
        "false_alert_papers_per_100_clean_papers": rate(alert_papers, eligible),
        "false_alert_flags_per_100_clean_papers": rate(false_flags, eligible),
        "false_alert_flags_per_100_clean_claims": rate(false_flags, evaluated_claims),
        "warning": ("Caller-labelled bookkeeping only; CLEAN_UNCHANGED, complete inventory, "
                    "and NO_ERROR labels require independent verification for a real held-out "
                    "performance claim. An unchanged publication can contain real errors. "
                    "Held/unknown papers are not negative controls."),
    }
