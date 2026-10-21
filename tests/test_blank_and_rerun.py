"""Tests for scripts/blank-and-rerun.py (P2 of 2026-10-20).

House rule: BOTH directions. The case this suite exists for is the hollow test:
a suite that compares a stored number to itself passes with or without the
function it names. `test_a_hollow_test_makes_the_claim_fail` is that case; the
TESTS-BITE case beside it is what stops the tool flagging everything.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "blank-and-rerun.py"

POOL = (
    "def dl_tau2(q, df, c):\n"
    "    return max(0.0, (q - df) / c)\n"
    "\n"
    "def label():\n"
    "    return 'DerSimonian-Laird'\n"
)
# Known-answer test: calls the function and compares to a reference value.
GOOD_TEST = (
    "import pool\n"
    "assert abs(pool.dl_tau2(12.0, 4, 20.0) - 0.4) < 1e-12\n"
)
# Hollow test: compares the stored reference to itself. Passes without pool.
HOLLOW_TEST = (
    "import pool\n"
    "R_VALUE = 0.4\n"
    "ours = 0.4\n"
    "assert abs(ours - R_VALUE) < 1e-12\n"
)


@pytest.fixture(scope="module")
def bar():
    spec = importlib.util.spec_from_file_location("blank_and_rerun", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project(tmp_path: Path, test_src: str) -> str:
    (tmp_path / "pool.py").write_text(POOL, encoding="utf-8")
    (tmp_path / "check.py").write_text(test_src, encoding="utf-8")
    return '"%s" check.py' % sys.executable


def test_a_known_answer_test_bites(bar, tmp_path):
    cmd = _project(tmp_path, GOOD_TEST)
    r = bar.check(str(tmp_path), "pool.py", ["dl_tau2"], cmd, timeout=120)
    assert r["verdict"] == "TESTS-BITE"
    assert r["functions"][0]["outcome"] == "BITES"


def test_a_hollow_test_makes_the_claim_fail(bar, tmp_path):
    cmd = _project(tmp_path, HOLLOW_TEST)
    r = bar.check(str(tmp_path), "pool.py", ["dl_tau2"], cmd, timeout=120)
    assert r["verdict"] == "CLAIM-FAILS"
    assert r["functions"][0]["outcome"] == "SURVIVED"


def test_one_untested_function_is_enough_to_fail_the_claim(bar, tmp_path):
    cmd = _project(tmp_path, GOOD_TEST)
    r = bar.check(str(tmp_path), "pool.py", ["dl_tau2", "label"], cmd, timeout=120)
    assert r["verdict"] == "CLAIM-FAILS"


def test_the_original_file_is_never_modified(bar, tmp_path):
    cmd = _project(tmp_path, GOOD_TEST)
    bar.check(str(tmp_path), "pool.py", ["dl_tau2"], cmd, timeout=120)
    assert (tmp_path / "pool.py").read_text(encoding="utf-8") == POOL


def test_a_suite_red_before_blanking_is_inconclusive_not_a_pass(bar, tmp_path):
    cmd = _project(tmp_path, GOOD_TEST + "assert False\n")
    r = bar.check(str(tmp_path), "pool.py", ["dl_tau2"], cmd, timeout=120)
    assert r["verdict"] == "INCONCLUSIVE"
    assert "BEFORE blanking" in r["reason"]


def test_a_missing_function_is_inconclusive(bar, tmp_path):
    cmd = _project(tmp_path, GOOD_TEST)
    r = bar.check(str(tmp_path), "pool.py", ["reml_tau2"], cmd, timeout=120)
    assert r["verdict"] == "INCONCLUSIVE"
    assert r["functions"][0]["outcome"] == "NOT-FOUND"


def test_blanking_keeps_signature_decorators_and_neighbours(bar):
    src = "import functools\n@functools.lru_cache\ndef f(x):\n    y = x\n    return y\n\nZ = 1\n"
    out = bar.blank_function(src, "f")
    assert "@functools.lru_cache\ndef f(x):\n" in out
    assert "return y" not in out and "NotImplementedError" in out and "Z = 1" in out


def test_blanking_a_one_line_method(bar):
    src = "class P:\n    def size(self, xs): return len(xs)\n"
    out = bar.blank_function(src, "P.size")
    assert "return len" not in out
    compile(out, "x.py", "exec")


def test_cli_exit_codes(tmp_path):
    cmd = _project(tmp_path, HOLLOW_TEST)
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "--root", str(tmp_path), "--file", "pool.py",
                        "--function", "dl_tau2", "--cmd", cmd], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CLAIM-FAILS" in r.stdout


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
