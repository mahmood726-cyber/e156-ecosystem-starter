"""Tests for scripts/reuse.py -- the offline "copy it, don't regenerate it" index.

The tool's value is letting a token-capped student find existing kit code to copy
instead of paying an agent to regenerate it. Failure modes worth covering:
  - Python extraction must PARSE, never EXECUTE (a kit file with import-time side
    effects must still index without running them)
  - JavaScript extraction (no stdlib JS parser) picks up `function name(args)`
  - minified/vendored bundles must be skipped (else thousands of garbage symbols)
  - the committed index must be PORTABLE: kit-relative paths, never absolute
  - scoring: phrase-in-name outranks token-only; threshold drops noise
  - root resolution: explicit override wins; a missing dir is skipped, not fatal
  - CLI: build then find round-trips; missing index fails-closed (exit 2)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "reuse.py"


@pytest.fixture(scope="module")
def reuse():
    spec = importlib.util.spec_from_file_location("reuse", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["reuse"] = module
    spec.loader.exec_module(module)
    return module


# --- Python extraction (AST, never executed) --------------------------------


def test_python_extracts_public_function_with_signature(reuse, tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(
        '"""Module."""\n'
        "def render_forest(studies, opts, *, log=False):\n"
        '    """Draw a forest plot."""\n'
        "    return 1\n",
        encoding="utf-8",
    )
    syms = reuse.extract_python("kit", tmp_path, f)
    by_name = {s.name: s for s in syms}
    assert "render_forest" in by_name
    s = by_name["render_forest"]
    assert s.kind == "function" and s.lang == "py" and s.public
    assert s.signature == "render_forest(studies, opts, *, log=False)"
    assert s.doc == "Draw a forest plot."
    assert s.relpath == "mod.py"


def test_python_marks_private_and_keeps_class_methods(reuse, tmp_path):
    f = tmp_path / "m.py"
    f.write_text(
        "def _helper():\n    pass\n"
        "class Loader:\n"
        '    """Loads tables."""\n'
        "    def load(self, name):\n"
        "        return name\n"
        "    def _internal(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    syms = {s.name: s for s in reuse.extract_python("kit", tmp_path, f)}
    assert syms["_helper"].public is False
    assert "Loader" in syms and syms["Loader"].kind == "class"
    assert "Loader.load" in syms and syms["Loader.load"].kind == "method"
    # private methods (other than __init__) are dropped
    assert "Loader._internal" not in syms


def test_python_parses_but_does_not_execute(reuse, tmp_path):
    """A kit file with an import-time side effect must index WITHOUT running it."""
    f = tmp_path / "danger.py"
    f.write_text(
        "raise RuntimeError('import-time side effect must not run')\n"
        "def safe():\n    return 1\n",
        encoding="utf-8",
    )
    syms = {s.name: s for s in reuse.extract_python("kit", tmp_path, f)}
    assert "safe" in syms  # parsed fine; the raise never executed


def test_python_syntax_error_is_skipped_not_fatal(reuse, tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def (((:\n", encoding="utf-8")
    assert reuse.extract_python("kit", tmp_path, f) == []


# --- JavaScript extraction --------------------------------------------------


def test_js_extracts_function_with_nearby_doc(reuse, tmp_path):
    f = tmp_path / "chart.js"
    f.write_text(
        "// renders a funnel plot from study points\n"
        "function renderFunnel(svgEl, studies, opts) {\n"
        "  return svgEl;\n"
        "}\n",
        encoding="utf-8",
    )
    syms = {s.name: s for s in reuse.extract_js("kit", tmp_path, f)}
    assert "renderFunnel" in syms
    s = syms["renderFunnel"]
    assert s.lang == "js" and s.kind == "function"
    assert s.signature == "renderFunnel(svgEl, studies, opts)"
    assert "funnel" in s.doc.lower()


def test_js_extracts_arrow_const(reuse, tmp_path):
    f = tmp_path / "a.js"
    f.write_text("const computeCI = (est, se) => est + se;\n", encoding="utf-8")
    syms = {s.name: s for s in reuse.extract_js("kit", tmp_path, f)}
    assert "computeCI" in syms
    assert syms["computeCI"].signature == "computeCI(est, se)"


# --- Minified / vendored skipping -------------------------------------------


def test_minified_js_is_skipped(reuse, tmp_path):
    kit = tmp_path / "k"
    (kit / "vendor").mkdir(parents=True)
    # A *.min.js bundle and a long-line bundle: both must be ignored.
    (kit / "plotly.min.js").write_text(
        "function includeBasePlot(e,t){return e}\n", encoding="utf-8")
    (kit / "bundle.js").write_text("var x=1;" + "a" * 2000 + "\n", encoding="utf-8")
    # vendored file inside a vendor/ dir
    (kit / "vendor" / "lib.js").write_text(
        "function vendored(a){return a}\n", encoding="utf-8")
    # one real authored file
    (kit / "real.js").write_text("function authored(a){return a}\n", encoding="utf-8")
    index = reuse.build_index([("k", kit)])
    names = {s["name"] for s in index["symbols"]}
    assert "authored" in names
    assert "includeBasePlot" not in names  # .min.js skipped
    assert "vendored" not in names          # vendor/ skipped
    # bundle.js has a >1000-char line -> skipped, so nothing from it


# --- build_index: portability + determinism ---------------------------------


def test_build_index_is_portable_and_deterministic(reuse, tmp_path):
    kit = tmp_path / "mykit"
    kit.mkdir()
    (kit / "z.py").write_text("def zeta():\n    pass\n", encoding="utf-8")
    (kit / "a.py").write_text("def alpha():\n    pass\n", encoding="utf-8")
    index = reuse.build_index([("mykit", kit)])
    blob = json.dumps(index)
    # No absolute build-machine path leaks into the committed index.
    assert str(tmp_path) not in blob
    assert all(not s["relpath"].startswith(("/", "C:", "c:")) for s in index["symbols"])
    # Deterministic ordering by (kit, relpath, line): a.py before z.py.
    relpaths = [s["relpath"] for s in index["symbols"]]
    assert relpaths == sorted(relpaths)
    assert index["kits"] == ["mykit"]
    assert index["symbol_count"] == len(index["symbols"]) == 2


# --- Scoring / find ---------------------------------------------------------


def _index(reuse, symbols):
    return {"schema": 1, "kits": ["k"], "symbol_count": len(symbols), "symbols": symbols}


def test_phrase_in_name_outranks_token_only(reuse):
    idx = _index(reuse, [
        {"kit": "k", "name": "renderForest", "kind": "function", "lang": "js",
         "relpath": "c.js", "line": 1, "signature": "renderForest(a)", "doc": "", "public": True},
        {"kit": "k", "name": "helper", "kind": "function", "lang": "py",
         "relpath": "h.py", "line": 1, "signature": "helper(forest)", "doc": "a forest", "public": True},
    ])
    hits = reuse.find(idx, "renderforest", top=5, min_score=1)
    assert hits[0].symbol["name"] == "renderForest"


def test_find_threshold_drops_nonmatches(reuse):
    idx = _index(reuse, [
        {"kit": "k", "name": "unrelated", "kind": "function", "lang": "py",
         "relpath": "u.py", "line": 1, "signature": "unrelated()", "doc": "", "public": True},
    ])
    assert reuse.find(idx, "forest", top=5, min_score=1) == []


def test_find_respects_top_limit(reuse):
    syms = [
        {"kit": "k", "name": f"forest{i}", "kind": "function", "lang": "py",
         "relpath": "f.py", "line": i, "signature": f"forest{i}()", "doc": "", "public": True}
        for i in range(10)
    ]
    hits = reuse.find(_index(reuse, syms), "forest", top=3, min_score=1)
    assert len(hits) == 3


# --- Root resolution --------------------------------------------------------


def test_resolve_roots_explicit_override(reuse, tmp_path, monkeypatch):
    monkeypatch.delenv("REUSE_ROOTS", raising=False)
    real = tmp_path / "k1"
    real.mkdir()
    missing = tmp_path / "nope"
    roots = reuse.resolve_roots(f"k1={real},gone={missing}")
    assert roots == [("k1", real)]  # missing dir dropped, not fatal


def test_resolve_roots_env(reuse, tmp_path, monkeypatch):
    d = tmp_path / "envkit"
    d.mkdir()
    monkeypatch.setenv("REUSE_ROOTS", f"envkit={d}")
    roots = reuse.resolve_roots(None)
    assert ("envkit", d) in roots


# --- CLI round-trip ---------------------------------------------------------


def test_cli_build_then_find(reuse, tmp_path, capsys):
    kit = tmp_path / "ck"
    kit.mkdir()
    (kit / "viz.py").write_text(
        "def render_funnel(points):\n"
        '    """Funnel plot."""\n'
        "    return points\n",
        encoding="utf-8",
    )
    out = tmp_path / "idx.json"
    rc = reuse.main(["build", "--roots", f"ck={kit}", "--out", str(out)])
    assert rc == 0 and out.exists()
    rc = reuse.main(["find", "funnel", "--index", str(out)])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "render_funnel" in captured
    assert "don't regenerate" in captured


def test_cli_find_missing_index_fails_closed(reuse, tmp_path, capsys):
    rc = reuse.main(["find", "x", "--index", str(tmp_path / "absent.json")])
    assert rc == 2
    assert "no index" in capsys.readouterr().err.lower()


def test_cli_find_no_match_exit_1(reuse, tmp_path, capsys):
    out = tmp_path / "i.json"
    out.write_text(json.dumps(_index(reuse, [
        {"kit": "k", "name": "thing", "kind": "function", "lang": "py",
         "relpath": "t.py", "line": 1, "signature": "thing()", "doc": "", "public": True},
    ])), encoding="utf-8")
    rc = reuse.main(["find", "nonexistentkeyword", "--index", str(out)])
    assert rc == 1


def test_cli_build_no_roots_exit_2(reuse, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("REUSE_ROOTS", raising=False)
    missing = tmp_path / "none"
    rc = reuse.main(["build", "--roots", f"x={missing}", "--out", str(tmp_path / "o.json")])
    assert rc == 2
    assert "no kit roots" in capsys.readouterr().err.lower()
