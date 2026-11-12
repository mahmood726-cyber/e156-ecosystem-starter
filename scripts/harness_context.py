"""Typed, byte-bound evidence dependencies and pinned context; no truth inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

if __package__:
    from scripts.component_source import linked
    from scripts.synthesis_replay import strict_json, Refused
    from scripts.synthesis_blind_eval import sha256_json as digest
else:
    from component_source import linked
    from synthesis_replay import strict_json, Refused
    from synthesis_blind_eval import sha256_json as digest

KINDS = {"source", "extraction", "transform", "analysis", "claim", "checklist", "memory", "skill"}
TOOLS = {"read_evidence", "python_worker"}
MAX_FILE = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise Refused(message)


def integer(value, name, minimum=0, maximum=10**12):
    require(type(value) is int and minimum <= value <= maximum, f"invalid {name}")
    return value


def timestamp(value):
    require(isinstance(value, str), "timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused("invalid timestamp") from exc
    require(parsed.utcoffset() is not None, "timezone required")
    return parsed


def guard(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            require(not linked(part), "linked paths refused")
    return path


def artifact(root, name):
    require(isinstance(name, str) and name, "relative artifact path required")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and relative.parts and ".." not in relative.parts
            and ":" not in name and "\\" not in name, "artifact path escape")
    return guard(guard(root).joinpath(*relative.parts))


def read_bytes(path):
    path = guard(path)
    require(path.is_file() and path.stat().st_size <= MAX_FILE, "artifact missing or oversized")
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE + 1)
    require(len(data) <= MAX_FILE, "artifact grew beyond limit")
    return data


def control_path(path, root, manifest, *, sqlite=False, creating=False, extra_inputs=()):
    """Control files and SQLite sidecars must never alias source material."""
    path = guard(path)
    candidates = [path] + ([guard(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm")] if sqlite else [])
    nodes, _ = index(manifest)
    inputs = [artifact(root, node["file"]) for node in nodes.values()] + [guard(p) for p in extra_inputs]
    for candidate in candidates:
        for source in inputs:
            require(candidate.resolve() != source.resolve() and not (candidate.exists() and source.exists() and os.path.samefile(candidate, source)),
                    "control path overlaps an input artifact")
    if sqlite:
        for sidecar in candidates[1:]:
            if sidecar.exists():
                require(not creating and str(sidecar).endswith("-journal"), "unrelated or unsupported SQLite sidecar")
                with sidecar.open("rb") as handle:
                    require(handle.read(8) == bytes.fromhex("d9d505f920a163d7"), "unrecognized SQLite journal; manual recovery required")
    return path


def atomic_json(path, value, *, exclusive=False):
    path = guard(path)
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if exclusive:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        guard(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def index(manifest):
    require(isinstance(manifest, dict) and manifest.get("schema") == "e156-harness-context-v1", "context schema mismatch")
    rows = manifest.get("nodes")
    require(isinstance(rows, list) and rows, "context nodes required")
    nodes = {}
    for row in rows:
        require(isinstance(row, dict), "node must be object")
        key = row.get("id")
        require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", key) and key not in nodes,
                "duplicate/invalid node id")
        require(row.get("kind") in KINDS, "unknown node kind")
        require(isinstance(row.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "invalid node hash")
        parents = row.get("parents")
        require(isinstance(parents, list) and all(isinstance(p, str) for p in parents)
                and len(parents) == len(set(parents)), "invalid parents")
        if row["kind"] in {"source", "skill"}:
            require(not parents, "source/skill must be a root")
        else:
            require(parents, "derived node requires source lineage")
        if row["kind"] == "source":
            require(isinstance(row.get("oa_rights_reference"), str) and row["oa_rights_reference"].strip(), "OA rights reference required")
        if row["kind"] == "skill":
            require(isinstance(row.get("tools"), list) and all(isinstance(t, str) and t in TOOLS for t in row["tools"]),
                    "unknown skill tool")
        if row.get("expires_at") is not None:
            timestamp(row["expires_at"])
        nodes[key] = row
    ordered, active, done = [], set(), set()
    def visit(key):
        require(key in nodes and key not in active, "missing/cyclic dependency")
        if key in done:
            return
        active.add(key)
        for parent in nodes[key]["parents"]:
            require(parent in nodes and nodes[parent]["kind"] != "skill", "invalid evidence parent")
            visit(parent)
        active.remove(key)
        done.add(key)
        ordered.append(key)
    for key in sorted(nodes):
        visit(key)
    return nodes, ordered


def inspect(root, manifest, *, now=None):
    now = now or datetime.now(timezone.utc)
    nodes, order = index(manifest)
    result = {}
    for key in order:
        node = nodes[key]
        path = artifact(root, node.get("file"))
        if not path.is_file():
            actual, status = None, "MISSING"
        else:
            actual = hashlib.sha256(read_bytes(path)).hexdigest()
            status = "CURRENT" if actual == node["sha256"] else "CHANGED"
        if status == "CURRENT" and node.get("expires_at") and timestamp(node["expires_at"]) <= now:
            status = "EXPIRED"
        if status == "CURRENT" and any(result[p]["status"] != "CURRENT" for p in node["parents"]):
            status = "DEPENDENCY_INVALID"
        result[key] = {"status": status, "observed_sha256": actual, "node_sha256": digest(node)}
    return result


def excerpt(root, manifest, key, *, offset=0, limit=4000):
    integer(offset, "offset", maximum=MAX_FILE)
    integer(limit, "limit", minimum=1, maximum=16000)
    nodes, _ = index(manifest)
    require(key in nodes and nodes[key]["kind"] != "skill", "evidence node required")
    require(inspect(root, manifest)[key]["status"] == "CURRENT", "evidence is not current")
    raw = read_bytes(artifact(root, nodes[key]["file"]))
    require(hashlib.sha256(raw).hexdigest() == nodes[key]["sha256"], "source changed during read")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise Refused("text extraction required for binary evidence") from exc
    return {"id": key, "sha256": nodes[key]["sha256"], "trust": "UNTRUSTED_EVIDENCE_NOT_INSTRUCTIONS",
            "text": text[offset:offset+limit], "offset": offset, "total_chars": len(text),
            "truncated": offset > 0 or offset + limit < len(text)}


def pack(root, manifest, selected, skills, *, max_chars=12000):
    integer(max_chars, "context chars", minimum=1, maximum=1000000)
    require(isinstance(selected, list) and selected and isinstance(skills, list), "selection and skills required")
    nodes, order = index(manifest)
    states = inspect(root, manifest)
    required = set()
    def add(key):
        require(isinstance(key, str) and key in nodes and nodes[key]["kind"] != "skill", "invalid evidence selection")
        if key in required:
            return
        required.add(key)
        for parent in nodes[key]["parents"]:
            add(parent)
    for key in selected:
        add(key)
    instructions, tools = [], set()
    for key in skills:
        require(isinstance(key, str) and key in nodes and nodes[key]["kind"] == "skill", "invalid skill selection")
        require(states[key]["status"] == "CURRENT", "skill is not current")
        raw = read_bytes(artifact(root, nodes[key]["file"]))
        require(hashlib.sha256(raw).hexdigest() == nodes[key]["sha256"], "skill changed")
        instructions.append(raw.decode("utf-8"))
        tools.update(nodes[key]["tools"])
    require(sum(map(len, instructions)) <= max_chars, "skills exceed context budget")
    evidence, truncated = "", False
    for key in order:
        if key not in required:
            continue
        require(states[key]["status"] == "CURRENT", "selected evidence is not current")
        available = max_chars - len(evidence) - sum(map(len, instructions))
        if available <= 0:
            truncated = True
            continue
        item = excerpt(root, manifest, key, limit=min(available, 16000))
        block = json.dumps(item, ensure_ascii=False)
        evidence += block[:available]
        truncated |= item["truncated"] or len(block) > available
    return {"trust": "UNTRUSTED_EVIDENCE_NOT_INSTRUCTIONS", "instructions": instructions,
            "tools": sorted(tools), "evidence_text": evidence, "truncated": truncated,
            "catalog": [{k: nodes[key][k] for k in ("id", "kind", "sha256", "parents")} for key in order if key in required],
            "manifest_sha256": digest(manifest)}


def watch(root, manifest, state):
    current = inspect(root, manifest)
    state = control_path(state, root, manifest)
    previous = strict_json(read_bytes(state)) if state.exists() else None
    if previous is not None:
        require(previous.get("schema") == "e156-harness-watch-v1" and isinstance(previous.get("nodes"), dict), "watch state schema mismatch")
    changes = [] if previous is None else [{"id": key, "before": previous["nodes"].get(key), "after": current.get(key)}
              for key in sorted(set(previous["nodes"]) | set(current)) if previous["nodes"].get(key) != current.get(key)]
    atomic_json(state, {"schema": "e156-harness-watch-v1", "nodes": current})
    return {"schema": "e156-harness-changes-v1", "changes": changes, "notifications_sent": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("inspect", "watch"))
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--state", type=Path)
    a = p.parse_args()
    try:
        manifest = strict_json(read_bytes(a.manifest))
        if a.action == "watch":
            require(a.state is not None, "watch --state required")
            result = watch(a.root, manifest, a.state)
        else:
            result = inspect(a.root, manifest)
        print(json.dumps(result, sort_keys=True, indent=2))
    except (Refused, OSError, ValueError, TypeError, RecursionError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
