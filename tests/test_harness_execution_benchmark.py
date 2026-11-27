"""Framework-independent controls for the comparative execution apparatus."""
import copy
import hashlib
import json
import shutil
import subprocess
from types import SimpleNamespace
import pytest

from scripts import harness_execution_benchmark as benchmark


@pytest.fixture(scope="module")
def observed_example():
    protocol = benchmark.load(benchmark.PROTOCOL)
    case = benchmark.load(benchmark.ROOT / "benchmarks/harness-execution-development.json")[1]
    row = benchmark.worker(case, "e156_baseline", protocol)
    return case, row, protocol


@pytest.fixture
def example(observed_example):
    # Worker observations and expected cases cross a JSON boundary in the real
    # suite. Isolate them so mutating telemetry cannot also mutate its oracle.
    case, row, protocol = observed_example
    return copy.deepcopy(case), copy.deepcopy(row), copy.deepcopy(protocol)


def test_positive_control_requires_completion_evidence_and_unchanged_source(example):
    case, row, protocol = example
    assert all(benchmark.grade(case, row, protocol).values())
    for mutation in ({"terminal_status": "REFUSED", "prediction": None}, {"successful_tool_results": []},
                     {"source_after_sha256": "f" * 64}, {"prediction": {"disposition": "ABSTAIN"}},
                     {"observed_model_calls": 7}, {"observed_tool_attempts": 7}):
        changed = {**row, **mutation}
        assert not all(benchmark.grade(case, changed, protocol).values())


def test_oracle_detects_invented_excerpt_or_unauthorized_execution(example):
    case, row, protocol = example
    for field, value in (("text", "invented"), ("sha256", "0" * 64), ("offset", 99)):
        changed = copy.deepcopy(row)
        changed["successful_tool_results"][0]["result"][field] = value
        assert not benchmark.grade(case, rehash(changed), protocol)["valid_successes"]
    changed = copy.deepcopy(row)
    changed["successful_tool_results"][0]["request"]["name"] = "execute"
    assert not benchmark.grade(case, rehash(changed), protocol)["valid_successes"]


def test_stops_and_provider_failures_cannot_fabricate_predictions(example):
    _, _, protocol = example
    case = development_case("repeated_result")
    row = benchmark.worker(case, "e156_guarded", protocol)
    assert all(benchmark.grade(case, row, protocol).values())
    assert not all(benchmark.grade(case, {**row, "prediction": {"disposition": "NO_FLAG"}}, protocol).values())
    case = development_case("provider_timeout")
    row = benchmark.worker(case, "e156_baseline", protocol)
    assert all(benchmark.grade(case, row, protocol).values())
    for changes in ({"terminal_status": "ERROR"}, {"terminal_status": "unknown"}, {"provider_failures": 2},
                    {"provider_failure_retained": False}, {"first_provider_failure_call": 2}):
        assert not all(benchmark.grade(case, {**row, **changes}, protocol).values())


def development_case(family):
    cases = benchmark.load(benchmark.ROOT / "benchmarks/harness-execution-development.json")
    return next(case for case in cases if case["family"] == family)


def rehash(row):
    row["raw_trace_sha256"] = benchmark.context.digest(row["trace"])
    return row


def scripted_abstention(case, row, messages=(), dialect="langchain"):
    """A complete synthetic native-feedback transcript, with an actual answer step."""
    row = copy.deepcopy(row)
    row["trace"] = [event for event in row["trace"] if event["kind"] not in {"native_run", "native_messages", "terminal_exception"}]
    step = case["steps"][0]
    previous = ({"type": "ai", "content": "", "tool_calls": [
        {"name": step["name"], "args": step["args"], "id": step["call_id"]}]} if dialect == "langchain" else
        {"kind": "response", "parts": [{"part_kind": "tool-call", "tool_name": step["name"],
            "args": step["args"], "tool_call_id": step["call_id"]}]})
    history = [previous, *messages]
    row["trace"].append({"kind": "model", "index": 1, "request": history, "script": case["steps"][1]})
    text = benchmark.answer(case["steps"][1])
    last = ({"type": "ai", "content": text} if dialect == "langchain" else
            {"kind": "response", "parts": [{"part_kind": "text", "content": text}]})
    row["trace"].append({"kind": "native_messages", "messages": [*history, last]})
    row.update(terminal_status="COMPLETED", prediction=json.loads(text), observed_model_calls=2, error=None)
    return rehash(row)


