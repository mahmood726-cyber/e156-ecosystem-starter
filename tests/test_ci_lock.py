"""Hash-pinned CI dependency lock guard (port S-D from meta-harness).

meta-harness installs its CI deps with
`pip install --require-hashes -r docs/offline/requirements.lock`, so a
compromised or silently-republished PyPI artefact fails the install instead
of running in CI. This repo's python-tests job used to run
`pip install --upgrade pip pytest` -- whatever was latest that minute.

This suite is the gate that keeps it locked: every `pip install` in
.github/workflows/test.yml must be `--require-hashes` against a lock file in
the repo, and every line of that lock must be `name==version` with at least
one `--hash=sha256:<64 hex>`. No bare package names, no ranges, no un-hashed
lines.

House rule (see test_gate_can_fail.py): a check that cannot fail is not a
check. So each rule is exercised both ways -- the real files must pass, and
planted bad copies in tmp_path must be refused.

Stdlib only: PyYAML is deliberately NOT in the lock, so the workflow is
scanned line-wise rather than parsed as YAML.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

PORT_VERSION = "1.0.0"

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"
LOCK = REPO_ROOT / "requirements-ci.lock"

_PIP_INSTALL = re.compile(r"\bpip3?(\.exe)?\s+install\b")
_PINNED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9.+!_-]+$")
_HASH = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")
# pip options that consume the following token as their value.
_VALUE_OPTS = {
    "-r", "--requirement", "-c", "--constraint", "-i", "--index-url",
    "--extra-index-url", "-f", "--find-links", "-t", "--target",
}
_REQ_OPTS = {"-r", "--requirement"}


# --------------------------------------------------------------------------
# The checker
# --------------------------------------------------------------------------

def lock_problems(lock_path: Path) -> list[str]:
    """Return every reason `lock_path` is not a valid hash-pinned lock."""
    if not lock_path.is_file():
        return [f"{lock_path}: lock file does not exist"]
    problems = []
    entries = 0
    for n, raw in enumerate(lock_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        entries += 1
        tokens = line.split()
        spec = tokens[0]
        rest = tokens[1:]
        if rest and rest[0] == ";":  # `name==ver ; marker --hash=...`
            hashes_at = next((i for i, t in enumerate(rest) if t.startswith("--hash")), len(rest))
            rest = rest[hashes_at:]
        if not _PINNED.match(spec):
            problems.append(f"{lock_path.name}:{n}: not pinned with '==': {spec!r}")
        hashes = [t for t in rest if t.startswith("--hash")]
        if not hashes:
            problems.append(f"{lock_path.name}:{n}: no --hash for {spec!r}")
        for h in hashes:
            if not _HASH.match(h):
                problems.append(f"{lock_path.name}:{n}: malformed hash {h!r}")
        for t in rest:
            if not t.startswith("--hash"):
                problems.append(f"{lock_path.name}:{n}: unexpected token {t!r}")
    if entries == 0:
        problems.append(f"{lock_path.name}: lock has no entries")
    return problems


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Drop YAML comment lines and join shell `\\` continuations."""
    out: list[tuple[int, str]] = []
    buf, start = "", 0
    for n, raw in enumerate(text.splitlines(), 1):
        if not buf and raw.lstrip().startswith("#"):
            continue
        if not buf:
            start = n
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        out.append((start, buf + stripped))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def _install_problems(segment: str, where: str, repo_root: Path) -> list[str]:
    try:
        tokens = shlex.split(segment, comments=True)
    except ValueError as exc:
        return [f"{where}: cannot tokenise pip install line ({exc})"]
    idx = next((i for i, t in enumerate(tokens) if t == "install" and i and "pip" in tokens[i - 1]), None)
    if idx is None:
        return [f"{where}: pip install in a form this guard cannot parse"]
    args = tokens[idx + 1:]
    problems = []
    if "--require-hashes" not in args:
        problems.append(f"{where}: pip install without --require-hashes")
    locks, positional = [], []
    i = 0
    while i < len(args):
        a = args[i]
        if a in _VALUE_OPTS:
            if a in _REQ_OPTS and i + 1 < len(args):
                locks.append(args[i + 1])
            i += 2
            continue
        if a.startswith("--requirement="):
            locks.append(a.split("=", 1)[1])
        elif a.startswith("-r") and len(a) > 2:
            locks.append(a[2:])
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    if positional:
        problems.append(f"{where}: installs unlocked package(s) {positional}")
    if not locks:
        problems.append(f"{where}: pip install not against a lock (-r <lock>)")
    for lock in locks:
        problems.extend(f"{where}: {p}" for p in lock_problems(repo_root / lock))
    return problems


