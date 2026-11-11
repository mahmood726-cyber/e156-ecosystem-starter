#!/usr/bin/env python3
"""Offline memory contract controls, not a held-out retrieval-quality benchmark.

Runs the actual recall module against temporary, explicitly synthetic stores.
No private memory, model API or network is used. Output records every case and
hashes both the implementation and this evaluator. Exit 0: all controls pass;
1: a behavioral control fails; 2: the evaluator cannot run or write its report.
Only load implementations you trust: --implementation imports Python code.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


SCHEMA = "e156-memory-contract-v1"
DEFAULT_IMPLEMENTATION = Path(__file__).with_name("recall.py")


def load_implementation(path: Path):
    spec = importlib.util.spec_from_file_location("e156_memory_under_test", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load memory implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _memory(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    (store / "context.md").write_text(
        "---\nname: quasar\ndescription: quasar telescope observations\n---\n"
        "Synthetic test context. Recheck the source before use.\n", encoding="utf-8"
    )


def _query(module, store: Path) -> tuple[int, dict]:
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(io.StringIO()):
        code = module.main(["quasar", "--memory-dir", str(store), "--json"])
    return code, json.loads(output.getvalue())


def _retrieval(module, root):
    _memory(root)
    hits = module.recall("quasar telescope", root)
    return bool(hits) and hits[0][1]["name"] == "quasar"


def _no_match(module, root):
    _memory(root)
    return module.recall("unrelatedword", root) == []


def _discovery(module, root, mode):
    cwd = root / "working-project"
    cwd.mkdir()
    stores = root / ".claude" / "projects"
    if mode == "exact":
        expected = stores / module._encode_project_dir(cwd) / "memory"
        _memory(expected)
    else:
        expected = None
    if mode != "none":
        _memory(stores / "unrelated-project" / "memory")
    if mode == "multiple":
        _memory(stores / "another-unrelated-project" / "memory")
    with patch.dict(os.environ):
        os.environ.pop("CLAUDE_MEMORY_DIR", None)
        with patch.object(module.Path, "home", return_value=root), \
                patch.object(module.Path, "cwd", return_value=cwd):
            return module.discover_memory_dir() == expected


def _bad_store(module, root, mode):
    store = root / "store"
    if mode != "missing":
        _memory(store)
    if mode == "invalid_utf8":
        (store / "broken.md").write_bytes(b"\xff\xfeinvalid")
    if mode == "directory":
        (store / "broken.md").mkdir()
    code, payload = _query(module, store)
    return code == 2 and "error" in payload and not payload.get("hits")


def _identity(module, root):
    _memory(root)
    code, payload = _query(module, root)
    expected = hashlib.sha256((root / "context.md").read_bytes()).hexdigest()
    hits = payload.get("hits", [])
    return code == 0 and len(hits) == 1 and hits[0].get("sha256") == expected


def _epistemic_status(module, root):
    _memory(root)
    code, payload = _query(module, root)
    hits = payload.get("hits", [])
    return code == 0 and len(hits) == 1 and hits[0].get("evidence_status") == "unverified_memory"


CASES = (
    ("relevant-explicit-store", "Relevant context is retrievable", _retrieval),
    ("no-match", "Unmatched query returns no hits", _no_match),
    ("exact-project", "Exact project wins over unrelated stores", lambda m, p: _discovery(m, p, "exact")),
    ("no-project-store", "Absent project store returns no inferred store", lambda m, p: _discovery(m, p, "none")),
    ("sole-unrelated-store", "A sole unrelated store is not selected", lambda m, p: _discovery(m, p, "sole")),
    ("multiple-unrelated-stores", "No newest-store fallback", lambda m, p: _discovery(m, p, "multiple")),
    ("missing-explicit-store", "Missing store returns JSON error with exit 2", lambda m, p: _bad_store(m, p, "missing")),
    ("invalid-utf8", "Unreadable corpus returns JSON error with exit 2", lambda m, p: _bad_store(m, p, "invalid_utf8")),
    ("directory-as-memory", "Non-file corpus entry returns JSON error with exit 2", lambda m, p: _bad_store(m, p, "directory")),
    ("byte-identity", "Each hit carries its actual byte SHA-256", _identity),
    ("memory-is-not-evidence", "Each hit is explicitly unverified memory", _epistemic_status),
)


def evaluate(implementation: Path = DEFAULT_IMPLEMENTATION) -> dict:
    source_hash = hashlib.sha256(implementation.read_bytes()).hexdigest()
    module = load_implementation(implementation)
    results = []
    for case_id, expected, check in CASES:
        with tempfile.TemporaryDirectory(prefix="e156-memory-control-") as temp:
            try:
                passed = check(module, Path(temp)) is True
                observation = "contract satisfied" if passed else "contract not satisfied"
            except Exception as exc:
                # A crash is a failed case, not a successful refusal. Do not
                # publish exception text, which may embed machine-local paths.
                passed, observation = False, f"unexpected {type(exc).__name__}"
        results.append({"id": case_id, "expected": expected,
                        "passed": passed, "observation": observation})
    # Reject mutation of the imported implementation during an evaluation.
    if hashlib.sha256(implementation.read_bytes()).hexdigest() != source_hash:
        raise ValueError("memory implementation changed during evaluation")
    return {
        "schema": SCHEMA,
        "evaluation_kind": "synthetic_development_contracts",
        "scientific_accuracy_measured": False,
        "held_out": False,
        "implementation_sha256": source_hash,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases_total": len(results),
        "cases_passed": sum(r["passed"] for r in results),
        "all_passed": bool(results) and all(r["passed"] for r in results),
        "results": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", type=Path, default=DEFAULT_IMPLEMENTATION)
    parser.add_argument("--output", type=Path, help="write JSON as well as stdout")
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.resolve() in (args.implementation.resolve(), Path(__file__).resolve()):
            raise ValueError("output must not overwrite implementation or evaluator")
        report = evaluate(args.implementation)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "error": type(exc).__name__, "all_passed": False}))
        return 2
    print(rendered, end="")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