def test_abstention_requires_retained_refusal():
    case = development_case("unknown_tool")
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, "e156_baseline", protocol)
    assert not all(benchmark.grade(case, {**row, "prediction": {"disposition": "ABSTAIN"}}, protocol).values())
    row = scripted_abstention(case, row)
    assert all(benchmark.grade(case, row, protocol).values())
    for changes in ({"refusal_evidence": [], "refusal_retained": False}, {"trace": []},
                    {"refusal_retained": False}, {"prediction": {"disposition": "NO_FLAG"}}):
        assert not all(benchmark.grade(case, {**row, **changes}, protocol).values())


@pytest.mark.parametrize("arm", ["e156_baseline", "e156_guarded"])
@pytest.mark.parametrize("family,cause", [("unknown_tool", "unauthorized_tool"),
                                        ("invalid_arguments", "invalid_arguments"),
                                        ("source_drift", "source_drift")])
def test_legitimate_e156_refusals_have_explicit_bound_causes(arm, family, cause):
    case = development_case(family)
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, arm, protocol)
    assert row["contract_satisfied"] and row["refusal_retained"]
    assert row["prediction"] is None and not row["apparatus_errors"]
    assert row["refusal_evidence"]
    assert {event["cause"] for event in row["refusal_evidence"]} == {cause}
    assert all(event in row["trace"] and event["reason"] for event in row["refusal_evidence"])
    changed = copy.deepcopy(row)
    changed["refusal_evidence"][0]["request"] = {"name": "unrelated", "arguments": {}}
    assert not all(benchmark.grade(case, rehash(changed), protocol).values())


@pytest.mark.parametrize("arm", ["e156_baseline", "e156_guarded"])
@pytest.mark.parametrize("fault", [RuntimeError, ValueError])
@pytest.mark.parametrize("boundary", ["tool", "provider"])
def test_swallowed_callback_faults_are_apparatus_errors(monkeypatch, arm, fault, boundary):
    case = development_case("invalid_arguments")
    protocol = benchmark.load(benchmark.PROTOCOL)
    operation, require = benchmark.runtime.Journal.operation, benchmark.runtime.require
    def broken(*args, **kwargs):
        raise fault("deliberately injected unexpected callback failure")
    if boundary == "tool":
        # This is the review's original reproducer: fail before Observer.invoke
        # can record a legitimate tool-validation refusal.
        monkeypatch.setattr(benchmark.Observer, "invoke", broken)
    else:
        monkeypatch.setattr(benchmark.runtime, "response_usage", broken)
    row = benchmark.worker(case, arm, protocol)
    assert row["terminal_status"] == "ERROR" and not row["contract_satisfied"]
    assert row["error"]["type"] == "builtins." + fault.__name__
    assert row["apparatus_errors"] and not row["refusal_evidence"]
    assert benchmark.runtime.Journal.operation is operation and benchmark.runtime.require is require
    native = next(event["report"] for event in row["trace"] if event["kind"] == "native_run")
    assert native["status"] == "UNRESOLVED"  # Production fail-closed behavior is preserved.
    summary = benchmark.summarize([row])[0]
    assert summary["attempted"] == summary["apparatus_errors"] == 1
    assert summary["satisfied"] == 0


@pytest.mark.parametrize("fault", [RuntimeError, benchmark.context.Refused])
def test_unexpected_fault_cannot_hide_behind_an_earlier_refusal(monkeypatch, fault):
    case = development_case("invalid_arguments")
    protocol = benchmark.load(benchmark.PROTOCOL)
    original = benchmark.Observer.invoke
    def broken(self, *args, **kwargs):
        try:
            return original(self, *args, **kwargs)
        except benchmark.context.Refused:
            raise fault("unexpected failure after the expected refusal") from None
    monkeypatch.setattr(benchmark.Observer, "invoke", broken)
    row = benchmark.worker(case, "e156_baseline", protocol)
    assert row["refusal_evidence"] and row["apparatus_errors"]
    assert row["terminal_status"] == "ERROR" and not row["contract_satisfied"]


