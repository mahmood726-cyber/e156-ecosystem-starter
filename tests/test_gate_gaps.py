"""Tests for scripts/render-gate-gaps.py -- the gate-gap registry and its --check.

Two jobs. First, `test_this_repo_is_current` IS the enforcement: it runs --check on
this checkout, so the python-tests CI job fails when a workflow job or check script
lands with no entry in docs/gate-gaps.json, when a gate's bytes move under its seal,
or when docs/GATE_GAPS.md is stale.

Second, a check that cannot fail is not a check. Every refusal reason gets a PLANTED
defect that must be refused, and the clean fixture must pass -- the clean case is what
stops "refuses everything" from reading as "works". The plants run on a minimal
fixture repo, and the most important ones (an unregistered job, a stale seal, a
hand-edited page) are repeated on a copy of THIS repo's real workflow, so the parser
is proven on the YAML it actually has to read.
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
SCRIPT_PATH = REPO_ROOT / "scripts" / "render-gate-gaps.py"

WORKFLOW = """\
name: tests
on: [push]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - run: bash scripts/parity.sh
  # a comment between jobs belongs to neither seal
  drift:
    runs-on: ubuntu-latest
    if: false
    steps:
      - run: echo never
"""

CHECKER = """\
import argparse, sys
ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
sys.exit(0)
"""

HOOK = """\
import json, sys
payload = json.loads(sys.stdin.read())
target = payload.get("tool_input", {})
sys.exit(0)
"""


@pytest.fixture(scope="module")
def rgg():
    spec = importlib.util.spec_from_file_location("render_gate_gaps", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(gid: str, kind: str) -> dict:
    return {"id": gid, "kind": kind, "name": gid, "stops": "a planted defect",
            "would_not_stop": ["anything it was not written for"], "source": "fixture", "seal": {}}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def repo(tmp_path, rgg):
    """A minimal repo that is CURRENT: two jobs (one disabled), a script, a hook."""
    _write(tmp_path / ".github/workflows/ci.yml", WORKFLOW)
    _write(tmp_path / "scripts/parity.sh", "#!/usr/bin/env bash\nexit 0\n")   # gate via CI run step
    _write(tmp_path / "scripts/thing-check.py", CHECKER)                      # gate via --check
    _write(tmp_path / "scripts/guard.py", HOOK)                               # gate via hook payload
    _write(tmp_path / "scripts/helper.py", "print('not a gate')\n")           # not enumerated
    entries = [
        _entry(".github/workflows/ci.yml#jobs.unit", "ci-job"),
        _entry(".github/workflows/ci.yml#jobs.drift", "declared-gap"),
        _entry("scripts/parity.sh", "script"),
        _entry("scripts/thing-check.py", "script"),
        _entry("scripts/guard.py", "hook"),
    ]
    _write(tmp_path / rgg.REGISTRY_PATH, json.dumps({"schema": rgg.SCHEMA, "gates": entries}))
    assert rgg.reseal(tmp_path, [e["id"] for e in entries]) == []
    rgg.write_doc(tmp_path)
    return tmp_path


def _registry(rgg, root: Path) -> dict:
    return json.loads((root / rgg.REGISTRY_PATH).read_text(encoding="utf-8"))


def _save(rgg, root: Path, data: dict) -> None:
    rgg.write_registry(root, data)
    rgg.write_doc(root)  # keep the page current so only the planted defect is in play


def _assert_refused(rgg, root: Path, needle: str) -> list[str]:
    code, reasons = rgg.check(root)
    assert code == rgg.REFUSED, reasons
    assert any(needle in r for r in reasons), reasons
    return reasons


# --------------------------------------------------------------------------
# This repository -- the enforcement
# --------------------------------------------------------------------------

def test_this_repo_is_current():
    """The real registry covers every real gate, every seal matches, the page is current."""
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), "--check"],
                          capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CURRENT" in proc.stdout


def test_real_enumeration_finds_the_gates_the_brief_names(rgg):
    """The census is mechanical, so pin that it still sees what it must."""
    census = rgg.enumerate_gates(REPO_ROOT)
    for gid in ("scripts/protect-test-config.py", "scripts/blank-and-rerun.py",
                "scripts/gate-can-fail.py", "scripts/regen-hashes.sh",
                "scripts/check-i18n-parity.sh", "scripts/search-record-reconcile.py",
                ".github/workflows/test.yml#jobs.python-tests",
                ".github/workflows/test.yml#jobs.hash-check"):
        assert gid in census, gid
    assert census["scripts/protect-test-config.py"]["allowed_kinds"] == ("hook",)
    drift = census[".github/workflows/test.yml#jobs.sentinel-rule-list-drift"]
    assert drift["allowed_kinds"] == ("declared-gap",), "the if: false job must be a declared gap, not a gate"
    assert "scripts/install-sentinel.sh" not in census, "a shellcheck ARGUMENT is not a CI-run gate"


# --------------------------------------------------------------------------
# Clean -> passes
# --------------------------------------------------------------------------

def test_clean_fixture_passes(rgg, repo):
    assert rgg.check(repo) == (rgg.CURRENT, [])


def test_clean_fixture_passes_through_the_cli(repo):
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), "--check", "--root", str(repo)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
    assert "CURRENT" in proc.stdout


def test_crlf_checkout_has_the_same_seal(rgg, repo):
    """A Windows checkout (core.autocrlf=true) must not break seals CI computed on LF."""
    for rel in (".github/workflows/ci.yml", "scripts/thing-check.py"):
        p = repo / rel
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert rgg.check(repo) == (rgg.CURRENT, [])


def test_comment_between_jobs_does_not_move_a_seal(rgg, repo):
    wf = repo / ".github/workflows/ci.yml"
    wf.write_text(wf.read_text(encoding="utf-8").replace(
        "  # a comment between jobs", "\n  # an edited comment\n  # a comment between jobs"), encoding="utf-8")
    assert rgg.check(repo) == (rgg.CURRENT, [])


# --------------------------------------------------------------------------
# Planted defects -> refused
# --------------------------------------------------------------------------

def test_planted_unregistered_ci_job_is_refused(rgg, repo):
    wf = repo / ".github/workflows/ci.yml"
    wf.write_text(wf.read_text(encoding="utf-8") +
                  "  sneaky:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n",
                  encoding="utf-8")
    _assert_refused(rgg, repo, ".github/workflows/ci.yml#jobs.sneaky: UNREGISTERED")


def test_planted_unregistered_check_script_is_refused(rgg, repo):
    _write(repo / "scripts/new-guard.py", CHECKER.replace("--check", "--selftest"))
    _assert_refused(rgg, repo, "scripts/new-guard.py: UNREGISTERED")


def test_planted_unregistered_shell_check_is_refused(rgg, repo):
    _write(repo / "scripts/new-check.sh", 'case "$1" in\n    --check) exit 1 ;;\nesac\n')
    _assert_refused(rgg, repo, "scripts/new-check.sh: UNREGISTERED")


def test_planted_stale_seal_on_a_script_is_refused(rgg, repo):
    p = repo / "scripts/thing-check.py"
    p.write_text(p.read_text(encoding="utf-8").replace("sys.exit(0)", "sys.exit(0)  # loosened"),
                 encoding="utf-8")
    _assert_refused(rgg, repo, "scripts/thing-check.py: STALE SEAL")


def test_planted_stale_seal_on_a_ci_job_is_refused_and_only_that_job(rgg, repo):
    wf = repo / ".github/workflows/ci.yml"
    wf.write_text(wf.read_text(encoding="utf-8").replace("bash scripts/parity.sh",
                                                         "bash scripts/parity.sh || true"),
                  encoding="utf-8")
    reasons = _assert_refused(rgg, repo, "#jobs.unit: STALE SEAL")
    assert not any("#jobs.drift" in r for r in reasons), "editing one job must not re-open another"


def test_planted_stale_seal_on_an_extra_dependency_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    gate = next(e for e in data["gates"] if e["id"] == ".github/workflows/ci.yml#jobs.unit")
    gate["seal"]["scripts/parity.sh"] = ""
    _save(rgg, repo, data)
    assert rgg.reseal(repo, [gate["id"]]) == []
    rgg.write_doc(repo)
    assert rgg.check(repo)[0] == rgg.CURRENT
    (repo / "scripts/parity.sh").write_text("#!/usr/bin/env bash\nexit 0  # never fails\n", encoding="utf-8")
    _assert_refused(rgg, repo, "#jobs.unit: STALE SEAL on `scripts/parity.sh`")


def test_planted_stale_md_is_refused(rgg, repo):
    doc = repo / rgg.DOC_PATH
    doc.write_text(doc.read_text(encoding="utf-8").replace("anything it was not written for",
                                                           "nothing -- it is complete"), encoding="utf-8")
    _assert_refused(rgg, repo, "GATE_GAPS.md: STALE")


def test_planted_registry_edit_without_rerender_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    data["gates"][0]["would_not_stop"].append("a newly admitted gap")
    rgg.write_registry(repo, data)  # page NOT re-rendered
    _assert_refused(rgg, repo, "GATE_GAPS.md: STALE")


def test_planted_missing_md_is_refused(rgg, repo):
    (repo / rgg.DOC_PATH).unlink()
    _assert_refused(rgg, repo, "GATE_GAPS.md: missing")


def test_planted_disabled_job_registered_as_a_gate_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    next(e for e in data["gates"] if e["id"].endswith("#jobs.drift"))["kind"] = "ci-job"
    _save(rgg, repo, data)
    _assert_refused(rgg, repo, "must be 'declared-gap'")


def test_planted_reenabled_declared_gap_is_refused(rgg, repo):
    wf = repo / ".github/workflows/ci.yml"
    wf.write_text(wf.read_text(encoding="utf-8").replace("    if: false\n", ""), encoding="utf-8")
    _assert_refused(rgg, repo, "#jobs.drift: kind 'declared-gap' contradicts the code")


def test_planted_hook_registered_as_plain_script_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    next(e for e in data["gates"] if e["id"] == "scripts/guard.py")["kind"] = "script"
    _save(rgg, repo, data)
    _assert_refused(rgg, repo, "must be 'hook'")


def test_planted_orphan_entry_is_refused(rgg, repo):
    (repo / "scripts/thing-check.py").unlink()
    _assert_refused(rgg, repo, "scripts/thing-check.py: ORPHAN")


def test_planted_empty_gap_list_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    data["gates"][0]["would_not_stop"] = []
    _save(rgg, repo, data)
    _assert_refused(rgg, repo, "`would_not_stop` must be a non-empty list")


def test_planted_unsealed_entry_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    data["gates"][0]["seal"] = {}
    _save(rgg, repo, data)
    _assert_refused(rgg, repo, "`seal` must be a non-empty")


def test_planted_seal_that_skips_the_gate_itself_is_refused(rgg, repo):
    data = _registry(rgg, repo)
    gate = next(e for e in data["gates"] if e["id"] == "scripts/thing-check.py")
    gate["seal"] = {"scripts/helper.py": rgg.dependency_digest(repo, "scripts/helper.py")}
    _save(rgg, repo, data)
    _assert_refused(rgg, repo, "seal does not cover the gate's own implementation")


def test_planted_duplicate_and_unknown_kind_are_refused(rgg, repo):
    data = _registry(rgg, repo)
    data["gates"].append(dict(data["gates"][0]))
    data["gates"][1]["kind"] = "advisory"
    _save(rgg, repo, data)
    reasons = _assert_refused(rgg, repo, "duplicate id")
    assert any("kind must be one of" in r for r in reasons), reasons


def test_unparseable_workflow_is_inconclusive_not_current(rgg, repo):
    _write(repo / ".github/workflows/flow.yml", "name: x\njobs: {a: {runs-on: ubuntu-latest}}\n")
    code, reasons = rgg.check(repo)
    assert code == rgg.INCONCLUSIVE, reasons


def test_missing_registry_is_inconclusive_through_the_cli(repo, rgg):
    (repo / rgg.REGISTRY_PATH).unlink()
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), "--check", "--root", str(repo)],
                          capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout
    assert "INCONCLUSIVE" in proc.stdout


def test_reseal_repairs_only_the_named_gate(rgg, repo):
    for rel in ("scripts/thing-check.py", "scripts/parity.sh"):
        p = repo / rel
        p.write_text(p.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    assert rgg.reseal(repo, ["scripts/thing-check.py"]) == []
    rgg.write_doc(repo)
    code, reasons = rgg.check(repo)
    assert code == rgg.REFUSED
    assert all("scripts/parity.sh" in r for r in reasons), reasons


def test_check_mode_writes_nothing(repo):
    doc = repo / "docs/GATE_GAPS.md"
    doc.write_text("hand-edited\n", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), "--check", "--root", str(repo)],
                          capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout
    assert doc.read_text(encoding="utf-8") == "hand-edited\n"


# --------------------------------------------------------------------------
# The same plants on a copy of THIS repo's real workflow and registry
# --------------------------------------------------------------------------

@pytest.fixture
def real_copy(tmp_path, rgg):
    shutil.copytree(REPO_ROOT / ".github", tmp_path / ".github")
    shutil.copytree(REPO_ROOT / "scripts", tmp_path / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "docs").mkdir()
    for rel in (rgg.REGISTRY_PATH, rgg.DOC_PATH):
        shutil.copy2(REPO_ROOT / rel, tmp_path / rel)
    assert rgg.check(tmp_path) == (rgg.CURRENT, [])
    return tmp_path


def test_real_workflow_new_job_is_refused(rgg, real_copy):
    wf = real_copy / ".github/workflows/test.yml"
    wf.write_text(wf.read_text(encoding="utf-8") +
                  "\n  extra-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n",
                  encoding="utf-8")
    _assert_refused(rgg, real_copy, "#jobs.extra-gate: UNREGISTERED")


def test_real_gate_change_is_refused(rgg, real_copy):
    p = real_copy / "scripts/check-i18n-parity.sh"
    p.write_text(p.read_text(encoding="utf-8").replace("langs=(fr pt ar ur)", "langs=(fr)"),
                 encoding="utf-8")
    reasons = _assert_refused(rgg, real_copy, "scripts/check-i18n-parity.sh: STALE SEAL")
    assert any("#jobs.i18n-parity: STALE SEAL" in r for r in reasons), \
        "the CI job sealed the script it runs, so narrowing the script re-opens the job too"


def test_real_hand_edited_page_is_refused(rgg, real_copy):
    doc = real_copy / rgg.DOC_PATH
    doc.write_text(doc.read_text(encoding="utf-8") + "\nExtra hand-written claim.\n", encoding="utf-8")
    _assert_refused(rgg, real_copy, "GATE_GAPS.md: STALE")
