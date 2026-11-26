"""Synthetic end-to-end study orchestration; no paid calls or scientific labels."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import timedelta

import pytest

from scripts import harness_context as context, harness_runtime as runtime
from scripts import harness_study_runner as runner
from tests.test_synthesis_study_preflight import bundle, write_json, reseal


def response(text='{"disposition":"NO_FLAG","reason":"SYNTHETIC result"}'):
    return {"id": "synthetic-response", "model": "synthetic-model", "service_tier": "default",
        "status": "completed", "output": [{"type": "message", "role": "assistant", "content": [
        {"type": "output_text", "text": text}]}], "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}}


@pytest.fixture
def study(bundle):
    b = bundle
    b["protocol"]["purpose"] = "synthetic_contract"
    model = {"model": "synthetic-model", "max_output_tokens": 100,
        "input_microusd_per_million": 1000000, "output_microusd_per_million": 2000000,
        "price_reference": "SYNTHETIC upper bound, not provider pricing", "price_expires_at": "2099-01-01T00:00:00Z"}
    graphs = {}
    for mapping in b["inventory"]["tasks"]:
        graphs[mapping["claim_id"]] = context.strict_json((b["evidence"] / mapping["context_file"]).read_bytes())
    for arm, mapping in zip(b["protocol"]["arms"], b["inventory"]["arms"]):
        configs = {}
        for cid, graph in graphs.items():
            configs[cid] = {"schema": "e156-harness-runtime-v1", "project_id": "synthetic-study",
                "context_sha256": context.digest(graph), "selected": ["source"], "skills": [],
                "task": "SYNTHETIC inspect evidence", "task_kind": "review",
                "routes": {"review": ["only"]}, "models": {"only": model}, "worker": None,
                "request_policy": {"service_tier": "default"},
                "limits": {"model_calls": 2, "model_tokens": 1000, "tool_calls": 2,
                    "cost_microusd": 10000, "wall_ms": 60000, "request_ms": 10000, "context_chars": 4000}}
        artifact = {"schema": "e156-study-arm-configs-v1", "runtime_profile": runtime.profile(), "configurations": configs}
        for field, obj in (("config_file", artifact), ("model_config_file", runner.model_contract(configs)),
                           ("tools_file", runner.tools_contract(configs, graphs, b["inputs"]))):
            write_json(b["evidence"] / mapping[field], obj)
            arm[{"config_file": "config_sha256", "model_config_file": "model_config_sha256", "tools_file": "tools_sha256"}[field]] = context.digest(obj)
        arm["runtime"], arm["runtime_version"], arm["model_snapshot"] = "e156", context.digest(runtime.profile()), "synthetic-model"
    reseal(b)
    b["work"] = b["inputs"].parent / "work"
    b["budget"] = runtime.units(model_calls=8, model_tokens=4000, tool_calls=8, cost_microusd=40000, wall_ms=240000)
    b["mode"] = "SYNTHETIC_CONTRACT"
    b["fixtures"] = {runner.case_id(context.digest(b["protocol"]), a["arm_id"], t["claim_id"]):
        {"input_tokens": 20, "responses": [response()]} for a in b["protocol"]["arms"] for t in b["protocol"]["tasks"]}
    return b


def test_complete_prepare_execute_measure_freeze_mask_compare(study):
    plan = runner.prepare(**study)
    assert plan["status"] == "PREPARED_NOT_RUN"
    for _ in plan["schedule"]:
        result = runner.execute(study["work"])
        assert result["status"] == "CASE_RECORDED"
    assert runner.execute(study["work"])["status"] == "EXECUTION_COMPLETE"
    drafts = runner.records(study["work"])
    assert all(d["matched_record"]["prediction"]["review_seconds"] is None for d in drafts.values())
    measurements = {cid: {"schema": "e156-study-measurement-v1", "case_sha256": d["case_sha256"],
        "report_sha256": d["report_sha256"], "review_seconds": 0, "api_cost_usd": None,
        "human_review_cost_usd": None, "evidence_reference": "SYNTHETIC measurement fixture",
        "observed_at": runner.now()} for cid, d in drafts.items()}
    frozen = runner.freeze(study["work"], measurements)
    assert frozen["scientific_results"] is None
    assert len(frozen["runs"]["records"]) == len(plan["schedule"])
    assert frozen["comparison"]["matched_budget_status"] == "UNVERIFIED"
    assert len(frozen["masked"]["samples"]) == len(plan["schedule"])
    with pytest.raises(context.Refused, match="frozen"):
        runner.execute(study["work"])
    with pytest.raises(context.Refused): runner.freeze(study["work"], measurements)


def test_budget_and_unknown_execution_are_never_silently_retried(study, monkeypatch):
    runner.prepare(**study)
    original = runner.bounded_native.run
    monkeypatch.setattr(runner.bounded_native, "run", lambda *a, **k: (_ for _ in ()).throw(runner.bounded_native.Refused("synthetic transport loss")))
    assert runner.execute(study["work"])["status"] == "EXECUTION_UNKNOWN"
    monkeypatch.setattr(runner.bounded_native, "run", original)
    assert runner.execute(study["work"])["status"] == "EXECUTION_UNKNOWN"
    assert not list(study["work"].glob("cases/*/run.sqlite"))


def test_cap_stops_dispatch_and_retains_all_planned_rows(study):
    study["budget"]["model_tokens"] = 1000
    runner.prepare(**study)
    runner.execute(study["work"])
    assert runner.execute(study["work"])["status"] == "STUDY_BUDGET_STOP"
    runner.abort(study["work"])
    drafts = runner.records(study["work"])
    assert len(drafts) == 4
    assert sum(d["matched_record"]["status"] == "NOT_ATTEMPTED" for d in drafts.values()) == 3


def test_live_gate_never_uses_synthetic_fixture_or_missing_credentials(study, monkeypatch):
    study["mode"], study["fixtures"] = "LIVE", None
    runner.prepare(**study)
    with pytest.raises(context.Refused, match="paid"): runner.execute(study["work"])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(context.Refused, match="unavailable"): runner.execute(study["work"], allow_paid=True)


@pytest.mark.parametrize("defect", ["ignored_model_setting", "unselected_source", "different_task", "cap_mismatch"])
def test_false_configuration_identity_refused(study, defect):
    mapping = study["inventory"]["arms"][0]
    path = study["evidence"] / mapping["config_file"]
    artifact = context.strict_json(path.read_bytes())
    cfg = artifact["configurations"]["T1"]
    if defect == "ignored_model_setting": cfg["models"]["only"]["temperature"] = 0
    elif defect == "unselected_source": cfg["selected"] = []
    elif defect == "different_task": cfg["task"] = "Different task"
    else: cfg["limits"]["model_tokens"] = 1001
    write_json(path, artifact)
    study["protocol"]["arms"][0]["config_sha256"] = context.digest(artifact)
    reseal(study)
    with pytest.raises(context.Refused): runner.prepare(**study)
    assert not study["work"].exists()


def test_finished_child_settled_after_parent_loss_without_dispatch(study, monkeypatch):
    plan = runner.prepare(**study)
    original = runner._retain
    def crash(*args, **kwargs): raise OSError("synthetic parent settlement loss")
    monkeypatch.setattr(runner, "_retain", crash)
    with pytest.raises(OSError): runner.execute(study["work"])
    monkeypatch.setattr(runner, "_retain", original)
    monkeypatch.setattr(runner.bounded_native, "run", lambda *a, **k: pytest.fail("settlement must not dispatch"))
    key = plan["schedule"][0]
    assert runner.settle(study["work"], key)["status"] == "CASE_RECORDED"
    state = runner.read(study["work"] / "state.json")
    assert state["cases"][key]["dispatches"] == 1
    assert state["cases"][key]["reserved"]["model_tokens"] == 1000


def recovery_receipt(study, plan, key):
    case = plan["cases"][key]
    directory = study["work"] / "cases" / key
    journal = runtime.Journal(directory / "run.sqlite", case["config"], case["context"], directory / "inputs")
    events = journal.events()
    reservation = journal.operations(events)["model:0"]["reservation"]
    raw = response()
    return {"schema": "e156-harness-recovery-v1", "reviewer": "SYNTHETIC reviewer",
        "reason": "SYNTHETIC exact response recovery", "evidence_reference": "SYNTHETIC only",
        "attestation": "I verified this terminal response belongs to this exact request",
        "config_sha256": context.digest(case["config"]), "context_sha256": context.digest(case["context"]),
        "journal_sha256": context.digest(events[-1]), "operation_id": "model:0",
        "reservation_sha256": context.digest(reservation), "request_sha256": context.digest(reservation["request"]),
        "response": raw, "response_sha256": context.digest(raw)}


def test_unknown_response_reconciliation_resume_retains_deadline_and_budget(study):
    for fixture in study["fixtures"].values(): fixture["responses"] = [{"synthetic_timeout": True}]
    plan = runner.prepare(**study)
    key = plan["schedule"][0]
    assert runner.execute(study["work"])["runtime_status"] == "UNRESOLVED"
    before = runner.read(study["work"] / "state.json")["cases"][key]
    receipt = recovery_receipt(study, plan, key)
    wrong = copy.deepcopy(receipt); wrong["response"]["service_tier"] = "priority"
    with pytest.raises(context.Refused, match="model/tier"): runner.reconcile(study["work"], key, wrong)
    assert runner.reconcile(study["work"], key, receipt)["status"] == "RECONCILED_NOT_RESUMED"
    assert runner.execute(study["work"], resume=key)["runtime_status"] == "COMPLETED"
    after = runner.read(study["work"] / "state.json")["cases"][key]
    assert after["dispatches"] == 2
    assert (after["started_at"], after["deadline_at"], after["reserved"]) == (before["started_at"], before["deadline_at"], before["reserved"])
    # The script contains only a timeout; completion must come from journal replay.
    runner.abort(study["work"])
    row = runner.records(study["work"])[key]
    assert row["matched_record"]["usage"]["model_tokens"] == 30
    assert row["operation_counts"]["model"]["reconciled"] == 1


def test_abort_retains_unresolved_evidence_and_unknown_usage(study):
    for fixture in study["fixtures"].values(): fixture["responses"] = [{"synthetic_timeout": True}]
    plan = runner.prepare(**study); key = plan["schedule"][0]
    runner.execute(study["work"])
    runner.abort(study["work"])
    draft = runner.records(study["work"])[key]
    assert draft["matched_record"]["status"] == "FAILED"
    assert draft["matched_record"]["usage"]["model_tokens"] is None
    assert draft["accounting"]["unresolved_reserved"]["model_calls"] == 1
    assert len(list((study["work"] / "cases" / key).glob("record-*.json"))) == 2


def test_bad_response_identity_is_retained_for_reconciliation(study):
    for fixture in study["fixtures"].values(): fixture["responses"][0]["model"] = "wrong-model"
    plan = runner.prepare(**study); key = plan["schedule"][0]
    assert runner.execute(study["work"])["runtime_status"] == "UNRESOLVED"
    item = runner.read(study["work"] / "state.json")["cases"][key]
    report = runner.read(study["work"] / item["record_file"])["report"]
    op = runtime.Journal.operations(report["events"])["model:0"]
    assert op["finish"]["received"]["model"] == "wrong-model"
    assert op["finish"]["received"]["usage"]["total_tokens"] == 30


def test_malformed_response_is_recorded_and_recoverable_without_crashing_resume(study):
    for fixture in study["fixtures"].values(): fixture["responses"][0]["output"][0]["content"] = None
    plan = runner.prepare(**study); key = plan["schedule"][0]
    first = runner.execute(study["work"])
    assert first == {"status": "CASE_RECORDED", "case_id": key, "runtime_status": "UNRESOLVED"}
    item = runner.read(study["work"] / "state.json")["cases"][key]
    report = runner.read(study["work"] / item["record_file"])["report"]
    operation = runtime.Journal.operations(report["events"])["model:0"]
    assert operation["finish"]["kind"] == "UNRESOLVED"
    assert operation["finish"]["received"]["output"][0]["content"] is None
    assert runner.execute(study["work"], resume=key)["runtime_status"] == "UNRESOLVED"
    after = runner.read(study["work"] / "state.json")["cases"][key]
    assert runner.read(study["work"] / after["record_file"])["report"]["events"] == report["events"]
    assert (after["started_at"], after["deadline_at"], after["reserved"]) == (item["started_at"], item["deadline_at"], item["reserved"])
    assert runner.reconcile(study["work"], key, recovery_receipt(study, plan, key))["status"] == "RECONCILED_NOT_RESUMED"
    assert runner.execute(study["work"], resume=key)["runtime_status"] == "COMPLETED"
    runner.abort(study["work"])
    row = runner.records(study["work"])[key]
    assert row["matched_record"]["usage"]["model_tokens"] == 30
    assert row["operation_counts"]["model"] == {"allocated": 1, "finished": 0, "reconciled": 1, "unresolved": 0}


def test_post_preflight_guard_change_refused(study, monkeypatch):
    original = runner.preflight.preflight
    def changed(*args):
        value = original(*args)
        path = study["evidence"] / study["inventory"]["arms"][0]["config_file"]
        artifact = runner.read(path)
        artifact["configurations"]["T1"]["progress_policy"] = {"repeated_result_limit": 2}
        write_json(path, artifact)
        return value
    monkeypatch.setattr(runner.preflight, "preflight", changed)
    with pytest.raises(context.Refused, match="changed after preflight"): runner.prepare(**study)
    assert not study["work"].exists()


def test_child_case_lock_fences_parent_and_stale_dispatch(study, monkeypatch):
    plan = runner.prepare(**study); key = plan["schedule"][0]
    monkeypatch.setattr(runner.bounded_native, "run", lambda *a, **k: (_ for _ in ()).throw(runner.bounded_native.Refused("synthetic unknown launch")))
    runner.execute(study["work"])
    directory = study["work"] / "cases" / key
    code = "from scripts.harness_study_runner import lease; from pathlib import Path; import sys;\nwith lease(Path(sys.argv[1])):\n print('LOCKED',flush=True)\n sys.stdin.readline()\n"
    proc = subprocess.Popen([sys.executable, "-c", code, str(directory / "case.lock")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "LOCKED"
        with pytest.raises(context.Refused, match="already executing"): runner.settle(study["work"], key)
        with pytest.raises(context.Refused, match="already executing"): runner.abort(study["work"])
    finally:
        proc.communicate("release\n", timeout=10)
    assert proc.returncode == 0
    runner.abort(study["work"])
    item = runner.read(study["work"] / "state.json")["cases"][key]
    with pytest.raises(context.Refused, match="no longer authorized"):
        runner.child(directory, "SYNTHETIC_CONTRACT", item["deadline_at"], directory / "attempt-1.json")


def test_missing_review_measurements_never_freeze_or_default_to_zero(study):
    runner.prepare(**study); runner.abort(study["work"])
    with pytest.raises(context.Refused, match="complete measured"): runner.freeze(study["work"], {})
    assert not (study["work"] / "frozen").exists()


def test_private_files_not_staged_or_sent_to_model(study):
    plan = runner.prepare(**study)
    for key, case in plan["cases"].items():
        assert set(case["files"]) == {case["context"]["nodes"][0]["file"]}
    runner.execute(study["work"])
    key = plan["schedule"][0]
    item = runner.read(study["work"] / "state.json")["cases"][key]
    report = runner.read(study["work"] / item["record_file"])["report"]
    assert "PRIVATE-DO-NOT-EXPORT" not in json.dumps(report)


def test_resume_without_case_id_cli_refuses(study):
    runner.prepare(**study)
    result = subprocess.run([sys.executable, "-m", "scripts.harness_study_runner", "resume", "--work", str(study["work"])],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert runner.read(study["work"] / "state.json")["cases"] == {}


def measurements_for(work):
    return {cid: {"schema": "e156-study-measurement-v1", "case_sha256": d["case_sha256"],
        "report_sha256": d["report_sha256"], "review_seconds": 0, "api_cost_usd": None,
        "human_review_cost_usd": None, "evidence_reference": "SYNTHETIC measured fixture",
        "observed_at": runner.now()} for cid, d in runner.records(work).items()}


@pytest.mark.parametrize("phase", ["staging", "published"])
def test_interrupted_freeze_resumes_without_reexecuting(study, monkeypatch, phase):
    runner.prepare(**study); runner.abort(study["work"])
    measurements = measurements_for(study["work"])
    original_mask, original_json = runner.matched.mask, context.atomic_json
    def fail(*args, **kwargs): raise OSError("synthetic freeze interruption")
    def state_failure(path, value, **kwargs):
        if Path(path).name == "state.json" and value.get("frozen"): fail()
        return original_json(path, value, **kwargs)
    if phase == "staging": monkeypatch.setattr(runner.matched, "mask", fail)
    else: monkeypatch.setattr(context, "atomic_json", state_failure)
    with pytest.raises(OSError): runner.freeze(study["work"], measurements)
    assert not runner.read(study["work"] / "state.json")["frozen"]
    assert (study["work"] / "frozen").exists() == (phase == "published")
    monkeypatch.setattr(runner.matched, "mask", original_mask)
    monkeypatch.setattr(context, "atomic_json", original_json)
    monkeypatch.setattr(runner.bounded_native, "run", lambda *a, **k: pytest.fail("freeze must not dispatch"))
    assert runner.freeze(study["work"], measurements)["status"] == "DEVELOPMENT_LEDGER_FROZEN"
    receipt = runner.read(study["work"] / "frozen" / "receipt.json")
    for name, expected in receipt["files"].items():
        assert runner.sha((study["work"] / "frozen" / name).read_bytes()) == expected


def test_reconcile_settles_pending_result_before_changing_journal(study, monkeypatch):
    for fixture in study["fixtures"].values(): fixture["responses"] = [{"synthetic_timeout": True}]
    plan = runner.prepare(**study); key = plan["schedule"][0]
    original = runner._retain
    def fail(*args, **kwargs): raise OSError("synthetic parent loss")
    monkeypatch.setattr(runner, "_retain", fail)
    with pytest.raises(OSError): runner.execute(study["work"])
    monkeypatch.setattr(runner, "_retain", original)
    assert runner.reconcile(study["work"], key, recovery_receipt(study, plan, key))["status"] == "RECONCILED_NOT_RESUMED"
    assert runner.execute(study["work"], resume=key)["runtime_status"] == "COMPLETED"


def reconfigure(study, change):
    graphs = {t["claim_id"]: runner.read(study["evidence"] / t["context_file"]) for t in study["inventory"]["tasks"]}
    for arm, mapping in zip(study["protocol"]["arms"], study["inventory"]["arms"]):
        artifact = runner.read(study["evidence"] / mapping["config_file"])
        cfgs = artifact["configurations"]
        for cid, cfg in cfgs.items():
            cfg["context_sha256"] = context.digest(graphs[cid])
            change(cfg)
        for field, obj in (("config_file", artifact), ("model_config_file", runner.model_contract(cfgs)),
                           ("tools_file", runner.tools_contract(cfgs, graphs, study["inputs"]))):
            write_json(study["evidence"] / mapping[field], obj)
            arm[runner.preflight.ARM_FILES[field]] = context.digest(obj)
    reseal(study)
    study["fixtures"] = {runner.case_id(context.digest(study["protocol"]), a["arm_id"], t["claim_id"]):
        {"input_tokens": 20, "responses": [response()]} for a in study["protocol"]["arms"] for t in study["protocol"]["tasks"]}


def test_actual_child_watchdog_expires_without_parent_supervisor(study, monkeypatch):
    reconfigure(study, lambda cfg: cfg["limits"].update(wall_ms=2000))
    for fixture in study["fixtures"].values():
        fixture["responses"] = [{"synthetic_sleep_ms": 5000, "response": response()}]
    plan = runner.prepare(**study); key = plan["schedule"][0]
    children = []
    def lose_parent(command, **kwargs):
        children.append(subprocess.Popen(command, env=kwargs["environment"], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        raise runner.bounded_native.Refused("synthetic parent supervisor lost")
    monkeypatch.setattr(runner.bounded_native, "run", lose_parent)
    try:
        assert runner.execute(study["work"])["status"] == "EXECUTION_UNKNOWN"
        child = children[0]
        stdout, stderr = child.communicate(timeout=8)
        assert child.returncode == 124, stderr.decode(errors="replace")
        before = runner.read(study["work"] / "state.json")["cases"][key]
        with pytest.raises(context.Refused, match="original case deadline expired"):
            runner.execute(study["work"], resume=key)
        assert runner.read(study["work"] / "state.json")["cases"][key] == before
        runner.abort(study["work"])
        row = runner.records(study["work"])[key]
        assert row["matched_record"]["status"] == "TIMEOUT"
        assert row["matched_record"]["usage"]["model_tokens"] is None
    finally:
        for child in children:
            if child.poll() is None: child.kill()
            child.communicate(timeout=5)


def test_worker_configs_refused_before_preparation(study):
    reconfigure(study, lambda cfg: cfg.update(worker={"unexpected": "worker"}))
    with pytest.raises(context.Refused, match="read-only"): runner.prepare(**study)
    assert not study["work"].exists()


def test_development_protocol_does_not_invent_custody_or_unseen_receipts(study):
    study["protocol"]["purpose"] = "development"
    for role in runner.preflight.REFERENCE_ROLES - {"analysis_plan_reference"}: study["protocol"].pop(role)
    study["inventory"]["references"] = [r for r in study["inventory"]["references"] if r["role"] == "analysis_plan_reference"]
    reconfigure(study, lambda cfg: None)
    result = runner.prepare(**study)
    assert result["protocol"]["purpose"] == "development"
    assert result["scientific_results"] is None


def test_scoped_evidence_tool_round_is_recorded(study):
    raw = b"SYNTHETIC skill: read source evidence only."
    (study["inputs"] / "skill.txt").write_bytes(raw)
    for mapping in study["inventory"]["tasks"]:
        path = study["evidence"] / mapping["context_file"]
        graph = runner.read(path)
        graph["nodes"].append({"id": "read", "kind": "skill", "file": "skill.txt", "sha256": runner.sha(raw),
                               "parents": [], "expires_at": None, "tools": ["read_evidence"]})
        mapping["context_sha256"] = write_json(path, graph)
    reconfigure(study, lambda cfg: cfg.update(skills=["read"]))
    call = response()
    call["output"] = [{"type": "function_call", "call_id": "synthetic-read", "name": "read_evidence",
                        "arguments": '{"id":"source","offset":0,"limit":20}'}]
    for fixture in study["fixtures"].values(): fixture["responses"] = [call, response()]
    plan = runner.prepare(**study)
    assert runner.execute(study["work"])["runtime_status"] == "COMPLETED"
    runner.abort(study["work"])
    draft = runner.records(study["work"])[plan["schedule"][0]]
    assert draft["matched_record"]["usage"]["tool_calls"] == 1
    assert draft["matched_record"]["usage"]["model_tokens"] == 60


def test_future_protocol_refused_before_work_or_dispatch(study):
    study["protocol"]["frozen_at"] = "2099-01-01T00:00:00Z"
    reconfigure(study, lambda cfg: None)
    with pytest.raises(context.Refused, match="future"): runner.prepare(**study)
    assert not study["work"].exists()


def test_future_measurement_refused_before_publication(study):
    runner.prepare(**study); runner.abort(study["work"])
    measurements = measurements_for(study["work"])
    next(iter(measurements.values()))["observed_at"] = "2099-01-01T00:00:00Z"
    with pytest.raises(context.Refused, match="measurement.*freeze"): runner.freeze(study["work"], measurements)
    assert not (study["work"] / "frozen").exists()


def test_actual_child_watchdog_covers_snapshot_validation(tmp_path):
    directory = tmp_path / "case"; directory.mkdir()
    deadline = (context.timestamp(runner.now()) + timedelta(seconds=2)).isoformat()
    code = "from scripts import harness_study_runner as r; import sys,time; from pathlib import Path; r._load=lambda *a: time.sleep(10); r.child(Path(sys.argv[1]),'SYNTHETIC_CONTRACT',sys.argv[2],Path(sys.argv[1])/'attempt-1.json')"
    result = subprocess.run([sys.executable, "-c", code, str(directory), deadline], capture_output=True, timeout=8)
    assert result.returncode == 124, result.stderr.decode(errors="replace")


@pytest.mark.parametrize("phase", ["staging", "published"])
@pytest.mark.parametrize("entry_kind", ["file", "empty_directory"])
def test_freeze_refuses_unmanifested_files_before_publication_or_adoption(study, monkeypatch, phase, entry_kind):
    plan = runner.prepare(**study); runner.abort(study["work"])
    measurements = measurements_for(study["work"])
    state = runner.read(study["work"] / "state.json")
    generation = context.digest({"plan_sha256": context.digest(plan), "measurements": measurements,
        "records": {key: row["record_sha256"] for key, row in state["cases"].items()}})
    destination = study["work"] / "exports" / generation / "bundle"
    if phase == "published":
        original = context.atomic_json
        def fail_state(path, value, **kwargs):
            if Path(path).name == "state.json" and value.get("frozen"): raise OSError("synthetic state commit interruption")
            return original(path, value, **kwargs)
        monkeypatch.setattr(context, "atomic_json", fail_state)
        with pytest.raises(OSError): runner.freeze(study["work"], measurements)
        monkeypatch.setattr(context, "atomic_json", original)
        destination = study["work"] / "frozen"
    destination.mkdir(parents=True, exist_ok=True)
    if entry_kind == "file":
        (destination / "UNMANIFESTED-CANARY.txt").write_text("SYNTHETIC private canary", encoding="utf-8")
    else:
        (destination / "UNMANIFESTED-DIRECTORY").mkdir()
    with pytest.raises(context.Refused, match="unexpected export entry"):
        runner.freeze(study["work"], measurements)
    assert not runner.read(study["work"] / "state.json")["frozen"]
    if phase == "staging": assert not (study["work"] / "frozen").exists()