@pytest.mark.parametrize("exception", [RuntimeError("unexpected adapter fault"),
                                      benchmark.context.Refused("unrecognized refusal cause")])
def test_unrecognized_adapter_failures_cannot_pass_refusal(monkeypatch, exception):
    def broken(*args, **kwargs):
        raise exception
    monkeypatch.setattr(benchmark, "e156", broken)
    row = benchmark.worker(development_case("unknown_tool"), "e156_baseline", benchmark.load(benchmark.PROTOCOL))
    assert row["terminal_status"] == "ERROR" and not row["contract_satisfied"]
    assert row["apparatus_errors"] and not row["refusal_retained"]


def test_refusal_oracle_rejects_contradictions_and_unsupported_causes():
    case = development_case("invalid_arguments")
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, "e156_baseline", protocol)
    assert row["terminal_status"] == "UNRESOLVED" and row["contract_satisfied"]
    for changes in ({"prediction": {"disposition": "NO_FLAG"}},
                    {"prediction": {"disposition": "ABSTAIN"}},
                    {"refusal_evidence": [], "refusal_retained": False},
                    {"apparatus_errors": [{"type": "builtins.RuntimeError"}]},
                    {"trace": []}):
        assert not all(benchmark.grade(case, {**row, **changes}, protocol).values())
    changed = copy.deepcopy(row)
    changed["refusal_evidence"][0]["cause"] = "source_drift"
    assert not all(benchmark.grade(case, rehash(changed), protocol).values())
    changed = copy.deepcopy(row)
    changed["refusal_evidence"][0]["reason"] = "unrecognized guard failure"
    assert not all(benchmark.grade(case, rehash(changed), protocol).values())


@pytest.mark.parametrize("changes", [
    {"observed_model_calls": -1}, {"observed_model_calls": 0}, {"observed_model_calls": True},
    {"observed_tool_attempts": -1}, {"observed_tool_attempts": False},
    {"successful_tool_results": None}, {"successful_tool_results": [{}]},
    {"prediction": "NO_FLAG"}, {"refusal_evidence": None}, {"apparatus_errors": None},
    {"refusal_retained": "false"}, {"unauthorized_success": "false"},
    {"source_before_sha256": "not a digest"}, {"terminal_status": []},
])
def test_malformed_observations_fail_closed_without_crashing(example, changes):
    case, row, protocol = example
    assert not all(benchmark.grade(case, {**row, **changes}, protocol).values())
    assert not all(benchmark.grade(case, {}, protocol).values())


def test_native_refusal_feedback_is_bound_to_the_original_model_call(tmp_path):
    case = development_case("unknown_tool")
    obs = benchmark.Observer(case, tmp_path, {})
    obs.step([])
    obs.step([])  # Final answer; history still contains feedback for the first call.
    message = {"type": "tool", "status": "error", "name": "not_authorized",
               "tool_call_id": "bad", "content": "Unknown tool"}
    obs.feedback([message], "langchain")
    obs.feedback([message], "langchain")
    assert len(obs.refusal_evidence) == 1
    assert obs.refusal_evidence[0]["model_call"] == 1
    assert obs.refusal_evidence[0]["cause"] == "unauthorized_tool"


@pytest.mark.parametrize("dialect,message", [
    ("langchain", {"type": "tool", "status": "error", "name": "not_authorized",
                   "tool_call_id": "bad", "content": "Unknown tool"}),
    ("pydantic", {"parts": [{"part_kind": "tool-return", "outcome": "retried",
                             "tool_name": "not_authorized", "tool_call_id": "bad",
                             "retry": {"cause": "unknown_tool"}}]}),
])
def test_native_refusal_cause_requires_matching_feedback(tmp_path, dialect, message):
    case = development_case("unknown_tool")
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, "e156_baseline", protocol)
    obs = benchmark.Observer(case, tmp_path, {})
    obs.step([])
    obs.feedback([message], dialect)
    row.update(refusal_evidence=obs.refusal_evidence, trace=obs.events)
    row = scripted_abstention(case, row, [message], dialect)
    assert all(benchmark.grade(case, row, protocol).values())
    for bad_reason in ('not JSON', '{}', json.dumps({"tool_call_id": "other"})):
        changed = copy.deepcopy(row)
        changed["refusal_evidence"][0]["reason"] = bad_reason
        assert not all(benchmark.grade(case, rehash(changed), protocol).values())


