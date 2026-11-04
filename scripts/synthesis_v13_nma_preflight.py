"""Conservative NMA/IPD preflight; no pooled-effect model is fitted here.

Flags potential overlap, ignored multi-arm dependence or inconsistent subset
accounting only with caller-attested source evidence. These are review candidates.
A complete replay manifest is a readiness check, not statistical reproduction.
"""
from __future__ import annotations
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def _named(row: Mapping, fields: Sequence[str]) -> bool:
    return all(isinstance(row.get(k), str) and row[k].strip() for k in fields)


def duplicate_trial_population(rows: Sequence[Mapping]) -> dict:
    """Check repeated inclusion of the same participants for one NMA outcome.

    Several reports of a trial are not automatically duplicates: distinct
    cohorts, periods or endpoints may be legitimate. A shared family label alone
    is insufficient; an attested same-cohort key and model dependence handling
    must be present before surfacing a review candidate.
    """
    if not isinstance(rows, (list, tuple)) or not rows:
        return {"status": "HOLD", "reason": "no structured study rows"}
    required = (
        "synthesis_id", "trial_family_id", "cohort_id", "endpoint",
        "time_window", "contrast_id", "source_version", "source_locator",
        "report_id", "dependence_handling",
    )
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, Mapping) or not _named(row, required):
            return {"status": "HOLD", "reason": "trial, endpoint, cohort or source identity incomplete"}
        if row.get("same_cohort_source_verified") is not True:
            return {"status": "HOLD", "reason": "cohort overlap not source-verified"}
        if row.get("included_as_independent_effect") not in (True, False):
            return {"status": "HOLD", "reason": "model inclusion unverified"}
        if row["dependence_handling"] not in {
                "INDEPENDENT_UNCORRELATED", "CORRELATION_ACCOUNTED_FOR", "UNKNOWN"}:
            return {"status": "HOLD", "reason": "published dependence model unknown"}
        if row["dependence_handling"] == "UNKNOWN":
            return {"status": "HOLD", "reason": "cannot infer independent study weighting"}
        if not row["included_as_independent_effect"]:
            continue
        key = tuple(row[k] for k in required[:6])
        groups[key].append((row["report_id"], row["dependence_handling"]))
    issues = []
    for key, reports in sorted(groups.items()):
        if len(reports) < 2:
            continue
        if sum(method == "INDEPENDENT_UNCORRELATED" for _, method in reports) >= 2:
            issues.append({"key": key, "reports": [r for r, _ in reports]})
    return {
        "status": "REVIEW_CANDIDATE" if issues else "NO_FLAG",
        "possible_duplicate_groups": issues,
        "reason": ("attested same-cohort independent effects may be repeated"
                   if issues else "no attested unaccounted repeated effect"),
        "warning": "Inspect original trial populations and fitted covariance before alleging error",
    }


def shared_control_dependence(comparisons: Sequence[Mapping]) -> dict:
    """Identify a shared control that a published model treats as independent."""
    if not isinstance(comparisons, (list, tuple)) or len(comparisons) < 2:
        return {"status": "HOLD", "reason": "at least two contrasts required"}
    fields = (
        "trial_family_id", "cohort_id", "endpoint", "time_window",
        "control_arm_id", "comparison_id", "analysis_model", "source_locator",
    )
    groups: dict[tuple[str, ...], list[tuple[str, str]]] = defaultdict(list)
    for row in comparisons:
        if not isinstance(row, Mapping) or not _named(row, fields):
            return {"status": "HOLD", "reason": "multi-arm source/analysis identity incomplete"}
        if row.get("control_identity_verified") is not True:
            return {"status": "HOLD", "reason": "same control arm not source-verified"}
        if row["analysis_model"] not in {
                "INDEPENDENT_UNCORRELATED", "CORRELATION_ACCOUNTED_FOR", "UNKNOWN"}:
            return {"status": "HOLD", "reason": "unknown analysis model"}
        if row["analysis_model"] == "UNKNOWN":
            return {"status": "HOLD", "reason": "covariance handling not independently established"}
        key = tuple(row[k] for k in fields[:5])
        groups[key].append((row["comparison_id"], row["analysis_model"]))
    issues = [
        {"key": key, "contrasts": [v[0] for v in vals]}
        for key, vals in sorted(groups.items())
        if len({v[0] for v in vals}) >= 2
        and sum(v[1] == "INDEPENDENT_UNCORRELATED" for v in vals) >= 2
    ]
    return {
        "status": "REVIEW_CANDIDATE" if issues else "NO_FLAG",
        "possible_shared_control_groups": issues,
        "warning": "A shared control is legitimate when covariance is correctly accounted for",
    }


def restricted_analysis_accounting(record: Mapping) -> dict:
    """Compare published counts for an explicitly restricted sensitivity analysis.

    A different population definition or an analysis that adds or substitutes
    studies can legitimately report more participants. A review candidate does
    not identify which count is wrong or establish the cause of the mismatch.
    """
    if not isinstance(record, Mapping):
        return {"status": "INVALID", "reason": "record must be a mapping"}
    locations = ("source_version", "restriction_locator", "primary_locator", "restricted_locator")
    if not _named(record, locations) or record.get("same_source_version_verified") is not True:
        return {"status": "HOLD", "reason": "exact source version and analysis locations are required"}
    if record.get("relationship") == "NOT_A_RESTRICTION":
        return {"status": "NOT_COMPARABLE", "reason": "the second analysis is not a subset"}
    if record.get("relationship") != "RESTRICTION":
        return {"status": "HOLD", "reason": "the paper must explicitly describe a restriction"}
    if record.get("same_participant_count_basis_verified") is not True:
        return {"status": "HOLD", "reason": "participant-count definitions must be verified as comparable"}
    primary = record.get("primary_participants")
    restricted = record.get("restricted_participants")
    if any(type(n) is not int or n < 0 for n in (primary, restricted)):
        return {"status": "HOLD", "reason": "exact nonnegative integer participant counts are required"}
    if restricted <= primary:
        return {"status": "NO_FLAG", "reason": "the restriction does not report more participants"}
    return {
        "status": "REVIEW_CANDIDATE",
        "reason": "the reported restriction has more participants than its primary analysis",
        "participant_excess": restricted - primary,
        **{name: record[name] for name in locations},
    }


def replay_readiness(record: Mapping) -> dict:
    """Demand original published replay before correction and RoB reassessment.

    Does not run a statistical package, verify output or label a paper wrong.
    """
    if not isinstance(record, Mapping):
        return {"status": "INVALID", "reason": "record must be a mapping"}
    fields = (
        "synthesis_id", "outcome", "source_version", "source_locator",
        "trial_family_matrix_reference", "original_event_data_reference",
        "endpoint_estimand_ledger_reference", "published_model_specification",
        "published_output_reference", "exact_replay_code_reference",
        "source_verified_extraction_receipt", "unique_population_receipt",
        "original_replay_result_reference", "corrected_replay_result_reference",
        "conclusion_sensitivity_reference", "rob2_reference",
        "rob_nma_reference", "transitivity_consistency_reference",
    )
    missing = [k for k in fields if not isinstance(record.get(k), str)
               or not record[k].strip()]
    if missing:
        return {"status": "HOLD", "reason": "replay evidence missing", "fields": missing}
    if (record.get("original_replay_completed") is not True
            or record.get("corrected_replay_completed") is not True
            or record.get("all_outcomes_verified") is not True):
        return {"status": "HOLD", "reason": "published-first and corrected replay incomplete"}
    return {
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "reason": "source/replay/RoB receipts declared, not externally authenticated",
    }
