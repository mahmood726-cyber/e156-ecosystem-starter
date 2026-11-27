"""Synthetic evidence bindings only: no corpus, human approval or model execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from scripts import harness_context as context, harness_derivation as derivation
from scripts import synthesis_study_preflight as study


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return sha(raw)


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("preflight must not execute worker or contact network")
    monkeypatch.setattr(derivation.worker, "execute", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def bundle(tmp_path):
    inputs, evidence = tmp_path / "public", tmp_path / "private"
    inputs.mkdir(); evidence.mkdir()
    claims, tasks, mappings = [], [], []
    for index in (1, 2):
        cid, name = "T" + str(index), "paper" + str(index) + ".txt"
        raw = ("SYNTHETIC source fixture " + cid + ": no research evidence.").encode()
        (inputs / name).write_bytes(raw)
        claims.append({"claim_id": cid, "family_id": "SYNTHETIC-F" + str(index),
            "doi": "10.0000/SYNTHETIC-" + cid, "split": "test", "original_state": "VERIFIED_ORIGINAL",
            "original_version": "synthetic", "retrieval_path": "synthetic", "source_locator": "synthetic",
            "original_sha256": sha(raw)})
        tasks.append({"claim_id": cid, "input_file": name, "input_sha256": sha(raw),
            "oa_rights_reference": "Synthetic bytes only", "source_files": [{"file": name, "sha256": sha(raw)}]})
        graph = {"schema": "e156-harness-context-v1", "nodes": [{"id": "source", "kind": "source",
            "file": name, "sha256": sha(raw), "parents": [], "expires_at": None,
            "oa_rights_reference": "Synthetic bytes only"}]}
        context_name = cid + ".context.json"
        mappings.append({"claim_id": cid, "node_id": "source", "context_file": context_name,
                         "context_sha256": write_json(evidence / context_name, graph)})
    manifest = {"schema": "synthesis-blind-manifest-v1", "cohort_id": "SYNTHETIC",
        "selection_rule": "Synthetic contracts only", "seed": 9, "frozen_at": "2026-11-01T09:00:00Z",
        "claims": claims}
    arms, arm_files = [], []
    for aid in ("A", "B"):
        arm = {"arm_id": aid, "runtime": "synthetic", "runtime_version": "fixture-v1", "model_snapshot": "synthetic"}
        files = {"arm_id": aid}
        for field, hash_field in study.ARM_FILES.items():
            value = {"fixture": field, "private_canary": "PRIVATE-DO-NOT-EXPORT",
                     "value": aid if field == "config_file" else "shared"}
            name = aid + "." + field + ".json"
            write_json(evidence / name, value)
            files[field], arm[hash_field] = name, study.digest(value)
        arms.append(arm); arm_files.append(files)
    protocol = {"schema": "synthesis-matched-protocol-v1", "purpose": "prospective", "comparison_kind": "harness_only",
        "frozen_at": "2026-11-01T09:01:00Z", "manifest_sha256": study.digest(manifest), "arms": arms,
        "tasks": tasks, "retry_policy": "one_record_all_internal_attempts", "order_seed": 19,
        "limits": {"wall_seconds": 60, "model_tokens": 1000, "tool_calls": 10, "api_cost_usd": 1, "review_seconds": 120},
        **{role: "SYNTHETIC-DECLARATION-" + role for role in study.REFERENCE_ROLES}}
    inventory = {"schema": "synthesis-study-evidence-inventory-v1", "manifest_sha256": study.digest(manifest),
        "protocol_sha256": study.digest(protocol), "references": [], "arms": arm_files, "tasks": mappings}
    for role in sorted(study.REFERENCE_ROLES):
        name = role + ".json"
        record = {"schema": "synthesis-study-reference-v1", "role": role, "reference": protocol[role],
            "manifest_sha256": study.digest(manifest), "protocol_sha256": study.digest(protocol),
            "statement": "SYNTHETIC PRIVATE-DO-NOT-EXPORT: no human approval or unseen corpus supplied."}
        inventory["references"].append({"role": role, "reference": protocol[role], "file": name,
                                         "sha256": write_json(evidence / name, record)})
    return {"manifest": manifest, "protocol": protocol, "inventory": inventory, "inputs": inputs, "evidence": evidence}


def run(bundle):
    return study.preflight(**bundle)


def reseal(bundle):
    """Update only synthetic scope after deliberate protocol mutations."""
    m, p, inv = bundle["manifest"], bundle["protocol"], bundle["inventory"]
    p["manifest_sha256"] = study.digest(m)
    inv["manifest_sha256"], inv["protocol_sha256"] = study.digest(m), study.digest(p)
    for row in inv["references"]:
        path = bundle["evidence"] / row["file"]
        record = context.strict_json(path.read_bytes())
        record["manifest_sha256"], record["protocol_sha256"] = study.digest(m), study.digest(p)
        row["sha256"] = write_json(path, record)


def make_derived(bundle):
    mapping, task = bundle["inventory"]["tasks"][0], bundle["protocol"]["tasks"][0]
    path = bundle["evidence"] / mapping["context_file"]
    graph = context.strict_json(path.read_bytes())
    parent_states = context.inspect(bundle["inputs"], graph)
    output = "SYNTHETIC derived fixture, no actual execution claimed by this test."
    node = {"id": "derived", "kind": "extraction", "file": "derived.txt", "sha256": sha(output.encode()),
            "parents": ["source"], "expires_at": None}
    recipe = b"raise AssertionError('RECEIPT CODE MUST NEVER EXECUTE')\n"
    (bundle["inputs"] / "recipe.py").write_bytes(recipe)
    policy = {"image": "python@sha256:" + "a" * 64, "memory_mb": 128, "cpus": 1,
              "pids": 32, "tmp_mb": 16, "output_bytes": 65536}
    bindings = derivation.bindings({"source": graph["nodes"][0]}, parent_states, ["source"])
    receipt = {"schema": "e156-derivation-receipt-v1", "node": copy.deepcopy(node), "inputs": bindings,
        "recipe_sha256": sha(recipe), "execution": {"started_at": "2026-11-01T08:00:00Z",
        "ended_at": "2026-11-01T08:01:00Z", "runner_profile": {name: "a" * 64 for name in derivation.PROFILE_FILES},
        "worker_policy": policy, "timeout_seconds": 30, "result": {"trust": "UNTRUSTED_WORKER_OUTPUT",
        "image": policy["image"], "container_removed": True,
        "input_hashes": {key: value["sha256"] for key, value in bindings.items()}, "code_sha256": sha(recipe),
        "stdout": output, "stderr": ""}}}
    receipt_hash = write_json(bundle["inputs"] / "receipt.json", receipt)
    node["derivation"] = {"recipe_file": "recipe.py", "recipe_sha256": sha(recipe),
                           "receipt_file": "receipt.json", "receipt_sha256": receipt_hash}
    (bundle["inputs"] / node["file"]).write_bytes(output.encode())
    graph["nodes"].append(node)
    mapping["node_id"], mapping["context_sha256"] = "derived", write_json(path, graph)
    task["input_file"], task["input_sha256"] = node["file"], node["sha256"]
    reseal(bundle)
    return graph, path


def test_bound_files_never_claim_external_approval_or_export_private_data(bundle):
    result = run(bundle)
    assert result["status"] == "EVIDENCE_BOUND_NOT_RUN" and result["scientific_results"] is None
    assert {r["status"] for r in result["tasks"].values()} == {"RAW_SOURCE"}
    assert set(result["external_requirements"].values()) == {"UNVERIFIED_EXTERNAL"}
    encoded = json.dumps(result)
    assert "PRIVATE-DO-NOT-EXPORT" not in encoded and str(bundle["evidence"]) not in encoded
    assert all(row["file"] not in encoded for row in bundle["inventory"]["references"])


def test_derived_receipt_is_checked_without_executing_recipe(bundle):
    make_derived(bundle)
    result = run(bundle)
    assert result["tasks"]["T1"]["status"] == "RECEIPT_BOUND"
    assert result["external_requirements"]["semantic_fidelity"] == "UNVERIFIED_EXTERNAL"


@pytest.mark.parametrize("defect", ["missing", "output", "parent", "receipt", "recipe"])
def test_missing_or_changed_derived_evidence_refused(bundle, defect):
    graph, path = make_derived(bundle)
    node = graph["nodes"][-1]
    if defect == "missing":
        node.pop("derivation")
        bundle["inventory"]["tasks"][0]["context_sha256"] = write_json(path, graph)
    else:
        filename = {"output": "derived.txt", "parent": "paper1.txt", "receipt": "receipt.json", "recipe": "recipe.py"}[defect]
        (bundle["inputs"] / filename).write_bytes(b"SYNTHETIC altered bytes")
    with pytest.raises(study.Refused): run(bundle)


def test_forged_receipt_input_hash_rejected_even_when_receipt_rehashed(bundle):
    graph, path = make_derived(bundle)
    receipt = context.strict_json((bundle["inputs"] / "receipt.json").read_bytes())
    receipt["inputs"]["source"]["sha256"] = "0" * 64
    graph["nodes"][-1]["derivation"]["receipt_sha256"] = write_json(bundle["inputs"] / "receipt.json", receipt)
    bundle["inventory"]["tasks"][0]["context_sha256"] = write_json(path, graph)
    with pytest.raises(study.Refused, match="receipt-bound"): run(bundle)


@pytest.mark.parametrize("mapping", ["arms", "tasks", "references"])
@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate", "extra_field"])
def test_mapping_inventories_are_exact(bundle, mapping, defect):
    rows = bundle["inventory"][mapping]
    if defect == "missing": rows.pop()
    elif defect == "duplicate": rows.append(copy.deepcopy(rows[0]))
    elif defect == "extra_field": rows[0]["unexpected"] = True
    else:
        row = copy.deepcopy(rows[0]); row[{"arms": "arm_id", "tasks": "claim_id", "references": "role"}[mapping]] = "UNKNOWN"
        rows.append(row)
    with pytest.raises(study.Refused): run(bundle)


@pytest.mark.parametrize("field", ["manifest_sha256", "protocol_sha256"])
def test_inventory_scope_binding(bundle, field):
    bundle["inventory"][field] = "0" * 64
    with pytest.raises(study.Refused, match="scope"): run(bundle)


@pytest.mark.parametrize("defect", ["missing", "extra", "schema"])
def test_inventory_top_level_schema_is_strict(bundle, defect):
    if defect == "missing": bundle["inventory"].pop("references")
    elif defect == "extra": bundle["inventory"]["approved"] = True
    else: bundle["inventory"]["schema"] = "unknown"
    with pytest.raises(study.Refused): run(bundle)


@pytest.mark.parametrize("field,value", [("manifest_sha256", "0" * 64), ("protocol_sha256", "0" * 64),
    ("role", "wrong"), ("reference", "wrong"), ("statement", ""), ("unexpected", True)])
def test_reference_envelope_scope_is_inside_hashed_file(bundle, field, value):
    row = bundle["inventory"]["references"][0]
    path = bundle["evidence"] / row["file"]
    record = context.strict_json(path.read_bytes()); record[field] = value
    row["sha256"] = write_json(path, record)
    with pytest.raises(study.Refused): run(bundle)


@pytest.mark.parametrize("defect", ["missing", "tampered", "null_hash", "hash_only"])
def test_reference_file_required_and_bound(bundle, defect):
    row = bundle["inventory"]["references"][0]
    if defect == "missing": row["file"] = "absent.json"
    elif defect == "tampered": (bundle["evidence"] / row["file"]).write_bytes(b"{}")
    elif defect == "null_hash": row["sha256"] = None
    else: row.pop("file")
    with pytest.raises((study.Refused, OSError)): run(bundle)


def test_arm_configuration_hashes_are_canonical_json_and_files_required(bundle):
    row = bundle["inventory"]["arms"][0]
    path = bundle["evidence"] / row["config_file"]
    old = path.read_bytes(); value = context.strict_json(old)
    path.write_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
    result = run(bundle)
    assert result["arms"]["A"]["config_sha256"]["canonical_json_sha256"] == study.digest(value)
    assert result["arms"]["A"]["config_sha256"]["file_sha256"] != sha(old)
    value["changed"] = True; write_json(path, value)
    with pytest.raises(study.Refused, match="canonical JSON"): run(bundle)


@pytest.mark.parametrize("defect", ["node", "file", "hash", "source_inventory"])
def test_task_context_binding_and_exact_sources(bundle, defect):
    row = bundle["inventory"]["tasks"][0]; path = bundle["evidence"] / row["context_file"]
    graph = context.strict_json(path.read_bytes())
    if defect == "node": row["node_id"] = "absent"
    elif defect == "file": graph["nodes"][0]["file"] = "other.txt"
    elif defect == "hash": graph["nodes"][0]["sha256"] = "0" * 64
    else:
        source = copy.deepcopy(bundle["protocol"]["tasks"][1]["source_files"][0])
        bundle["protocol"]["tasks"][0]["source_files"].append(source)
        reseal(bundle)
    row["context_sha256"] = write_json(path, graph)
    with pytest.raises(study.Refused): run(bundle)


@pytest.mark.parametrize("name", ["../escape.json", "/absolute.json", "C:/absolute.json", "a\\b", "./alias.json"])
def test_evidence_path_escape_and_aliases_refused(bundle, name):
    bundle["inventory"]["references"][0]["file"] = name
    with pytest.raises(study.Refused): run(bundle)


@pytest.mark.parametrize("nested", [False, True])
def test_private_and_input_roots_cannot_overlap(bundle, nested):
    if nested:
        root = bundle["inputs"] / "nested"; root.mkdir()
    else: root = bundle["inputs"]
    bundle["evidence"] = root
    with pytest.raises(study.Refused, match="separate"): run(bundle)


def test_hardlinked_private_file_refused(bundle):
    source = bundle["inputs"] / "paper1.txt"
    target = bundle["evidence"] / "alias.txt"
    os.link(source, target)
    bundle["inventory"]["arms"][0]["config_file"] = "alias.txt"
    with pytest.raises(study.Refused, match="aliases"): run(bundle)


def test_linked_private_path_refused(bundle):
    target = bundle["evidence"].parent / "linked-private"
    try: target.symlink_to(bundle["evidence"], target_is_directory=True)
    except OSError: pytest.skip("directory symlink privilege unavailable")
    bundle["evidence"] = target
    with pytest.raises(study.Refused, match="linked"): run(bundle)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction contract")
def test_windows_junction_evidence_root_refused(bundle):
    target = bundle["evidence"].parent / "junction-private"
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(bundle["evidence"])], capture_output=True, timeout=10)
    assert made.returncode == 0, made.stderr
    bundle["evidence"] = target
    with pytest.raises(study.Refused, match="linked"): run(bundle)


def test_source_size_bound_precedes_legacy_prepare(bundle, monkeypatch):
    monkeypatch.setattr(context, "MAX_FILE", 1024)
    (bundle["inputs"] / "paper1.txt").write_bytes(b"x" * 1025)
    def forbidden(*args): raise AssertionError("legacy unbounded prepare reached")
    monkeypatch.setattr(study.matched, "prepare", forbidden)
    with pytest.raises(study.Refused, match="oversized"): run(bundle)


def test_growth_between_precheck_and_matched_prepare_is_still_bounded(bundle, monkeypatch):
    monkeypatch.setattr(context, "MAX_FILE", 1024)
    original = study.matched.prepare
    def grow_then_prepare(*args):
        (bundle["inputs"] / "paper1.txt").write_bytes(b"x" * 1025)
        return original(*args)
    monkeypatch.setattr(study.matched, "prepare", grow_then_prepare)
    # The second reader refuses before allocation, rather than discovering an
    # ordinary hash mismatch only after an unbounded read of the grown file.
    with pytest.raises(study.Refused, match="oversized"): run(bundle)


@pytest.mark.parametrize("kind", ["reference", "arm", "context"])
def test_private_artifact_size_bound(bundle, monkeypatch, kind):
    monkeypatch.setattr(context, "MAX_FILE", 8192)
    inv = bundle["inventory"]
    name = inv["references"][0]["file"] if kind == "reference" else inv["arms"][0]["config_file"] if kind == "arm" else inv["tasks"][0]["context_file"]
    (bundle["evidence"] / name).write_bytes(b"x" * 8193)
    with pytest.raises(study.Refused, match="oversized"): run(bundle)


def test_previously_checked_private_file_cannot_change_during_preflight(bundle, monkeypatch):
    original = context.inspect
    def alter_after_inspection(*args, **kwargs):
        result = original(*args, **kwargs)
        row = bundle["inventory"]["references"][0]
        (bundle["evidence"] / row["file"]).write_bytes(b"SYNTHETIC changed after reference check")
        return result
    monkeypatch.setattr(context, "inspect", alter_after_inspection)
    with pytest.raises(study.Refused, match="changed during preflight"): run(bundle)


def test_unrelated_graph_node_cannot_hide_oversized_input(bundle, monkeypatch):
    row = bundle["inventory"]["tasks"][0]
    path = bundle["evidence"] / row["context_file"]
    graph = context.strict_json(path.read_bytes())
    raw = b"x" * 8193
    (bundle["inputs"] / "unrelated.txt").write_bytes(raw)
    graph["nodes"].append({"id": "unrelated", "kind": "source", "file": "unrelated.txt", "sha256": sha(raw),
                           "parents": [], "expires_at": None, "oa_rights_reference": "Synthetic fixture"})
    row["context_sha256"] = write_json(path, graph)
    monkeypatch.setattr(context, "MAX_FILE", 8192)
    with pytest.raises(study.Refused, match="oversized"): run(bundle)


def test_cli_strict_json_and_no_overwrite(bundle):
    paths = {}
    for key in ("manifest", "protocol", "inventory"):
        paths[key] = bundle["evidence"] / (key + ".json")
        write_json(paths[key], bundle[key])
    output = bundle["evidence"] / "output.json"
    command = [sys.executable, "-B", "-m", "scripts.synthesis_study_preflight"]
    for key, path in {**paths, "inputs": bundle["inputs"], "evidence": bundle["evidence"], "output": output}.items():
        command.extend(["--" + key, str(path)])
    first = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert first.returncode == 0, first.stderr
    before = output.read_bytes()
    again = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert again.returncode == 2 and output.read_bytes() == before
    raw = paths["inventory"].read_text(encoding="utf-8")
    paths["inventory"].write_bytes(raw.replace('"schema":', '"schema": "duplicate", "schema":', 1).encode())
    rejected = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert rejected.returncode == 2 and "study preflight refused" in rejected.stderr
    assert output.read_bytes() == before


def test_cli_invalid_private_evidence_does_not_leak_json_keys_or_paths(bundle):
    paths = {}
    for key in ("manifest", "protocol", "inventory"):
        paths[key] = bundle["evidence"] / (key + ".json")
        write_json(paths[key], bundle[key])
    row = bundle["inventory"]["arms"][0]
    (bundle["evidence"] / row["config_file"]).write_bytes(
        b'{"PRIVATE-ERROR-CANARY":1,"PRIVATE-ERROR-CANARY":2}')
    output = bundle["evidence"] / "rejected.json"
    command = [sys.executable, "-m", "scripts.synthesis_study_preflight"]
    for key, path in {**paths, "inputs": bundle["inputs"], "evidence": bundle["evidence"], "output": output}.items():
        command.extend(["--" + key, str(path)])
    rejected = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert rejected.returncode == 2 and not output.exists()
    assert "PRIVATE-ERROR-CANARY" not in rejected.stderr
    assert str(bundle["evidence"]) not in rejected.stderr