def test_coercion_cannot_borrow_a_future_valid_request(example):
    case, row, protocol = copy.deepcopy(example)
    future = copy.deepcopy(case["steps"][0])
    case["steps"].insert(1, future)
    case["steps"][0]["args"]["offset"] = "0"
    row["successful_tool_results"] = row["successful_tool_results"][:1]
    assert not benchmark.grade(case, row, protocol)["valid_successes"]


def test_native_feedback_uses_structure_not_source_text(tmp_path):
    obs = benchmark.Observer({}, tmp_path, {})
    obs.feedback([{"type": "human", "content": 'Unknown tool name, status: error'}], "langchain")
    assert not obs.native_refusal
    obs.feedback([{"type": "tool", "status": "error"}], "langchain")
    assert obs.native_refusal
    obs.native_refusal = False
    obs.feedback([{"parts": [{"part_kind": "tool-return", "outcome": "retried"}]}], "pydantic")
    assert obs.native_refusal


def test_all_error_rows_remain_in_summary(example):
    _, row, _ = example
    row.update(arm="arbitrary", family="clean", contract_satisfied=False, terminal_status="ERROR",
               elapsed_seconds_excluding_import_and_fixture_setup=None)
    summary = benchmark.summarize([row, row])[0]
    assert summary["attempted"] == summary["apparatus_errors"] == 2
    assert summary["satisfied"] == 0 and summary["elapsed_median_seconds"] is None


def test_case_inventory_and_duplicate_ids_fail_closed():
    cases = benchmark.load(benchmark.ROOT / "benchmarks/harness-execution-development.json")
    assert {c["family"] for c in benchmark.validate_cases(cases)} == benchmark.FAMILIES
    with pytest.raises(benchmark.context.Refused):
        benchmark.validate_cases([cases[0], cases[0]])


