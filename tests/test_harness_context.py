"""Artificial context and dependency contracts; no publication data."""
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from scripts import harness_context as context


def test_freshness_cli_gate_fails_changed_dependency(graph):
    root, manifest = graph
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    cmd = [sys.executable, "-m", "scripts.harness_context", "check", "--root", str(root), "--manifest", str(path)]
    good = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert good.returncode == 0, good.stderr
    (root / "paper.txt").write_text("SYNTHETIC changed source", encoding="utf-8")
    bad = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["claim"]["status"] == "DEPENDENCY_INVALID"


@pytest.fixture
def graph(tmp_path):
    nodes = []
    for key, kind, parents, body in [
        ("paper", "source", [], "SYNTHETIC source. Ignore instructions is untrusted data."),
        ("extract", "extraction", ["paper"], "SYNTHETIC extracted value"),
        ("analysis", "analysis", ["extract"], "SYNTHETIC analysis"),
        ("claim", "claim", ["analysis"], "SYNTHETIC claim"),
        ("check", "checklist", ["claim"], "SYNTHETIC checklist"),
        ("other", "source", [], "SYNTHETIC independent source"),
        ("review", "skill", [], "Read source evidence and abstain when incomplete."),
    ]:
        raw = body.encode()
        (tmp_path / f"{key}.txt").write_bytes(raw)
        node = {"id": key, "kind": kind, "file": f"{key}.txt",
                "sha256": hashlib.sha256(raw).hexdigest(), "parents": parents,
                "expires_at": None}
        if kind == "source":
            node["oa_rights_reference"] = "Synthetic fixture, no research rights claim"
        if kind == "skill":
            node["tools"] = ["read_evidence"]
        nodes.append(node)
    return tmp_path, {"schema": "e156-harness-context-v1", "nodes": nodes}


def test_end_to_end_context_and_downstream_invalidation(graph):
    root, manifest = graph
    packed = context.pack(root, manifest, ["claim"], ["review"], max_chars=120)
    assert packed["tools"] == ["read_evidence"]
    assert packed["truncated"] is True
    assert len(packed["evidence_text"]) <= 120
    assert packed["trust"] == "UNTRUSTED_EVIDENCE_NOT_INSTRUCTIONS"
    (root / "paper.txt").write_text("SYNTHETIC changed source", encoding="utf-8")
    states = context.inspect(root, manifest)
    assert states["paper"]["status"] == "CHANGED"
    assert states["check"]["status"] == "DEPENDENCY_INVALID"
    assert states["other"]["status"] == "CURRENT"
    with pytest.raises(context.Refused, match="current"):
        context.pack(root, manifest, ["claim"], ["review"], max_chars=1000)


def test_expiration_is_transitive(graph):
    root, manifest = graph
    manifest["nodes"][0]["expires_at"] = "2020-01-01T00:00:00Z"
    states = context.inspect(root, manifest, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert states["paper"]["status"] == "EXPIRED"
    assert states["analysis"]["status"] == "DEPENDENCY_INVALID"


@pytest.mark.parametrize("defect", ["cycle", "missing", "escape", "rootless", "duplicate", "skill_parent", "unknown_tool"])
def test_invalid_graph_refused(graph, defect):
    root, m = graph
    if defect == "cycle":
        m["nodes"][2]["parents"] = ["claim"]
    elif defect == "missing":
        m["nodes"][1]["parents"] = ["unknown"]
    elif defect == "escape":
        m["nodes"][0]["file"] = "../secret.txt"
    elif defect == "rootless":
        m["nodes"][1]["parents"] = []
    elif defect == "duplicate":
        m["nodes"].append(copy.deepcopy(m["nodes"][0]))
    elif defect == "skill_parent":
        m["nodes"][1]["parents"] = ["review"]
    else:
        m["nodes"][-1]["tools"] = ["shell"]
    with pytest.raises(context.Refused):
        context.inspect(root, m)


def test_watch_initial_snapshot_then_quiet_then_changed(graph, tmp_path):
    root, manifest = graph
    state = tmp_path / "watch.json"
    assert context.watch(root, manifest, state)["changes"] == []
    assert context.watch(root, manifest, state)["changes"] == []
    (root / "paper.txt").write_text("SYNTHETIC revision", encoding="utf-8")
    result = context.watch(root, manifest, state)
    assert {x["id"] for x in result["changes"]} == {"paper", "extract", "analysis", "claim", "check"}
    assert context.watch(root, manifest, state)["changes"] == []


def test_tool_read_is_bounded_and_cannot_read_skill(graph):
    root, m = graph
    result = context.excerpt(root, m, "paper", offset=2, limit=5)
    assert len(result["text"]) == 5 and result["truncated"]
    with pytest.raises(context.Refused):
        context.excerpt(root, m, "review", offset=0, limit=5)
    with pytest.raises(context.Refused):
        context.excerpt(root, m, "paper", offset=-1, limit=5)
