"""Content-minimized trace export and exact-request offline regression replay.

Hash chains detect accidental modification, not forgery by a host controlling
the entire record. Private input reports contain prompts, sources and responses.
"""
from __future__ import annotations

import argparse
import copy
import hmac
import json
from pathlib import Path
import sqlite3

if __package__:
    from scripts import harness_runtime as runtime
else:
    import harness_runtime as runtime

context = runtime.context
require, digest = context.require, context.digest
STATUSES = {"PREPARED_NOT_RUN", "INSPECTED", "COMPLETED", "CANCELLED", "BUDGET_STOP",
            "UNRESOLVED", "REFUSED", "RECONCILED_NOT_RESUMED", "STALLED"}


def validate(report):
    require(isinstance(report, dict) and report.get("schema") == "e156-harness-run-v1", "private run schema required")
    require(report.get("status") in STATUSES, "unknown run status")
    events = report.get("events")
    require(isinstance(events, list) and events, "complete event history required")
    previous = None
    for event in events:
        require(isinstance(event, dict) and event.get("previous") == previous, "broken trace event chain")
        context.timestamp(event.get("at"))
        previous = digest(event)
    require(events[0].get("kind") == "READY", "trace anchor required")
    anchor = events[0].get("anchor")
    require(isinstance(anchor, dict) and isinstance(anchor.get("code"), dict), "trace code anchor required")
    for key in ("config_sha256", "context_sha256"):
        require(report.get(key) == anchor.get(key) and isinstance(anchor.get(key), str)
                and len(anchor[key]) == 64 and all(c in "0123456789abcdef" for c in anchor[key]), "trace binding mismatch")
    require(report.get("actual_billed_usd") is None and report.get("scientific_disposition") == "HOLD", "trace evidence boundary changed")
    require(report.get("cost_basis") == "CONSERVATIVE_FROZEN_PRICE_POLICY_NOT_INVOICE"
            and report.get("resource_accounting") == "VALIDATED_USAGE_OR_UNRESOLVED_RESERVATION", "trace accounting basis changed")
    operations = runtime.Journal.operations(events)
    require(report.get("usage") == runtime.Journal.totals(operations), "trace usage summary mismatch")
    # Older v1 reports have no redundant accounting or identity summaries.
    for key, expected in (("run_id", digest(events[0])), ("journal_sha256", digest(events[-1])),
                          ("accounting", runtime.accounting(operations))):
        if key in report:
            require(report[key] == expected, "trace identity/accounting summary mismatch")
    if report["status"] in {"COMPLETED", "CANCELLED", "STALLED"}:
        require(all(op["finish"] and op["finish"]["kind"] != "UNRESOLVED" for op in operations.values()),
                "completed trace contains unresolved attempts")
    if report["status"] == "STALLED":
        stop = report.get("stop")
        require(isinstance(stop, dict) and stop.get("reason") == "REPEATED_TOOL_RESULT", "stall summary required")
        context.integer(stop.get("limit"), "stall limit", minimum=2)
        require(stop["limit"] <= 100 and report.get("prediction") is None, "invalid stall policy/prediction")
        progress, observed = runtime.Progress(stop["limit"]), None
        for key, op in operations.items():
            if not key.startswith("model:"):
                continue
            require(observed is None, "model executed after declared stall")
            calls = [c for c in op["finish"]["data"].get("output", []) if c.get("type") == "function_call"]
            if not calls:
                progress = runtime.Progress(stop["limit"])
                continue
            require(len(calls) == 1, "unsupported stall calls")
            call = calls[0]
            request = {"name": call.get("name"), "arguments": context.strict_json(call.get("arguments", "").encode("utf-8"))}
            tool = operations.get("tool:" + call.get("call_id", ""))
            require(tool and tool["reservation"]["request"] == request, "stall tool binding mismatch")
            observed = progress.observe(request, tool["finish"]["data"])
        require(observed == stop, "stall summary does not match recorded results")
    else:
        require(report.get("stop") is None, "unexpected stall summary")
    return operations


def export(report):
    """Allowlisted metadata only; hashes and timing can still identify a run."""
    operations = validate(report)
    events = report["events"]
    run_id = digest(events[0])
    attempts = []
    for key, op in operations.items():
        start, end = op["reservation"], op["finish"]
        category = key.split(":", 1)[0]
        state = end["kind"] if end else "IN_FLIGHT"
        settled = state in {"FINISHED", "RECONCILED"}
        attempts.append({
            "attempt_id": digest([run_id, key]), "category": category if category in {"count", "model", "tool"} else "other",
            "state": state, "request_sha256": start["request_sha256"],
            "result_sha256": digest(end["data"]) if settled else None,
            "received_sha256": digest(end["received"]) if end and end.get("received") is not None else None,
            "reserved": start["reserved"], "usage": end["usage"] if settled else None,
            "wall_basis": "RESERVATION_CEILING" if not settled or state == "RECONCILED" else "MEASURED_OPERATION",
            "started_at": context.timestamp(start["at"]).isoformat(),
            "settled_at": context.timestamp(end["at"]).isoformat() if end else None,
            "history": [e["kind"] for e in events[1:] if e["id"] == key],
        })
    return {"schema": "e156-harness-trace-v1", "run_id": run_id, "journal_sha256": digest(events[-1]),
            "config_sha256": report["config_sha256"], "context_sha256": report["context_sha256"],
            "code_sha256": digest(events[0]["anchor"]["code"]), "status": report["status"],
            "stop_reason": report.get("stop", {}).get("reason"),
            "attempts": attempts, "accounting": runtime.accounting(operations), "usage": report["usage"],
            "actual_billed_usd": None, "scientific_disposition": "HOLD",
            "disclosure": "CONTENT_OMITTED_HASHES_AND_TIMING_REMAIN_LINKABLE",
            "integrity_basis": "LOCAL_HASH_CHAIN_NOT_EXTERNAL_AUTHENTICATION"}


