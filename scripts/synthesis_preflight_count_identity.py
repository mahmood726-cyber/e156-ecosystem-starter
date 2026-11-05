"""Fail-closed, *synthetic-safe* preflight for same-result raw count comparisons.

This is an additive v1.3 intake helper: it does not modify frozen v1.1/v1.2
interfaces, access sources, fit a statistical model, or adjudicate errors.
Callers must independently authenticate all source records and permissions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# All twelve estimator fields are required even for a descriptive count. An
# explicit "not_applicable" is preferred to pretending an unknown is matched.
ESTIMATOR_FIELDS = (
    "population", "endpoint", "time_window", "effect_measure", "estimand",
    "model", "adjustment", "multiplicity", "missingness", "censoring",
    "variance_method", "test_statistic_identity",
)
RESULT_FIELDS = (
    "publication_id", "source_result_id", "data_version", "source_version",
    "count_basis", "denominator_basis",
) + ESTIMATOR_FIELDS
COUNT_BASES = frozenset({"unique_participants", "events", "trial_families", "visits"})
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def compare_raw_counts(left: Any, right: Any) -> dict[str, Any]:
    """Compare counts *only* for an explicitly matched result and source version.

    Return CONSISTENT, REVIEW (a candidate, never a confirmed error),
    NOT_COMPARABLE (verified different identity), or NOT_ENOUGH_INFO.
    A source digest is an identifier, not evidence that its content is correct.
    """
    base: dict[str, Any] = {
        "status": "NOT_ENOUGH_INFO", "disposition": "HOLD",
        "source_support": "NOT_ENOUGH_INFO", "maturity": "SCREENED",
        "human_adjudicated": False, "author_confirmed": False,
        "certified_error": False, "email_eligible": False,
    }
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return {**base, "reason": "both records must be mappings"}
    for side_name, record in (("left", left), ("right", right)):
        for key in RESULT_FIELDS + ("locator", "source_sha256"):
            value = record.get(key)
            if not isinstance(value, str) or not value.strip() or value.strip().lower() in {"unknown", "unverified", "not_enough_info"}:
                return {**base, "reason": f"{side_name}: missing/unverified {key}"}
        if SHA256.fullmatch(record["source_sha256"]) is None:
            return {**base, "reason": f"{side_name}: invalid source_sha256"}
        if record["count_basis"] not in COUNT_BASES:
            return {**base, "reason": f"{side_name}: unsupported count_basis"}
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return {**base, "reason": f"{side_name}: count must be a nonnegative exact integer"}
    differing = tuple(key for key in RESULT_FIELDS if left[key] != right[key])
    if differing:
        return {
            **base, "status": "NOT_COMPARABLE",
            "reason": "result identity/estimator/source version differs",
            "mismatched_fields": list(differing),
        }
    lhs, rhs = left["value"], right["value"]
    if lhs == rhs:
        return {
            **base, "status": "CONSISTENT", "disposition": "NO_FLAG",
            "source_support": "SUPPORTED", "maturity": "REPRODUCED",
            "reason": "exact matched-result integer counts agree", "left": lhs,
            "right": rhs, "difference": 0,
        }
    return {
        **base, "status": "REVIEW", "disposition": "HOLD",
        "source_support": "CONTRADICTED", "maturity": "REPRODUCED",
        "reason": "same-result counts differ; inspect source/denominator before alleging error",
        "left": lhs, "right": rhs, "difference": lhs - rhs,
    }
