"""Narrow native Pydantic Agent bridge over the checked Responses transport.

No provider SDK, streaming, fallback, media, compaction or native provider tools.
All public validation/profile helpers import only the standard library and local
standard-library modules. Native dependencies are loaded only by run().
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
from typing import Annotated


SCHEMA = "e156-native-pydantic-v1"
WITNESS_SCHEMA = "e156-native-pydantic-request-v1"
TOOL_WITNESS_SCHEMA = "e156-native-pydantic-tool-v1"
EXECUTION_SCHEMA = "e156-native-pydantic-execution-v1"
POLICY = {
    "model_adapter": "custom_Model_over_checked_Responses",
    "agent_output": "str", "streaming": False, "retries": 0, "instrumentation": False,
    "tools": ["read_evidence"], "sequential_tools": True,
    "parallel_tool_calls": False, "store": False, "service_tier": "default",
    "reasoning_include": ["reasoning.encrypted_content"],
    "decoding": "provider_defaults_except_frozen_output_limit",
    "history": "opaque_outputs_bound_to_journal",
    "replay": "native_agent_from_start_with_journal_cache",
    "normalization": "omit_framework_message_timestamps_run_and_conversation_ids",
    "detect_loops": {
        "window": 3, "repeated_call_threshold": None, "repeated_result_threshold": 3,
        "alternating_calls_threshold": None, "repeated_text_threshold": None,
        "stream_detector": None, "repeated_parallel_call_threshold": None, "action": "error",
    },
}
TERMINATIONS = {
    "COMPLETED": {"COMPLETED"},
    "BUDGET_STOP": {"BUDGET_STOP", "NATIVE_USAGE_LIMIT"},
    "UNRESOLVED": {"UNRESOLVED", "INTERRUPTED"},
    "REFUSED": {"LOOP_DETECTED", "NATIVE_VALIDATION", "OUTPUT_VALIDATION", "CONTRACT_REFUSED", "PROVIDER_TERMINAL"},
    "CANCELLED": {"CANCELLED"},
}


def _modules():
    if __package__:
        from scripts import harness_context, harness_runtime
    else:
        import harness_context, harness_runtime
    return harness_context, harness_runtime


def profile():
    root = Path(__file__).resolve().parents[1]
    names = ("scripts/harness_native_pydantic.py", "scripts/harness_native_environment.py", "scripts/harness_execution_benchmark.py",
             "benchmarks/requirements-execution-windows.lock")
    return {"schema": "e156-native-pydantic-profile-v1", "files": {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}}


def _environment_helper():
    if __package__:
        from scripts import harness_native_environment
    else:
        import harness_native_environment
    return harness_native_environment


def environment():
    context, _ = _modules()
    context.require(sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 13)
                    and sys.platform == "win32" and platform.machine().upper() == "AMD64",
                    "native adapter requires locked Windows x64 CPython 3.13 environment")
    # Verify installed RECORDs and the complete executable footprint without
    # importing SDKs, reading final benchmark cases or processing .pth files.
    verification = _environment_helper().verify()
    return {"schema": "e156-native-pydantic-environment-v1",
            "python": {"implementation": sys.implementation.name, "version": list(sys.version_info[:3]),
                       "system": platform.system(), "machine": platform.machine()},
            **verification}


def descriptor():
    context, _ = _modules()
    return {"schema": SCHEMA, "profile": profile(), "environment_sha256": context.digest(environment()),
            "policy": copy.deepcopy(POLICY)}


def validate_config(config):
    context, _ = _modules()
    require = context.require
    native = config.get("native_runtime") if isinstance(config, dict) else None
    require(isinstance(native, dict) and set(native) == {"schema", "profile", "environment_sha256", "policy"}
            and native["schema"] == SCHEMA and context.digest(native["profile"]) == context.digest(profile())
            and context.digest(native["policy"]) == context.digest(POLICY), "native adapter descriptor/profile/policy mismatch")
    require(isinstance(native["environment_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", native["environment_sha256"]) is not None,
            "native environment digest required")
    require(config.get("request_policy") == {"service_tier": "default"}, "native default service tier required")
    require(config.get("worker") is None and "progress_policy" not in config,
            "native adapter accepts read-only tools and native guard only")
    routes, models = config.get("routes"), config.get("models")
    require(isinstance(config.get("task_kind"), str) and isinstance(routes, dict) and set(routes) == {config["task_kind"]}
            and isinstance(models, dict) and len(models) == 1, "native adapter requires one frozen model/route")
    require(routes[config["task_kind"]] == list(models), "native fallback is unsupported")


def _normalized(messages):
    """Remove only native run-generated identity/time fields, never source data."""
    context, _ = _modules()
    context.require(isinstance(messages, list), "native messages must be a list")
    value = copy.deepcopy(messages)
    for message in value:
        context.require(isinstance(message, dict) and isinstance(message.get("parts"), list), "native message malformed")
        for name in ("timestamp", "run_id", "conversation_id"):
            message.pop(name, None)
        for part in message.get("parts", []):
            context.require(isinstance(part, dict), "native message part malformed")
            # Provider fields and nested tool content remain completely intact.
            part.pop("timestamp", None)
    return value


def _projection(message):
    value = _normalized([message])[0]
    value.pop("provider_details", None)
    return value


def _received(raw, model, quote, runtime, context):
    """Validate before settling, retaining any unsupported received response."""
    require = context.require
    usage = runtime.model_usage(raw, model, quote)
    require(raw.get("model") == model["model"] and raw.get("service_tier") == "default",
            "native provider model/tier mismatch")
    require(isinstance(raw.get("id"), str) and bool(raw["id"]), "native response id required")
    calls = []
    for item in raw["output"]:
        kind = item.get("type")
        if kind == "message":
            require(item.get("role") == "assistant" and isinstance(item.get("content"), list)
                    and bool(item["content"]), "unsupported native message")
            for part in item["content"]:
                require(isinstance(part, dict) and part.get("type") == "output_text"
                        and isinstance(part.get("text"), str), "unsupported native output content")
        elif kind == "function_call":
            require(isinstance(item.get("name"), str) and bool(item["name"])
                    and isinstance(item.get("call_id"), str) and bool(item["call_id"])
                    and isinstance(item.get("arguments"), str), "malformed native function call")
            calls.append(item)
        elif kind == "reasoning":
            require(isinstance(item.get("id"), str) and bool(item["id"])
                    and isinstance(item.get("summary"), list), "malformed native reasoning item")
            require(all(isinstance(p, dict) and p.get("type") == "summary_text" and isinstance(p.get("text"), str)
                        for p in item["summary"]), "malformed native reasoning summary")
            require(item.get("encrypted_content") is None or isinstance(item["encrypted_content"], str),
                    "malformed native reasoning state")
        else:
            raise context.Refused("unsupported native response item")
        require(item.get("id") is None or isinstance(item["id"], str), "malformed native item id")
    require(len(calls) <= 1 and (not calls or raw["status"] == "completed"), "unsupported native parallel/incomplete calls")
    for field, key in (("input_tokens_details", "cached_tokens"), ("output_tokens_details", "reasoning_tokens")):
        if field in raw["usage"]:
            detail = raw["usage"][field]
            require(isinstance(detail, dict), "malformed native usage details")
            if key in detail:
                context.integer(detail[key], key)
                bound = raw["usage"]["input_tokens" if field.startswith("input") else "output_tokens"]
                require(detail[key] <= bound, "native usage detail exceeds total")
    return usage


def validate_recovery_response(raw, config, quote):
    """Reject unsupported native recovery data before the journal is changed."""
    context, runtime = _modules()
    validate_config(config)
    try:
        return _received(raw, next(iter(config["models"].values())), quote, runtime, context)
    except (KeyError, TypeError, ValueError) as exc:
        raise context.Refused("malformed native recovered response") from exc


def _inventory(events, context):
    return [{"id": event["id"], "request_sha256": event["request_sha256"],
             "execution_witness_sha256": event.get("execution_witness_sha256")}
            for event in events if event.get("kind") == "RESERVED"]


def describe_report(report, config, termination="INTERRUPTED"):
    """Attach provenance from retained operations; never infer native callbacks."""
    context, _ = _modules()
    result = copy.deepcopy(report)
    result["native_runtime"] = copy.deepcopy(config["native_runtime"])
    result["native_execution"] = {"schema": EXECUTION_SCHEMA,
        "environment_sha256": config["native_runtime"]["environment_sha256"],
        "operations": _inventory(result["events"], context), "termination": termination}
    validate_report(result, config)
    return result


def validate_report(report, config):
    """Check native provenance without loading the native dependencies."""
    context, runtime = _modules()
    require, digest = context.require, context.digest
    validate_config(config)
    require(isinstance(report, dict) and digest(report.get("native_runtime")) == digest(config["native_runtime"]),
            "native report descriptor mismatch")
    native = report.get("native_execution")
    require(isinstance(native, dict) and set(native) == {"schema", "environment_sha256", "operations", "termination"}
            and native["schema"] == EXECUTION_SCHEMA
            and native["environment_sha256"] == config["native_runtime"]["environment_sha256"],
            "native execution metadata mismatch")
    require(isinstance(report.get("status"), str) and isinstance(native["termination"], str)
            and native["termination"] in TERMINATIONS.get(report["status"], set()), "native termination/status mismatch")
    events = report.get("events")
    require(isinstance(events, list) and events and isinstance(events[0], dict)
            and events[0].get("kind") == "READY", "native events missing")
    operations = runtime.Journal.operations(events)
    require(native["operations"] == _inventory(events, context), "native operation inventory mismatch")
    model = next(iter(config["models"].values()))
    previous_models, previous_operations = {}, {}
    turns = []
    for key, operation in operations.items():
        reservation = operation["reservation"]
        witness = reservation.get("execution_witness")
        require(isinstance(witness, dict) and reservation.get("execution_witness_sha256") == digest(witness),
                "native operation witness missing or changed")
        if key.startswith(("count:", "model:")):
            prefix, turn = key.split(":", 1)
            require(turn.isdigit() and str(int(turn)) == turn, "invalid native turn id")
            require(set(witness) == {"schema", "messages", "parameters", "settings"}
                    and witness["schema"] == WITNESS_SCHEMA and isinstance(witness["messages"], list)
                    and isinstance(witness["parameters"], dict) and witness["settings"] is None,
                    "native request witness schema mismatch")
            _validate_parameters(witness["parameters"], runtime, context)
            for message in witness["messages"]:
                require(isinstance(message, dict) and message.get("kind") in {"request", "response"}
                        and isinstance(message.get("parts"), list), "native message witness malformed")
                if message["kind"] == "response":
                    _bound_response(message, previous_models, digest, require)
            require(digest(wire_from_witness(witness, config, previous_operations)) == reservation["request_sha256"],
                    "native witness does not reconstruct wire request")
            if prefix == "count":
                turns.append(int(turn))
            else:
                count = operations.get("count:" + turn)
                require(count is not None and count["finish"] is not None
                        and count["finish"]["kind"] == "FINISHED"
                        and count["reservation"]["request_sha256"] == reservation["request_sha256"]
                        and count["reservation"]["execution_witness_sha256"] == reservation["execution_witness_sha256"],
                        "native model/count witness mismatch")
                finish = operation["finish"]
                if finish and finish["kind"] in {"FINISHED", "RECONCILED"}:
                    _received(finish["data"], model, count["finish"]["data"], runtime, context)
                    previous_models[key] = operation
        else:
            require(key.startswith("tool:") and set(witness) == {
                "schema", "model_operation_id", "response_sha256", "call_id", "name", "arguments"}
                and witness["schema"] == TOOL_WITNESS_SCHEMA and witness["name"] == "read_evidence"
                and key == "tool:" + witness["call_id"], "native tool witness malformed")
            source = previous_models.get(witness["model_operation_id"])
            require(source is not None and digest(source["finish"]["data"]) == witness["response_sha256"],
                    "native tool response binding mismatch")
            calls = [i for i in source["finish"]["data"]["output"] if i["type"] == "function_call"]
            require(len(calls) == 1 and calls[0]["name"] == witness["name"] and calls[0]["call_id"] == witness["call_id"]
                    and context.strict_json(calls[0]["arguments"].encode()) == witness["arguments"]
                    and reservation["request"] == {"name": witness["name"], "arguments": witness["arguments"]},
                    "native tool call witness mismatch")
        previous_operations[key] = operation
    require(turns == list(range(len(turns))), "native turn inventory is not contiguous")
    if report["status"] == "COMPLETED":
        require(bool(previous_models), "native completion lacks provider response")
        raw = next(reversed(previous_models.values()))["finish"]["data"]
        require(not any(i["type"] == "function_call" for i in raw["output"])
                and report.get("prediction") == runtime.prediction(raw), "native completion prediction mismatch")
    else:
        require(report.get("prediction") is None, "native stop cannot fabricate prediction")


def _validate_parameters(params, runtime, context):
    require = context.require
    instructions = params.get("instruction_parts")
    require(isinstance(instructions, list) and len(instructions) == 1
            and isinstance(instructions[0], dict) and isinstance(instructions[0].get("content"), str),
            "native instructions mismatch")
    expected = runtime.tool_schemas(["read_evidence"])[0]
    tool = {"name": expected["name"], "description": expected["description"], "parameters_json_schema": expected["parameters"],
            "outer_typed_dict_key": None, "strict": True, "sequential": True, "kind": "function", "metadata": None,
            "timeout": None, "durable": None, "defer_loading": False, "unless_native": None, "with_native": None,
            "tool_kind": None, "unless_tool_kind": None, "return_schema": None, "include_return_schema": None,
            "toolset_id": "<agent>", "capability_id": None}
    expected_params = {"function_tools": [tool], "native_tools": [], "tool_visibility": {"read_evidence": "visible"},
        "revealed_tool_names": [], "introduced_tool_names": [], "deferred_capability_ids": [], "deferred_capabilities": [],
        "output_mode": "text", "output_object": None, "output_tools": [], "prompted_output_template": None,
        "allow_text_output": True, "allow_image_output": False,
        "instruction_parts": [{"content": instructions[0]["content"], "dynamic": False, "on_change": "rewrite",
                               "name": None, "id": "agent", "part_kind": "instruction"}],
        "instruction_visibility": None, "thinking": None, "cache": None}
    require(context.digest(params) == context.digest(expected_params), "native prepared parameters differ from pinned contract")


def wire_from_witness(witness, config, operations):
    """Reconstruct the exact submitted payload using journal-bound raw outputs."""
    context, runtime = _modules()
    require, digest = context.require, context.digest
    require(isinstance(witness, dict) and set(witness) == {"schema", "messages", "parameters", "settings"}
            and witness["schema"] == WITNESS_SCHEMA and witness["settings"] is None
            and isinstance(witness["messages"], list) and isinstance(witness["parameters"], dict),
            "native request witness schema mismatch")
    _validate_parameters(witness["parameters"], runtime, context)
    require(digest(witness["messages"]) == digest(_normalized(witness["messages"])), "native witness is not normalized")
    transcript, calls, seen_calls = [], {}, set()
    for message in witness["messages"]:
        require(isinstance(message, dict) and isinstance(message.get("parts"), list), "native message malformed")
        if message.get("kind") == "response":
            raw = _bound_response(message, operations, digest, require)
            transcript.extend(copy.deepcopy(raw["output"]))
            for item in raw["output"]:
                if item["type"] == "function_call":
                    require(item["call_id"] not in seen_calls, "native history repeats call id")
                    seen_calls.add(item["call_id"])
                    calls[item["call_id"]] = item
            continue
        require(message.get("kind") == "request", "unsupported native message kind")
        for part in message["parts"]:
            require(isinstance(part, dict), "native request part malformed")
            kind = part.get("part_kind")
            if kind in {"user-prompt", "system-prompt"}:
                require(isinstance(part.get("content"), str), "native media input unsupported")
                transcript.append({"role": "user" if kind == "user-prompt" else "system", "content": part["content"]})
            elif kind == "tool-return":
                call_id = part.get("tool_call_id")
                require(isinstance(call_id, str) and call_id in calls
                        and part.get("tool_name") == "read_evidence" and part.get("outcome") == "success",
                        "unsupported native tool result")
                operation = operations.get("tool:" + call_id)
                require(operation is not None and operation["finish"] is not None and operation["finish"]["kind"] == "FINISHED"
                        and digest(part.get("content")) == digest(operation["finish"]["data"]),
                        "native tool result not journal-bound")
                transcript.append({"type": "function_call_output", "call_id": call_id,
                                   "output": json.dumps(part["content"], ensure_ascii=False, sort_keys=True)})
                del calls[call_id]
            else:
                raise context.Refused("unsupported native request part")
    require(not calls, "native history has unanswered tool calls")
    model = next(iter(config["models"].values()))
    return {"model": model["model"], "input": transcript,
            "instructions": witness["parameters"]["instruction_parts"][0]["content"],
            "tools": runtime.tool_schemas(["read_evidence"]), "parallel_tool_calls": False,
            "max_output_tokens": model["max_output_tokens"], "store": False,
            "include": ["reasoning.encrypted_content"], "service_tier": "default"}


def _bound_response(message, operations, digest, require):
    details = message.get("provider_details")
    require(isinstance(details, dict) and set(details) == {"e156_native_response"}, "native response binding missing")
    binding = details["e156_native_response"]
    require(isinstance(binding, dict) and set(binding) == {
        "model_operation_id", "response_sha256", "request_sha256", "projection_sha256"}, "native response binding malformed")
    require(all(isinstance(v, str) for v in binding.values()), "native response binding values malformed")
    operation = operations.get(binding["model_operation_id"])
    require(operation is not None and operation["finish"] is not None
            and operation["finish"]["kind"] in {"FINISHED", "RECONCILED"}, "native response not journaled")
    raw = operation["finish"]["data"]
    require(binding["response_sha256"] == digest(raw)
            and binding["request_sha256"] == operation["reservation"]["request_sha256"]
            and binding["projection_sha256"] == digest(_projection(message)), "native response history changed")
    expected_parts = []
    for item in raw["output"]:
        common = {"id": item.get("id"), "provider_name": "openai", "provider_details": None}
        if item["type"] == "message":
            expected_parts.extend({**common, "part_kind": "text", "content": part["text"], "citations": None}
                                  for part in item["content"])
        elif item["type"] == "reasoning":
            expected_parts.append({**common, "part_kind": "thinking", "content": "\n".join(p["text"] for p in item["summary"]),
                                   "signature": item.get("encrypted_content")})
        else:
            expected_parts.append({**common, "part_kind": "tool-call", "tool_name": item["name"], "args": item["arguments"],
                                   "tool_call_id": item["call_id"], "tool_kind": None})
    require(digest(message["parts"]) == digest(expected_parts)
            and message.get("model_name") == raw["model"] and message.get("model_id") == "openai:" + raw["model"]
            and message.get("provider_name") == "openai" and message.get("provider_response_id") == raw["id"],
            "native response projection differs from received data")
    usage = message.get("usage")
    require(isinstance(usage, dict), "native response usage missing")
    for field, expected in (("input_tokens", raw["usage"]["input_tokens"]), ("output_tokens", raw["usage"]["output_tokens"]),
                            ("cache_read_tokens", raw["usage"].get("input_tokens_details", {}).get("cached_tokens", 0)),
                            ("output_reasoning_tokens", raw["usage"].get("output_tokens_details", {}).get("reasoning_tokens", 0))):
        require(digest(usage.get(field)) == digest(expected), "native response usage differs from received data")
    return raw


class _Terminal(Exception):
    def __init__(self, status):
        self.status = status


def run(config, manifest, root, state, *, provider=None, allow_paid=False, create=False):
    context, runtime = _modules()
    require, digest = context.require, context.digest
    validate_config(config)
    actual_environment = environment()
    require(digest(actual_environment) == config["native_runtime"]["environment_sha256"], "native environment changed")
    _environment_helper().install_source_only({key: actual_environment[key] for key in ("dependencies", "execution_files")})
    from pydantic import Field, StrictStr, TypeAdapter
    from pydantic_ai import Agent, Tool, RunContext
    from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior
    from pydantic_ai.messages import (ModelRequest, ModelResponse, UserPromptPart, TextPart, ThinkingPart,
                                      ToolCallPart, ModelMessagesTypeAdapter)
    from pydantic_ai.models import Model, check_allow_model_requests
    from pydantic_ai.usage import RequestUsage, UsageLimits
    from pydantic_ai_harness.detect_loops import DetectLoops, LoopDetectedError

    journal = runtime.Journal(state, config, manifest, root, create=create)
    packed = context.pack(root, manifest, config["selected"], config["skills"], max_chars=config["limits"]["context_chars"])
    require(packed["tools"] == ["read_evidence"], "native adapter requires exactly read_evidence access")
    provider = provider if provider is not None else runtime.Responses(allow_paid=allow_paid)
    model_config = next(iter(config["models"].values()))

    class CheckedModel(Model):
        def __init__(self):
            super().__init__()
            self.turn = 0
            self.last_raw = None
            self.last_operation = None
            self.seen_calls = set()

        @property
        def model_name(self):
            return model_config["model"]

        @property
        def system(self):
            return "openai"

        async def request(self, messages, model_settings, model_request_parameters):
            check_allow_model_requests()
            settings, params = self.prepare_request(model_settings, model_request_parameters)
            serialized = _normalized(json.loads(ModelMessagesTypeAdapter.dump_json(messages)))
            parameters = json.loads(TypeAdapter(type(params)).dump_json(params))
            require(settings is None, "native model settings outside frozen policy")
            _validate_parameters(parameters, runtime, context)
            witness = {"schema": WITNESS_SCHEMA, "messages": serialized, "parameters": parameters, "settings": settings}
            operations = journal.operations(journal.events())
            payload = wire_from_witness(witness, config, operations)
            payload_sha, turn = digest(payload), self.turn
            self.turn += 1

            def count(timeout):
                require(context.timestamp(model_config["price_expires_at"]) > datetime.now(timezone.utc), "price policy expired")
                value = provider.count(payload, timeout)
                try:
                    require(isinstance(value, dict), "native token count missing")
                    context.integer(value.get("input_tokens"), "input count")
                except context.Refused:
                    raise runtime.ReceivedInvalid(value) from None
                return value, runtime.units()

            quote = journal.operation(f"count:{turn}", payload, runtime.units(wall_ms=journal.allowance()), count, witness=witness)
            require(digest(payload) == payload_sha, "native request changed after counting")
            reserve = runtime.units(model_calls=1, model_tokens=quote["input_tokens"] + model_config["max_output_tokens"],
                                    cost_microusd=runtime.price(model_config, quote["input_tokens"], model_config["max_output_tokens"]),
                                    wall_ms=journal.allowance())

            def respond(timeout):
                require(context.timestamp(model_config["price_expires_at"]) > datetime.now(timezone.utc), "price policy expired")
                raw = provider.respond(payload, timeout)
                try:
                    usage = _received(raw, model_config, quote, runtime, context)
                except (context.Refused, KeyError, TypeError, ValueError):
                    raise runtime.ReceivedInvalid(raw) from None
                return raw, usage

            operation_id = f"model:{turn}"
            raw = journal.operation(operation_id, payload, reserve, respond, witness=witness)
            _received(raw, model_config, quote, runtime, context)
            self.last_raw, self.last_operation = raw, operation_id
            if raw["status"] != "completed":
                raise _Terminal(raw["status"])
            parts = []
            for item in raw["output"]:
                if item["type"] == "message":
                    parts.extend(TextPart(p["text"], id=item.get("id"), provider_name="openai") for p in item["content"])
                elif item["type"] == "reasoning":
                    parts.append(ThinkingPart("\n".join(p["text"] for p in item["summary"]), id=item["id"],
                                              signature=item.get("encrypted_content"), provider_name="openai"))
                else:
                    require(item["call_id"] not in self.seen_calls, "native duplicate call id")
                    self.seen_calls.add(item["call_id"])
                    parts.append(ToolCallPart(item["name"], item["arguments"], item["call_id"], id=item.get("id"), provider_name="openai"))
            usage = raw["usage"]
            response = ModelResponse(parts=parts, model_name=raw["model"], model_id="openai:" + raw["model"],
                                     provider_name="openai", provider_response_id=raw["id"],
                                     usage=RequestUsage(input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"],
                                         cache_read_tokens=usage.get("input_tokens_details", {}).get("cached_tokens", 0),
                                         output_reasoning_tokens=usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)),
                                     finish_reason="tool_call" if any(i["type"] == "function_call" for i in raw["output"]) else "stop")
            projection = _projection(json.loads(ModelMessagesTypeAdapter.dump_json([response]))[0])
            response.provider_details = {"e156_native_response": {"model_operation_id": operation_id,
                "response_sha256": digest(raw), "request_sha256": payload_sha, "projection_sha256": digest(projection)}}
            return response

    checked_model = CheckedModel()

    def read_evidence(ctx: RunContext, id: StrictStr, offset: Annotated[int, Field(strict=True, ge=0)],
                      limit: Annotated[int, Field(strict=True, ge=1, le=16000)]):
        raw, model_operation = checked_model.last_raw, checked_model.last_operation
        require(isinstance(raw, dict), "native tool lacks model response")
        calls = [item for item in raw["output"] if item["type"] == "function_call"]
        args = {"id": id, "offset": offset, "limit": limit}
        require(len(calls) == 1 and calls[0]["call_id"] == ctx.tool_call_id and calls[0]["name"] == "read_evidence"
                and context.strict_json(calls[0]["arguments"].encode()) == args, "native tool dispatch mismatch")
        require(id in {node["id"] for node in packed["catalog"]}, "native tool evidence outside task scope")
        witness = {"schema": TOOL_WITNESS_SCHEMA, "model_operation_id": model_operation,
                   "response_sha256": digest(raw), "call_id": ctx.tool_call_id, "name": "read_evidence", "arguments": args}

        def execute(timeout):
            result = context.excerpt(root, manifest, id, offset=offset, limit=limit)
            return result, runtime.units(tool_calls=1)

        return journal.operation("tool:" + ctx.tool_call_id, {"name": "read_evidence", "arguments": args},
                                 runtime.units(tool_calls=1, wall_ms=journal.allowance()), execute, witness=witness)

    agent = Agent(checked_model, output_type=str, name="e156_native_pydantic", retries=0,
                  instructions=runtime.SYSTEM + "\n" + "\n".join(packed["instructions"]),
                  tools=[Tool(read_evidence, takes_ctx=True, description="Bounded read_evidence", strict=True,
                              sequential=True, max_retries=0)],
                  capabilities=[DetectLoops(**POLICY["detect_loops"])])
    # This pinned release moved instrumentation out of the constructor.
    # An explicit per-agent value overrides ambient Agent.instrument_all().
    agent.instrument = False
    prediction = None
    try:
        agent.run_sync(json.dumps({"trust": packed["trust"], "catalog": packed["catalog"], "evidence": packed["evidence_text"],
                                   "truncated": packed["truncated"]}),
                       message_history=[ModelRequest(parts=[UserPromptPart(config["task"])])],
                       usage_limits=UsageLimits(request_limit=config["limits"]["model_calls"],
                           tool_calls_limit=config["limits"]["tool_calls"], total_tokens_limit=config["limits"]["model_tokens"]))
        try:
            prediction = runtime.prediction(checked_model.last_raw)
            status = termination = "COMPLETED"
        except (context.Refused, TypeError, KeyError, ValueError):
            status, termination = "REFUSED", "OUTPUT_VALIDATION"
    except runtime.Unresolved:
        status = termination = "UNRESOLVED"
    except runtime.BudgetStop:
        status = termination = "BUDGET_STOP"
    except UsageLimitExceeded:
        status, termination = "BUDGET_STOP", "NATIVE_USAGE_LIMIT"
    except LoopDetectedError:
        status, termination = "REFUSED", "LOOP_DETECTED"
    except UnexpectedModelBehavior:
        status, termination = "REFUSED", "NATIVE_VALIDATION"
    except _Terminal as exc:
        status, termination = ("CANCELLED", "CANCELLED") if exc.status == "cancelled" else ("REFUSED", "PROVIDER_TERMINAL")
    except context.Refused:
        status, termination = "REFUSED", "CONTRACT_REFUSED"
    require(digest(environment()) == config["native_runtime"]["environment_sha256"], "native environment changed during run")
    return describe_report(journal.report(status, prediction), config, termination)
