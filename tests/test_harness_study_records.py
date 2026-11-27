"""Synthetic adapter contracts only; no provider calls or measured study results."""
import copy
from datetime import timedelta
import hashlib
import socket

import pytest

from scripts import harness_study_records as records
from scripts import harness_runtime as runtime
from scripts import harness_trace as trace
from test_harness_runtime import job, Provider, answer, run
from test_harness_trace import receipt_for, journal_for

context = runtime.context


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Synthetic adapter tests must not use network")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def inputs(job, report, *, outcome="RETURNED", dispatches=1):
    config, manifest, _, _ = job
    source = manifest["nodes"][0]
    arm = {"arm_id": "SYNTHETIC-A", "description": "Synthetic adapter fixture",
           "runtime": "e156", "runtime_version": context.digest(runtime.profile())}
    task = {"claim_id": "SYNTHETIC-T1", "input_file": source["file"], "input_sha256": source["sha256"],
            "source_files": [{"file": source["file"], "sha256": source["sha256"]}]}
    protocol_hash = context.digest({"fixture": "SYNTHETIC adapter contract, no study"})
    began = context.timestamp(report["events"][0]["at"]) if report else context.timestamp("2026-11-26T00:00:00Z")
    ended = context.timestamp(report["events"][-1]["at"]) if report else began
    case = {"schema": "e156-study-case-v1", "protocol_sha256": protocol_hash, "arm_id": arm["arm_id"],
            "claim_id": task["claim_id"], "config_sha256": context.digest(config),
            "context_sha256": context.digest(manifest), "started_at": (began - timedelta(seconds=1)).isoformat(),
            "ended_at": (ended + timedelta(seconds=2)).isoformat(), "dispatches": dispatches,
            "outcome": outcome, "execution_mode": "SYNTHETIC_CONTRACT"}
    case["case_id"] = context.digest({key: case[key] for key in ("protocol_sha256", "arm_id", "claim_id")})
    return case, report, config, manifest, arm, task, protocol_hash


def measurement(args, **changes):
    case, report = args[:2]
    return {"schema": "e156-study-measurement-v1", "case_sha256": context.digest(case),
            "report_sha256": context.digest(report) if report is not None else None,
            "review_seconds": 2.5, "api_cost_usd": None, "human_review_cost_usd": None,
            "evidence_reference": "SYNTHETIC timing fixture, not an actual human measurement",
            "observed_at": (context.timestamp(case["ended_at"]) + timedelta(seconds=1)).isoformat(), **changes}


def rechain(report):
    """Forge a coherent unsigned local chain to exercise semantic checks."""
    previous = None
    for event in report["events"]:
        event["previous"] = previous
        previous = context.digest(event)
    operations = runtime.Journal.operations(report["events"])
    report.update(run_id=context.digest(report["events"][0]), journal_sha256=previous,
                  usage=runtime.Journal.totals(operations), accounting=runtime.accounting(operations))


def tool_response(*, name="read_evidence", args='{"id":"paper","offset":0,"limit":12}'):
    response = answer()
    response["output"] = [{"type": "function_call", "call_id": "SYNTHETIC-tool", "name": name, "arguments": args}]
    return response