def test_worker_environment_drops_credentials_and_tracing(monkeypatch):
    monkeypatch.setenv("SYNTHETIC_PROVIDER_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setenv("LANGSMITH_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    env = benchmark.environment()
    assert "SYNTHETIC_PROVIDER_API_KEY" not in env and "LANGSMITH_API_KEY" not in env
    assert env["LANGCHAIN_TRACING_V2"] == "false"


def test_dropped_live_adapter_trace_is_an_error_in_attempted_denominator(monkeypatch):
    case = development_case("finite_reads")
    protocol = benchmark.load(benchmark.PROTOCOL)
    original = benchmark.e156
    captured = []
    def lose_telemetry(obs, *args):
        result = original(obs, *args)
        captured.extend(obs.events)
        obs.events.clear()
        return result
    monkeypatch.setattr(benchmark, "e156", lose_telemetry)
    row = benchmark.worker(case, "e156_baseline", protocol)
    assert sum(event["kind"] == "model" for event in captured) == row["observed_model_calls"] == 3
    assert len(row["successful_tool_results"]) == 2
    assert row["terminal_status"] == "ERROR" and not row["contract_satisfied"]
    assert any(event.get("origin") == "trace_validation" for event in row["apparatus_errors"])
    summary = benchmark.summarize([row])[0]
    assert summary["attempted"] == summary["apparatus_errors"] == 1 and summary["satisfied"] == 0


def test_reproduced_empty_trace_false_counts_and_hash_cannot_pass(example):
    case, row, protocol = copy.deepcopy(example)
    row.update(trace=[], observed_model_calls=6, observed_tool_attempts=0, raw_trace_sha256="0" * 64,
               contract_satisfied=True)
    assert not all(benchmark.grade(case, row, protocol).values())
    finalized = benchmark.finalize_observation(case, row, protocol)
    assert finalized["terminal_status"] == "ERROR" and not finalized["contract_satisfied"]
    assert finalized["rejected_raw_trace_sha256"] == "0" * 64


@pytest.mark.parametrize("mutation", ["drop_model", "model_index", "model_script", "model_count",
    "tool_count", "drop_attempt", "drop_result", "extra_result", "attempt_request", "result_payload",
    "drop_terminal", "prediction", "source_hash", "bool_index", "bool_failure_count"])
def test_trace_event_and_counter_disagreements_fail_after_rehash(example, mutation):
    case, row, protocol = copy.deepcopy(example)
    models = [event for event in row["trace"] if event["kind"] == "model"]
    if mutation == "drop_model": row["trace"].remove(models[0])
    elif mutation == "model_index": models[1]["index"] = 0
    elif mutation == "bool_index": models[0]["index"] = False
    elif mutation == "model_script": models[0]["script"]["args"]["offset"] = 99
    elif mutation == "model_count": row["observed_model_calls"] += 1
    elif mutation == "tool_count": row["observed_tool_attempts"] = 0
    elif mutation == "bool_failure_count": row["provider_failures"] = False
    elif mutation.startswith("drop_"):
        kind = {"drop_attempt": "tool_attempt", "drop_result": "tool_result", "drop_terminal": "native_run"}[mutation]
        row["trace"].remove(next(event for event in row["trace"] if event["kind"] == kind))
    elif mutation == "extra_result": row["trace"].append(copy.deepcopy(next(event for event in row["trace"] if event["kind"] == "tool_result")))
    elif mutation == "attempt_request": next(event for event in row["trace"] if event["kind"] == "tool_attempt")["request"]["arguments"]["offset"] = 99
    elif mutation == "result_payload": next(event for event in row["trace"] if event["kind"] == "tool_result")["result"]["text"] = "invented"
    elif mutation == "prediction": row["prediction"] = {"disposition": "NO_FLAG", "reason": "not the recorded answer"}
    elif mutation == "source_hash": row["source_before_sha256"] = row["source_after_sha256"] = "0" * 64
    rehash(row)
    assert not benchmark.grade(case, row, protocol)["trace_consistent"]
    assert benchmark.finalize_observation(case, row, protocol)["terminal_status"] == "ERROR"


def test_cached_reads_cannot_hide_a_dropped_model_from_native_journal():
    case = development_case("repeated_result")
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, "e156_baseline", protocol)
    last = next(event for event in reversed(row["trace"]) if event["kind"] == "model")
    row["trace"].remove(last)
    row["observed_model_calls"] -= 1
    rehash(row)
    assert "native journal model count mismatch" in benchmark.trace_errors(case, row)
    assert benchmark.finalize_observation(case, row, protocol)["terminal_status"] == "ERROR"


@pytest.mark.parametrize("family,kind", [("provider_timeout", "provider_failure"),
                                       ("source_drift", "source_mutation"),
                                       ("invalid_arguments", "tool_refusal"),
                                       ("unknown_tool", "refusal_evidence")])
def test_required_failure_and_refusal_events_cannot_be_omitted(family, kind):
    case = development_case(family)
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, "e156_baseline", protocol)
    row["trace"] = [event for event in row["trace"] if event["kind"] != kind]
    if kind == "provider_failure":
        row.update(provider_failures=0, provider_failure_retained=False, first_provider_failure_call=None)
    if kind == "refusal_evidence":
        row.update(refusal_evidence=[], refusal_retained=False)
    rehash(row)
    assert benchmark.finalize_observation(case, row, protocol)["terminal_status"] == "ERROR"


@pytest.mark.parametrize("value", [10**400, float("nan"), float("inf"), True])
def test_bad_elapsed_values_are_serializable_apparatus_errors(example, value):
    case, row, protocol = copy.deepcopy(example)
    row["elapsed_seconds_excluding_import_and_fixture_setup"] = value
    result = benchmark.finalize_observation(case, row, protocol)
    assert result["terminal_status"] == "ERROR" and not result["contract_satisfied"]
    assert result["elapsed_seconds_excluding_import_and_fixture_setup"] is None
    assert result["rejected_elapsed_seconds_excluding_import_and_fixture_setup"]["repr"] == repr(value)
    json.dumps(result, allow_nan=False)


