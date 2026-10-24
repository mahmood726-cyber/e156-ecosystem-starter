"""Tests for scripts/verify-local.py and the opt-in .githooks/pre-commit.

Three things are under test, and each gets BOTH directions (a known-good input
that must pass and a planted defect that must be refused), because a check that
cannot fail is not a check:

  1. PARITY. tests read .github/workflows/test.yml and fail if any CI job or
     step has no verify-local limb (and is not listed CI-only with a reason), if
     a limb points at a CI step that no longer exists, or if the file lists and
     flags a limb passes differ from CI's. This is what stops local and CI from
     drifting apart silently -- the defect the meta-harness original was built
     after (its hook ran no unit tests; its CI ran no index check).
  2. FAIL-CLOSED LEDGER. A missing tool is COULD-NOT-EXECUTE (exit 2), never a
     skip; --allow-missing turns it into a visible NOT RUN only for the limb
     named, only when the tool really is missing, and never hides a failure.
  3. THE HOOK calls verify-local and nothing else, and refuses the commit when
     verify-local does.

None of these tests runs the full verify-local: its pytest limb would re-enter
this suite. Real limbs are exercised against throwaway copies instead.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify-local.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"
HOOK = REPO_ROOT / ".githooks" / "pre-commit"


@pytest.fixture(scope="module")
def vl():
    """Import the hyphenated script as a module (registered in sys.modules so
    its dataclasses resolve their own module)."""
    spec = importlib.util.spec_from_file_location("verify_local", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_local"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def _silent(*_a, **_k):
    pass


# --------------------------------------------------------------------------
# 1. Parity with .github/workflows/test.yml
# --------------------------------------------------------------------------

def test_real_workflow_is_in_parity(vl, workflow_text):
    """Known-good: the committed CI workflow and the committed limbs agree."""
    assert vl.find_drift(workflow_text) == []


def test_parser_sees_every_ci_job(vl, workflow_text):
    """Guard the guard: if the parser silently read fewer jobs, parity over the
    remainder would be a flattering pass."""
    jobs = vl.parse_workflow(workflow_text)
    declared = re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", workflow_text.split("\njobs:\n", 1)[1], re.M)
    assert sorted(jobs) == sorted(declared)
    assert all(job["steps"] for job in jobs.values())


def test_planted_new_ci_step_without_limb_is_refused(vl, workflow_text):
    planted = workflow_text.replace(
        "      - name: Run handoff-locale bash tests\n",
        "      - name: Run brand-new bash tests\n"
        "        run: bash tests/test-new-layers.bash\n"
        "      - name: Run handoff-locale bash tests\n",
    )
    assert planted != workflow_text
    drift = vl.find_drift(planted)
    assert any("Run brand-new bash tests" in p and "no verify-local limb" in p for p in drift), drift


def test_planted_new_ci_job_without_limb_is_refused(vl, workflow_text):
    planted = workflow_text.replace(
        "  lint:\n",
        "  typecheck:\n"
        "    name: mypy\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: Run mypy\n"
        "        run: mypy scripts/\n"
        "\n"
        "  lint:\n",
    )
    drift = vl.find_drift(planted)
    assert any("typecheck" in p and "Run mypy" in p for p in drift), drift
    assert any("job 'typecheck' has no step mirrored" in p for p in drift), drift


def test_planted_renamed_ci_step_leaves_limb_stale(vl, workflow_text):
    planted = workflow_text.replace("- name: Run pytest", "- name: Run the pytest suite")
    drift = vl.find_drift(planted)
    assert any("limb 'pytest' claims CI step python-tests / 'Run pytest'" in p for p in drift), drift


def test_planted_enabling_disabled_job_demands_a_limb(vl, workflow_text):
    """Preserve the historical guard: an enabled CI check must gain a limb.

    Start from a synthetic disabled job, enable it without mapping its step,
    and insist that local/CI parity refuses. The separate test below verifies
    that disabling an actively mapped gate is also refused.
    """
    disabled = workflow_text.replace("  sentinel-rule-list-drift:\n",
                                     "  sentinel-rule-list-drift:\n    if: false\n")
    assert disabled != workflow_text
    enabled = disabled.replace("    if: false\n", "")
    unmapped = tuple(l for l in vl.LIMBS if l.name != "sentinel-rule-list-drift")
    drift = vl.find_drift(enabled, limbs=unmapped)
    assert any("sentinel-rule-list-drift" in item and "no verify-local limb" in item
               for item in drift), drift


def test_planted_disabling_active_sentinel_gate_is_refused(vl, workflow_text):
    """A previously green mapped job may not silently become skipped."""
    planted = workflow_text.replace("  sentinel-rule-list-drift:\n",
                                    "  sentinel-rule-list-drift:\n    if: false\n")
    assert planted != workflow_text
    drift = vl.find_drift(planted)
    assert any("sentinel-rule-list-drift" in p and "disabled in CI" in p for p in drift), drift


def test_planted_sentinel_checkout_pin_drift_is_refused(vl, workflow_text):
    planted = workflow_text.replace(vl.SENTINEL_PIN, "0" * 40)
    assert planted != workflow_text
    drift = vl.find_drift(planted)
    assert any("Sentinel CI checkout pin differs" in p for p in drift), drift


@pytest.mark.parametrize("dropped", range(10))
def test_planted_missing_limb_is_refused(vl, workflow_text, dropped):
    """Delete any one limb from verify-local: the CI step it mirrored is now
    unmatched, and parity must say so."""
    assert len(vl.LIMBS) == 10
    limbs = [l for i, l in enumerate(vl.LIMBS) if i != dropped]
    drift = vl.find_drift(workflow_text, limbs=limbs)
    job, step = vl.LIMBS[dropped].ci_steps[0]
    assert any(job in p and step in p and "no verify-local limb" in p for p in drift), drift


def test_planted_ci_only_entry_without_reason_is_refused(vl, workflow_text):
    no_reason = dict(vl.CI_ONLY_STEPS)
    no_reason[("bash-tests", "Show bash version")] = "  "
    drift = vl.find_drift(workflow_text, ci_only_steps=no_reason)
    assert any("has no reason" in p for p in drift), drift


def test_planted_pester_file_added_in_ci_only_is_refused(vl, workflow_text):
    # Use the last named suite so new legitimate suites cannot invalidate the plant.
    last_suite = vl.PESTER_FILES[-1]
    needle = f"            '{last_suite}'\n"
    assert needle in workflow_text, "Pester suite fixture format changed"
    planted = workflow_text.replace(
        needle,
        f"            '{last_suite}',\n"
        "            'scripts\\pester.new-suite.tests.ps1'\n",
        1,
    )
    assert planted != workflow_text
    drift = vl.find_drift(planted)
    assert any(p.startswith("Pester file lists differ") for p in drift), drift

def test_planted_shellcheck_file_dropped_in_ci_is_refused(vl, workflow_text):
    # The CI command is backslash-continued across physical lines.  The old
    # "\\n" string matched a *literal n*, never the actual newline, making
    # this planted-drift negative control fail before it exercised the gate.
    needle = "            scripts/install-overmind.sh " + chr(92) + "\n"
    assert needle in workflow_text, "ShellCheck fixture format changed"
    planted = workflow_text.replace(needle, "", 1)
    drift = vl.find_drift(planted)
    assert any(p.startswith("ShellCheck file lists differ") for p in drift), drift


def test_planted_changed_ci_command_is_refused(vl, workflow_text):
    planted = workflow_text.replace("bash scripts/check-i18n-parity.sh", "bash scripts/check-i18n-parity-v2.sh")
    drift = vl.find_drift(planted)
    assert any("check-i18n-parity.sh" in p for p in drift), drift


def test_empty_workflow_is_a_refusal_not_a_pass(vl):
    assert vl.find_drift("name: tests\non: push\n") != []


# --------------------------------------------------------------------------
# 2. Fail-closed ledger
# --------------------------------------------------------------------------

def _limb(vl, name, fn):
    return vl.Limb(name, f"fake {name}", (), fn)


def _missing(_ctx):
    raise _missing.exc("frobtool not found on PATH")


def _ctx(vl, tmp_path, which=lambda _n: None):
    return vl.Context(root=tmp_path, which=which)


def test_all_pass_exits_zero(vl, tmp_path):
    limbs = [_limb(vl, "a", lambda c: (vl.PASS, "")), _limb(vl, "b", lambda c: (vl.PASS, ""))]
    code, results = vl.run_limbs(limbs, _ctx(vl, tmp_path), out=_silent)
    assert code == 0
    assert [v for _, v, _ in results] == [vl.PASS, vl.PASS]


def test_one_refused_exits_one_and_every_limb_still_runs(vl, tmp_path):
    ran = []

    def rec(verdict):
        def fn(_c):
            ran.append(verdict)
            return verdict, "detail"
        return fn

    limbs = [_limb(vl, "a", rec(vl.REFUSED)), _limb(vl, "b", rec(vl.PASS))]
    code, _ = vl.run_limbs(limbs, _ctx(vl, tmp_path), out=_silent)
    assert code == 1
    assert ran == [vl.REFUSED, vl.PASS]  # no early exit


def test_missing_tool_is_could_not_execute_exit_two(vl, tmp_path):
    _missing.exc = vl.ToolMissing
    lines = []
    limbs = [_limb(vl, "a", lambda c: (vl.PASS, "")), _limb(vl, "frob", _missing)]
    code, results = vl.run_limbs(limbs, _ctx(vl, tmp_path), out=lines.append)
    assert code == 2
    assert results[1][1] == vl.NOEXEC
    assert any("--allow-missing frob" in ln for ln in lines)


def test_allow_missing_prints_not_run_and_exits_zero(vl, tmp_path):
    _missing.exc = vl.ToolMissing
    lines = []
    limbs = [_limb(vl, "a", lambda c: (vl.PASS, "")), _limb(vl, "frob", _missing)]
    code, results = vl.run_limbs(limbs, _ctx(vl, tmp_path), allow_missing=["frob"], out=lines.append)
    assert code == 0
    assert results[1][1] == vl.NOT_RUN
    assert any("NOT RUN" in ln and "frob" in ln for ln in lines)
    assert not any("all 2 limbs PASS" in ln for ln in lines)  # never claims a full pass


def test_allow_missing_cannot_hide_a_failure(vl, tmp_path):
    """The excuse covers a MISSING tool only. A limb whose tool is present runs,
    and a failing one is REFUSED even if it was named in --allow-missing."""
    limbs = [_limb(vl, "frob", lambda c: (vl.REFUSED, "it ran and failed"))]
    code, results = vl.run_limbs(limbs, _ctx(vl, tmp_path), allow_missing=["frob"], out=_silent)
    assert code == 1
    assert results[0][1] == vl.REFUSED


def test_allow_missing_for_one_limb_does_not_excuse_another(vl, tmp_path):
    _missing.exc = vl.ToolMissing
    limbs = [_limb(vl, "frob", _missing), _limb(vl, "grob", _missing)]
    code, results = vl.run_limbs(limbs, _ctx(vl, tmp_path), allow_missing=["frob"], out=_silent)
    assert code == 2
    assert [v for _, v, _ in results] == [vl.NOT_RUN, vl.NOEXEC]


def test_crashing_limb_is_could_not_execute(vl, tmp_path):
    def boom(_c):
        raise RuntimeError("kaboom")

    code, results = vl.run_limbs([_limb(vl, "x", boom)], _ctx(vl, tmp_path), out=_silent)
    assert code == 2
    assert results[0][1] == vl.NOEXEC and "kaboom" in results[0][2]


def test_refused_dominates_could_not_execute(vl, tmp_path):
    _missing.exc = vl.ToolMissing
    limbs = [_limb(vl, "a", lambda c: (vl.REFUSED, "")), _limb(vl, "frob", _missing)]
    code, _ = vl.run_limbs(limbs, _ctx(vl, tmp_path), out=_silent)
    assert code == 1


def test_real_shellcheck_limb_with_no_tool_on_path(vl, tmp_path):
    """Real limb, tool absent: COULD-NOT-EXECUTE, then NOT RUN only when named."""
    shellcheck = next(l for l in vl.LIMBS if l.name == "shellcheck")
    ctx = _ctx(vl, tmp_path, which=lambda _n: None)
    code, res = vl.run_limbs([shellcheck], ctx, out=_silent)
    assert (code, res[0][1]) == (2, vl.NOEXEC)
    code, res = vl.run_limbs([shellcheck], ctx, allow_missing=["shellcheck"], out=_silent)
    assert (code, res[0][1]) == (0, vl.NOT_RUN)


def test_unknown_allow_missing_name_is_a_usage_error(vl, capsys):
    assert vl.main(["--allow-missing", "no-such-limb"]) == 2
    assert "unknown limb" in capsys.readouterr().err


def test_limb_names_are_unique_and_every_limb_mirrors_a_ci_step(vl):
    names = [l.name for l in vl.LIMBS]
    assert len(names) == len(set(names))
    assert all(l.ci_steps for l in vl.LIMBS)


def test_version_constant(vl):
    assert re.fullmatch(r"\d+\.\d+\.\d+", vl.__version__)


# Real hash-check limb against a throwaway copy: good copy passes, a tampered
# docs/HASH.txt is refused. This is the limb's own known-answer test.

def _hash_fixture(tmp_path):
    for rel in ("install/install.ps1", "install/install.sh", "docs/HASH.txt",
                "docs/HASH-linux.txt", "scripts/regen-hashes.sh"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, dst)  # byte copy: no eol conversion
    return tmp_path


def test_real_hash_check_limb_passes_good_tree(vl, tmp_path):
    hash_check = next(l for l in vl.LIMBS if l.name == "hash-check")
    code, res = vl.run_limbs([hash_check], vl.Context(_hash_fixture(tmp_path)), out=_silent)
    assert (code, res[0][1]) == (0, vl.PASS), res


def test_real_hash_check_limb_refuses_tampered_hash(vl, tmp_path):
    root = _hash_fixture(tmp_path)
    (root / "docs" / "HASH.txt").write_bytes(b"0" * 64)
    hash_check = next(l for l in vl.LIMBS if l.name == "hash-check")
    code, res = vl.run_limbs([hash_check], vl.Context(root), out=_silent)
    assert (code, res[0][1]) == (1, vl.REFUSED), res
    assert "DRIFT: install.ps1" in res[0][2]


# --------------------------------------------------------------------------
# 3. The opt-in hook
# --------------------------------------------------------------------------

def test_hook_calls_only_verify_local():
    text = HOOK.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "scripts/verify-local.py" in code
    invoked = set(re.findall(r"\b((?:scripts|tests)/[\w./-]+)", code))
    assert invoked == {"scripts/verify-local.py"}, invoked
    assert len(re.findall(r'"\$PY" scripts/verify-local\.py', code)) == 1


def test_hook_files_are_lf_and_pinned_lf():
    for name in ("pre-commit", "pre-push"):
        assert b"\r\n" not in (REPO_ROOT / ".githooks" / name).read_bytes()
    attrs = (REPO_ROOT / ".githooks" / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\s+text eol=lf\s*$", attrs, re.M)


def _bash(vl):
    return vl.Context(REPO_ROOT).bash()


def _hook_repo(tmp_path, stub_exit):
    """A throwaway repo whose scripts/verify-local.py is a stub that records its
    argv and exits with `stub_exit`."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".githooks").mkdir()
    shutil.copyfile(HOOK, repo / ".githooks" / "pre-commit")
    (repo / "scripts" / "verify-local.py").write_text(
        "import sys, pathlib\n"
        "pathlib.Path('argv.txt').write_text(' '.join(sys.argv[1:]))\n"
        f"sys.exit({stub_exit})\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _run_hook(vl, repo, **env):
    e = dict(os.environ)
    e.pop("E156_VERIFY_ALLOW_MISSING", None)
    e.update(env)
    return subprocess.run([_bash(vl), ".githooks/pre-commit"], cwd=str(repo), env=e,
                          capture_output=True, text=True)


def test_hook_passes_when_verify_local_passes(vl, tmp_path):
    repo = _hook_repo(tmp_path, 0)
    p = _run_hook(vl, repo)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (repo / "argv.txt").read_text() == ""


@pytest.mark.parametrize("stub_exit", [1, 2])
def test_hook_refuses_commit_when_verify_local_does_not_pass(vl, tmp_path, stub_exit):
    repo = _hook_repo(tmp_path, stub_exit)
    p = _run_hook(vl, repo)
    assert p.returncode == stub_exit, p.stdout + p.stderr
    assert "REFUSED" in p.stdout


def test_hook_forwards_explicit_allow_missing(vl, tmp_path):
    repo = _hook_repo(tmp_path, 0)
    p = _run_hook(vl, repo, E156_VERIFY_ALLOW_MISSING="shellcheck link-check")
    assert p.returncode == 0, p.stdout + p.stderr
    assert (repo / "argv.txt").read_text() == "--allow-missing shellcheck --allow-missing link-check"


def test_hook_refuses_when_verify_local_is_absent(vl, tmp_path):
    repo = _hook_repo(tmp_path, 0)
    (repo / "scripts" / "verify-local.py").unlink()
    p = _run_hook(vl, repo)
    assert p.returncode != 0
    assert "fail closed" in p.stdout


def test_sentinel_limb_refuses_missing_clone(vl, tmp_path):
    limb = next(x for x in vl.LIMBS if x.name == "sentinel-rule-list-drift")
    with pytest.raises(vl.ToolMissing, match="SENTINEL_REPO"):
        limb.fn(vl.Context(tmp_path, env={}))


def test_sentinel_limb_refuses_wrong_commit(vl, tmp_path):
    root = tmp_path / "Sentinel"
    (root / "sentinel" / "rules").mkdir(parents=True)
    ctx = vl.Context(tmp_path, env={"SENTINEL_REPO": str(root)},
                     which=lambda _: "/usr/bin/git")
    calls = []
    def runner(cmd, timeout=1800):
        calls.append(cmd)
        return 0, "0" * 40 + "\n"
    ctx.run = runner
    verdict, detail = vl.limb_sentinel_rule_list(ctx)
    assert verdict == vl.REFUSED and vl.SENTINEL_PIN in detail
    assert len(calls) == 1  # do not run source-drift check against wrong revision


def test_sentinel_limb_checks_documentation_after_exact_pin(vl, tmp_path):
    root = tmp_path / "Sentinel"
    (root / "sentinel" / "rules").mkdir(parents=True)
    ctx = vl.Context(tmp_path, env={"SENTINEL_REPO": str(root)},
                     which=lambda n: "/usr/bin/" + n)
    calls = []
    def runner(cmd, timeout=1800):
        calls.append(cmd)
        if "rev-parse" in cmd:
            return 0, vl.SENTINEL_PIN + "\n"
        return 1, "FAIL: generated documentation drift"
    ctx.run = runner
    verdict, detail = vl.limb_sentinel_rule_list(ctx)
    assert verdict == vl.REFUSED
    assert "documentation drift" in detail
    assert len(calls) == 2  # exact SHA is necessary, but never sufficient