def test_completed_record_and_complete_package_use_observations_not_prices(job):
    args = inputs(job, run(job, Provider()))
    draft = records.draft(*args)
    row = draft["matched_record"]
    assert row["status"] == "COMPLETE"
    assert row["prediction"] == {"disposition": "NO_FLAG", "review_seconds": None}
    assert row["usage"] == {"model_tokens": 30, "tool_calls": 0, "api_cost_usd": None, "human_review_cost_usd": None}
    assert row["internal_attempts"] == 1
    assert draft["operation_counts"]["count"]["allocated"] == draft["operation_counts"]["model"]["allocated"] == 1
    assert draft["accounting"]["observed"]["cost_microusd"] == 40
    assert row["wall_seconds"] == (context.timestamp(args[0]["ended_at"]) - context.timestamp(args[0]["started_at"])).total_seconds()
    result = records.finalize(*args, measurement(args))
    package, finalized = result["package"], result["record"]
    raw = records.canonical_bytes(package)
    assert raw.endswith(b"\n") and not raw.startswith(b"\xef\xbb\xbf")
    assert finalized["record_evidence_sha256"] == hashlib.sha256(raw).hexdigest()
    assert finalized["record_evidence_sha256"] != context.digest(package)
    assert finalized["record_evidence_reference"] == "evidence/" + hashlib.sha256(raw).hexdigest() + ".json"
    assert finalized["prediction"]["review_seconds"] == 2.5
    assert finalized["usage"]["api_cost_usd"] is None
    assert package["case"] == args[0] and package["report"] == args[1] and package["draft"] == draft
    assert package["measurement"]["evidence_reference"].startswith("SYNTHETIC")
    assert draft["scientific_validation"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("field,value", [("runtime", "pydantic"), ("runtime_version", "f" * 64)])
def test_records_cannot_relabel_actual_runtime_or_version(job, field, value):
    args = inputs(job, run(job, Provider()))
    args[4][field] = value
    with pytest.raises(context.Refused, match="runtime"):
        records.finalize(*args, measurement(args))


@pytest.mark.parametrize("prediction", [
    {"disposition": "FLAG", "reason": "Synthetic", "flag_root_id": "synthetic-root", "evidence_locator": "paper:0"},
    {"disposition": "ABSTAIN", "reason": "Synthetic", "stop_point": "synthetic-stop"}])
def test_terminal_prediction_is_derived_from_last_settled_response(job, prediction):
    job[0]["routes"]["extract"] = ["small"]
    result = run(job, Provider([answer(records.canonical_bytes(prediction).decode())]))
    row = records.draft(*inputs(job, result))["matched_record"]
    assert row["prediction"] == {k: v for k, v in prediction.items() if k != "reason"} | {"review_seconds": None}


def test_invalid_structured_output_has_exact_runtime_fallback(job):
    job[0]["routes"]["extract"] = ["small"]
    result = run(job, Provider([answer("SYNTHETIC invalid JSON")]))
    row = records.draft(*inputs(job, result))["matched_record"]
    assert row["status"] == "COMPLETE"
    assert row["prediction"] == {"disposition": "ABSTAIN", "stop_point": "OUTPUT_VALIDATION", "review_seconds": None}


def test_unbound_prediction_summary_cannot_become_study_result(job):
    result = run(job, Provider())
    result["prediction"] = {"disposition": "FLAG", "reason": "Synthetic forgery", "flag_root_id": "fake", "evidence_locator": "fake"}
    trace.validate(result)  # Chain integrity alone does not bind this summary.
    with pytest.raises(context.Refused, match="terminal prediction"):
        records.draft(*inputs(job, result))


def test_ambiguous_model_failure_keeps_reservation_separate_and_usage_unknown(job):
    result = run(job, Provider([TimeoutError("SYNTHETIC unknown outcome")]))
    value = records.draft(*inputs(job, result))
    row = value["matched_record"]
    assert row["status"] == "FAILED"  # Generic UNRESOLVED is not proof of a deadline.
    assert row["prediction"] == {"disposition": "ABSTAIN", "stop_point": "RUNTIME_UNRESOLVED", "review_seconds": None}
    assert row["usage"]["model_tokens"] is None and row["usage"]["tool_calls"] == 0
    assert value["accounting"]["observed"]["model_tokens"] == 0
    assert value["accounting"]["unresolved_reserved"]["model_tokens"] == 120
    assert value["operation_counts"]["model"]["unresolved"] == 1


def test_unresolved_tool_does_not_erase_observed_model_usage(job):
    result = run(job, Provider([tool_response(args='{"id":"paper","offset":-1,"limit":12}')]))
    assert result["status"] == "UNRESOLVED"
    value = records.draft(*inputs(job, result))
    assert value["matched_record"]["usage"]["model_tokens"] == 30
    assert value["matched_record"]["usage"]["tool_calls"] is None
    assert value["accounting"]["unresolved_reserved"]["tool_calls"] == 1


@pytest.mark.parametrize("kind", ["BUDGET_STOP", "REFUSED", "CANCELLED"])
def test_noncompleted_returns_abstain(job, kind):
    response = answer()
    if kind == "BUDGET_STOP": job[0]["limits"]["model_calls"] = 0
    elif kind == "REFUSED": response = tool_response(name="unauthorized-synthetic")
    else: response["status"] = "cancelled"
    report = run(job, Provider([response]))
    assert report["status"] == kind
    row = records.draft(*inputs(job, report))["matched_record"]
    assert row["status"] == "FAILED" and row["prediction"]["disposition"] == "ABSTAIN"
    assert row["prediction"]["stop_point"] == "RUNTIME_" + kind


@pytest.mark.parametrize("outcome,status", [("DEADLINE", "TIMEOUT"), ("INTERRUPTED", "FAILED")])
def test_no_report_for_abnormal_case_has_unknown_usage(job, outcome, status):
    value = records.draft(*inputs(job, None, outcome=outcome))
    assert value["matched_record"]["status"] == status
    assert value["matched_record"]["usage"] == {key: None for key in ("model_tokens", "tool_calls", "api_cost_usd", "human_review_cost_usd")}
    assert value["report_sha256"] is value["accounting"] is value["operation_counts"] is None
    with pytest.raises(context.Refused, match="lacks report"):
        records.draft(*inputs(job, None))


def test_deadline_overrides_even_an_available_completed_response(job):
    row = records.draft(*inputs(job, run(job, Provider()), outcome="DEADLINE"))["matched_record"]
    assert row["status"] == "TIMEOUT" and row["prediction"]["disposition"] == "ABSTAIN"
    assert row["usage"]["model_tokens"] == 30


def test_not_attempted_has_zero_dispatch_and_known_zero_usage(job):
    args = inputs(job, None, outcome="NOT_ATTEMPTED", dispatches=0)
    value = records.draft(*args)
    row = value["matched_record"]
    assert row["status"] == "NOT_ATTEMPTED" and row["internal_attempts"] == 0
    assert row["prediction"]["disposition"] == "ABSTAIN"
    assert row["usage"] == {"model_tokens": 0, "tool_calls": 0, "api_cost_usd": None, "human_review_cost_usd": None}
    finalized = records.finalize(*args, measurement(args, review_seconds=0))
    assert finalized["record"]["prediction"]["review_seconds"] == 0
    args[0]["dispatches"] = 1
    with pytest.raises(context.Refused, match="unattempted"):
        records.draft(*args)
    with pytest.raises(context.Refused, match="unattempted"):
        records.draft(*inputs(job, run(job, Provider()), outcome="NOT_ATTEMPTED", dispatches=0))


def test_recovery_preserves_whole_lifecycle_and_counts_dispatches_not_operations(job):
    provider = Provider([TimeoutError("SYNTHETIC interrupted call")])
    run(job, provider)
    journal_for(job).reconcile(receipt_for(job))
    report = run(job, provider, create=False)
    args = inputs(job, report, dispatches=2)
    args[0]["started_at"] = (context.timestamp(args[0]["started_at"]) - timedelta(seconds=120)).isoformat()
    value = records.draft(*args)
    assert provider.calls == provider.counts == 1
    assert value["matched_record"]["internal_attempts"] == 2
    assert value["matched_record"]["wall_seconds"] >= 123
    assert value["matched_record"]["usage"]["model_tokens"] == 30
    assert value["operation_counts"]["model"] == {"allocated": 1, "finished": 0, "reconciled": 1, "unresolved": 0}
    assert value["accounting"]["recovered_wall_reserved"]["wall_ms"] > 0
    assert value["accounting"]["unresolved_reserved"] == runtime.units()


@pytest.mark.parametrize("field,value", [("dispatches", 0), ("dispatches", True), ("dispatches", -1),
    ("outcome", "UNKNOWN"), ("execution_mode", "UNKNOWN"), ("case_id", "f" * 64),
    ("protocol_sha256", "f" * 64), ("config_sha256", "f" * 64), ("context_sha256", "f" * 64),
    ("claim_id", "another"), ("arm_id", "another"), ("started_at", "2099-01-01T00:00:00Z"),
    ("ended_at", "2000-01-01T00:00:00Z")])
def test_invalid_case_scope_lifecycle_or_dispatches_refused(job, field, value):
    args = inputs(job, run(job, Provider()))
    args[0][field] = value
    with pytest.raises(context.Refused): records.draft(*args)


@pytest.mark.parametrize("defect", ["extra", "missing", "task_hash", "task_file", "source_hash", "duplicate_source", "wrong_profile", "event_time"])
def test_exact_contract_and_context_trace_binding(job, defect):
    args = inputs(job, run(job, Provider()))
    if defect == "extra": args[0]["invented"] = True
    elif defect == "missing": args[0].pop("ended_at")
    elif defect == "task_hash": args[5]["input_sha256"] = "f" * 64
    elif defect == "task_file": args[5]["input_file"] = "another.txt"
    elif defect == "source_hash": args[5]["source_files"][0]["sha256"] = "f" * 64
    elif defect == "duplicate_source": args[5]["source_files"] *= 2
    elif defect == "wrong_profile":
        args[1]["events"][0]["anchor"]["code"]["harness_runtime.py"] = "f" * 64
        rechain(args[1])
    else:
        args[1]["events"][-1]["at"] = "2099-01-01T00:00:00Z"
        rechain(args[1])
    with pytest.raises(context.Refused): records.draft(*args)


def test_forged_settled_usage_is_recomputed_from_raw_response(job):
    report = run(job, Provider())
    report["events"][-1]["usage"]["model_tokens"] = 1
    rechain(report)
    trace.validate(report)
    with pytest.raises(context.Refused, match="observed operation usage"):
        records.draft(*inputs(job, report))


@pytest.mark.parametrize("defect", ["tool", "cancelled", "empty"])
def test_completed_status_cannot_hide_missing_terminal_model(job, defect):
    if defect == "tool":
        job[0]["limits"]["model_calls"] = 1
        report = run(job, Provider([tool_response()]))
    elif defect == "empty":
        job[0]["limits"]["model_calls"] = 0
        report = run(job, Provider())
    else:
        response = answer()
        response["status"] = "cancelled"
        report = run(job, Provider([response]))
    report["status"] = "COMPLETED"
    report["prediction"] = {"disposition": "ABSTAIN", "reason": "Invalid structured response", "stop_point": "OUTPUT_VALIDATION"}
    with pytest.raises(context.Refused): records.draft(*inputs(job, report))


@pytest.mark.parametrize("field,value", [("review_seconds", None), ("review_seconds", True),
    ("review_seconds", -1), ("review_seconds", float("nan")), ("api_cost_usd", float("inf")),
    ("human_review_cost_usd", -1), ("case_sha256", "f" * 64), ("report_sha256", "f" * 64),
    ("evidence_reference", ""), ("observed_at", "2000-01-01T00:00:00Z")])
def test_missing_invalid_or_unbound_measurements_cannot_finalize(job, field, value):
    args = inputs(job, run(job, Provider()))
    with pytest.raises(context.Refused):
        records.finalize(*args, measurement(args, **{field: value}))


@pytest.mark.parametrize("defect", ["extra", "missing"])
def test_measurement_schema_is_exact(job, defect):
    args = inputs(job, run(job, Provider()))
    measured = measurement(args)
    if defect == "extra": measured["approval"] = "invented"
    else: measured.pop("review_seconds")
    with pytest.raises(context.Refused): records.finalize(*args, measured)


def test_editable_draft_is_not_authority_and_package_is_detached(job):
    args = inputs(job, run(job, Provider()))
    draft = records.draft(*args)
    draft["matched_record"]["prediction"]["disposition"] = "FLAG"
    measured = measurement(args, api_cost_usd=0.001, human_review_cost_usd=0.02)
    result = records.finalize(*args, measured)
    assert result["record"]["prediction"]["disposition"] == "NO_FLAG"
    assert result["record"]["usage"]["api_cost_usd"] == 0.001
    before = records.canonical_bytes(result["package"])
    args[0]["dispatches"] = 99
    measured["review_seconds"] = 99
    assert records.canonical_bytes(result["package"]) == before
    modified = copy.deepcopy(result["package"])
    modified["measurement"]["review_seconds"] = 99
    assert hashlib.sha256(records.canonical_bytes(modified)).hexdigest() != result["record"]["record_evidence_sha256"]


def explicit_policy(job):
    job[0]["request_policy"] = {"service_tier": "default"}
    response = answer()
    response.update(model=job[0]["models"]["small"]["model"], service_tier="default")
    return response


def forge_requests(report, mutate, categories=("count", "model")):
    """Rehash malicious requests so rejection depends on semantics, not broken hashes."""
    for event in report["events"]:
        if event["kind"] == "RESERVED" and event["id"].split(":", 1)[0] in categories:
            mutate(event["request"])
            event["request_sha256"] = context.digest(event["request"])
    rechain(report)
    trace.validate(report)


@pytest.mark.parametrize("field,value", [("service_tier", "flex"), ("parallel_tool_calls", True),
    ("parallel_tool_calls", 0), ("store", True), ("store", 0), ("include", []),
    ("include", ["reasoning.encrypted_content", "unexpected"]), ("temperature", 0.9)])
def test_coherently_rehashed_requests_cannot_change_frozen_policy(job, field, value):
    response = explicit_policy(job)
    report = run(job, Provider([response]))
    forge_requests(report, lambda request: request.update({field: value}))
    with pytest.raises(context.Refused, match="request"):
        records.draft(*inputs(job, report))


@pytest.mark.parametrize("field", ["service_tier", "parallel_tool_calls", "store", "include"])
def test_missing_static_request_fields_are_not_defaulted(job, field):
    report = run(job, Provider([explicit_policy(job)]))
    forge_requests(report, lambda request: request.pop(field))
    with pytest.raises(context.Refused, match="model request fields"):
        records.draft(*inputs(job, report))


def test_configured_model_outside_selected_route_cannot_supply_record(job):
    job[0]["routes"]["extract"] = ["small"]
    report = run(job, Provider())
    forge_requests(report, lambda request: request.update(model=job[0]["models"]["large"]["model"]))
    with pytest.raises(context.Refused, match="selected-route"):
        records.draft(*inputs(job, report))


@pytest.mark.parametrize("stage", ["count", "model"])
def test_unresolved_reservations_still_validate_static_request_contract(job, stage):
    explicit_policy(job)
    class FailingCount(Provider):
        def count(self, payload, timeout):
            raise TimeoutError("SYNTHETIC ambiguous input count")
    provider = FailingCount() if stage == "count" else Provider([TimeoutError("SYNTHETIC ambiguous model")])
    report = run(job, provider)
    assert report["status"] == "UNRESOLVED"
    forge_requests(report, lambda request: request.update(service_tier="flex"), categories=(stage,))
    with pytest.raises(context.Refused, match="frozen request policy"):
        records.draft(*inputs(job, report))


@pytest.mark.parametrize("field,value", [("model", "synthetic-other-model"), ("service_tier", "flex"),
                                         ("model", None), ("service_tier", None)])
def test_explicit_policy_requires_matching_settled_response_metadata(job, field, value):
    response = explicit_policy(job)
    report = run(job, Provider([response]))
    if value is None:
        report["events"][-1]["data"].pop(field)
    else:
        report["events"][-1]["data"][field] = value
    rechain(report)
    trace.validate(report)
    with pytest.raises(context.Refused, match="response model/service-tier"):
        records.draft(*inputs(job, report))


def test_explicit_policy_and_recovery_accept_matching_response_metadata(job):
    response = explicit_policy(job)
    provider = Provider([TimeoutError("SYNTHETIC ambiguous request")])
    run(job, provider)
    journal_for(job).reconcile(receipt_for(job, response))
    report = run(job, provider, create=False)
    draft = records.draft(*inputs(job, report, dispatches=2))
    assert draft["matched_record"]["status"] == "COMPLETE"
    assert draft["operation_counts"]["model"]["reconciled"] == 1
    assert draft["matched_record"]["usage"]["model_tokens"] == 30
