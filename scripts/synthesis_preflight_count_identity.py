"""Fail-closed, *synthetic-safe* preflight for same-result raw count comparisons.

This is an additive v1.3 intake helper: it does not modify frozen v1.1/v1.2
interfaces, access sources, fit a statistical model, or adjudicate errors.
Callers must independently authenticate all source records and permissions.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

# analysis_cell_id is a mandatory arm/subgroup/stratum identifier (use
# "overall" when genuinely unstratified). Different arms can legitimately have
# different event counts despite sharing endpoint, time and source result IDs.
# All twelve estimator fields are required even for a descriptive count. An
# explicit "not_applicable" is preferred to pretending an unknown is matched.
ESTIMATOR_FIELDS = (
    "population", "endpoint", "time_window", "effect_measure", "estimand",
    "model", "adjustment", "multiplicity", "missingness", "censoring",
    "variance_method", "test_statistic_identity",
)
RESULT_FIELDS = (
    "publication_id", "source_result_id", "data_version", "source_version",
    "count_basis", "denominator_basis", "analysis_cell_id",
) + ESTIMATOR_FIELDS
COUNT_BASES = frozenset({"unique_participants", "events", "trial_families", "visits"})
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
# An unknown/irrelevant population, outcome or version is not a matched
# identity, even when both records use the same placeholder. Explicit
# not_applicable remains valid for optional statistical mechanics (e.g. model
# for a descriptive raw count), never for the core result identity.
CORE_IDENTITY_FIELDS = frozenset({
    "publication_id", "source_result_id", "data_version", "source_version",
    "denominator_basis", "analysis_cell_id", "population", "endpoint", "time_window",
    "effect_measure", "estimand", "locator",
})
# Compare *normalized* missing-value markers. Without this, two synthetic
# "not-reported" or "source_limited" result IDs can wrongly pass identity
# matching and produce a misleading arithmetic REVIEW candidate.
UNKNOWN_LITERALS = frozenset({
    "unknown", "unverified", "not_enough_info", "not_applicable", "n/a",
    "na", "none", "null", "missing", "not_specified", "not_available",
    "not_reported", "source_limited", "unavailable", "unclear",
    "undetermined", "tbd", "?",
})
# In raw descriptive counts, statistical mechanics can explicitly be absent.
# This is not permission to omit an endpoint, source result, or source version.
OPTIONAL_METHOD_ABSENCE = frozenset({"not_applicable", "n/a", "na", "none"})


def _missing_field(value: Any, key: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    # Reject hidden format and control code points in metadata identities.
    # These can conceal mismatched source versions, result IDs or locators.
    # Refuse rather than rewriting identity bytes.
    if any(unicodedata.category(char).startswith("C") for char in value):
        return True
    normalized = re.sub(r"[\s_-]+", "_", value.strip().casefold())
    if normalized not in UNKNOWN_LITERALS:
        return False
    return key in CORE_IDENTITY_FIELDS or normalized not in OPTIONAL_METHOD_ABSENCE


def compare_raw_counts(left: Any, right: Any) -> dict[str, Any]:
    """Compare counts only for the same result, arm/stratum and source version.

    Return CONSISTENT, REVIEW (a candidate, never a confirmed error),
    NOT_COMPARABLE (verified different identity), or NOT_ENOUGH_INFO.
    A source digest is an identifier, not evidence that its content is correct.
    """
    base: dict[str, Any] = {
        "status": "NOT_ENOUGH_INFO", "disposition": "HOLD",
        "source_support": "NOT_ENOUGH_INFO", "maturity": "SCREENED",
        "human_adjudicated": False, "author_confirmed": False,
        "certified_error": False, "email_eligible": False,
        "arithmetic_reproduced": False, "source_authenticated": False,
    }
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return {**base, "reason": "both records must be mappings"}
    for side_name, record in (("left", left), ("right", right)):
        for key in RESULT_FIELDS + ("locator", "source_sha256"):
            value = record.get(key)
            if _missing_field(value, key):
                return {**base, "reason": f"{side_name}: missing/unverified {key}"}
        if SHA256.fullmatch(record["source_sha256"]) is None:
            return {**base, "reason": f"{side_name}: invalid source_sha256"}
        if record["count_basis"] not in COUNT_BASES:
            return {**base, "reason": f"{side_name}: unsupported count_basis"}
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return {**base, "reason": f"{side_name}: count must be a nonnegative exact integer"}
    # A shared denominator *basis* (e.g. randomized) is not evidence that
    # the two snapshots used the same number of eligible units. When either
    # caller supplies an exact analysis denominator, require a valid number
    # on both sides and compare it before interpreting any numerator delta.
    # Older callers without this optional field retain the screened contract;
    # absence alone never authenticates denominator comparability.
    denominator_present = (
        "analysis_denominator_n" in left,
        "analysis_denominator_n" in right,
    )
    if any(denominator_present):
        if not all(denominator_present):
            return {**base, "reason": "analysis denominator size supplied on only one side"}
        for side_name, record in (("left", left), ("right", right)):
            size = record["analysis_denominator_n"]
            if type(size) is not int or size <= 0:
                return {**base, "reason": f"{side_name}: invalid analysis_denominator_n"}
            # One patient may have multiple recurrent events, but a unique
            # participant count cannot exceed its stated eligible cohort.
            if record["count_basis"] == "unique_participants" and record["value"] > size:
                return {**base, "reason": f"{side_name}: unique count exceeds analysis denominator"}
        if left["analysis_denominator_n"] != right["analysis_denominator_n"]:
            return {
                **base, "status": "NOT_COMPARABLE",
                "reason": "reported analysis denominator sizes differ",
                "mismatched_fields": ["analysis_denominator_n"],
            }
    differing = tuple(key for key in RESULT_FIELDS if left[key] != right[key])
    if differing:
        return {
            **base, "status": "NOT_COMPARABLE",
            "reason": "result identity/estimator/source version differs",
            "mismatched_fields": list(differing),
        }
    # Same source location in the same declared document/result version
    # must identify the same source bytes. A changed digest with unchanged
    # locator is unresolved version/provenance drift, not a reproduced count
    # agreement or discrepancy. Different locations may legitimately refer
    # to distinct representations (e.g. article vs supplement).
    if (left["locator"] == right["locator"]
            and left["source_sha256"].casefold() != right["source_sha256"].casefold()):
        return {
            **base,
            "reason": "same source locator/version has conflicting SHA-256 digests",
        }
    lhs, rhs = left["value"], right["value"]
    if lhs == rhs:
        return {
            **base, "status": "CONSISTENT", "disposition": "NO_FLAG",
            "source_support": "NOT_ENOUGH_INFO", "maturity": "SCREENED",
            "arithmetic_reproduced": True,
            "reason": "exact matched-result integer counts agree", "left": lhs,
            "right": rhs, "difference": 0,
        }
    return {
        **base, "status": "REVIEW", "disposition": "HOLD",
        "source_support": "NOT_ENOUGH_INFO", "maturity": "SCREENED",
        "arithmetic_reproduced": True,
        "reason": "same-result counts differ; inspect source/denominator before alleging error",
        "left": lhs, "right": rhs, "difference": lhs - rhs,
    }
