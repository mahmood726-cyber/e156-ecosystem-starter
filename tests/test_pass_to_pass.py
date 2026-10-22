"""Tests for scripts/pass-to-pass.py (2026-10-22 research-log practice).

House rule: BOTH directions. The cases this suite exists for are the quiet
regressions: a test that used to pass now fails, is skipped at run time, or is
gone. The KEPT cases beside them are what stop the tool flagging everything.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pass-to-pass.py"

SUITE = (
    "def test_pool():\n"
    "    assert abs((12.0 - 4) / 20.0 - 0.4) < 1e-12\n"
    "\n"
    "def test_label():\n"
    "    assert 'DerSimonian-Laird'.startswith('Der')\n"
)
PYTEST = '"%s" -m pytest -q -p no:cacheprovider' % sys.executable


@pytest.fixture(scope="module")
def p2p():
    spec = importlib.util.spec_from_file_location("pass_to_pass", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _before_after(p2p, tmp_path: Path, after_src: str):
    test_file = tmp_path / "test_suite.py"
    test_file.write_text(SUITE, encoding="utf-8")
    before = p2p.run_suite(PYTEST, str(tmp_path), 300)
    test_file.write_text(after_src, encoding="utf-8")
    return p2p.compare(before, p2p.run_suite(PYTEST, str(tmp_path), 300))


def test_an_unchanged_suite_is_kept(p2p, tmp_path):
    r = _before_after(p2p, tmp_path, SUITE)
    assert r["verdict"] == "KEPT"
    assert r["regressions"] == []


def test_adding_a_test_is_kept_and_reported(p2p, tmp_path):
    r = _before_after(p2p, tmp_path, SUITE + "\ndef test_new():\n    assert True\n")
    assert r["verdict"] == "KEPT"
    assert any(t.endswith("test_new") for t in r["new_tests"])


def test_a_test_that_now_fails_is_a_regression(p2p, tmp_path):
    r = _before_after(p2p, tmp_path, SUITE.replace("- 0.4)", "- 0.5)"))
    assert r["verdict"] == "REGRESSED"
    assert [row["now"] for row in r["regressions"]] == ["failed"]


def test_a_runtime_skip_is_a_regression(p2p, tmp_path):
    # the case honest-ratchet cannot see: the name and decorators are unchanged
    src = SUITE.replace("def test_label():\n", "def test_label():\n    import pytest; pytest.skip('later')\n")
    r = _before_after(p2p, tmp_path, src)
    assert r["verdict"] == "REGRESSED"
    assert [row["now"] for row in r["regressions"]] == ["skipped"]


def test_a_deleted_test_is_a_regression(p2p, tmp_path):
    r = _before_after(p2p, tmp_path, SUITE.split("\ndef test_label")[0] + "\n")
    assert r["verdict"] == "REGRESSED"
    assert r["regressions"][0]["now"] == "missing"


def test_a_suite_that_no_longer_imports_is_a_regression(p2p, tmp_path):
    r = _before_after(p2p, tmp_path, "import no_such_module_xyz\n" + SUITE)
    assert r["verdict"] == "REGRESSED"


def test_no_result_file_is_inconclusive_not_a_pass(p2p, tmp_path):
    snap = p2p.run_suite('"%s" -c pass' % sys.executable, str(tmp_path), 60)
    assert snap["problem"]
    assert p2p.compare(snap, snap)["verdict"] == "INCONCLUSIVE"


def test_nothing_passing_before_is_inconclusive(p2p):
    before = dict(cmd="x", tests={"t::a": "failed"}, problem="")
    after = dict(cmd="x", tests={"t::a": "passed"}, problem="")
    r = p2p.compare(before, after)
    assert r["verdict"] == "INCONCLUSIVE"


def test_a_failing_test_that_starts_passing_is_not_a_regression(p2p):
    before = dict(cmd="x", tests={"t::a": "passed", "t::b": "failed"}, problem="")
    after = dict(cmd="x", tests={"t::a": "passed", "t::b": "passed"}, problem="")
    r = p2p.compare(before, after)
    assert r["verdict"] == "KEPT"
    assert r["now_passing"] == ["t::b"]


def test_a_teardown_error_is_not_masked_by_the_pass(p2p, tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text(
        '<testsuites><testsuite>'
        '<testcase classname="t" name="a"/>'
        '<testcase classname="t" name="a"><error message="teardown"/></testcase>'
        '</testsuite></testsuites>', encoding="utf-8")
    assert p2p.parse_junit(str(xml)) == {"t::a": "error"}


def test_cli_snapshot_then_compare_exit_codes(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_suite.py").write_text(SUITE, encoding="utf-8")
    snap = tmp_path / "before.json"
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "snapshot", "--cmd", PYTEST,
                        "--out", str(snap), "--root", str(proj)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert sum(o == "passed" for o in json.loads(snap.read_text(encoding="utf-8"))["tests"].values()) == 2
    (proj / "test_suite.py").write_text(SUITE.replace("- 0.4)", "- 0.5)"), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "compare", "--before", str(snap),
                        "--cmd", PYTEST, "--root", str(proj)], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REGRESSED" in r.stdout


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
