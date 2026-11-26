"""Synthetic progress-policy integration and failed-trace replay controls."""
import copy
import pytest

from scripts import harness_runtime as runtime
from scripts import harness_trace as trace
from test_harness_runtime import job, Provider, answer, run


def configure(job, limit=3):
    job[0]["progress_policy"] = {"repeated_result_limit": limit}
    job[0]["limits"].update(model_calls=6, tool_calls=6)


def reading(call_id, offset=0):
    value = answer()
    value["output"] = [{"type": "function_call", "call_id": call_id, "name": "read_evidence",
                        "arguments": '{"id":"paper","offset":%d,"limit":10}' % offset}]
    return value


def test_repeated_results_stop_before_fourth_model_call_and_resume_is_stable(job):
    configure(job)
    provider = Provider([reading(str(i)) for i in range(6)])
    report = run(job, provider)
    assert report["status"] == "STALLED" and report["prediction"] is None
    assert provider.calls == 3 and report["usage"]["tool_calls"] == 3
    assert report["stop"]["reason"] == "REPEATED_TOOL_RESULT"
    assert report["stop"]["repetitions"] == report["stop"]["limit"] == 3
    again = run(job, provider, create=False)
    assert again["stop"] == report["stop"] and provider.calls == 3
    assert trace.export(report)["stop_reason"] == "REPEATED_TOOL_RESULT"


def test_progress_policy_is_opt_in(job):
    job[0]["limits"].update(model_calls=6, tool_calls=6)
    provider = Provider([reading(str(i)) for i in range(6)])
    assert run(job, provider)["status"] == "BUDGET_STOP"
    assert provider.calls == 6


def test_new_arguments_break_repetition_and_allow_normal_completion(job):
    configure(job)
    provider = Provider([reading("a"), reading("b"), reading("c", 1), reading("d"), reading("e"), answer()])
    report = run(job, provider)
    assert report["status"] == "COMPLETED" and provider.calls == 6


def test_new_result_breaks_repetition(job, monkeypatch):
    configure(job)
    original = runtime.Journal.operation
    results = iter([{"synthetic": 1}, {"synthetic": 1}, {"synthetic": 2}, {"synthetic": 1}])
    def changed_result(self, key, request, reserve, execute):
        if key.startswith("tool:"):
            data = next(results)
            execute = lambda timeout: (data, runtime.units(tool_calls=1))
        return original(self, key, request, reserve, execute)
    monkeypatch.setattr(runtime.Journal, "operation", changed_result)
    report = run(job, Provider([reading(str(i)) for i in range(4)] + [answer()]))
    assert report["status"] == "COMPLETED"


def test_reused_call_ids_cannot_evade_guard_or_repeat_cached_tool(job):
    configure(job)
    report = run(job, Provider([reading("same") for _ in range(6)]))
    assert report["status"] == "STALLED"
    assert report["usage"]["model_calls"] == 3 and report["usage"]["tool_calls"] == 1


@pytest.mark.parametrize("value", [True, 1, 0, -1, 101, "3", None])
def test_invalid_progress_threshold_refuses_before_provider(job, value):
    configure(job, value)
    provider = Provider()
    with pytest.raises(runtime.Refused):
        run(job, provider)
    assert provider.calls == provider.counts == 0


def test_stalled_trace_replays_with_identical_stop_and_accounting(job):
    configure(job)
    report = run(job, Provider([reading(str(i)) for i in range(6)]))
    config, manifest, root, _ = job
    result = trace.replay(report, config, manifest, root, root / "replay.sqlite")
    assert result["verdict"] == "PASS" and result["checks"]["stop_matches"]


def test_settled_refusal_is_replayable_but_unknown_provider_outcome_is_not(job):
    response = reading("bad")
    response["output"][0]["name"] = "forbidden"
    report = run(job, Provider([response]))
    assert report["status"] == "REFUSED"
    config, manifest, root, _ = job
    result = trace.replay(report, config, manifest, root, root / "replay.sqlite")
    assert result["verdict"] == "PASS"


def test_forged_stop_summary_refused(job):
    configure(job)
    report = run(job, Provider([reading(str(i)) for i in range(6)]))
    for key, value in (("result_sha256", "f" * 64), ("tool_request_sha256", "f" * 64), ("repetitions", 1)):
        changed = copy.deepcopy(report)
        changed["stop"][key] = value
        with pytest.raises(runtime.Refused):
            trace.export(changed)