def test_parent_normalizes_retained_apparatus_failure_even_with_consistent_trace(example):
    case, row, protocol = copy.deepcopy(example)
    event = {"kind": "apparatus_exception", "origin": "injected", "type": "builtins.RuntimeError", "message": "review test"}
    row["trace"].append(event)
    row["apparatus_errors"].append(event)
    result = benchmark.finalize_observation(case, rehash(row), protocol)
    assert result["terminal_status"] == "ERROR" and not result["contract_satisfied"]
    assert event in result["apparatus_errors"]
    assert benchmark.summarize([result])[0]["apparatus_errors"] == 1


@pytest.mark.parametrize("corruption", ["false_pass", "missing_fields", "not_object", "malformed_json",
                                      "nonfinite_extra", "false_fail"])
def test_parent_regrades_untrusted_child_results_and_retains_every_attempt(example, tmp_path, monkeypatch, corruption):
    case, row, protocol = copy.deepcopy(example)
    protocol.update(arms=["e156_baseline"], repetitions=1)
    cases_path = tmp_path / "development.json"
    cases_path.write_text(json.dumps([case]), encoding="utf-8")
    original_load = benchmark.load
    monkeypatch.setattr(benchmark, "load", lambda path: protocol if path == benchmark.PROTOCOL else original_load(path))
    monkeypatch.setattr(benchmark, "dependency_manifest", lambda: {name: {"version": "test-only"} for name in benchmark.PACKAGES})
    if corruption == "false_pass": row.update(trace=[], observed_tool_attempts=0, contract_satisfied=True)
    elif corruption == "missing_fields": row = {key: row[key] for key in ("case_id", "family", "arm")}
    elif corruption == "not_object": row = []
    elif corruption == "nonfinite_extra": row["unused_metadata"] = float("nan")
    elif corruption == "false_fail": row.update(contract_satisfied=False, checks={"invented_failure": False})
    stdout = "{" if corruption == "malformed_json" else json.dumps(row)
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=stdout, stderr=""))
    output = tmp_path / "observations.json"
    report = benchmark.run_suite(cases_path, "development", output)
    assert report["attempted"] == len(report["rows"]) == 1
    attempt = report["rows"][0]
    assert attempt["contract_satisfied"] == (corruption == "false_fail")
    assert (attempt["terminal_status"] == "ERROR") == (corruption != "false_fail")
    assert [json.loads(line) for line in output.with_suffix(".json.attempts.jsonl").read_text().splitlines()] == report["rows"]


def test_published_evidence_hashes_survive_windows_git_checkout(tmp_path):
    """Exercise Git's actual Windows newline policy, including on Linux CI."""
    root = benchmark.ROOT
    artifact_dir = "benchmarks/execution"
    protocol = "benchmarks/harness-execution-protocol.json"
    shutil.copytree(root / artifact_dir, tmp_path / artifact_dir)
    shutil.copyfile(root / protocol, tmp_path / protocol)
    shutil.copyfile(root / ".gitattributes", tmp_path / ".gitattributes")
    def git(*args):
        subprocess.run(["git", "-c", "core.autocrlf=true", "-C", str(tmp_path), *args],
                       check=True, capture_output=True, timeout=30)
    git("init")
    git("add", ".gitattributes", artifact_dir, protocol)
    # Only delete explicit test copies, then force a real smudged checkout.
    for path in (tmp_path / artifact_dir).iterdir():
        assert path.resolve().is_relative_to(tmp_path.resolve()) and path.is_file()
        path.unlink()
    (tmp_path / protocol).unlink()
    git("checkout-index", "--all", "--force")
    published = tmp_path / artifact_dir
    manifest = json.loads((published / "publication-manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((published / name).read_bytes()).hexdigest() == expected["sha256"], name
    frozen = json.loads((published / "public-reviewer-final-pre-execution.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((tmp_path / protocol).read_bytes()).hexdigest() == frozen["source_sha256"][protocol]
