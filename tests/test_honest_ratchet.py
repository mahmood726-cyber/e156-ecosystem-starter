"""Tests for scripts/honest-ratchet.py (port of the meta-harness honest-state ratchet).

House rule: BOTH directions. A ratchet that refuses everything also "passes" a
must-refuse test, and one that refuses nothing passes a must-allow test; only
the pair says anything.

`test_repo_protective_state_has_not_got_quieter` is the enforcement: it runs
--check against THIS repo, so the existing python-tests CI job refuses a PR
that deletes a test, a rules file, a protected pattern, a guard script or a CI
job without a named acknowledgement in docs/ratchet-acknowledgements.json.

The planted-defect tests work on a temp copy of the repo, never the checkout.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "honest-ratchet.py"

# What a temp copy needs for the ratchet to measure the real state.
COPY_PATHS = ("tests", "scripts", "rules", "install", "bootstrap", ".github", "docs/ratchet-baseline.json",
              "docs/ratchet-acknowledgements.json")


@pytest.fixture(scope="module")
def hr():
    spec = importlib.util.spec_from_file_location("honest_ratchet", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo_copy(tmp_path):
    dst = tmp_path / "repo"
    for rel in COPY_PATHS:
        src = REPO_ROOT / rel
        if src.is_dir():
            shutil.copytree(src, dst / rel, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        elif src.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / rel)
    return dst


def run(*args, root=None):
    cmd = [sys.executable, str(SCRIPT_PATH), *args]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def write_acks(root, entries):
    (root / "docs" / "ratchet-acknowledgements.json").write_text(
        json.dumps({"_doc": "test", "acknowledgements": entries}), encoding="utf-8")


def drop_function(path: Path, name: str):
    """Delete one top-level `def <name>` (and its body) from a pytest file."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith("def %s(" % name))
    while start > 0 and lines[start - 1].startswith("@"):
        start -= 1
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t"):
        end += 1
    path.write_text("".join(lines[:start] + lines[end:]), encoding="utf-8")


VICTIM_FILE = "tests/test_push_portfolio.py"


def victim_name(hr, root):
    return sorted(hr.pytest_tests((root / VICTIM_FILE).read_text(encoding="utf-8")))[0]


# ---------------------------------------------------------------- enforcement

def test_repo_protective_state_has_not_got_quieter():
    r = run("--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_selftest_passes():
    r = run("--selftest")
    assert r.returncode == 0, r.stdout + r.stderr


def test_version_constant(hr):
    assert hr.VERSION == "1.0.0"
    assert run("--version").stdout.strip() == hr.VERSION


# ------------------------------------------------------------ planted defects

def test_unchanged_copy_passes(repo_copy):
    assert run("--check", root=repo_copy).returncode == 0


def test_deleted_test_is_refused(hr, repo_copy):
    name = victim_name(hr, repo_copy)
    drop_function(repo_copy / VICTIM_FILE, name)
    r = run("--check", root=repo_copy)
    assert r.returncode == 1, r.stdout
    assert "REFUSED" in r.stdout
    assert "pytest:%s" % VICTIM_FILE in r.stdout
    assert "%s::%s" % ("pytest-names:" + VICTIM_FILE, name) in r.stdout


def test_acknowledged_deletion_passes(hr, repo_copy):
    name = victim_name(hr, repo_copy)
    base = hr.measure(repo_copy)["counts"]["pytest:" + VICTIM_FILE]
    drop_function(repo_copy / VICTIM_FILE, name)
    write_acks(repo_copy, [
        {"item": "pytest:" + VICTIM_FILE, "base": base, "new": base - 1,
         "reason": "planted: duplicate case folded", "date": "2026-10-21"},
        {"item": "pytest-names:%s::%s" % (VICTIM_FILE, name),
         "reason": "planted: duplicate case folded", "date": "2026-10-21"},
    ])
    r = run("--check", root=repo_copy)
    assert r.returncode == 0, r.stdout


def test_acknowledgement_must_name_exact_counts(hr, repo_copy):
    name = victim_name(hr, repo_copy)
    base = hr.measure(repo_copy)["counts"]["pytest:" + VICTIM_FILE]
    drop_function(repo_copy / VICTIM_FILE, name)
    write_acks(repo_copy, [
        {"item": "pytest:" + VICTIM_FILE, "base": base, "new": base - 2,
         "reason": "wrong count", "date": "2026-10-21"},
        {"item": "pytest-names:%s::%s" % (VICTIM_FILE, name), "reason": "x", "date": "2026-10-21"},
    ])
    assert run("--check", root=repo_copy).returncode == 1


def test_acknowledgement_without_reason_or_date_is_ignored(hr, repo_copy):
    name = victim_name(hr, repo_copy)
    base = hr.measure(repo_copy)["counts"]["pytest:" + VICTIM_FILE]
    drop_function(repo_copy / VICTIM_FILE, name)
    write_acks(repo_copy, [
        {"item": "pytest:" + VICTIM_FILE, "base": base, "new": base - 1, "reason": "", "date": "2026-10-21"},
        {"item": "pytest-names:%s::%s" % (VICTIM_FILE, name), "reason": "x", "date": "yesterday"},
    ])
    assert run("--check", root=repo_copy).returncode == 1


def test_added_test_passes(repo_copy):
    p = repo_copy / VICTIM_FILE
    p.write_text(p.read_text(encoding="utf-8") + "\n\ndef test_planted_extra():\n    assert True\n",
                 encoding="utf-8")
    assert run("--check", root=repo_copy).returncode == 0


def test_newly_skipped_test_is_refused(hr, repo_copy):
    p = repo_copy / VICTIM_FILE
    name = victim_name(hr, repo_copy)
    text = p.read_text(encoding="utf-8")
    text = text.replace("def %s(" % name, "@pytest.mark.skip\ndef %s(" % name, 1)
    if "import pytest" not in text:
        text = "import pytest\n" + text
    p.write_text(text, encoding="utf-8")
    assert run("--check", root=repo_copy).returncode == 1


def test_renamed_test_is_refused_even_at_equal_count(hr, repo_copy):
    p = repo_copy / VICTIM_FILE
    name = victim_name(hr, repo_copy)
    p.write_text(p.read_text(encoding="utf-8").replace("def %s(" % name, "def test_zz_renamed(", 1),
                 encoding="utf-8")
    r = run("--check", root=repo_copy)
    assert r.returncode == 1
    assert "pytest:%s: count" not in r.stdout  # count unchanged; the NAME is what was lost


def test_deleted_pester_it_block_is_refused(repo_copy):
    p = repo_copy / "scripts" / "pester.phase4.tests.ps1"
    lines = p.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    i = next(i for i, l in enumerate(lines) if l.lstrip().startswith("It "))
    lines[i] = lines[i].replace("It ", "# It ", 1)
    p.write_text("".join(lines), encoding="utf-8")
    assert run("--check", root=repo_copy).returncode == 1


def test_deleted_bash_case_is_refused(repo_copy):
    p = repo_copy / "tests" / "test-new-layers.bash"
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    i = next(i for i, l in enumerate(lines) if l.lstrip().startswith('start "'))
    del lines[i]
    p.write_text("".join(lines), encoding="utf-8")
    assert run("--check", root=repo_copy).returncode == 1


def test_removed_rules_file_is_refused(repo_copy):
    (repo_copy / "rules" / "lessons.md").unlink()
    r = run("--check", root=repo_copy)
    assert r.returncode == 1
    assert "rules::rules/lessons.md" in r.stdout


def test_removed_protected_pattern_is_refused(repo_copy):
    p = repo_copy / "scripts" / "protect-test-config.py"
    p.write_text(p.read_text(encoding="utf-8").replace('    "tox.ini",\n', "", 1), encoding="utf-8")
    r = run("--check", root=repo_copy)
    assert r.returncode == 1
    assert "PROTECTED_NAMES:tox.ini" in r.stdout


def test_removed_guard_script_is_refused(repo_copy):
    (repo_copy / "scripts" / "gate-can-fail.py").unlink()
    assert run("--check", root=repo_copy).returncode == 1


def test_disabled_ci_job_is_refused(repo_copy):
    p = repo_copy / ".github" / "workflows" / "test.yml"
    text = p.read_text(encoding="utf-8")
    text = text.replace("    name: Python tests (Ubuntu)\n", "    name: Python tests (Ubuntu)\n    if: false\n", 1)
    p.write_text(text, encoding="utf-8")
    r = run("--check", root=repo_copy)
    assert r.returncode == 1
    assert "ci-jobs-enabled::python-tests" in r.stdout


def test_update_refuses_to_bless_an_unacknowledged_loss(repo_copy):
    baseline = repo_copy / "docs" / "ratchet-baseline.json"
    before = baseline.read_bytes()
    (repo_copy / "rules" / "lessons.md").unlink()
    assert run("--update", root=repo_copy).returncode == 1
    assert baseline.read_bytes() == before


def test_update_after_an_addition_raises_the_floor(repo_copy):
    p = repo_copy / VICTIM_FILE
    original = p.read_text(encoding="utf-8")
    p.write_text(original + "\n\ndef test_planted_extra():\n    assert True\n", encoding="utf-8")
    assert run("--update", root=repo_copy).returncode == 0
    p.write_text(original, encoding="utf-8")  # now removing the added test is a loss
    assert run("--check", root=repo_copy).returncode == 1


def test_missing_baseline_fails_closed(repo_copy):
    (repo_copy / "docs" / "ratchet-baseline.json").unlink()
    r = run("--check", root=repo_copy)
    assert r.returncode == 2
    assert "COULD-NOT-EXECUTE" in r.stdout


def test_malformed_acknowledgements_fail_closed(repo_copy):
    (repo_copy / "docs" / "ratchet-acknowledgements.json").write_text("{not json", encoding="utf-8")
    assert run("--check", root=repo_copy).returncode == 2
