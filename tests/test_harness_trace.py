"""Synthetic fault injection and portable offline transcript contracts."""
import copy
import json
import os
import sqlite3
import subprocess
import sys
import threading

import pytest

from scripts import harness_trace as trace
from scripts import harness_runtime as runtime
from scripts import harness_context as context
from test_harness_runtime import job, Provider, answer, run


def receipt_for(job, response=None):
    config, manifest, root, state = job
    journal = runtime.Journal(state, config, manifest, root)
    events = journal.events()
    reservation = runtime.Journal.operations(events)["model:0"]["reservation"]
    response = response or answer()
    return {"schema": "e156-harness-recovery-v1", "operation_id": "model:0",
            "journal_sha256": context.digest(events[-1]), "reservation_sha256": context.digest(reservation),
            "request_sha256": reservation["request_sha256"], "config_sha256": context.digest(config),
            "context_sha256": context.digest(manifest), "response_sha256": context.digest(response), "response": response,
            "reviewer": "Synthetic reviewer", "reason": "Synthetic recovery exercise",
            "evidence_reference": "Synthetic archived response fixture",
            "attestation": "I verified this terminal response belongs to this exact request"}


def journal_for(job):
    config, manifest, root, state = job
    return runtime.Journal(state, config, manifest, root)


def test_reservation_waits_for_short_reader_lock_without_repeating_action(job, monkeypatch):
    config, manifest, root, state = job
    journal = runtime.Journal(state, config, manifest, root, create=True)
    reader = sqlite3.connect(state, check_same_thread=False)
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM events").fetchall()
    appended = threading.Event()
    original_append = journal._append
    def append(con, events, event):
        original_append(con, events, event)
        if event["kind"] == "RESERVED": appended.set()
    monkeypatch.setattr(journal, "_append", append)
    def release_reader():
        appended.wait(2)
        # Force COMMIT to encounter the shared reader before releasing it.
        threading.Event().wait(.1)
        reader.rollback()
        reader.close()
    releaser = threading.Thread(target=release_reader)
    releaser.start()
    calls = []
    try:
        journal.operation("synthetic-lock", {}, runtime.units(tool_calls=1, wall_ms=1000),
                          lambda timeout: (calls.append("once") or {}, runtime.units(tool_calls=1)))
    finally:
        releaser.join(3)
    assert not releaser.is_alive()
    assert calls == ["once"]
    assert journal.events()[-1]["kind"] == "FINISHED"


def test_long_reader_lock_refuses_before_side_effect(job):
    config, manifest, root, state = job
    config["limits"]["request_ms"] = 20
    journal = runtime.Journal(state, config, manifest, root, create=True)
    reader = sqlite3.connect(state)
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM events").fetchall()
    calls = []
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            journal.operation("synthetic-lock", {}, runtime.units(tool_calls=1, wall_ms=20),
                              lambda timeout: (calls.append("unexpected") or {}, runtime.units(tool_calls=1)))
    finally:
        reader.rollback()
        reader.close()
    assert calls == []
    assert len(journal.events()) == 1


def test_recovery_resumes_without_repeating_accepted_call_and_retains_history(job):
    provider = Provider([TimeoutError("synthetic ambiguous outcome")])
    interrupted = run(job, provider)
    assert interrupted["accounting"]["observed"]["model_tokens"] == 0
    assert interrupted["accounting"]["unresolved_reserved"]["model_tokens"] == 120
    receipt = receipt_for(job)
    recovered = journal_for(job).reconcile(receipt)
    resumed = run(job, provider, create=False)
    assert resumed["status"] == "COMPLETED" and provider.calls == provider.counts == 1
    assert recovered["events"][:-1] == interrupted["events"]
    assert recovered["accounting"]["observed"]["model_tokens"] == 30
    assert recovered["accounting"]["unresolved_reserved"] == runtime.units()
    assert recovered["accounting"]["recovered_wall_reserved"]["wall_ms"] > 0
    assert resumed["actual_billed_usd"] is None
    exported = trace.export(resumed)
    assert exported["attempts"][1]["history"] == ["RESERVED", "UNRESOLVED", "RECONCILED"]
    assert exported["attempts"][1]["wall_basis"] == "RESERVATION_CEILING"
    with pytest.raises(context.Refused, match="stale"):
        journal_for(job).reconcile(receipt)


