"""Bind local study evidence offline; never authenticate approval or run a model.

Inventory, context and reference-file hashes bind exact bytes. Arm config,
model-config and tools hashes bind canonical JSON through matched.digest.
Derivation receipts are checked for consistency, never executed or certified.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re

if __package__:
    from scripts import harness_context as context, synthesis_matched_eval as matched
else:
    import harness_context as context
    import synthesis_matched_eval as matched

Refused = context.Refused
require = context.require
digest = matched.digest
REFERENCE_ROLES = {"analysis_plan_reference", "custodian_receipt_reference",
                   "independent_review_plan_reference", "unseen_corpus_receipt_reference"}
ARM_FILES = {"config_file": "config_sha256", "model_config_file": "model_config_sha256",
             "tools_file": "tools_sha256"}
EXTERNAL = ("human_identity", "custody", "rights", "unseen_status", "budget_authorization",
            "reviewer_independence", "semantic_fidelity")
_UNSET = object()


def _keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + " fields mismatch")


def _text(value, label):
    require(isinstance(value, str) and value and value == value.strip(), "invalid " + label)
    return value


def _bound(actual, expected, label):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid " + label)
    require(hmac.compare_digest(actual, expected), label + " mismatch")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(name):
    _text(name, "relative path")
    path = PurePosixPath(name)
    require(str(path) == name and all(p == p.rstrip(" .") for p in path.parts), "noncanonical artifact path")
    return name  # context.artifact additionally refuses escapes and linked paths.


def _entries(rows, key, fields, label):
    require(isinstance(rows, list) and rows, "nonempty " + label + " required")
    result = {}
    for row in rows:
        _keys(row, fields, label)
        value = _text(row[key], key)
        require(value not in result, "duplicate " + label)
        result[value] = row
    return result


class _Files:
    def __init__(self, inputs, evidence):
        self.inputs, self.evidence = context.guard(inputs).resolve(), context.guard(evidence).resolve()
        require(self.inputs.is_dir() and self.evidence.is_dir(), "study roots must exist")
        require(self.inputs != self.evidence and self.inputs not in self.evidence.parents
                and self.evidence not in self.inputs.parents, "input and private evidence roots must be separate")
        self.seen = {}

    def read(self, name, *, private, expected=_UNSET):
        root = self.evidence if private else self.inputs
        path = context.artifact(root, _path(name))
        raw = context.read_bytes(path)
        observed = _sha(raw)
        if expected is not _UNSET:
            _bound(observed, expected, "artifact SHA-256")
        for previous, (old_hash, old_private) in self.seen.items():
            if path == previous or os.path.samefile(path, previous):
                require(private == old_private, "private evidence aliases public input")
                _bound(observed, old_hash, "artifact changed during preflight")
        self.seen[path] = observed, private
        return raw

    def verify(self):
        for path, (expected, _) in self.seen.items():
            _bound(_sha(context.read_bytes(path)), expected, "artifact changed during preflight")


def preflight(manifest, protocol, inventory, inputs, evidence):
    """Verify supplied file bindings, retaining all external requirements as unmet."""
    files = _Files(inputs, evidence)
    _keys(inventory, {"schema", "manifest_sha256", "protocol_sha256", "references", "arms", "tasks"}, "inventory")
    require(inventory["schema"] == "synthesis-study-evidence-inventory-v1", "inventory schema mismatch")
    _bound(digest(manifest), inventory["manifest_sha256"], "inventory manifest scope")
    _bound(digest(protocol), inventory["protocol_sha256"], "inventory protocol scope")
    require(isinstance(protocol, dict) and isinstance(protocol.get("tasks"), list), "protocol tasks required")
    # Record every task/source before prepare; both readers enforce size bounds.
    for task in protocol["tasks"]:
        require(isinstance(task, dict) and isinstance(task.get("source_files"), list), "task source inventory required")
        files.read(task.get("input_file"), private=False, expected=task.get("input_sha256"))
        for source in task["source_files"]:
            _keys(source, {"file", "sha256"}, "source")
            files.read(source["file"], private=False, expected=source["sha256"])
    try:
        prepared = matched.prepare(manifest, protocol, files.inputs)
    except matched.Refused as exc:
        raise Refused(str(exc)) from exc

    references = _entries(inventory["references"], "role", {"role", "reference", "file", "sha256"}, "reference mapping")
    roles = {"analysis_plan_reference"} if protocol["purpose"] == "development" else REFERENCE_ROLES
    require(set(references) == roles, "required study references missing or extra")
    reference_results = {}
    for role, row in references.items():
        require(row["reference"] == _text(protocol.get(role), role), "reference differs from protocol")
        raw = files.read(row["file"], private=True, expected=row["sha256"])
        record = context.strict_json(raw)
        _keys(record, {"schema", "role", "reference", "manifest_sha256", "protocol_sha256", "statement"}, "reference envelope")
        require(record["schema"] == "synthesis-study-reference-v1" and record["role"] == role
                and record["reference"] == row["reference"], "reference envelope identity mismatch")
        _bound(digest(manifest), record["manifest_sha256"], "reference manifest scope")
        _bound(digest(protocol), record["protocol_sha256"], "reference protocol scope")
        _text(record["statement"], "reference statement")
        reference_results[role] = {"file_sha256": _sha(raw), "status": "FILE_BOUND_NOT_AUTHENTICATED"}

    arm_files = _entries(inventory["arms"], "arm_id", {"arm_id", *ARM_FILES}, "arm mapping")
    arms = {a["arm_id"]: a for a in protocol["arms"]}
    require(set(arm_files) == set(arms), "arm mapping inventory mismatch")
    arm_results = {}
    for aid, row in arm_files.items():
        arm_results[aid] = {}
        for field, hash_field in ARM_FILES.items():
            raw = files.read(row[field], private=True)
            value = context.strict_json(raw)
            require(isinstance(value, dict), "arm artifact must be a JSON object")
            canonical_hash = digest(value)
            _bound(canonical_hash, arms[aid][hash_field], "arm canonical JSON " + hash_field)
            arm_results[aid][hash_field] = {"canonical_json_sha256": canonical_hash, "file_sha256": _sha(raw)}

    mappings = _entries(inventory["tasks"], "claim_id", {"claim_id", "context_file", "context_sha256", "node_id"}, "task mapping")
    tasks = {t["claim_id"]: t for t in protocol["tasks"]}
    require(set(mappings) == set(tasks), "task mapping inventory mismatch")
    task_results = {}
    for cid, mapping in mappings.items():
        raw = files.read(mapping["context_file"], private=True, expected=mapping["context_sha256"])
        graph = context.strict_json(raw)
        _keys(graph, {"schema", "nodes"}, "context manifest")
        nodes, _ = context.index(graph)
        node_id = _text(mapping["node_id"], "node_id")
        require(node_id in nodes, "task node missing")
        node, task = nodes[node_id], tasks[cid]
        require(node["kind"] != "skill" and node["file"] == task["input_file"], "task node/file binding mismatch")
        _bound(node["sha256"], task["input_sha256"], "task node hash")
        # Track all reads made by inspect, including derivation evidence; do not run it.
        for item in nodes.values():
            files.read(item.get("file"), private=False, expected=item["sha256"])
            if "derivation" in item:
                for kind in ("recipe", "receipt"):
                    files.read(item["derivation"][kind + "_file"], private=False,
                               expected=item["derivation"][kind + "_sha256"])
        states = context.inspect(files.inputs, graph)
        require(all(s["status"] == "CURRENT" for s in states.values()), "context evidence not current or receipt-bound")
        reachable, pending = set(), [node_id]
        while pending:
            key = pending.pop()
            if key not in reachable:
                reachable.add(key)
                pending.extend(nodes[key]["parents"])
        source_rows = [(nodes[k]["file"], nodes[k]["sha256"]) for k in reachable if nodes[k]["kind"] == "source"]
        declared = [(s["file"], s["sha256"]) for s in task["source_files"]]
        require(len(source_rows) == len(set(source_rows)) and set(source_rows) == set(declared),
                "reachable sources differ from task source inventory")
        require(node["kind"] == "source" or all("derivation" in nodes[k]
                for k in reachable if nodes[k]["kind"] != "source"), "derived ancestor lacks receipt")
        task_results[cid] = {"status": "RAW_SOURCE" if node["kind"] == "source" else "RECEIPT_BOUND",
                             "input_sha256": task["input_sha256"], "context_file_sha256": _sha(raw),
                             "node_sha256": digest(node), "source_count": len(source_rows)}
    files.verify()
    return {"schema": "synthesis-study-preflight-v1", "status": "EVIDENCE_BOUND_NOT_RUN",
            "purpose": protocol["purpose"], "manifest_sha256": digest(manifest),
            "protocol_sha256": prepared["protocol_sha256"], "inventory_sha256": digest(inventory),
            "references": reference_results, "arms": arm_results, "tasks": task_results,
            "external_requirements": {field: "UNVERIFIED_EXTERNAL" for field in EXTERNAL},
            "scientific_results": None,
            "limitations": ["File and receipt consistency does not authenticate approval, execution or scientific truth.",
                            "Recipe code is never executed by this preflight; semantic fidelity remains unverified.",
                            "Adapters must expose only the frozen task/source allowlist, never entire input or private evidence directories.",
                            "No model calls, study execution or budget enforcement is performed."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "protocol", "inventory", "inputs", "evidence", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        originals = {name: context.read_bytes(getattr(args, name)) for name in ("manifest", "protocol", "inventory")}
        result = preflight(*(context.strict_json(originals[name]) for name in ("manifest", "protocol", "inventory")),
                           args.inputs, args.evidence)
        for name, raw in originals.items():
            _bound(_sha(context.read_bytes(getattr(args, name))), _sha(raw), "control input changed")
        context.atomic_json(args.output, result, exclusive=True)
    except (Refused, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        # Detailed local exceptions can contain private paths or JSON field names.
        # CLI diagnostics may be retained in shared automation logs.
        parser.error("study preflight refused (" + type(exc).__name__ + "); inspect private inputs locally")


if __name__ == "__main__":
    main()
