"""Offline E156 trace-to-study records; consistency is not external authentication.

No execution, network, file writes or measurement imputation occurs here.
Runner dispatches, operation allocations, observed usage and reservations are
different quantities. Final v1 records require supplied human-time measurements.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import math
import re

if __package__:
    from scripts import harness_runtime as runtime, harness_trace as trace
else:
    import harness_runtime as runtime
    import harness_trace as trace

context = runtime.context
require, Refused, digest = context.require, context.Refused, context.digest
CASE_FIELDS = {"schema", "case_id", "protocol_sha256", "arm_id", "claim_id", "config_sha256",
               "context_sha256", "started_at", "ended_at", "dispatches", "outcome", "execution_mode"}
MEASUREMENT_FIELDS = {"schema", "case_sha256", "report_sha256", "review_seconds", "api_cost_usd",
                      "human_review_cost_usd", "evidence_reference", "observed_at"}
TERMINAL = {"COMPLETED", "CANCELLED", "BUDGET_STOP", "UNRESOLVED", "REFUSED", "STALLED"}


def canonical_bytes(value):
    """Evidence-file encoding: compact sorted UTF-8 JSON followed by one LF."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _text(value, field):
    require(isinstance(value, str) and value and value == value.strip(), "invalid " + field)
    return value


def _keys(value, keys, field):
    require(isinstance(value, dict) and set(value) == keys, field + " fields mismatch")


def _hash(actual, expected, field):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid " + field)
    require(hmac.compare_digest(actual, expected), field + " mismatch")


def _same(actual, expected, field):
    _hash(digest(actual), digest(expected), field)


def _number(value, field, *, nullable=False):
    if nullable and value is None:
        return
    require(type(value) in (int, float), "numeric " + field + " required")
    try:
        valid = math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    require(valid, "invalid " + field)


def _task_binding(config, manifest, task):
    require(isinstance(task, dict), "task required")
    nodes, _ = context.index(manifest)
    selected = config.get("selected")
    require(isinstance(selected, list) and selected
            and all(isinstance(key, str) and key in nodes for key in selected)
            and len(selected) == len(set(selected)), "selected task nodes invalid")
    matched = [nodes[key] for key in selected if nodes[key].get("file") == task.get("input_file")
               and nodes[key].get("sha256") == task.get("input_sha256") and nodes[key]["kind"] != "skill"]
    require(len(matched) == 1, "task file/hash not bound to selected context")
    pending, reachable = list(selected), set()
    while pending:
        key = pending.pop()
        if key not in reachable:
            reachable.add(key)
            pending.extend(nodes[key]["parents"])
    source_rows = [(nodes[key]["file"], nodes[key]["sha256"]) for key in reachable if nodes[key]["kind"] == "source"]
    declared = task.get("source_files")
    require(isinstance(declared, list) and all(isinstance(s, dict) and set(s) == {"file", "sha256"}
            and all(isinstance(v, str) for v in s.values()) for s in declared),
            "task sources required")
    pairs = [(s["file"], s["sha256"]) for s in declared]
    require(len(source_rows) == len(set(source_rows)) and len(pairs) == len(set(pairs))
            and set(source_rows) == set(pairs), "selected sources differ from task inventory")


def _model_policy(config, request):
    static = {"parallel_tool_calls": False, "store": False, "include": ["reasoning.encrypted_content"],
              **config.get("request_policy", {})}
    _keys(request, {"model", "input", "instructions", "tools", "max_output_tokens"} | set(static), "model request")
    _same({key: request[key] for key in static}, static, "frozen request policy")
    context.integer(request["max_output_tokens"], "requested output limit", minimum=1)
    route = config["routes"][config["task_kind"]]
    policies = {digest(model): model for model in (config["models"][key] for key in route)
                if model["model"] == request.get("model") and model["max_output_tokens"] == request.get("max_output_tokens")}
    require(len(policies) == 1, "unambiguous selected-route model policy required")
    return next(iter(policies.values()))


