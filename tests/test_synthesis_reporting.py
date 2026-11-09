"""Synthetic-only contracts for blinded Synthesis reporting and journal yield."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


journal = _load("synthesis_journal_yield")
blind = _load("synthesis_blind_eval")


def journal_record(index: int = 1, **changes):
    # 10.0000/SYNTHETIC-n deliberately cannot refer to a real research article.
    row = {
        "doi": f"10.0000/SYNTHETIC-{index}", "journal": "Synthetic Journal",
        "family_id": f"synthetic-family-{index}", "access": "ACCESSIBLE_VOR",
        "source_version": "synthetic-original-v1", "retrieval_path": "synthetic fixture",
        "source_locator": "Table 1", "deep_audit": True, "audit_outcome": "NEGATIVE",
        "review_seconds": 1800, "root_causes": [], "sent_ids": [],
        "reply_ids": [], "correction_ids": [],
    }
    row.update(changes)
    return row


def verified_root(synthesis_discovery: bool = True):
    item = {
        "root_id": "synthetic-root-1", "status": "SOURCE_VERIFIED",
        "evidence_locator": "Synthetic Figure 1", "source_reference": "synthetic packet",
        "synthesis_discovery": synthesis_discovery,
    }
    if synthesis_discovery:
        item["detection_record"] = "synthetic detection receipt"
    return item


def evaluation_fixture():
    cases = [
        {"claim_id": key, "family_id": family,
         "doi": f"10.0000/SYNTHETIC-{key}", "split": split,
         "original_state": "VERIFIED_ORIGINAL", "original_version": "synthetic-v1",
         "retrieval_path": "synthetic-locked-archive", "source_locator": "Table 1",
         "original_sha256": "a" * 64}
        for key, family, split in (("D", "family-D", "development"),
                                   ("T1", "family-T1", "test"),
                                   ("T2", "family-T2", "test"))
    ]
    manifest = {
        "schema": "synthesis-blind-manifest-v1", "cohort_id": "synthetic-claims",
        "selection_rule": "synthetic fixed claim order, no replacement", "seed": 7,
        "frozen_at": "2026-11-01T09:00:00Z", "claims": cases,
    }
    predictions = {
        "schema": "synthesis-predictions-v1",
        "manifest_sha256": blind.sha256_json(manifest),
        "frozen_at": "2026-11-01T10:00:00Z",
        "predictions": [
            {"claim_id": "T1", "disposition": "FLAG", "flag_root_id": "r1",
             "evidence_locator": "Table 1", "predicted_at": "2026-11-01T09:30:00Z",
             "review_seconds": 120},
            {"claim_id": "T2", "disposition": "NO_FLAG",
             "predicted_at": "2026-11-01T09:40:00Z", "review_seconds": 100},
        ],
    }
    adjudications = {
        "schema": "synthesis-adjudications-v1",
        "prediction_sha256": blind.sha256_json(predictions),
        "adjudications": [
            {"claim_id": "T1", "truth": "ERROR", "flag_root_match": True,
             "independent_masked": True, "adjudicated_at": "2026-11-01T11:00:00Z",
             "evidence_reference": "synthetic independent label"},
            {"claim_id": "T2", "truth": "NO_ERROR",
             "independent_masked": True, "adjudicated_at": "2026-11-01T11:00:00Z",
             "evidence_reference": "synthetic independent label"},
        ],
    }
    return manifest, predictions, adjudications


def test_yield_uses_accessible_denominator_and_explicit_root_evidence():
    found = journal_record(1, audit_outcome="VERIFIED", root_causes=[verified_root()],
                           sent_ids=["synthetic-sent"], reply_ids=["synthetic-inbound"])
    normal = journal_record(2)
    limited = journal_record(3, access="SOURCE_LIMITED", stop_point="supplement unavailable",
                             deep_audit=False, audit_outcome="NOT_AUDITED", review_seconds=60)
    result = journal.summarise([found, normal, limited])
    j = result["journals"]["Synthetic Journal"]
    assert j["screened_unique_dois"] == 3
    assert j["accessible_vor"] == 2 and j["source_limited"] == 1
    assert j["deep_audits"] == 2 and j["explicit_negative_audits"] == 1
    assert j["verified_synthesis_discoveries"] == 1
    assert j["verified_discoveries_per_100_accessible"] == 50.0
    assert j["sent_messages"] == j["replied_messages"] == 1


def test_published_correction_is_not_credited_as_new_synthesis_discovery():
    root = verified_root(False)
    root.update(status="PUBLISHED_CORRECTION", correction_reference="synthetic correction")
    j = journal.summarise([journal_record(1, audit_outcome="VERIFIED", root_causes=[root])])["journals"]["Synthetic Journal"]
    assert j["source_verified_unique_roots"] == 1
    assert j["published_corrected_unique_roots"] == 1
    assert j["verified_synthesis_discoveries"] == 0


def test_same_family_root_across_two_reports_is_one_portfolio_root():
    a = journal_record(1, audit_outcome="VERIFIED", root_causes=[verified_root()])
    b = journal_record(2, family_id=a["family_id"], audit_outcome="VERIFIED",
                       root_causes=[verified_root()])
    result = journal.summarise([a, b])
    assert result["portfolio_unique_verified_synthesis_discoveries"] == 1


@pytest.mark.parametrize("changes", [
    {"source_locator": ""},
    {"review_seconds": float("nan")},
    {"access": "BLOCKED", "deep_audit": True, "stop_point": "login"},
    {"audit_outcome": "VERIFIED", "root_causes": []},
    {"audit_outcome": "NEGATIVE", "root_causes": [verified_root()]},
    {"audit_outcome": "NOT_AUDITED"},
])
def test_yield_rejects_invalid_evidence_or_contradictory_status(changes):
    with pytest.raises(journal.LedgerError):
        journal.summarise([journal_record(**changes)])


def test_yield_rejects_duplicate_doi_even_with_different_case():
    with pytest.raises(journal.LedgerError, match="duplicate DOI"):
        journal.summarise([journal_record(1), journal_record(1, doi="10.0000/synthetic-1")])


def test_yield_requires_discovery_provenance_for_verified_root():
    root = verified_root()
    del root["detection_record"]
    with pytest.raises(journal.LedgerError):
        journal.summarise([journal_record(audit_outcome="VERIFIED", root_causes=[root])])


def test_blind_predictions_frozen_without_truth_are_not_accuracy():
    manifest, predictions, _ = evaluation_fixture()
    result = blind.evaluate(manifest, predictions)
    assert result["status"] == "PREDICTIONS_FROZEN_AWAITING_BLIND_ADJUDICATION"
    assert result["metrics"] is None
    assert result["test_claims"] == 2


def test_blind_complete_adjudication_reports_claim_level_confusion_and_intervals():
    manifest, predictions, adjudications = evaluation_fixture()
    result = blind.evaluate(manifest, predictions, adjudications)
    m = result["metrics"]
    assert result["status"] == "ADJUDICATED"
    assert (m["TP"], m["TN"], m["FN"], m["FP"]) == (1, 1, 0, 0)
    assert m["precision_on_adjudicated_flags"]["estimate"] == 1.0
    assert m["automatic_error_recall_including_abstentions"]["denominator"] == 1
    assert m["precision_on_adjudicated_flags"]["wilson_95ci"][0] < 1.0


def test_blind_wrong_root_counts_both_false_alert_and_missed_error():
    manifest, predictions, adjudications = evaluation_fixture()
    adjudications["adjudications"][0]["flag_root_match"] = False
    m = blind.evaluate(manifest, predictions, adjudications)["metrics"]
    assert (m["FP_WRONG_ROOT"], m["FN"], m["TP"]) == (1, 1, 0)
    assert m["false_alerts_per_adjudicated_negative_claim"]["numerator"] == 0


def test_blind_negative_flag_is_false_alert_with_correct_denominator():
    manifest, predictions, adjudications = evaluation_fixture()
    adjudications["adjudications"][0]["truth"] = "NO_ERROR"
    adjudications["adjudications"][0]["flag_root_match"] = False
    m = blind.evaluate(manifest, predictions, adjudications)["metrics"]
    assert m["FP_NEGATIVE"] == 1
    assert m["false_alerts_per_adjudicated_negative_claim"]["denominator"] == 2


def test_blind_abstention_on_known_error_reduces_automatic_recall():
    manifest, predictions, adjudications = evaluation_fixture()
    predictions["predictions"][0].update(disposition="ABSTAIN", stop_point="source unavailable")
    adjudications["prediction_sha256"] = blind.sha256_json(predictions)
    m = blind.evaluate(manifest, predictions, adjudications)["metrics"]
    assert m["ABSTAIN_ERROR"] == 1
    assert m["automatic_error_recall_including_abstentions"]["estimate"] == 0.0


def test_blind_unknown_truth_is_not_treated_as_negative():
    manifest, predictions, adjudications = evaluation_fixture()
    adjudications["adjudications"][1]["truth"] = "UNKNOWN"
    result = blind.evaluate(manifest, predictions, adjudications)
    assert result["status"] == "ADJUDICATED_WITH_UNKNOWN_TRUTH"
    assert result["metrics"]["TN"] == 0
    assert result["metrics"]["UNKNOWN_TRUTH"] == 1


def test_source_limited_original_cannot_produce_a_supported_flag():
    manifest, predictions, adjudications = evaluation_fixture()
    item = manifest["claims"][1]
    item.update(original_state="SOURCE_LIMITED", stop_point="original figure unavailable")
    predictions["manifest_sha256"] = blind.sha256_json(manifest)
    adjudications["prediction_sha256"] = blind.sha256_json(predictions)
    with pytest.raises(blind.EvaluationError, match="requires abstention"):
        blind.evaluate(manifest, predictions, adjudications)


@pytest.mark.parametrize("corrupt", [
    "family_leak", "label_leak", "manifest_sha", "missing_prediction",
    "early_prediction", "early_adjudication", "missing_independence", "prediction_sha",
])
def test_blind_refuses_leakage_or_incomplete_protocol(corrupt):
    manifest, predictions, adjudications = evaluation_fixture()
    if corrupt == "family_leak":
        manifest["claims"][0]["family_id"] = "family-T1"
    elif corrupt == "label_leak":
        manifest["claims"][1]["truth"] = "ERROR"
    elif corrupt == "manifest_sha":
        predictions["manifest_sha256"] = "0" * 64
    elif corrupt == "missing_prediction":
        predictions["predictions"].pop()
    elif corrupt == "early_prediction":
        predictions["predictions"][0]["predicted_at"] = "2026-10-31T08:00:00Z"
    elif corrupt == "early_adjudication":
        adjudications["adjudications"][0]["adjudicated_at"] = "2026-11-01T09:55:00Z"
    elif corrupt == "missing_independence":
        adjudications["adjudications"][0]["independent_masked"] = False
    elif corrupt == "prediction_sha":
        adjudications["prediction_sha256"] = "0" * 64
    with pytest.raises(blind.EvaluationError):
        blind.evaluate(manifest, predictions, adjudications)
