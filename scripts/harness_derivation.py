"""Execute a checked Docker derivation and publish locally bound evidence receipts.

Receipts are unsigned consistency evidence from a trusted local producer, not
authentication, source truth, or proof against an owner who replaces all files.
Validation never executes recipe code. Only the explicit run action executes it.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re

if __package__:
    from scripts import harness_context as context, harness_worker as worker
else:
    import harness_context as context
    import harness_worker as worker

require, Refused, digest = context.require, context.Refused, context.digest
PROFILE_FILES = ("harness_derivation.py", "harness_context.py", "harness_worker.py",
                 "bounded_native.py", "component_source.py", "component_lock.py", "synthesis_replay.py", "synthesis_blind_eval.py")
REFERENCE_FIELDS = {"receipt_file", "receipt_sha256", "recipe_file", "recipe_sha256"}
RESULT_FIELDS = {"trust", "image", "container_removed", "input_hashes", "code_sha256", "stdout", "stderr"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def profile():
    return {name: sha((Path(__file__).parent / name).read_bytes()) for name in PROFILE_FILES}


def _hash(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid derivation hash")


def _timeout(value):
    require(type(value) in (int, float) and math.isfinite(value) and 1 <= value <= 300,
            "invalid derivation timeout")


def _result(value, policy, inputs, recipe_hash):
    require(isinstance(value, dict) and set(value) == RESULT_FIELDS, "worker result fields mismatch")
    require(value["trust"] == "UNTRUSTED_WORKER_OUTPUT" and value["image"] == policy["image"]
            and value["container_removed"] is True, "worker execution/cleanup not established")
    require(value["input_hashes"] == {key: row["sha256"] for key, row in inputs.items()}
            and value["code_sha256"] == recipe_hash, "worker input/recipe binding mismatch")
    require(isinstance(value["stdout"], str) and isinstance(value["stderr"], str), "worker streams required")
    require(all(len(value[key].encode("utf-8")) <= context.MAX_FILE for key in ("stdout", "stderr")),
            "worker stream exceeds artifact limit")


def bindings(nodes, states, parents):
    return {key: {"sha256": nodes[key]["sha256"], "lineage_sha256": states[key]["lineage_sha256"]}
            for key in sorted(parents)}


def validate(root, node, inputs):
    """Check retained execution evidence against current graph; never run code."""
    ref = node["derivation"]
    require(isinstance(ref, dict) and set(ref) == REFERENCE_FIELDS, "derivation reference fields mismatch")
    for field in ("receipt_sha256", "recipe_sha256"): _hash(ref[field])
    raw = context.read_bytes(context.artifact(root, ref["receipt_file"]))
    require(sha(raw) == ref["receipt_sha256"], "derivation receipt changed")
    recipe = context.read_bytes(context.artifact(root, ref["recipe_file"]))
    require(sha(recipe) == ref["recipe_sha256"], "derivation recipe changed")
    receipt = context.strict_json(raw)
    require(isinstance(receipt, dict) and set(receipt) == {"schema", "node", "inputs", "recipe_sha256", "execution"}
            and receipt["schema"] == "e156-derivation-receipt-v1", "derivation receipt schema mismatch")
    require(receipt["node"] == {k: v for k, v in node.items() if k != "derivation"}
            and receipt["inputs"] == inputs and receipt["recipe_sha256"] == ref["recipe_sha256"],
            "derivation lineage/output binding mismatch")
    execution = receipt["execution"]
    require(isinstance(execution, dict) and set(execution) == {
        "started_at", "ended_at", "runner_profile", "worker_policy", "timeout_seconds", "result"},
        "derivation execution fields mismatch")
    require(context.timestamp(execution["started_at"]) <= context.timestamp(execution["ended_at"]),
            "derivation execution chronology invalid")
    recorded = execution["runner_profile"]
    require(isinstance(recorded, dict) and set(recorded) == set(PROFILE_FILES), "derivation runner profile missing")
    for value in recorded.values(): _hash(value)
    # Historical producer hashes are retained, not silently compared to new code.
    worker.policy_check(execution["worker_policy"])
    _timeout(execution["timeout_seconds"])
    _result(execution["result"], execution["worker_policy"], inputs, ref["recipe_sha256"])
    require(sha(execution["result"]["stdout"].encode("utf-8")) == node["sha256"],
            "derivation output is not recorded worker stdout")


def _fresh(path):
    require(not context.guard(path).exists(), "derivation output already exists; use a new revision path")


def _exclusive_bytes(path, raw):
    with context.guard(path).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def run(root, manifest, spec, output_manifest, *, extra_inputs=()):
    """Create artifact, then receipt, then new manifest; never overwrite inputs."""
    require(isinstance(spec, dict) and set(spec) == {
        "schema", "node", "recipe_file", "receipt_file", "worker", "timeout_seconds"}
        and spec["schema"] == "e156-derivation-request-v1", "derivation request schema mismatch")
    require(isinstance(spec["node"], dict) and set(spec["node"]) == {"id", "kind", "file", "parents", "expires_at"}
            and spec["node"]["kind"] in context.KINDS - {"source", "skill"}, "derived node descriptor required")
    worker.policy_check(spec["worker"])
    _timeout(spec["timeout_seconds"])
    original_manifest, original_spec = digest(manifest), digest(spec)
    manifest, spec = copy.deepcopy(manifest), copy.deepcopy(spec)
    nodes, _ = context.index(manifest)
    node = spec["node"]
    # Validate the proposed topology before executing anything. This provisional
    # empty-output hash is never published or described as a calculation result.
    proposed = {**manifest, "nodes": [n for n in manifest["nodes"] if n["id"] != node["id"]]
                + [{**node, "sha256": sha(b"")}]}
    context.index(proposed)
    parents = node["parents"]
    states = context.inspect(root, manifest)
    require(all(key in nodes and states[key]["status"] == "CURRENT" for key in parents),
            "derivation parents are not current")
    inputs = bindings(nodes, states, parents)
    recipe_path = context.artifact(root, spec["recipe_file"])
    recipe_bytes = context.read_bytes(recipe_path)
    require(0 < len(recipe_bytes) <= 65536, "recipe size invalid")
    try: code = recipe_bytes.decode("utf-8")
    except UnicodeError as exc: raise Refused("recipe must be UTF-8") from exc
    recipe_hash = sha(recipe_bytes)
    destinations = [context.artifact(root, node["file"]), context.artifact(root, spec["receipt_file"]),
                    context.guard(output_manifest)]
    def check_paths():
        for i, path in enumerate(destinations):
            context.control_path(path, root, manifest, extra_inputs=(recipe_path, *extra_inputs,
                                 *[p for j, p in enumerate(destinations) if i != j]))
            _fresh(path)
    check_paths()
    runner_profile = profile()
    started = datetime.now(timezone.utc).isoformat()
    result = worker.execute(spec["worker"], root, manifest, parents, code, timeout=spec["timeout_seconds"])
    ended = datetime.now(timezone.utc).isoformat()
    require(digest(manifest) == original_manifest and digest(spec) == original_spec,
            "derivation configuration changed during execution")
    after = context.inspect(root, manifest)
    require(all(after[key]["status"] == "CURRENT" for key in parents)
            and bindings(nodes, after, parents) == inputs, "derivation inputs changed during execution")
    require(context.read_bytes(recipe_path) == recipe_bytes and profile() == runner_profile,
            "derivation recipe/runner changed during execution")
    _result(result, spec["worker"], inputs, recipe_hash)
    raw = result["stdout"].encode("utf-8")
    completed = {**node, "sha256": sha(raw)}
    receipt = {"schema": "e156-derivation-receipt-v1", "node": completed, "inputs": inputs,
               "recipe_sha256": recipe_hash, "execution": {"started_at": started, "ended_at": ended,
               "runner_profile": runner_profile, "worker_policy": spec["worker"],
               "timeout_seconds": spec["timeout_seconds"], "result": result}}
    receipt_raw = (json.dumps(receipt, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    require(len(receipt_raw) <= context.MAX_FILE, "derivation receipt exceeds limit")
    completed = {**completed, "derivation": {"receipt_file": spec["receipt_file"], "receipt_sha256": sha(receipt_raw),
                 "recipe_file": spec["recipe_file"], "recipe_sha256": recipe_hash}}
    updated = {**manifest, "nodes": [n for n in manifest["nodes"] if n["id"] != node["id"]] + [completed]}
    context.index(updated)
    check_paths()
    _exclusive_bytes(destinations[0], raw)
    _exclusive_bytes(destinations[1], receipt_raw)
    require(context.inspect(root, updated)[node["id"]]["status"] == "CURRENT", "new derivation failed validation")
    # A crash can leave orphan files or an unreadable partial manifest. Readers
    # refuse these; a valid new manifest is written only after complete evidence.
    # Retrying requires new revision paths, never implicit reruns.
    context.atomic_json(destinations[2], updated, exclusive=True)
    return updated


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("run",))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--output-manifest", type=Path, required=True)
    a = p.parse_args()
    try:
        result = run(a.root, context.strict_json(context.read_bytes(a.manifest)),
                     context.strict_json(context.read_bytes(a.spec)), a.output_manifest,
                     extra_inputs=(a.manifest, a.spec))
        print(json.dumps({"status": "DERIVATION_RECORDED", "manifest_sha256": digest(result),
                          "scientific_validation": "NOT_ESTABLISHED"}, sort_keys=True))
    except (Refused, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
