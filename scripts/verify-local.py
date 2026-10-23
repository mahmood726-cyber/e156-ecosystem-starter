#!/usr/bin/env python3
"""verify-local.py -- ONE STANDARD: run, locally, every check CI runs.

WHAT IT IS. A ledger runner. Each check that .github/workflows/test.yml runs and
that CAN run on a laptop is a named LIMB here: pytest, the two bash suites,
the HASH check, i18n parity, the Pester suites, ShellCheck, PSScriptAnalyzer and
the lychee link check. Every limb runs (no early exit), so one run names every
refusal, and the ledger prints one verdict per limb:

    PASS               the limb ran and its check passed
    REFUSED            the limb ran and its check failed
    COULD-NOT-EXECUTE  the limb could not run (tool or module missing, crash)
    NOT RUN            the tool was missing AND you said so: --allow-missing <limb>

WHY IT EXISTS. Ported from the meta-harness `scripts/verify_all.py` (v1 of the
"one standard" rule). There, the local hook and CI had silently disagreed: the
hook ran no unit tests, CI ran no index check, and a hand-edited served page
passed CI. The fix was one script that both run. Here CI is the authority and
this script mirrors it; tests/test_verify_local.py parses test.yml and FAILS if
any CI step has no limb here (or is not listed in CI_ONLY_STEPS with a reason),
so local and CI cannot drift without a red test.

FAIL-CLOSED. A limb that cannot execute is a refusal, not a skip. A missing
`shellcheck` is COULD-NOT-EXECUTE (exit 2), never a quiet green. If you know a
tool is missing and accept that, say so per limb with `--allow-missing <limb>`;
the ledger then prints that limb as NOT RUN, so the gap stays visible. The
excuse only applies when the tool really is missing: if it is present the limb
runs, and a failing limb is REFUSED whatever you pass.

EXIT CODES.
    0  every limb ran and passed (limbs you excused with --allow-missing are
       printed as NOT RUN and do not count against you -- you named them)
    1  at least one limb REFUSED
    2  no limb refused, but at least one COULD-NOT-EXECUTE; or a usage error

OPT-IN PRE-COMMIT HOOK. Nothing runs this for you. To run it before every
commit in your clone:

    git config core.hooksPath .githooks

.githooks/pre-commit calls only this script. See docs/VERIFY-LOCAL.md.

WHAT IT DOES NOT CHECK, named rather than implied.
  - It runs against the WORKING TREE, as CI runs against the pushed tree. With
    partially staged changes the two can differ; CI is the authority.
  - It never installs anything. CI installs ShellCheck (apt) and
    PSScriptAnalyzer (Install-Module); here a missing tool is COULD-NOT-EXECUTE.
  - Same tool, different host: CI runs Pester on windows-latest pwsh and the
    bash suites on Ubuntu. A local pass on another OS is strong evidence, not
    proof. lychee needs network, as it does in CI.
  - The sentinel-rule-list-drift job is `if: false` in CI (it needs a Sentinel
    clone), so it is not a limb; the parity test fails if CI ever enables it.

USAGE
    python scripts/verify-local.py
    python scripts/verify-local.py --allow-missing shellcheck --allow-missing link-check
    python scripts/verify-local.py --list
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

__version__ = "1.0.0"

PASS, REFUSED, NOEXEC, NOT_RUN = "PASS", "REFUSED", "COULD-NOT-EXECUTE", "NOT RUN"

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"

# The exact file lists CI uses. tests/test_verify_local.py asserts these equal
# the lists in test.yml, so editing one without the other is a red test.
PESTER_FILES = (
    "install\\pester.tests.ps1",
    "bootstrap\\pester.bat.tests.ps1",
    "scripts\\pester.doctor-report.tests.ps1",
    "scripts\\pester.install-sentinel.tests.ps1",
    "scripts\\pester.install-extractor.tests.ps1",
    "scripts\\pester.phase3.tests.ps1",
    "scripts\\pester.phase4.tests.ps1",
    "scripts\\pester.update.tests.ps1",
    "scripts\\pester.handoff-locale.tests.ps1",
    "scripts\\pester.install-long-term-plan.tests.ps1",
    "scripts\\pester.install-meta-harness.tests.ps1",
)
SHELLCHECK_FILES = (
    "install/install.sh",
    "scripts/install-sentinel.sh",
    "scripts/install-extractor.sh",
    "scripts/install-overmind.sh",
    "scripts/install-projectindex.sh",
    "scripts/install-long-term-plan.sh",
    "scripts/install-meta-harness.sh",
    "bootstrap/e156-setup.sh",
    "docs/e156-setup.sh",
)
SHELLCHECK_FLAGS = ("--severity=error", "--shell=bash")
PSSA_DIRS = ("install", "scripts", "bootstrap", "docs")
PSSA_EXCLUDE = ("PSAvoidUsingWriteHost", "PSUseShouldProcessForStateChangingFunctions")
LYCHEE_ARGS = ("--no-progress", "--include-fragments", "--accept", "200,206,403,429", "docs/**/*.html")

# CI steps that are environment set-up or diagnostics on a fresh runner, not
# checks. Each needs a reason; the parity test refuses an entry without one.
CI_ONLY_STEPS = {
    ("*", "uses:actions/checkout"): "runner set-up: the local tree is already checked out",
    ("pester", "Show PowerShell + Pester versions"): "diagnostic print only; the pester limb names the shell it used",
    ("pester", "uses:actions/upload-artifact"): "uploads pester-results.xml to the CI run page; nothing to check locally",
    ("bash-tests", "Show bash version"): "diagnostic print only; checks nothing",
    ("python-tests", "uses:actions/setup-python"): "runner set-up: provides Python 3.11; locally you run this with your own Python",
    ("python-tests", "Install pytest"): "runner set-up (pip install); verify-local never installs, a missing pytest is COULD-NOT-EXECUTE",
    ("meta-harness-unpack-windows", "uses:actions/setup-python"): "Windows runner set-up; locally the installed Python is used",
    ("meta-harness-unpack-windows", "Install locked test dependencies"): "Windows runner set-up using requirements-ci.lock; local pytest limb checks importability",
}
# Whole CI jobs with no limb. Only allowed while the job is disabled in CI
# (`if: false`); the parity test refuses the entry the moment CI enables it.
CI_ONLY_JOBS = {
    "sentinel-rule-list-drift": "`if: false` in CI (needs a Sentinel clone); run "
                                "`bash scripts/regen-sentinel-rule-list.sh --check` with SENTINEL_REPO set",
}


class ToolMissing(Exception):
    """A tool or module a limb needs is not available: COULD-NOT-EXECUTE."""


@dataclass
class Context:
    root: Path
    which: Callable[[str], str | None] = shutil.which
    env: dict = field(default_factory=lambda: dict(os.environ))

    def run(self, cmd, timeout=1800):
        p = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=self.env, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def need(self, *names):
        """First of `names` on PATH, else ToolMissing."""
        for n in names:
            hit = self.which(n)
            if hit:
                return hit
        raise ToolMissing(f"none of {', '.join(names)} found on PATH")

    def bash(self):
        override = self.env.get("E156_BASH")
        if override:
            if not Path(override).is_file():
                raise ToolMissing(f"E156_BASH={override} does not exist")
            return override
        hit = self.need("bash")
        # On Windows, C:\Windows\System32\bash.exe is the WSL launcher, not Git
        # Bash: it runs in a different filesystem. Prefer Git for Windows' bash.
        if os.name == "nt" and "system32" in hit.lower():
            git = self.which("git")
            if git:
                for cand in (Path(git).parents[1] / "bin" / "bash.exe", Path(git).parents[1] / "usr" / "bin" / "bash.exe"):
                    if cand.is_file():
                        return str(cand)
            raise ToolMissing(f"only the WSL launcher ({hit}) found; install Git for Windows or set E156_BASH")
        return hit

    def powershell(self):
        # CI uses pwsh (7.x). Windows PowerShell 5.1 is accepted as a fallback.
        return self.need("pwsh", "powershell")


def _tail(out, n=25):
    lines = out.strip().splitlines()
    named = [ln[:300] for ln in lines if ln.startswith(("FAILED ", "ERROR "))]
    return "\n".join(named + lines[-1:]) if named else "\n".join(lines[-n:])


def _ps(ctx, script):
    return [ctx.powershell(), "-NoProfile", "-NonInteractive", "-Command", script]


def _require_module(ctx, module, min_major=0):
    probe = (f"$m = Get-Module -ListAvailable {module} | Where-Object {{ $_.Version.Major -ge {min_major} }}; "
             "if ($m) { exit 0 } else { exit 3 }")
    rc, _ = ctx.run(_ps(ctx, probe), timeout=120)
    if rc != 0:
        need = f"{module} >= {min_major}" if min_major else module
        raise ToolMissing(f"PowerShell module {need} not installed "
                          f"(Install-Module {module} -Scope CurrentUser -Force -SkipPublisherCheck)")


def _verdict(rc, out, n=25):
    return (PASS if rc == 0 else REFUSED), _tail(out, n)


def limb_pytest(ctx):
    rc, out = ctx.run([sys.executable, "-c", "import pytest"], timeout=60)
    if rc != 0:
        raise ToolMissing("pytest not importable by this Python (python -m pip install pytest)")
    return _verdict(*ctx.run([sys.executable, "-m", "pytest", "tests/", "-q"]))


def limb_bash_install_sh(ctx):
    return _verdict(*ctx.run([ctx.bash(), "tests/test-install-sh.bash"]))


def limb_bash_handoff_locale(ctx):
    return _verdict(*ctx.run([ctx.bash(), "tests/test-handoff-locale.bash"]))


def limb_hash_check(ctx):
    return _verdict(*ctx.run([ctx.bash(), "scripts/regen-hashes.sh", "--check"]))


def limb_i18n_parity(ctx):
    return _verdict(*ctx.run([ctx.bash(), "scripts/check-i18n-parity.sh"]))


def limb_pester(ctx):
    _require_module(ctx, "Pester", min_major=5)
    files = ",".join(f"'{f}'" for f in PESTER_FILES)
    script = ("Import-Module Pester -MinimumVersion 5.0; "
              "$config = New-PesterConfiguration; "
              f"$config.Run.Path = @({files}); "
              "$config.Run.Exit = $true; "
              "$config.Output.Verbosity = 'Normal'; "
              "Invoke-Pester -Configuration $config")
    return _verdict(*ctx.run(_ps(ctx, script)), n=30)


def limb_shellcheck(ctx):
    exe = ctx.need("shellcheck")
    return _verdict(*ctx.run([exe, *SHELLCHECK_FLAGS, *SHELLCHECK_FILES]), n=40)


def limb_psscriptanalyzer(ctx):
    _require_module(ctx, "PSScriptAnalyzer")
    dirs = ",".join(f"'{d}'" for d in PSSA_DIRS)
    excl = ",".join(PSSA_EXCLUDE)
    script = ("Import-Module PSScriptAnalyzer; $allIssues = @(); "
              f"foreach ($d in {dirs}) {{ if (Test-Path $d) {{ "
              f"$allIssues += Invoke-ScriptAnalyzer -Path $d -Recurse -Severity Error -ExcludeRule {excl} }} }}; "
              "if ($allIssues.Count -gt 0) { $allIssues | Format-Table -AutoSize | Out-String -Width 200; "
              "Write-Output \"PSScriptAnalyzer found $($allIssues.Count) error-level issue(s).\"; exit 1 }; "
              "Write-Output 'PSScriptAnalyzer: clean.'")
    return _verdict(*ctx.run(_ps(ctx, script)), n=40)


def limb_link_check(ctx):
    exe = ctx.need("lychee")
    return _verdict(*ctx.run([exe, *LYCHEE_ARGS]), n=40)


@dataclass(frozen=True)
class Limb:
    name: str
    description: str
    ci_steps: tuple          # (job id, step key) pairs in test.yml this limb mirrors
    fn: Callable


LIMBS = (
    Limb("pytest", "pytest tests/",
         (("python-tests", "Run pytest"),
          ("meta-harness-unpack-windows", "Run actual Bash installer and negative release cases")),
         limb_pytest),
    Limb("bash-install-sh", "bash tests/test-install-sh.bash", (("bash-tests", "Run bash test suite"),), limb_bash_install_sh),
    Limb("bash-handoff-locale", "bash tests/test-handoff-locale.bash",
         (("bash-tests", "Run handoff-locale bash tests"),), limb_bash_handoff_locale),
    Limb("hash-check", "regen-hashes.sh --check (docs/HASH*.txt match install scripts)",
         (("hash-check", "Verify docs/HASH.txt + docs/HASH-linux.txt"),), limb_hash_check),
    Limb("i18n-parity", "check-i18n-parity.sh (<details> parity en/fr/pt/ar/ur)",
         (("i18n-parity", "Verify <details> count parity across en/fr/pt/ar/ur"),), limb_i18n_parity),
    Limb("pester", "Pester 5 suites (same file list as CI)", (("pester", "Run Pester suites"),), limb_pester),
    Limb("shellcheck", "ShellCheck --severity=error on shipped .sh files", (("lint", "ShellCheck"),), limb_shellcheck),
    Limb("psscriptanalyzer", "PSScriptAnalyzer error-level on .ps1", (("lint", "PSScriptAnalyzer"),), limb_psscriptanalyzer),
    Limb("link-check", "lychee --include-fragments on docs/**/*.html", (("link-check", "Lychee link checker"),), limb_link_check),
)


def run_limbs(limbs, ctx, allow_missing=(), out=print):
    """Run every limb; print the ledger; return (exit code, [(name, verdict, detail)])."""
    allow = set(allow_missing)
    out(f"VERIFY-LOCAL v{__version__}: {len(limbs)} limbs, all run, fail-closed. root={ctx.root}")
    results = []
    for limb in limbs:
        t0 = time.time()
        try:
            verdict, detail = limb.fn(ctx)
        except ToolMissing as exc:
            if limb.name in allow:
                verdict, detail = NOT_RUN, f"{exc} -- excused by --allow-missing {limb.name}"
            else:
                verdict, detail = NOEXEC, f"{exc} (pass --allow-missing {limb.name} to accept this explicitly)"
        except Exception as exc:  # a limb that blows up has no verdict -> refusal to certify
            verdict, detail = NOEXEC, f"{type(exc).__name__}: {exc}"
        results.append((limb.name, verdict, detail))
        out(f"  [{verdict:>17}] {limb.name}: {limb.description}  ({time.time() - t0:.0f}s)")
        if verdict != PASS:
            for line in str(detail).splitlines():
                out(f"        {line}")
    n_ref = sum(1 for _, v, _ in results if v == REFUSED)
    n_noexec = sum(1 for _, v, _ in results if v == NOEXEC)
    not_run = [n for n, v, _ in results if v == NOT_RUN]
    if n_ref:
        out(f"VERIFY-LOCAL: REFUSED -- {n_ref} of {len(limbs)} limbs failed"
            + (f", {n_noexec} could not execute" if n_noexec else "") + ". Fix the code, never the gate.")
        return 1, results
    if n_noexec:
        out(f"VERIFY-LOCAL: COULD-NOT-EXECUTE -- {n_noexec} of {len(limbs)} limbs could not run. "
            "Install the tool, or name it with --allow-missing <limb>.")
        return 2, results
    if not_run:
        out(f"VERIFY-LOCAL: PASS on {len(limbs) - len(not_run)} of {len(limbs)} limbs; "
            f"NOT RUN (excused by you): {', '.join(not_run)}. CI still runs them.")
        return 0, results
    out(f"VERIFY-LOCAL: all {len(limbs)} limbs PASS.")
    return 0, results


# --------------------------------------------------------------------------
# Parity with .github/workflows/test.yml (used by tests/test_verify_local.py)
# --------------------------------------------------------------------------

def parse_workflow(text):
    """Minimal, stdlib-only reader for the shape of test.yml (CI installs only
    pytest, so no PyYAML). Returns {job_id: {"if": str|None, "steps": [{"key",
    "text"}]}}. A step's key is its `name:`, else `uses:<action without @ref>`."""
    jobs, job, in_jobs, in_steps, step_lines, step_indent = {}, None, False, False, None, None

    def close_step():
        nonlocal step_lines
        if job is not None and step_lines:
            body = "\n".join(step_lines)
            # step-level keys only (`- name:` or name: at the step's own indent),
            # never a `name:` nested under `with:`
            lead = r"^(?:%s- |%s  )" % (" " * step_indent, " " * step_indent)
            m = re.search(lead + r"name:\s*(.+?)\s*$", body, re.M)
            if m:
                key = m.group(1).strip().strip("'\"")
            else:
                u = re.search(lead + r"uses:\s*([^@\s]+)", body, re.M)
                key = "uses:" + (u.group(1) if u else "?")
            jobs[job]["steps"].append({"key": key, "text": body})
        step_lines = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" ") and not line.startswith("#"):
            close_step()
            in_jobs = False
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            close_step()
            job, in_steps, step_indent = m.group(1), False, None
            jobs[job] = {"if": None, "steps": []}
            continue
        if job is None:
            continue
        indent = len(line) - len(line.lstrip())
        if line.strip() and not line.lstrip().startswith("#") and indent == 4:
            close_step()  # a job-level key ends any steps list
            in_steps = bool(re.match(r"^    steps:\s*$", line))
            step_indent = None
            m = re.match(r"^    if:\s*(.+?)\s*$", line)
            if m:
                jobs[job]["if"] = m.group(1)
            continue
        m = re.match(r"^(\s*)- ", line)
        if in_steps and m and (step_indent is None or len(m.group(1)) == step_indent):
            close_step()
            step_indent = len(m.group(1))
            step_lines = [line]
            continue
        if step_lines is not None:
            step_lines.append(line)
    close_step()
    return jobs