class RecordedProvider:
    """No network adapter, fallback, or invented response for unmatched requests."""
    def __init__(self, report):
        operations = validate(report)
        require(report["status"] in {"COMPLETED", "STALLED", "BUDGET_STOP", "REFUSED", "CANCELLED"},
                "run status cannot seed offline regressions")
        self.records = []
        for key, op in operations.items():
            category = key.split(":", 1)[0]
            require(category in {"count", "model", "tool"}, "unsupported recorded operation")
            require(op["finish"] and op["finish"]["kind"] in {"FINISHED", "RECONCILED"}, "unresolved trace cannot be replayed")
            if category != "tool":
                self.records.append((category, op["reservation"]["request_sha256"], copy.deepcopy(op["finish"]["data"])))
        require(self.records, "provider transcript is empty")
        self.position = 0

    def _take(self, kind, payload):
        require(self.position < len(self.records), "unrecorded provider call refused")
        category, request, response = self.records[self.position]
        require(category == kind and hmac.compare_digest(request, digest(payload)), "recorded request mismatch")
        self.position += 1
        return copy.deepcopy(response)

    def count(self, payload, timeout):
        return self._take("count", payload)

    def respond(self, payload, timeout):
        return self._take("model", payload)


def replay(report, config, manifest, root, state):
    provider = RecordedProvider(report)
    require(digest(config) == report["config_sha256"] and digest(manifest) == report["context_sha256"], "replay input binding mismatch")
    result = runtime.run(config, manifest, root, state, provider=provider, create=True)
    original = validate(report)
    repeated = validate(result)

    def signatures(operations):
        return [(key, op["reservation"]["request_sha256"], digest(op["finish"]["data"]))
                for key, op in operations.items() if op["finish"] and op["finish"]["kind"] in {"FINISHED", "RECONCILED"}]

    def non_wall(values):
        return {key: value for key, value in values.items() if key != "wall_ms"}

    def resources(operations):
        return [(key, non_wall(op["reservation"]["reserved"]),
                 non_wall(op["finish"]["usage"]) if op["finish"] and op["finish"]["kind"] in {"FINISHED", "RECONCILED"} else None)
                for key, op in operations.items()]

    checks = {"provider_transcript_consumed": provider.position == len(provider.records),
              "status_matches": result["status"] == report["status"],
              "prediction_matches": result["prediction"] == report["prediction"],
              "stop_matches": result.get("stop") == report.get("stop"),
              "operation_results_match": signatures(original) == signatures(repeated),
              "resource_accounting_matches": resources(original) == resources(repeated)
                  and non_wall(result["usage"]) == non_wall(report["usage"])}
    return {"schema": "e156-harness-regression-v1", "verdict": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks, "original_run_id": digest(report["events"][0]), "replay_run_id": result["run_id"],
            "original_code": report["events"][0]["anchor"]["code"], "replay_code": runtime.profile(),
            "provider_mode": "OFFLINE_RECORDED_RESPONSES", "scientific_disposition": "HOLD", "run": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "replay"))
    for field in ("input", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    for field in ("config", "manifest", "root", "state"):
        parser.add_argument("--" + field, type=Path)
    args = parser.parse_args()
    try:
        report = context.strict_json(context.read_bytes(args.input))
        context.guard(args.output)
        require(not args.output.exists(), "output already exists")
        if args.action == "export":
            result = export(report)
        else:
            require(all((args.config, args.manifest, args.root, args.state)), "replay requires config, manifest, root and new state")
            config = context.strict_json(context.read_bytes(args.config))
            manifest = context.strict_json(context.read_bytes(args.manifest))
            inputs = (args.input, args.config, args.manifest)
            context.control_path(args.state, args.root, manifest, sqlite=True, creating=True, extra_inputs=inputs)
            context.control_path(args.output, args.root, manifest, extra_inputs=inputs + (args.state,))
            result = replay(report, config, manifest, args.root, args.state)
        context.atomic_json(args.output, result, exclusive=True)
        if result.get("verdict") == "FAIL":
            raise SystemExit(1)
    except (context.Refused, OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
