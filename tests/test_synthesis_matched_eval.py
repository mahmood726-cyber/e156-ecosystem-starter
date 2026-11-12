"""Synthetic contracts only; no real papers, model calls, or human judgments."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import synthesis_blind_eval as blind
from scripts import synthesis_matched_eval as matched


@pytest.fixture
def study(tmp_path):
    claims, tasks = [], []
    for cid in ("T1", "T2", "T3"):
        data = f"SYNTHETIC contract packet {cid}".encode()
        (tmp_path / f"{cid}.txt").write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        claims.append({"claim_id": cid, "family_id": "F1" if cid != "T3" else "F2",
                       "doi": f"10.0000/SYNTHETIC-{cid}", "split": "test",
                       "original_state": "VERIFIED_ORIGINAL", "original_version": "synthetic",
                       "retrieval_path": "synthetic", "source_locator": "synthetic",
                       "original_sha256": digest})
        tasks.append({"claim_id": cid, "input_file": f"{cid}.txt", "input_sha256": digest,
                      "source_files": [{"file": f"{cid}.txt", "sha256": digest}],
                      "oa_rights_reference": "synthetic test bytes; not a research source"})
    manifest = {"schema": "synthesis-blind-manifest-v1", "cohort_id": "SYNTHETIC",
                "selection_rule": "synthetic contract only", "seed": 8,
                "frozen_at": "2026-11-01T09:00:00Z", "claims": claims}
    arms = [{"arm_id": a, "runtime": "synthetic adapter", "runtime_version": "test-v1",
             "config_sha256": "c" * 64, "model_snapshot": "synthetic-model",
             "model_config_sha256": "b" * 64,
             "tools_sha256": "d" * 64} for a in ("A", "B")]
    protocol = {"schema": "synthesis-matched-protocol-v1", "purpose": "synthetic_contract",
                "comparison_kind": "harness_only", "frozen_at": "2026-11-01T09:01:00Z",
                "manifest_sha256": blind.sha256_json(manifest), "arms": arms, "tasks": tasks,
                "retry_policy": "one_record_all_internal_attempts", "order_seed": 19,
                "limits": {"wall_seconds": 60, "model_tokens": 1000, "tool_calls": 10,
                           "api_cost_usd": 1, "review_seconds": 120},
                "analysis_plan_reference": "synthetic test plan"}
    records = []
    for arm in arms:
        for task in tasks:
            prediction = {"disposition": "NO_FLAG", "review_seconds": 10}
            if task["claim_id"] == "T1":
                prediction.update(disposition="FLAG", flag_root_id="synthetic-root",
                                  evidence_locator="synthetic paragraph")
            records.append({"arm_id": arm["arm_id"], "claim_id": task["claim_id"],
                            "arm_sha256": blind.sha256_json(arm),
                            "input_sha256": task["input_sha256"], "status": "COMPLETE",
                            "started_at": "2026-11-01T09:02:00Z",
                            "ended_at": "2026-11-01T09:02:20Z", "wall_seconds": 20,
                            "prediction": prediction, "internal_attempts": 1,
                            "record_evidence_reference": "synthetic timing/usage ledger",
                            "record_evidence_sha256": "e" * 64,
                            "usage": {"model_tokens": 50, "tool_calls": 1,
                                      "api_cost_usd": 0.1, "human_review_cost_usd": None}})
    runs = {"schema": "synthesis-matched-runs-v1", "protocol_sha256": blind.sha256_json(protocol),
            "frozen_at": "2026-11-01T10:00:00Z", "records": records}
    return manifest, protocol, runs, tmp_path


def reference(study):
    manifest, protocol, runs, root = study
    packet = matched.mask(manifest, protocol, runs, root)
    return {"schema": "synthesis-matched-adjudications-v1",
            "masked_packet_sha256": blind.sha256_json(packet),
            "adjudications": [{"sample_id": r["sample_id"],
                              "truth": {"T1": "ERROR", "T2": "NO_ERROR", "T3": "UNKNOWN"}[r["claim_id"]],
                              "flag_root_match": True, "independent_masked": True,
                              "adjudicated_at": "2026-11-01T11:00:00Z",
                              "evidence_reference": "synthetic reference only"}
                             for r in packet["samples"]]}


def test_end_to_end_mask_score_and_unknown_costs(study):
    m, p, r, root = study
    result = matched.compare(m, p, r, root, reference(study))
    assert result["purpose"] == "synthetic_contract"
    assert result["scientific_validation"] == "NOT_ESTABLISHED_BY_THIS_SOFTWARE"
    assert result["arms"]["A"]["evaluation"]["metrics"]["TP"] == 1
    assert result["arms"]["A"]["evaluation"]["metrics"]["UNKNOWN_TRUTH"] == 1
    assert result["arms"]["A"]["costs"]["api_cost_usd"]["total"] == pytest.approx(0.3)
    assert result["arms"]["A"]["costs"]["human_review_cost_usd"]["total"] is None
    assert result["arms"]["A"]["costs"]["human_review_cost_usd"]["missing_records"] == 3
    assert len(result["paired"][0]["families"]) == 2
    assert result["paired"][0]["error_root_detection"]["both"] == 1


def test_before_reference_only_records_no_accuracy(study):
    m, p, r, root = study
    result = matched.compare(m, p, r, root)
    assert result["paired"] is None
    assert result["arms"]["A"]["evaluation"]["metrics"] is None


def test_mask_whitelists_without_runtime_cost_or_timing(study):
    m, p, r, root = study
    packet = matched.mask(m, p, r, root)
    assert len(packet["samples"]) == 6
    assert len({x["sample_id"] for x in packet["samples"]}) == 6
    text = json.dumps(packet)
    for forbidden in ("synthetic adapter", "cost_usd", "review_seconds", "arm_id", "model_snapshot"):
        assert forbidden not in text


@pytest.mark.parametrize("status", ["FAILED", "TIMEOUT", "NOT_ATTEMPTED"])
def test_failed_cases_retained_as_abstentions(study, status):
    m, p, r, root = study
    row = r["records"][0]
    row["status"] = status
    if status == "NOT_ATTEMPTED":
        row["internal_attempts"] = 0
    row["prediction"] = {"disposition": "ABSTAIN", "review_seconds": 0, "stop_point": status}
    result = matched.compare(m, p, r, root, reference(study))
    metrics = result["arms"]["A"]["evaluation"]["metrics"]
    assert metrics["FN"] == metrics["ABSTAIN_ERROR"] == 1
    assert result["arms"]["A"]["status_counts"][status] == 1
    assert result["paired"][0]["error_root_detection"]["right_only"] == 1


@pytest.mark.parametrize("kind", ["missing", "duplicate", "input", "config", "early", "late", "failed_flag", "negative", "nan"])
def test_refuses_invalid_or_incomplete_run_records(study, kind):
    m, p, r, root = study
    row = r["records"][0]
    if kind == "missing":
        r["records"].pop()
    elif kind == "duplicate":
        r["records"].append(copy.deepcopy(row))
    elif kind == "input":
        row["input_sha256"] = "0" * 64
    elif kind == "config":
        row["arm_sha256"] = "0" * 64
    elif kind == "early":
        row["started_at"] = "2026-11-01T08:00:00Z"
    elif kind == "late":
        row["ended_at"] = "2026-11-01T10:01:00Z"
    elif kind == "failed_flag":
        row["status"] = "FAILED"
    else:
        row["usage"]["api_cost_usd"] = -1 if kind == "negative" else float("nan")
    with pytest.raises(matched.Refused):
        matched.compare(m, p, r, root)


def test_budget_breach_and_missing_usage_preserve_scores(study):
    m, p, r, root = study
    r["records"][0]["usage"]["model_tokens"] = 1001
    r["records"][3]["usage"]["api_cost_usd"] = None
    result = matched.compare(m, p, r, root, reference(study))
    assert result["matched_budget_status"] == "VIOLATION"
    assert result["arms"]["A"]["evaluation"]["metrics"]["TP"] == 1
    assert result["arms"]["B"]["costs"]["api_cost_usd"]["total"] is None
    assert result["budget_issues"]


@pytest.mark.parametrize("kind", ["changed_input", "traversal", "family_leak", "unequal_model", "unequal_decoding", "nested_label", "unapproved"])
def test_protocol_and_packet_fail_closed(study, kind):
    m, p, r, root = study
    if kind == "changed_input":
        (root / "T1.txt").write_text("changed", encoding="utf-8")
    elif kind == "traversal":
        p["tasks"][0]["input_file"] = "../T1.txt"
    elif kind == "family_leak":
        m["claims"].append({**m["claims"][0], "claim_id": "D", "split": "development"})
    elif kind == "unequal_model":
        p["arms"][1]["model_snapshot"] = "different-model"
    elif kind == "unequal_decoding":
        p["arms"][1]["model_config_sha256"] = "0" * 64
    elif kind == "nested_label":
        p["tasks"][0]["metadata"] = {"truth": "ERROR"}
    else:
        p["purpose"] = "prospective"
    p["manifest_sha256"] = blind.sha256_json(m)
    r["protocol_sha256"] = blind.sha256_json(p)
    with pytest.raises(matched.Refused):
        matched.compare(m, p, r, root)


@pytest.mark.parametrize("kind", ["omitted", "wrong_packet", "early", "inconsistent_truth", "unmasked"])
def test_independent_reference_binding_and_consistency(study, kind):
    m, p, r, root = study
    adjudications = reference(study)
    rows = adjudications["adjudications"]
    if kind == "omitted":
        rows.pop()
    elif kind == "wrong_packet":
        adjudications["masked_packet_sha256"] = "0" * 64
    elif kind == "early":
        rows[0]["adjudicated_at"] = r["frozen_at"]
    elif kind == "unmasked":
        rows[0]["independent_masked"] = False
    else:
        rows[0]["truth"] = "UNKNOWN" if rows[0]["truth"] != "UNKNOWN" else "ERROR"
    with pytest.raises(matched.Refused):
        matched.compare(m, p, r, root, adjudications)


def test_cli_roundtrip_and_no_overwrite(study):
    m, p, r, root = study
    for name, obj in (("manifest", m), ("protocol", p), ("runs", r)):
        (root / f"{name}.json").write_text(json.dumps(obj), encoding="utf-8")
    output = root / "masked.json"
    command = [sys.executable, str(Path(matched.__file__)), "mask", "--manifest", str(root / "manifest.json"),
               "--protocol", str(root / "protocol.json"), "--runs", str(root / "runs.json"),
               "--inputs", str(root), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert first.returncode == 0, first.stderr
    before = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert second.returncode != 0
    assert output.read_bytes() == before


def test_verified_source_must_match_checked_inventory(study):
    m, p, r, root = study
    m["claims"][0]["original_sha256"] = "f" * 64
    p["manifest_sha256"] = blind.sha256_json(m)
    with pytest.raises(matched.Refused, match="verified original"):
        matched.prepare(m, p, root)


def test_prepare_works_without_python312_path_junction_api(study, monkeypatch):
    m, p, _, root = study
    monkeypatch.delattr(Path, "is_junction", raising=False)
    assert matched.prepare(m, p, root)["status"] == "PREPARED_NOT_RUN"


def test_wrong_root_counts_as_false_alarm_and_missed_error(study):
    m, p, r, root = study
    judgments = reference(study)
    sid = matched._sample(r, "A", "T1")
    for row in judgments["adjudications"]:
        if row["sample_id"] == sid:
            row["flag_root_match"] = False
    result = matched.compare(m, p, r, root, judgments)
    metrics = result["arms"]["A"]["evaluation"]["metrics"]
    assert metrics["FP_WRONG_ROOT"] == metrics["FP"] == metrics["FN"] == 1
    assert result["paired"][0]["error_root_detection"]["right_only"] == 1
    assert result["paired"][0]["negative_claim_false_alert"]["denominator"] == 1


@pytest.mark.parametrize("value", [10**400, float("inf"), True])
def test_invalid_large_and_boolean_measurements_refused(study, value):
    m, p, r, root = study
    r["records"][0]["wall_seconds"] = value
    with pytest.raises(matched.Refused):
        matched.compare(m, p, r, root)


def test_aggregate_measurement_overflow_refused(study):
    m, p, r, root = study
    for row in r["records"]:
        row["usage"]["api_cost_usd"] = 1e308
    with pytest.raises(matched.Refused, match="overflow"):
        matched.compare(m, p, r, root)


def test_duplicate_json_fields_refused_at_cli(study):
    m, p, r, root = study
    for name, obj in (("manifest", m), ("protocol", p), ("runs", r)):
        encoded = json.dumps(obj)
        if name == "runs":
            encoded = encoded.replace('"wall_seconds": 20', '"wall_seconds": 1000, "wall_seconds": 20', 1)
        (root / f"{name}.json").write_text(encoded, encoding="utf-8")
    output = root / "comparison.json"
    run = subprocess.run([sys.executable, str(Path(matched.__file__)), "compare",
                          "--manifest", str(root / "manifest.json"), "--protocol", str(root / "protocol.json"),
                          "--runs", str(root / "runs.json"), "--inputs", str(root), "--output", str(output)],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 2
    assert "duplicate JSON key" in run.stderr
    assert not output.exists()