@pytest.mark.parametrize("defect", ["tip", "request", "response_digest", "config", "attestation", "reviewer", "nonterminal", "overrun", "provider_id"])
def test_recovery_rejects_unbound_or_invalid_evidence_without_journal_change(job, defect):
    raw = answer()
    raw["status"] = "in_progress"
    run(job, Provider([raw]))
    receipt = receipt_for(job)
    if defect in {"tip", "request", "response_digest", "config"}:
        receipt[{"tip": "journal_sha256", "request": "request_sha256", "response_digest": "response_sha256", "config": "config_sha256"}[defect]] = "f" * 64
    elif defect in {"attestation", "reviewer"}:
        receipt[defect] = ""
    else:
        if defect == "nonterminal": receipt["response"]["status"] = "queued"
        elif defect == "provider_id": receipt["response"]["id"] = "different-synthetic-id"
        else: receipt["response"]["usage"] = {"input_tokens": 21, "output_tokens": 10, "total_tokens": 31}
        receipt["response_sha256"] = context.digest(receipt["response"])
    before = journal_for(job).events()
    with pytest.raises(context.Refused):
        journal_for(job).reconcile(receipt)
    assert journal_for(job).events() == before


@pytest.mark.parametrize("late_error", [False, True])
def test_recovered_pending_call_fences_late_executor(job, late_error):
    class ConcurrentRecovery(Provider):
        def respond(self, payload, timeout):
            self.calls += 1
            journal_for(job).reconcile(receipt_for(job))
            if late_error:
                raise TimeoutError("synthetic late failure")
            return answer()
    provider = ConcurrentRecovery()
    result = run(job, provider)
    assert result["status"] == "REFUSED"
    assert result["events"][-1]["kind"] == "RECONCILED"
    assert len(result["events"]) == 5
    assert run(job, provider, create=False)["status"] == "COMPLETED"
    assert provider.calls == 1


def test_recovery_revalidates_sources(job):
    run(job, Provider([TimeoutError()]))
    receipt = receipt_for(job)
    (job[2] / "paper.txt").write_text("changed synthetic source", encoding="utf-8")
    with pytest.raises(context.Refused):
        journal_for(job).reconcile(receipt)


def test_export_omits_prompt_response_source_and_operator_content(job):
    job[0]["task"] = "private-task-canary"
    result = run(job, Provider([TimeoutError()]))
    receipt = receipt_for(job, answer('{"disposition":"NO_FLAG","reason":"private-response-canary"}'))
    receipt["reviewer"] = "private-reviewer-canary"
    journal_for(job).reconcile(receipt)
    result = run(job, Provider(), create=False)
    public = trace.export(result)
    serialized = json.dumps(public)
    for forbidden in ("private-task-canary", "private-response-canary", "private-reviewer-canary", "SYNTHETIC source fixture", "synthetic-response"):
        assert forbidden not in serialized
    assert trace.export(result) == public
    assert public["run_id"] == trace.export(journal_for(job).report("INSPECTED"))["run_id"]
    assert public["actual_billed_usd"] is None
    assert len(public["attempts"]) == 2


@pytest.mark.parametrize("defect", ["event", "usage", "anchor", "accounting", "identity", "completed_unknown"])
def test_trace_rejects_tampered_chain_or_summaries(job, defect):
    result = run(job, Provider([TimeoutError()]) if defect == "completed_unknown" else Provider())
    if defect == "event": result["events"][1]["request"]["model"] = "different"
    elif defect == "usage": result["usage"]["model_tokens"] = 0
    elif defect == "anchor": result["context_sha256"] = "f" * 64
    elif defect == "accounting": result["accounting"]["observed"]["model_tokens"] = 0
    elif defect == "identity": result["run_id"] = "f" * 64
    else: result["status"] = "COMPLETED"
    with pytest.raises(context.Refused):
        trace.export(result)


def test_offline_replay_recomputes_tool_and_consumes_complete_transcript(job):
    tool = answer()
    tool["output"] = [{"type": "function_call", "call_id": "synthetic-call", "name": "read_evidence",
                       "arguments": '{"id":"paper","offset":0,"limit":12}'}]
    provider = Provider([tool, answer()])
    original = run(job, provider)
    config, manifest, root, _ = job
    result = trace.replay(original, config, manifest, root, root / "replay.sqlite")
    assert result["verdict"] == "PASS" and all(result["checks"].values())
    assert result["run"]["usage"]["tool_calls"] == 1
    assert provider.calls == 2  # Replay had no access to the original provider.
    assert result["scientific_disposition"] == "HOLD"


