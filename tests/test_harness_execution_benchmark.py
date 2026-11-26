"""Framework-independent controls for the comparative execution apparatus."""
import copy
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


def test_abstention_requires_retained_refusal(example):
    case, row, protocol = example
    case = {**case, "expected": "refused"}
    row = {**row, "prediction": {"disposition": "ABSTAIN"}}
    assert not all(benchmark.grade(case, row, protocol).values())
    assert all(benchmark.grade(case, {**row, "refusal_retained": True}, protocol).values())


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