def _operations(report, config, manifest, began, ended):
    operations = trace.validate(report)
    _hash(digest(config), report["config_sha256"], "trace configuration")
    _hash(digest(manifest), report["context_sha256"], "trace context")
    _same(report["events"][0]["anchor"]["code"], runtime.profile(), "trace runtime profile")
    previous = began
    for event in report["events"]:
        at = context.timestamp(event["at"])
        require(previous <= at <= ended, "trace outside case lifecycle or chronology")
        previous = at
    counts = {kind: {"allocated": 0, "finished": 0, "reconciled": 0, "unresolved": 0}
              for kind in ("count", "model", "tool")}
    for key, op in operations.items():
        category, separator, suffix = key.partition(":")
        require(separator and suffix and category in counts and
                (category == "tool" or suffix.isdigit()), "unsupported study operation")
        counts[category]["allocated"] += 1
        if category in {"count", "model"}:
            policy = _model_policy(config, op["reservation"]["request"])
        if category == "model":
            count = operations.get("count:" + suffix)
            require(count and count["finish"] and count["finish"]["kind"] == "FINISHED", "model lacks completed input count")
            _same(count["reservation"]["request"], op["reservation"]["request"], "model/count request binding")
            quote = count["finish"]["data"]
            require(isinstance(quote, dict), "input count response required")
            context.integer(quote.get("input_tokens"), "input count")
        finish = op["finish"]
        if finish is None or finish["kind"] == "UNRESOLVED":
            counts[category]["unresolved"] += 1
            continue
        counts[category]["finished" if finish["kind"] == "FINISHED" else "reconciled"] += 1
        actual = {k: v for k, v in finish["usage"].items() if k != "wall_ms"}
        if category == "model":
            expected = runtime.model_usage(finish["data"], policy, quote)
            if "request_policy" in config:
                _same({key: finish["data"].get(key) for key in ("model", "service_tier")},
                      {"model": policy["model"], "service_tier": config["request_policy"]["service_tier"]},
                      "settled response model/service-tier binding")
        elif category == "count":
            require(finish["kind"] == "FINISHED" and isinstance(finish["data"], dict), "invalid count settlement")
            context.integer(finish["data"].get("input_tokens"), "input count")
            expected = runtime.units()
        else:
            require(finish["kind"] == "FINISHED", "unsupported tool recovery")
            expected = runtime.units(tool_calls=1)
        _same(actual, {k: v for k, v in expected.items() if k != "wall_ms"}, "observed operation usage")
    return operations, counts


def _completed_prediction(report, operations):
    require(operations, "completed run has no operations")
    key = next(reversed(operations))
    require(key.startswith("model:"), "completed run did not end at model response")
    finish = operations[key]["finish"]
    require(finish and finish["kind"] in {"FINISHED", "RECONCILED"}, "completed response is unsettled")
    response = finish["data"]
    require(isinstance(response, dict) and response.get("status") != "cancelled"
            and not any(item.get("type") == "function_call" for item in response.get("output", [])),
            "completed response still requests a tool")
    try:
        value = runtime.prediction(response)
    except Refused:
        value = {"disposition": "ABSTAIN", "reason": "Invalid structured response", "stop_point": "OUTPUT_VALIDATION"}
    _same(value, report.get("prediction"), "terminal prediction is not bound to recorded response")
    return {key: value[key] for key in ("disposition", "flag_root_id", "evidence_locator", "stop_point") if key in value}