def test_offline_provider_refuses_request_drift_or_extra_calls(job):
    result = run(job, Provider())
    provider = trace.RecordedProvider(result)
    request = copy.deepcopy(result["events"][1]["request"])
    with pytest.raises(context.Refused, match="mismatch"):
        provider.count({**request, "model": "changed"}, 1)
    provider.count(request, 1)
    provider.respond(request, 1)
    with pytest.raises(context.Refused, match="unrecorded"):
        provider.respond(request, 1)


def test_unresolved_trace_cannot_seed_successful_regression(job):
    result = run(job, Provider([TimeoutError()]))
    with pytest.raises(context.Refused):
        trace.RecordedProvider(result)
    assert trace.export(result)["attempts"][1]["usage"] is None


def test_replay_input_or_source_drift_refused_before_execution(job):
    original = run(job, Provider())
    config, manifest, root, _ = job
    with pytest.raises(context.Refused, match="binding"):
        trace.replay(original, {**config, "task": "changed"}, manifest, root, root / "replay.sqlite")
    (root / "paper.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(context.Refused):
        trace.replay(original, config, manifest, root, root / "replay.sqlite")
    assert not (root / "replay.sqlite").exists()


def test_replay_reports_output_regression(job, monkeypatch):
    original = run(job, Provider())
    monkeypatch.setattr(runtime, "prediction", lambda response: {"disposition": "NO_FLAG", "reason": "changed"})
    config, manifest, root, _ = job
    result = trace.replay(original, config, manifest, root, root / "replay.sqlite")
    assert result["verdict"] == "FAIL" and not result["checks"]["prediction_matches"]


@pytest.mark.parametrize("defect", ["price", "tokens"])
def test_replay_detects_non_wall_accounting_regression(job, monkeypatch, defect):
    original = run(job, Provider())
    if defect == "price":
        monkeypatch.setattr(runtime, "price", lambda *args: 0)
    else:
        validate_usage = runtime.model_usage
        def undercount(*args):
            usage = validate_usage(*args)
            usage["model_tokens"] = 0
            return usage
        monkeypatch.setattr(runtime, "model_usage", undercount)
    config, manifest, root, _ = job
    result = trace.replay(original, config, manifest, root, root / "replay.sqlite")
    assert result["verdict"] == "FAIL" and not result["checks"]["resource_accounting_matches"]
    assert result["checks"]["prediction_matches"] and result["checks"]["operation_results_match"]


def test_cli_recovery_export_and_replay_need_no_credentials(job):
    run(job, Provider([TimeoutError()]))
    config, manifest, root, state = job
    for name, data in (("config", config), ("manifest", manifest), ("receipt", receipt_for(job))):
        (root / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    command = [sys.executable, "-m", "scripts.harness_runtime", "reconcile", "--config", str(root / "config.json"),
               "--manifest", str(root / "manifest.json"), "--root", str(root), "--state", str(state),
               "--receipt", str(root / "receipt.json"), "--output", str(root / "recovered.json")]
    recovered = subprocess.run(command, capture_output=True, text=True, env=env, timeout=20)
    assert recovered.returncode == 0, recovered.stderr
    (root / "run.json").write_text(json.dumps(run(job, Provider(), create=False)), encoding="utf-8")
    base = [sys.executable, "-m", "scripts.harness_trace"]
    exported = subprocess.run(base + ["export", "--input", str(root / "run.json"), "--output", str(root / "public.json")],
                              capture_output=True, text=True, env=env, timeout=20)
    assert exported.returncode == 0, exported.stderr
    replayed = subprocess.run(base + ["replay", "--input", str(root / "run.json"), "--output", str(root / "regression.json"),
                                "--config", str(root / "config.json"), "--manifest", str(root / "manifest.json"),
                                "--root", str(root), "--state", str(root / "replay.sqlite")],
                              capture_output=True, text=True, env=env, timeout=20)
    assert replayed.returncode == 0, replayed.stderr
    assert json.loads((root / "regression.json").read_text())["verdict"] == "PASS"
