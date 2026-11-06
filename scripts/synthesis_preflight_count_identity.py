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
# Optional typed unit for an explicitly supplied denominator size.
# A numeric exposure of 100 people is not interchangeable with 100 person-years.
# No inferred conversion or source authentication occurs in this helper.
DENOMINATOR_UNITS = frozenset({
    "unique_participants", "events", "visits", "trial_families",
    "person_days", "person_months", "person_years",
})
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
    # Canonical result identities and source locators must not be padded.
    # Identical malformed labels on both sides cannot establish a matched
    # source; refuse instead of trimming or treating them as a REVIEW.
    # Ordinary spaces within printable human-readable labels remain valid.
    if value != value.strip():
        return True
    # Reject hidden format and control code points in metadata identities.
    # These can conceal mismatched source versions, result IDs or locators.
    # Refuse rather than rewriting identity bytes.
    if any(unicodedata.category(char).startswith("C") for char in value):
        return True
    # Canonically equivalent decomposed and precomposed labels must not
    # become different source/result identities in downstream contracts.
    # Require NFC without silently rewriting caller-supplied evidence.
    if unicodedata.normalize("NFC", value) != value:
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
    # A shared denominator basis does not prove a matching cohort size.
    # Validate the complete optional denominator contract before comparing
    # either its size or unit. Otherwise differing sizes could mask an
    # unsupported/one-sided unit and incorrectly report NOT_COMPARABLE
    # instead of the safer NOT_ENOUGH_INFO hold.
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

    # Units must be explicitly recognized on both sides whenever supplied;
    # unknown units cannot be converted into a verified size mismatch.
    unit_present = (
        "analysis_denominator_unit" in left,
        "analysis_denominator_unit" in right,
    )
    if any(unit_present):
        if not all(unit_present):
            return {**base, "reason": "analysis denominator unit supplied on only one side"}
        if not all(denominator_present):
            return {**base, "reason": "analysis denominator unit requires exact size on both sides"}
        for side_name, record in (("left", left), ("right", right)):
            unit = record["analysis_denominator_unit"]
            if type(unit) is not str or unit not in DENOMINATOR_UNITS:
                return {**base, "reason": f"{side_name}: unsupported analysis_denominator_unit"}

    # Validate optional trial-family manifests before a valid denominator-size
    # mismatch may conclude NOT_COMPARABLE. Invalid membership must fail
    # closed even if the two denominators differ.
    # Optional caller-supplied family membership contract. A reported
    # trial-family total is not a count of distinct families if its membership
    # includes duplicates or aliases of the same family. This is metadata
    # validation only; family IDs are not authenticated against publications.
    # Missing manifests on *both* sides preserve legacy screened behavior.
    membership_present = (
        "trial_family_ids" in left,
        "trial_family_ids" in right,
    )
    if any(membership_present):
        if not all(membership_present):
            return {**base, "reason": "trial-family membership supplied on only one side"}
        family_sets: dict[str, frozenset[str]] = {}
        for side_name, record in (("left", left), ("right", right)):
            if record["count_basis"] != "trial_families":
                return {**base, "reason": f"{side_name}: trial-family membership requires trial_families count basis"}
            members = record["trial_family_ids"]
            if (not isinstance(members, (list, tuple))
                    or len(members) != record["value"]
                    or any(_missing_field(member, "publication_id") for member in members)):
                return {**base, "reason": f"{side_name}: invalid or incomplete trial-family membership"}
            aliases = [unicodedata.normalize("NFKC", member).casefold()
                       for member in members]
            if len(set(aliases)) != len(members):
                return {**base, "reason": f"{side_name}: repeated or aliased trial-family membership"}
            # Matching spelling is required across sources; case/Unicode
            # aliases without reviewed equivalence cannot prove membership.
            family_sets[side_name] = frozenset(members)
    if any(denominator_present):
        for side_name, record in (("left", left), ("right", right)):
            size = record["analysis_denominator_n"]
            # When numerator and denominator represent the same unit,
            # the reported numerator cannot exceed the stated total.
            # Recurrent events per participant and counts per person-time
            # are *not* same-unit and must not be capped as cohort sizes.
            # Legacy unlabelled denominators retain the participant cap.
            unit = record.get("analysis_denominator_unit", "unique_participants")
            if record["count_basis"] == unit and record["value"] > size:
                return {**base, "reason": f"{side_name}: count exceeds same-unit analysis denominator"}
        if unit_present[0] and left["analysis_denominator_unit"] != right["analysis_denominator_unit"]:
            return {
                **base, "status": "NOT_COMPARABLE",
                "reason": "analysis denominator units differ",
                "mismatched_fields": ["analysis_denominator_unit"],
            }
        if left["analysis_denominator_n"] != right["analysis_denominator_n"]:
            return {
                **base, "status": "NOT_COMPARABLE",
                "reason": "reported analysis denominator sizes differ",
                "mismatched_fields": ["analysis_denominator_n"],
            }
    if any(membership_present):
        if family_sets["left"] != family_sets["right"]:
            # A changed spelling is not necessarily a distinct trial family.
            # Cross-record NFKC/case aliases require a reviewed identity
            # crosswalk; they cannot establish an authenticated difference.
            left_aliases = {
                unicodedata.normalize("NFKC", member).casefold(): member
                for member in family_sets["left"]
            }
            right_aliases = {
                unicodedata.normalize("NFKC", member).casefold(): member
                for member in family_sets["right"]
            }
            if any(left_aliases[alias] != right_aliases[alias]
                   for alias in left_aliases.keys() & right_aliases.keys()):
                return {
                    **base,
                    "reason": "unresolved cross-record trial-family identity alias",
                }
            return {
                **base, "status": "NOT_COMPARABLE",
                "reason": "trial-family membership differs",
                "mismatched_fields": ["trial_family_ids"],
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
