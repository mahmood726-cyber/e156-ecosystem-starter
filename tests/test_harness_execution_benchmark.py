"""Framework-independent controls for the comparative execution apparatus."""
import copy
import hashlib
import json
import shutil
import subprocess
import pytest

from scripts import harness_execution_benchmark as benchmark


@pytest.fixture
def example():
    protocol = benchmark.load(benchmark.PROTOCOL)
    case = benchmark.load(benchmark.ROOT / "benchmarks/harness-execution-development.json")[1]
    sha = benchmark.hashlib.sha256(case["source_text"].encode()).hexdigest()
    successes = [{"request": {"name": "read_evidence", "arguments": step["args"]}, "model_call": index + 1,
                  "result": {"sha256": sha, "offset": step["args"]["offset"],
                             "text": case["source_text"][step["args"]["offset"]:step["args"]["offset"] + step["args"]["limit"]]}}
                 for index, step in enumerate(case["steps"]) if step["kind"] == "tool"]
    row = {"terminal_status": "COMPLETED", "prediction": {"disposition": "NO_FLAG"},
           "observed_model_calls": 3, "observed_tool_attempts": 2, "successful_tool_results": successes,
           "source_before_sha256": sha, "source_after_sha256": sha, "refusal_retained": False,
           "refusal_evidence": [], "apparatus_errors": [], "trace": [],
           "provider_failure_retained": False, "provider_failures": 0}
    return case, row, protocol


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
        assert not all(benchmark.grade(case, changed, protocol).values())
    changed = copy.deepcopy(row)
    changed["successful_tool_results"][0]["request"]["name"] = "execute"
    assert not all(benchmark.grade(case, changed, protocol).values())


def test_stops_and_provider_failures_cannot_fabricate_predictions(example):
    case, row, protocol = example
    case = {**case, "expected": "bounded_stop"}
    row = {**row, "terminal_status": "STALLED", "prediction": None}
    assert all(benchmark.grade(case, row, protocol).values())
    assert not all(benchmark.grade(case, {**row, "prediction": {"disposition": "NO_FLAG"}}, protocol).values())
    case["expected"] = "provider_failed"
    row.update(terminal_status="PROVIDER_FAILED", provider_failure_retained=True, provider_failures=1, first_provider_failure_call=3)
    assert all(benchmark.grade(case, row, protocol).values())
    for changes in ({"terminal_status": "ERROR"}, {"terminal_status": "unknown"}, {"provider_failures": 2},
                    {"provider_failure_retained": False}, {"first_provider_failure_call": 1}):
        assert not all(benchmark.grade(case, {**row, **changes}, protocol).values())


def development_case(family):
    cases = benchmark.load(benchmark.ROOT / "benchmarks/harness-execution-development.json")
    return next(case for case in cases if case["family"] == family)


def test_abstention_requires_retained_refusal():
    case = development_case("unknown_tool")
    protocol = benchmark.load(benchmark.PROTOCOL)
    row = benchmark.worker(case, "e156_baseline", protocol)
    row = {**row, "prediction": {"disposition": "ABSTAIN"}}
    assert not all(benchmark.grade(case, row, protocol).values())  # Contradicts terminal REFUSED.
    row["terminal_status"] = "COMPLETED"
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
    assert not all(benchmark.grade(case, changed, protocol).values())


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
    assert not all(benchmark.grade(case, changed, protocol).values())
    changed = copy.deepcopy(row)
    changed["refusal_evidence"][0]["reason"] = "unrecognized guard failure"
    assert not all(benchmark.grade(case, changed, protocol).values())


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
    row.update(terminal_status="COMPLETED", prediction={"disposition": "ABSTAIN"},
               refusal_evidence=obs.refusal_evidence, trace=obs.events)
    assert all(benchmark.grade(case, row, protocol).values())
    for bad_reason in ('not JSON', '{}', json.dumps({"tool_call_id": "other"})):
        changed = copy.deepcopy(row)
        changed["refusal_evidence"][0]["reason"] = bad_reason
        assert not all(benchmark.grade(case, changed, protocol).values())


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
