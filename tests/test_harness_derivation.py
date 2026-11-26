"""Synthetic provenance contracts; actual execution is exercised in Docker CI."""
import copy
import hashlib
import json
import os
import subprocess
import sys

import pytest

from scripts import harness_context as context
from scripts import harness_derivation as derivation
from scripts import harness_worker as worker
from tests.test_harness_worker import bundle, real_policy


def spec(root, policy, *, key="analysis", parent="paper", suffix="1"):
    recipe = f"recipe-{key}-{suffix}.py"
    (root / recipe).write_text(f"from pathlib import Path\nprint(Path('/inputs/{parent}.data').read_text())\n", encoding="utf-8")
    return {"schema": "e156-derivation-request-v1", "node": {
        "id": key, "kind": "analysis", "file": f"{key}-{suffix}.txt",
        "parents": [parent], "expires_at": None}, "recipe_file": recipe,
        "receipt_file": f"{key}-{suffix}.receipt.json", "worker": policy, "timeout_seconds": 30}


@pytest.fixture
def simulated_worker(monkeypatch):
    calls = []
    def execute(policy, root, manifest, selected, code, **kwargs):
        calls.append(selected)
        nodes, _ = context.index(manifest)
        return {"trust": "UNTRUSTED_WORKER_OUTPUT", "image": policy["image"],
                "container_removed": True, "input_hashes": {k: nodes[k]["sha256"] for k in selected},
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "stdout": "SYNTHETIC constant output\n", "stderr": ""}
    monkeypatch.setattr(worker, "execute", execute)
    return calls


def test_legacy_derived_bytes_are_not_current(bundle):
    root, graph, _ = bundle
    graph["nodes"].append({**graph["nodes"][0], "id": "derived", "kind": "analysis", "parents": ["paper"]})
    assert context.inspect(root, graph)["derived"]["status"] == "DERIVATION_UNVERIFIED"
    with pytest.raises(context.Refused, match="current"):
        context.pack(root, graph, ["derived"], [])


def test_receipts_transitively_bind_identical_outputs_to_source_versions(bundle, simulated_worker):
    root, graph, policy = bundle
    first = derivation.run(root, graph, spec(root, policy), root / "v1.json")
    second = derivation.run(root, first, spec(root, policy, key="claim", parent="analysis"), root / "v2.json")
    assert all(x["status"] == "CURRENT" for x in context.inspect(root, second).values())
    (root / "paper.txt").write_bytes(b"SYNTHETIC changed source")
    second["nodes"][0]["sha256"] = hashlib.sha256((root / "paper.txt").read_bytes()).hexdigest()
    states = context.inspect(root, second)
    assert states["analysis"]["status"] == "DERIVATION_INVALID"
    assert states["claim"]["status"] == "DEPENDENCY_INVALID"
    third = derivation.run(root, second, spec(root, policy, suffix="2"), root / "v3.json")
    assert (root / "analysis-1.txt").read_bytes() == (root / "analysis-2.txt").read_bytes()
    states = context.inspect(root, third)
    assert states["analysis"]["status"] == "CURRENT"
    assert states["claim"]["status"] == "DERIVATION_INVALID"
    with pytest.raises(context.Refused, match="current"):
        context.excerpt(root, third, "claim")


@pytest.mark.parametrize("defect", ["receipt", "recipe", "parent_metadata", "node_metadata", "missing_receipt"])
def test_tampering_and_missing_evidence_refuse_current(bundle, simulated_worker, defect):
    root, graph, policy = bundle
    result = derivation.run(root, graph, spec(root, policy), root / "out.json")
    if defect == "parent_metadata": result["nodes"][0]["oa_rights_reference"] += " changed"
    elif defect == "node_metadata": result["nodes"][-1]["kind"] = "claim"
    elif defect == "missing_receipt": (root / "analysis-1.receipt.json").unlink()
    else:
        target = root / ("analysis-1.receipt.json" if defect == "receipt" else "recipe-analysis-1.py")
        target.write_bytes(target.read_bytes() + b"changed")
    assert context.inspect(root, result)["analysis"]["status"] == "DERIVATION_INVALID"


@pytest.mark.parametrize("defect", ["worker_failure", "source_drift", "recipe_drift", "profile_drift", "bad_result"])
def test_failure_and_execution_drift_never_publish(bundle, monkeypatch, simulated_worker, defect):
    root, graph, policy = bundle
    request = spec(root, policy)
    original = worker.execute
    def execute(*args, **kwargs):
        if defect == "worker_failure": raise context.Refused("synthetic worker failure")
        result = original(*args, **kwargs)
        if defect == "source_drift": (root / "paper.txt").write_bytes(b"SYNTHETIC drift")
        elif defect == "recipe_drift": (root / request["recipe_file"]).write_bytes(b"print('changed')")
        elif defect == "profile_drift": monkeypatch.setattr(derivation, "profile", lambda: {})
        else: result["container_removed"] = False
        return result
    monkeypatch.setattr(worker, "execute", execute)
    with pytest.raises(context.Refused):
        derivation.run(root, graph, request, root / "out.json")
    assert not (root / "out.json").exists()
    assert not (root / request["node"]["file"]).exists()