def draft(case, report, config, manifest, arm, task, protocol_sha256):
    """Return a non-final record; review time and actual charges remain unknown."""
    _keys(case, CASE_FIELDS, "case")
    require(case["schema"] == "e156-study-case-v1", "case schema mismatch")
    require(isinstance(arm, dict) and isinstance(task, dict), "frozen arm/task required")
    _hash(protocol_sha256, case["protocol_sha256"], "case protocol")
    for key, value in (("arm_id", arm.get("arm_id")), ("claim_id", task.get("claim_id"))):
        require(_text(case[key], key) == _text(value, key), "case " + key + " mismatch")
    _hash(digest({"protocol_sha256": protocol_sha256, "arm_id": case["arm_id"], "claim_id": case["claim_id"]}),
          case["case_id"], "case identity")
    runtime.configuration(config, manifest)
    _hash(digest(config), case["config_sha256"], "case configuration")
    _hash(digest(manifest), case["context_sha256"], "case context")
    _task_binding(config, manifest, task)
    require(case["outcome"] in {"RETURNED", "DEADLINE", "INTERRUPTED", "NOT_ATTEMPTED"}, "unknown lifecycle outcome")
    context.integer(case["dispatches"], "runner dispatches", minimum=0 if case["outcome"] == "NOT_ATTEMPTED" else 1)
    if case["outcome"] == "NOT_ATTEMPTED":
        require(case["dispatches"] == 0 and report is None, "unattempted case has dispatch/report evidence")
    require(case["execution_mode"] in {"LIVE", "SYNTHETIC_CONTRACT"}, "execution mode required")
    began, ended = context.timestamp(case["started_at"]), context.timestamp(case["ended_at"])
    require(ended >= began, "case lifecycle reversed")
    wall_seconds = (ended - began).total_seconds()
    _number(wall_seconds, "whole-task wall seconds")
    status, prediction = "FAILED", {"disposition": "ABSTAIN", "stop_point": "EXECUTION_INTERRUPTED"}
    accounting, counts, tokens, tools = None, None, None, None
    candidate = None
    if report is None:
        require(case["outcome"] != "RETURNED", "returned case lacks report")
    else:
        operations, counts = _operations(report, config, manifest, began, ended)
        require(report["status"] in TERMINAL, "report is not a terminal execution result")
        accounting = runtime.accounting(operations)
        tokens = None if counts["model"]["unresolved"] else accounting["observed"]["model_tokens"]
        tools = None if counts["tool"]["unresolved"] else accounting["observed"]["tool_calls"]
        if report["status"] == "COMPLETED":
            candidate = _completed_prediction(report, operations)
    if case["outcome"] == "NOT_ATTEMPTED":
        status, prediction = "NOT_ATTEMPTED", {"disposition": "ABSTAIN", "stop_point": "NOT_ATTEMPTED"}
        tokens, tools = 0, 0
    elif case["outcome"] == "DEADLINE":
        status, prediction = "TIMEOUT", {"disposition": "ABSTAIN", "stop_point": "EXECUTION_DEADLINE"}
    elif case["outcome"] == "RETURNED":
        if report["status"] == "COMPLETED":
            status, prediction = "COMPLETE", candidate
        else:
            prediction = {"disposition": "ABSTAIN", "stop_point": "RUNTIME_" + report["status"]}
    record = {"arm_id": case["arm_id"], "claim_id": case["claim_id"], "arm_sha256": digest(arm),
              "input_sha256": task["input_sha256"], "status": status, "started_at": case["started_at"],
              "ended_at": case["ended_at"], "wall_seconds": wall_seconds, "internal_attempts": case["dispatches"],
              "prediction": {**prediction, "review_seconds": None},
              "usage": {"model_tokens": tokens, "tool_calls": tools, "api_cost_usd": None, "human_review_cost_usd": None},
              "record_evidence_reference": None, "record_evidence_sha256": None}
    return {"schema": "e156-study-record-draft-v1", "case_sha256": digest(case),
            "report_sha256": digest(report) if report is not None else None, "matched_record": record,
            "execution_mode": case["execution_mode"], "runtime_status": report["status"] if report is not None else None,
            "operation_counts": counts, "accounting": accounting,
            "attempt_basis": "RUNNER_DISPATCHES_INCLUDING_RESUMES_NOT_PROVIDER_CALLS",
            "wall_basis": "LIFECYCLE_END_MINUS_FIRST_START_INCLUDING_RECOVERY_GAPS",
            "operation_count_basis": "DURABLE_ALLOCATIONS_DISPATCH_MAY_BE_UNKNOWN",
            "scientific_validation": "NOT_ESTABLISHED",
            "limitations": ["Local consistency does not authenticate provider usage, timing, human work or charges.",
                            "Frozen arm-template concretization and actual source bytes must be verified by the orchestrator.",
                            "Operation timing and price-policy reservations are not whole-task time or actual billing."]}


def finalize(case, report, config, manifest, arm, task, protocol_sha256, measurement):
    """Recompute from original evidence; never accept an editable draft as authority."""
    value = draft(case, report, config, manifest, arm, task, protocol_sha256)
    _keys(measurement, MEASUREMENT_FIELDS, "measurement")
    require(measurement["schema"] == "e156-study-measurement-v1", "measurement schema mismatch")
    _hash(value["case_sha256"], measurement["case_sha256"], "measurement case")
    _same(value["report_sha256"], measurement["report_sha256"], "measurement report")
    _number(measurement["review_seconds"], "review_seconds")
    for field in ("api_cost_usd", "human_review_cost_usd"):
        _number(measurement[field], field, nullable=True)
    _text(measurement["evidence_reference"], "measurement evidence reference")
    require(context.timestamp(measurement["observed_at"]) >= context.timestamp(case["ended_at"]),
            "measurement predates lifecycle end")
    package = copy.deepcopy({"schema": "e156-study-record-evidence-v1", "protocol_sha256": protocol_sha256,
        "case": case, "report": report, "config": config, "manifest": manifest, "arm": arm, "task": task,
        "draft": value, "measurement": measurement})
    evidence_hash = hashlib.sha256(canonical_bytes(package)).hexdigest()
    record = copy.deepcopy(value["matched_record"])
    record["prediction"]["review_seconds"] = measurement["review_seconds"]
    record["usage"].update({field: measurement[field] for field in ("api_cost_usd", "human_review_cost_usd")})
    record["record_evidence_reference"] = "evidence/" + evidence_hash + ".json"
    record["record_evidence_sha256"] = evidence_hash
    return {"package": package, "record": record}
