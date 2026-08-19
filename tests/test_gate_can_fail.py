"""Tests for scripts/gate-can-fail.py.

Same house rule as the rest of this kit: a detector that can only report "found
something" is not a detector. Every rule gets BOTH directions -- a file that must
fire it and a file that must not.

The specific failure this suite guards against is the one that actually happened
while the check was being written. `sys.exit(main())` is the standard gate shape,
so an early version treated any non-constant argument as "can fail" -- and every
one of the four real files that motivated the check ends exactly that way, with a
`main()` whose only return is 0. The first version would have missed all four
files it was written for, and its unit tests were passing throughout. So
`test_silent_main_is_flagged` is not a formality; it is the regression test for
the defect that made this tool worth having.

The second guard is against the opposite failure: a lint that flags everything
also "works" on a corpus full of defects. `test_known_good_do_not_fire` and the
empty-set case below are what stop that reading.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "gate-can-fail.py"


@pytest.fixture(scope="module")
def gcf():
    """Import the hyphenated script as a module."""
    spec = importlib.util.spec_from_file_location("gate_can_fail", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, name: str, src: str) -> None:
    (tmp_path / name).write_text(src, encoding="utf-8")


# --------------------------------------------------------------------------
# Direction 1: known-bad must fire
# --------------------------------------------------------------------------

def test_silent_main_is_flagged(gcf, tmp_path):
    """`sys.exit(main())` where main can only return 0 -- the real-world case."""
    _write(tmp_path, "silent_gate.py",
           "import sys\n"
           "def main():\n"
           "    print('ok')\n"
           "    return 0\n"
           "sys.exit(main())\n")
    result = gcf.scan(str(tmp_path))
    assert result["cannot_ever_fail"] == ["silent_gate.py"]
    assert result["verdict"] == "DEFECTS-FOUND"


def test_print_only_is_flagged(gcf, tmp_path):
    _write(tmp_path, "report_gate.py", "print('3 problems found')\n")
    assert gcf.scan(str(tmp_path))["cannot_ever_fail"] == ["report_gate.py"]


def test_bare_exit_is_flagged(gcf, tmp_path):
    """`sys.exit()` with no argument is `sys.exit(0)`."""
    _write(tmp_path, "bare_gate.py", "import sys\nprint('done')\nsys.exit()\n")
    assert gcf.scan(str(tmp_path))["cannot_ever_fail"] == ["bare_gate.py"]


# --------------------------------------------------------------------------
# Direction 2: known-good must NOT fire
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,src", [
    ("explicit_gate.py", "import sys\nif True:\n    sys.exit(1)\n"),
    ("return_gate.py", "import sys\ndef main():\n    if 1:\n        return 1\n    return 0\nsys.exit(main())\n"),
    ("raise_gate.py", "raise SystemExit('refused')\n"),
    ("exit_two_gate.py", "import sys\nsys.exit(2)\n"),
])
def test_known_good_do_not_fire(gcf, tmp_path, name, src):
    _write(tmp_path, name, src)
    result = gcf.scan(str(tmp_path))
    assert result["cannot_ever_fail"] == []
    assert result["verdict"] == "CLEAN"


def test_unresolvable_exit_is_not_convicted(gcf, tmp_path):
    """A lint must not manufacture a failure it cannot demonstrate.

    `sys.exit(compute())` where `compute` is not a module-level def cannot be
    resolved. Unproven is not the same as proven-broken, so it is left alone.
    """
    _write(tmp_path, "opaque_gate.py", "import sys\nfrom helpers import compute\nsys.exit(compute())\n")
    assert gcf.scan(str(tmp_path))["cannot_ever_fail"] == []


# --------------------------------------------------------------------------
# Scope: what is and is not in the denominator
# --------------------------------------------------------------------------

def test_file_not_named_a_gate_is_never_scanned(gcf, tmp_path):
    _write(tmp_path, "helper.py", "print('cannot fail, and does not claim to')\n")
    result = gcf.scan(str(tmp_path))
    assert result["files_checked"] == 0
    assert result["cannot_ever_fail"] == []


def test_verb_prefix_is_excluded_and_named(gcf, tmp_path):
    """Exclusions are counted and listed, never silently dropped.

    A verb prefix puts 'gate' in the object position: the file acts ON a gate
    rather than being one. That is a real distinction and also an obvious hiding
    place, which is why the excluded files are reported by name on every run.
    """
    _write(tmp_path, "test_build_gate.py", "def test_x():\n    assert True\n")
    _write(tmp_path, "fix_release_gate.py", "print('patched')\n")
    result = gcf.scan(str(tmp_path))
    assert sorted(result["excluded_by_verb_prefix"]) == ["fix_release_gate.py", "test_build_gate.py"]
    assert result["files_checked"] == 0
    assert result["cannot_ever_fail"] == []


def test_denominator_is_reported(gcf, tmp_path):
    """A count of hits with no count of what was looked at is not refutable."""
    _write(tmp_path, "a_gate.py", "import sys\nsys.exit(1)\n")
    _write(tmp_path, "b_gate.py", "print('hi')\n")
    result = gcf.scan(str(tmp_path))
    assert result["files_checked"] == 2
    assert len(result["cannot_ever_fail"]) == 1


# --------------------------------------------------------------------------
# "I could not check this" must never collapse into "this is fine"
# --------------------------------------------------------------------------

def test_unparsable_is_inconclusive_not_clean(gcf, tmp_path):
    _write(tmp_path, "broken_gate.py", "def main(:\n")
    result = gcf.scan(str(tmp_path))
    assert result["verdict"] == "INCONCLUSIVE"
    assert len(result["unparsable"]) == 1
    assert result["unparsable"][0]["file"] == "broken_gate.py"


def test_a_real_defect_outranks_an_unparsable_file(gcf, tmp_path):
    """DEFECTS-FOUND wins over INCONCLUSIVE: a found defect is the stronger fact."""
    _write(tmp_path, "broken_gate.py", "def main(:\n")
    _write(tmp_path, "silent_gate.py", "print('ok')\n")
    assert gcf.scan(str(tmp_path))["verdict"] == "DEFECTS-FOUND"


# --------------------------------------------------------------------------
# The tool's own selftest, and the CLI contract
# --------------------------------------------------------------------------

def test_selftest_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), "--selftest"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "selftest OK" in proc.stdout


def test_exit_codes(tmp_path):
    (tmp_path / "silent_gate.py").write_text("print('ok')\n", encoding="utf-8")
    bad = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path)],
                         capture_output=True, text=True)
    assert bad.returncode == 1

    (tmp_path / "silent_gate.py").unlink()
    (tmp_path / "good_gate.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    good = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path)],
                          capture_output=True, text=True)
    assert good.returncode == 0

    (tmp_path / "broken_gate.py").write_text("def main(:\n", encoding="utf-8")
    inconclusive = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path)],
                                  capture_output=True, text=True)
    assert inconclusive.returncode == 2


def test_json_output_carries_the_denominator(tmp_path):
    (tmp_path / "a_gate.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path), "--json"],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["files_checked"] == 1
    assert payload["verdict"] == "CLEAN"
    assert payload["cannot_ever_fail"] == []


def test_empty_set_says_so_rather_than_reading_as_a_pass(tmp_path):
    """A CLEAN over zero files is not evidence, and the output must say that."""
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path)],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "EMPTY SET" in proc.stdout


def test_missing_path_is_inconclusive(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path / "nope")],
                          capture_output=True, text=True)
    assert proc.returncode == 2