@pytest.mark.parametrize("defect", ["source", "recipe", "receipt", "manifest", "parent_receipt", "parent_recipe", "hardlink"])
def test_output_aliases_refused_before_execution(bundle, simulated_worker, defect):
    root, graph, policy = bundle
    graph = derivation.run(root, graph, spec(root, policy), root / "first.json")
    request = spec(root, policy, key="child", parent="analysis")
    if defect == "source": request["node"]["file"] = "paper.txt"
    elif defect == "recipe": request["node"]["file"] = request["recipe_file"]
    elif defect == "receipt": request["receipt_file"] = request["node"]["file"]
    elif defect == "manifest": request["node"]["file"] = "out.json"
    elif defect == "parent_receipt": request["node"]["file"] = "analysis-1.receipt.json"
    elif defect == "parent_recipe": request["node"]["file"] = "recipe-analysis-1.py"
    else:
        os.link(root / "paper.txt", root / request["node"]["file"])
    with pytest.raises(context.Refused):
        derivation.run(root, graph, request, root / "out.json")
    assert len(simulated_worker) == 1


def test_receipt_and_recipe_are_protected_control_inputs(bundle, simulated_worker):
    root, graph, policy = bundle
    result = derivation.run(root, graph, spec(root, policy), root / "out.json")
    for name in ("analysis-1.receipt.json", "recipe-analysis-1.py"):
        with pytest.raises(context.Refused, match="overlaps"):
            context.control_path(root / name, root, result)


def test_receipt_publication_failure_never_publishes_manifest(bundle, simulated_worker, monkeypatch):
    root, graph, policy = bundle
    request = spec(root, policy)
    original = derivation._exclusive_bytes
    def fail_receipt(path, raw):
        if path.name == request["receipt_file"]:
            raise OSError("SYNTHETIC failed receipt publication")
        original(path, raw)
    monkeypatch.setattr(derivation, "_exclusive_bytes", fail_receipt)
    with pytest.raises(OSError, match="receipt publication"):
        derivation.run(root, graph, request, root / "out.json")
    assert (root / request["node"]["file"]).is_file()  # An orphan, never an admitted node.
    assert not (root / "out.json").exists()
    with pytest.raises(context.Refused, match="already exists"):
        derivation.run(root, graph, request, root / "out.json")
    assert len(simulated_worker) == 1


@pytest.mark.parametrize("target", ["manifest.json", "request.json"])
def test_cli_protects_manifest_and_request_before_worker_execution(bundle, target):
    root, graph, policy = bundle
    request = spec(root, policy)
    request["node"]["file"] = target
    for name, value in (("manifest.json", graph), ("request.json", request)):
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    result = subprocess.run([sys.executable, "-m", "scripts.harness_derivation", "run",
        "--root", str(root), "--manifest", str(root / "manifest.json"),
        "--spec", str(root / "request.json"), "--output-manifest", str(root / "new.json")],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 2 and "overlaps" in result.stderr
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


def test_real_worker_derivation_and_recompute(bundle):
    root, graph, policy = real_policy(bundle)
    request = spec(root, policy)
    result = derivation.run(root, graph, request, root / "derived.json")
    assert (root / "analysis-1.txt").read_bytes() == b"SYNTHETIC isolated evidence\n"
    assert context.inspect(root, result)["analysis"]["status"] == "CURRENT"
    assert context.excerpt(root, result, "analysis")["text"] == "SYNTHETIC isolated evidence\n"
    receipt = json.loads((root / request["receipt_file"]).read_bytes())
    assert receipt["execution"]["result"]["container_removed"] is True
    assert receipt["execution"]["result"]["input_hashes"] == {"paper": graph["nodes"][0]["sha256"]}
    (root / "paper.txt").write_bytes(b"SYNTHETIC corrected input")
    result["nodes"][0]["sha256"] = hashlib.sha256((root / "paper.txt").read_bytes()).hexdigest()
    assert context.inspect(root, result)["analysis"]["status"] == "DERIVATION_INVALID"
    # Exercise the actual CLI and worker on the second revision, not a mock.
    request = spec(root, policy, suffix="2")
    (root / "updated.json").write_text(json.dumps(result), encoding="utf-8")
    (root / "request.json").write_text(json.dumps(request), encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "scripts.harness_derivation", "run",
        "--root", str(root), "--manifest", str(root / "updated.json"),
        "--spec", str(root / "request.json"), "--output-manifest", str(root / "v2.json")],
        capture_output=True, text=True, timeout=45)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["status"] == "DERIVATION_RECORDED"
    assert (root / "analysis-2.txt").read_bytes() == b"SYNTHETIC corrected input\n"
    assert context.inspect(root, json.loads((root / "v2.json").read_bytes()))["analysis"]["status"] == "CURRENT"