def workflow_problems(workflow_path: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    """Return every `pip install` in the workflow that is not hash-locked."""
    problems = []
    for n, line in _logical_lines(workflow_path.read_text(encoding="utf-8")):
        # Commands may be chained; check each piece on its own.
        for segment in re.split(r"&&|\|\||;|\|", line):
            if _PIP_INSTALL.search(segment):
                segment = re.sub(r"^\s*(-\s*)?(run:\s*)?", "", segment)
                problems.extend(_install_problems(segment, f"{workflow_path.name}:{n}", repo_root))
    return problems


# --------------------------------------------------------------------------
# Real files must pass
# --------------------------------------------------------------------------

def test_real_lock_is_hash_pinned():
    assert lock_problems(LOCK) == []


def test_real_workflow_installs_only_from_hashed_lock():
    assert workflow_problems(WORKFLOW) == []


def test_python_tests_job_uses_ci_lock():
    """The python-tests job specifically must install from requirements-ci.lock."""
    text = WORKFLOW.read_text(encoding="utf-8")
    job = text.split("  python-tests:", 1)[1].split("\n  hash-check:", 1)[0]
    assert "python -m pip install --require-hashes -r requirements-ci.lock" in job
    assert "python -m pytest tests/" in job  # the test run itself is unchanged


def test_lock_pins_pytest_and_its_runtime_deps():
    names = {
        line.split("==", 1)[0].lower()
        for line in LOCK.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert {"pytest", "iniconfig", "packaging", "pluggy", "pygments"} <= names


def test_lock_version_matches_port_version():
    m = re.search(r"^# LOCK_VERSION = (\S+)$", LOCK.read_text(encoding="utf-8"), re.M)
    assert m and m.group(1) == PORT_VERSION


# --------------------------------------------------------------------------
# Planted defects must be refused
# --------------------------------------------------------------------------

def _planted_workflow(tmp_path: Path, old: str, new: str) -> Path:
    (tmp_path / "requirements-ci.lock").write_text(LOCK.read_text(encoding="utf-8"), encoding="utf-8")
    text = WORKFLOW.read_text(encoding="utf-8")
    assert old in text
    wf = tmp_path / "test.yml"
    wf.write_text(text.replace(old, new), encoding="utf-8")
    return wf


GOOD_INSTALL = "python -m pip install --require-hashes -r requirements-ci.lock"


def test_good_temp_copy_passes(tmp_path):
    """Control: the untouched copy in tmp_path passes, so failures below are the plant."""
    wf = _planted_workflow(tmp_path, GOOD_INSTALL, GOOD_INSTALL)
    assert workflow_problems(wf, tmp_path) == []


@pytest.mark.parametrize("planted", [
    "python -m pip install --upgrade pip pytest",            # the pre-port line
    "pip install pytest",
    "python -m pip install -r requirements-ci.lock",          # lock, but no --require-hashes
    "python -m pip install --require-hashes pytest==9.1.1",   # hashes flag, no lock
    "python -m pip install --require-hashes -r requirements-ci.lock pytest",  # lock + extra bare pkg
    "python -m pip install --require-hashes -r missing.lock",  # lock that doesn't exist
    "pip install --require-hashes -r requirements-ci.lock && pip3 install requests",
    "python -m pip install \\\n          --upgrade pytest",  # unpinned split over a continuation
])
def test_planted_unpinned_install_is_refused(tmp_path, planted):
    wf = _planted_workflow(tmp_path, GOOD_INSTALL, planted)
    assert workflow_problems(wf, tmp_path), f"planted line was not refused: {planted!r}"


def test_planted_extra_step_is_refused(tmp_path):
    """A new unpinned step added elsewhere in the workflow is caught too."""
    wf = _planted_workflow(
        tmp_path,
        "      - name: Show bash version\n",
        "      - name: Sneaky dep\n        run: pip install shellcheck-py\n"
        "      - name: Show bash version\n",
    )
    problems = workflow_problems(wf, tmp_path)
    assert len(problems) >= 1 and "shellcheck-py" in " ".join(problems)


@pytest.mark.parametrize("bad_line", [
    "pytest>=9 --hash=sha256:" + "a" * 64,               # range, not ==
    "pytest==9.1.1",                                      # no hash
    "pytest==9.1.1 --hash=sha256:deadbeef",               # truncated hash
    "pytest==9.1.1 --hash=md5:" + "a" * 32,              # wrong algorithm
    "pytest",                                             # bare name
])
def test_planted_bad_lock_line_is_refused(tmp_path, bad_line):
    lock = tmp_path / "requirements-ci.lock"
    lock.write_text(LOCK.read_text(encoding="utf-8") + bad_line + "\n", encoding="utf-8")
    assert lock_problems(lock), f"bad lock line was not refused: {bad_line!r}"
    wf = _planted_workflow(tmp_path, GOOD_INSTALL, GOOD_INSTALL)
    lock.write_text(LOCK.read_text(encoding="utf-8") + bad_line + "\n", encoding="utf-8")
    assert workflow_problems(wf, tmp_path)


def test_empty_lock_is_refused(tmp_path):
    lock = tmp_path / "empty.lock"
    lock.write_text("# only comments\n", encoding="utf-8")
    assert lock_problems(lock)