def find_drift(workflow_text, limbs=LIMBS, ci_only_steps=None, ci_only_jobs=None):
    """Every way local and CI can disagree, as a list of human-readable problems.
    Empty list == in parity."""
    ci_only_steps = CI_ONLY_STEPS if ci_only_steps is None else ci_only_steps
    ci_only_jobs = CI_ONLY_JOBS if ci_only_jobs is None else ci_only_jobs
    jobs = parse_workflow(workflow_text)
    problems = []
    if not jobs:
        return ["no jobs parsed from the workflow -- a parity check over nothing is a refusal, not a pass"]

    mapped = {}
    for limb in limbs:
        for js in limb.ci_steps:
            mapped[js] = limb.name
    for (j, s), why in ci_only_steps.items():
        if not str(why).strip():
            problems.append(f"CI_ONLY_STEPS[{j!r}, {s!r}] has no reason")
    for j, why in ci_only_jobs.items():
        if not str(why).strip():
            problems.append(f"CI_ONLY_JOBS[{j!r}] has no reason")

    seen = set()
    for job_id, job in jobs.items():
        if job_id in ci_only_jobs:
            cond = (job["if"] or "").strip()
            if cond not in ("false", "${{ false }}"):
                problems.append(f"job {job_id!r} is listed CI-only because it is disabled in CI, "
                                f"but its `if:` is now {cond or '(none)'} -- add a limb for it")
            continue
        limb_hits = 0
        for step in job["steps"]:
            key = (job_id, step["key"])
            seen.add(key)
            if key in mapped:
                limb_hits += 1
            elif key in ci_only_steps or ("*", step["key"]) in ci_only_steps:
                pass
            else:
                problems.append(f"CI step {job_id} / {step['key']!r} has no verify-local limb "
                                "and is not in CI_ONLY_STEPS with a reason")
        if limb_hits == 0:
            problems.append(f"CI job {job_id!r} has no step mirrored by any verify-local limb")
    for j in ci_only_jobs:
        if j not in jobs:
            problems.append(f"CI_ONLY_JOBS names {j!r}, which is not a job in the workflow (stale entry)")
    for key, name in mapped.items():
        if key not in seen:
            problems.append(f"limb {name!r} claims CI step {key[0]} / {key[1]!r}, which no longer exists")
    for key in ci_only_steps:
        if key[0] != "*" and key not in seen:
            problems.append(f"CI_ONLY_STEPS names {key[0]} / {key[1]!r}, which no longer exists (stale entry)")

    # Same arguments, not just same step names.
    def step_text(job_id, key):
        for s in jobs.get(job_id, {}).get("steps", []):
            if s["key"] == key:
                return s["text"]
        return None

    def compare(label, local, ci):
        if ci is None:
            return
        if tuple(local) != tuple(ci):
            problems.append(f"{label} differ: verify-local={list(local)} CI={list(ci)}")

    t = step_text("pester", "Run Pester suites")
    if t is not None:
        m = re.search(r"\$files\s*=\s*@\((.*?)\)", t, re.S)
        compare("Pester file lists", PESTER_FILES, re.findall(r"'([^']+)'", m.group(1)) if m else [])
    t = step_text("lint", "ShellCheck")
    if t is not None:
        joined = re.sub(r"\\\s*\n\s*", " ", t)
        m = re.search(r"^\s*shellcheck\s+(.+)$", joined, re.M)
        toks = m.group(1).split() if m else []
        compare("ShellCheck flags", SHELLCHECK_FLAGS, [x for x in toks if x.startswith("-")])
        compare("ShellCheck file lists", SHELLCHECK_FILES, [x for x in toks if not x.startswith("-")])
    t = step_text("lint", "PSScriptAnalyzer")
    if t is not None:
        m = re.search(r"foreach\s*\(\$d in ([^)]*)\)", t)
        compare("PSScriptAnalyzer dirs", PSSA_DIRS, re.findall(r"'([^']+)'", m.group(1)) if m else [])
        m = re.search(r"-ExcludeRule\s+(\S+)", t)
        compare("PSScriptAnalyzer excluded rules", PSSA_EXCLUDE, m.group(1).split(",") if m else [])
        if "-Severity Error" not in t:
            problems.append("PSScriptAnalyzer CI step no longer uses -Severity Error; update the limb")
    t = step_text("link-check", "Lychee link checker")
    if t is not None:
        m = re.search(r"args:\s*>-?\s*\n(.*?)\n\s*fail:", t, re.S)
        ci_args = [a.strip("'\"") for a in m.group(1).split()] if m else []
        compare("lychee args", LYCHEE_ARGS, [a for a in ci_args if not a.startswith("#")])
    for job_id, key, needle in (("python-tests", "Run pytest", "pytest tests/"),
                                ("bash-tests", "Run bash test suite", "bash tests/test-install-sh.bash"),
                                ("bash-tests", "Run handoff-locale bash tests", "bash tests/test-handoff-locale.bash"),
                                ("hash-check", "Verify docs/HASH.txt + docs/HASH-linux.txt", "bash scripts/regen-hashes.sh --check"),
                                ("i18n-parity", "Verify <details> count parity across en/fr/pt/ar/ur", "bash scripts/check-i18n-parity.sh")):
        t = step_text(job_id, key)
        if t is not None and needle not in t:
            problems.append(f"CI step {job_id} / {key!r} no longer runs `{needle}`; update the limb")
    return problems


def main(argv=None, limbs=LIMBS, ctx=None):
    names = [l.name for l in limbs]
    ap = argparse.ArgumentParser(description="Run every CI check that can run locally (fail-closed).")
    ap.add_argument("--allow-missing", action="append", default=[], metavar="LIMB",
                    help="accept that LIMB's tool is missing; printed as NOT RUN. Repeatable. "
                         "Has no effect if the tool is present.")
    ap.add_argument("--list", action="store_true", help="list the limbs and the CI steps they mirror")
    ap.add_argument("--version", action="version", version=f"verify-local {__version__}")
    args = ap.parse_args(argv)
    unknown = [a for a in args.allow_missing if a not in names]
    if unknown:
        print(f"VERIFY-LOCAL: unknown limb(s) for --allow-missing: {', '.join(unknown)}. "
              f"Known: {', '.join(names)}", file=sys.stderr)
        return 2
    if args.list:
        for l in limbs:
            print(f"{l.name:20} {l.description}  <- CI " + "; ".join(f"{j} / {s}" for j, s in l.ci_steps))
        return 0
    code, _ = run_limbs(limbs, ctx or Context(REPO_ROOT), args.allow_missing)
    return code


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
