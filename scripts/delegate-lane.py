#!/usr/bin/env python3
"""delegate-lane.py -- OPT-IN: hand one task to a second agent CLI (Codex or
Antigravity) in its OWN isolated clone, non-interactively, and record where to
look for the result.

WHAT IT DOES, in order. Any refusal happens BEFORE anything is created.
  1. Refuses a lane name whose clone directory already exists. Two agents on one
     working tree overwrite each other's files; a lane is never reused.
  2. Refuses to start with less than --min-free-gb free (default 3 GB) on the
     disk that will hold the clone. Several clones that fill a disk kill every
     lane at once.
  3. Refuses a brief that still has a <FILL: marker, or that lacks the verbatim
     anti-hard-coding + abort block from templates/LANE-BRIEF.md.
  4. Clones the repo (git clone --shared: no object copy) and checks out --base
     DETACHED. The push URL is set to a dead value.
  5. Writes LANE_BRIEF.md into the clone ({LANE}, {BASE}, {VENDOR} substituted).
  6. Installs a lane-local pre-commit hook that refuses every commit. The hook
     lives in the CLONE's .git/hooks, so your own repo's hooks are untouched.
  7. Launches `codex exec` or `agy --print` in the background with stdin CLOSED
     (a CLI left reading stdin can sit there forever, or exit having done
     nothing), output to .lane/lane.log, and records pid + paths in
     .lane/lane.json.

HOW TO KNOW IF THE LANE WORKED. Not from this script's exit code and not from
the lane's: run scripts/lane-status.py. A lane is done when LANE_REPORT.json
exists in the clone and parses -- never because a process exited 0.

WHY A CLONE AND NOT `git worktree add`. A worktree shares .git/hooks and config
with your repo, so the commit-refusing hook would land in YOUR repo too. A
--shared clone has its own hooks and config and costs no object copy.

WHAT IT DOES NOT DO, named rather than implied.
  - A lane can still bypass the hook with `git commit --no-verify`. The hook is
    a seatbelt; the brief's rules and your review of the diff are the gate.
  - It does not judge the lane's work. Review the diff (cross-vendor-review.py
    can help) before you land anything.
  - It does not delete clones. Remove a lane's directory yourself when done.

OPT-IN. Nothing in the starter calls this. You run it by hand:

    python scripts/delegate-lane.py --task fix-parser --brief my-brief.md --vendor codex
    python scripts/lane-status.py --lanes-dir ../<repo>-lanes

Lanes go to --lanes-dir, else $E156_LANES_DIR, else <repo>/../<repo-name>-lanes.

EXIT CODES
    0   launched (NOT "succeeded": see lane-status.py)
    2   refused: lane directory exists / bad lane name
    3   refused: not enough free disk
    4   refused: vendor CLI not found on PATH
    5   refused: brief incomplete or missing the verbatim rules block
    6   git failed while preparing the clone

Standard library only. No model call is made by this script itself.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.0"

EXIT_OK, EXIT_EXISTS, EXIT_DISK, EXIT_NO_VENDOR, EXIT_BRIEF, EXIT_GIT = 0, 2, 3, 4, 5, 6

DEFAULT_MIN_FREE_GB = 3.0
LANE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
STATE_DIR = ".lane"            # inside the clone; excluded from git status
BRIEF_NAME = "LANE_BRIEF.md"
REPORT_NAME = "LANE_REPORT.json"

# Must appear word for word in every brief. templates/LANE-BRIEF.md carries the
# same block; tests/test_delegate_lane.py fails if the two drift apart.
RULES_BLOCK = """<!-- lane-rules:begin -->
- Never hard-code an expected value, a test answer, a fixture row or a special case for a named input to make a check pass. Fix the cause or report that you could not.
- Never delete, skip, xfail, weaken or re-scope an existing test, check, hook or tolerance.
- ABORT RULE: if the only way to make an acceptance command pass is to break a rule above, STOP. Write the report with status BLOCKED and say what you would have had to loosen and why.
- Do not commit, push or open a pull request. Leave every change uncommitted; the integrator lands it.
- A command's exit code is not evidence. Evidence is an artefact you can name: a test count, a file, a line of output.
<!-- lane-rules:end -->"""

LANE_PROMPT = (f"Read {BRIEF_NAME} in the current directory and do exactly what it says. "
               f"Your finish condition is writing {REPORT_NAME} as it specifies. Do not commit.")

PRE_COMMIT_HOOK = """#!/bin/sh
# Installed by delegate-lane.py: this clone is a delegated lane. Lanes never commit.
echo "REFUSED: this clone is a delegated lane (delegate-lane.py). Lanes never commit;" >&2
echo "leave your changes uncommitted and write LANE_REPORT.json. The integrator lands the work." >&2
exit 1
"""

VENDORS = ("codex", "agy")


def _utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def vendor_argv(vendor: str, exe: str) -> list[str]:
    if vendor == "codex":
        return [exe, "exec", "-s", "workspace-write", "--skip-git-repo-check", LANE_PROMPT]
    if vendor == "agy":
        return [exe, "--print", LANE_PROMPT]
    raise ValueError(f"unknown vendor {vendor!r}")


def free_bytes(path: Path) -> int:
    """Free bytes on the disk that holds `path` (or its nearest existing parent)."""
    p = path
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free


def check_brief(text: str) -> list[str]:
    """Problems with a brief; empty list means acceptable."""
    problems = []
    if "<FILL:" in text:
        problems.append("brief still contains <FILL: ...> markers -- fill every section")
    if RULES_BLOCK not in text.replace("\r\n", "\n"):
        problems.append("brief lacks the verbatim lane-rules block (anti-hard-coding + abort rule) "
                        "from templates/LANE-BRIEF.md")
    if REPORT_NAME not in text:
        problems.append(f"brief never names the report artefact {REPORT_NAME}")
    return problems


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)


def _repo_root(start: Path) -> Path | None:
    r = _git("rev-parse", "--show-toplevel", cwd=start)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def default_lanes_dir(repo: Path) -> Path:
    env = os.environ.get("E156_LANES_DIR")
    if env:
        return Path(env)
    return repo.parent / f"{repo.name}-lanes"


def _refuse(code: int, msg: str) -> int:
    print(f"REFUSED: {msg}", file=sys.stderr)
    return code


def launch(task: str, brief_path: Path, vendor: str, repo: Path, base: str, lanes_dir: Path,
           min_free_gb: float = DEFAULT_MIN_FREE_GB, free_bytes_override: int | None = None) -> int:
    if not LANE_NAME_RE.match(task):
        return _refuse(EXIT_EXISTS, f"lane name {task!r} must match {LANE_NAME_RE.pattern}")
    clone = lanes_dir / task
    if clone.exists():
        return _refuse(EXIT_EXISTS, f"{clone} exists -- a lane is never reused; pick a new --task name "
                                    "or inspect and remove the old clone yourself")
    free = free_bytes_override if free_bytes_override is not None else free_bytes(lanes_dir)
    need = int(min_free_gb * 1024 ** 3)
    if free < need:
        return _refuse(EXIT_DISK, f"{free // 1024 ** 2} MB free under {lanes_dir} "
                                  f"(< {min_free_gb:g} GB); not launching {task}")
    exe = shutil.which(vendor)
    if not exe:
        return _refuse(EXIT_NO_VENDOR, f"`{vendor}` not found on PATH")
    try:
        brief_text = brief_path.read_text(encoding="utf-8")
    except OSError as e:
        return _refuse(EXIT_BRIEF, f"cannot read brief {brief_path}: {e}")
    problems = check_brief(brief_text)
    if problems:
        return _refuse(EXIT_BRIEF, "; ".join(problems))
    base_r = _git("rev-parse", "--verify", f"{base}^{{commit}}", cwd=repo)
    if base_r.returncode != 0:
        return _refuse(EXIT_GIT, f"base {base!r} is not a commit in {repo}: {base_r.stderr.strip()}")
    base_sha = base_r.stdout.strip()

    lanes_dir.mkdir(parents=True, exist_ok=True)
    r = _git("clone", "-q", "--shared", "--no-checkout", str(repo), str(clone))
    if r.returncode != 0:
        return _refuse(EXIT_GIT, f"git clone failed: {r.stderr.strip()}")
    for step in (("checkout", "-q", "--detach", base_sha),
                 ("remote", "set-url", "--push", "origin", "REFUSED-lanes-never-push"),
                 ("config", "core.hooksPath", ".git/hooks")):
        r = _git(*step, cwd=clone)
        if r.returncode != 0:
            return _refuse(EXIT_GIT, f"git {step[0]} failed in {clone}: {r.stderr.strip()}")

    git_dir = clone / ".git"
    hook = git_dir / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_bytes(PRE_COMMIT_HOOK.encode("utf-8"))
    hook.chmod(0o755)
    exclude = git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n# delegate-lane.py\n/{STATE_DIR}/\n/{BRIEF_NAME}\n/{REPORT_NAME}\n")

    rendered = (brief_text.replace("{LANE}", task).replace("{BASE}", base_sha)
                .replace("{VENDOR}", vendor))
    (clone / BRIEF_NAME).write_bytes(rendered.encode("utf-8"))

    state = clone / STATE_DIR
    tmp = state / "tmp"
    tmp.mkdir(parents=True)
    log_path = state / "lane.log"
    argv = vendor_argv(vendor, exe)
    env = dict(os.environ, TMP=str(tmp), TEMP=str(tmp), TMPDIR=str(tmp))
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True
    with log_path.open("wb") as log:
        proc = subprocess.Popen(argv, cwd=clone, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, env=env, **kwargs)
    record = {
        "tool": "delegate-lane.py", "version": VERSION, "lane": task, "vendor": vendor,
        "argv": argv, "pid": proc.pid, "clone": str(clone), "base": base_sha,
        "log": str(log_path), "report": str(clone / REPORT_NAME), "brief": str(clone / BRIEF_NAME),
        "brief_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "launched_utc": _utc(),
    }
    (state / "lane.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    (state / "lane.pid").write_text(f"{proc.pid}\n", encoding="utf-8")
    print(f"LANE {task} launched: vendor={vendor} pid={proc.pid} base={base_sha[:12]} "
          f"clone={clone} log={log_path}")
    print(f"Judge it with: python scripts/lane-status.py {clone}  (never by an exit code)")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, help="lane name; becomes the clone directory name")
    ap.add_argument("--brief", required=True, type=Path, help="filled-in copy of templates/LANE-BRIEF.md")
    ap.add_argument("--vendor", required=True, choices=VENDORS)
    ap.add_argument("--base", default="HEAD", help="commit the lane starts from (default HEAD)")
    ap.add_argument("--repo", type=Path, default=None, help="repo to clone (default: the one you are in)")
    ap.add_argument("--lanes-dir", type=Path, default=None)
    ap.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    # Test hook: pretend the disk has this many free bytes. Hidden from --help.
    ap.add_argument("--free-bytes-override", type=int, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    a = ap.parse_args(argv)
    if shutil.which("git") is None:
        return _refuse(EXIT_GIT, "`git` not found on PATH")
    repo = _repo_root(a.repo or Path.cwd())
    if repo is None:
        return _refuse(EXIT_GIT, f"{a.repo or Path.cwd()} is not inside a git repository")
    lanes_dir = a.lanes_dir or default_lanes_dir(repo)
    return launch(a.task, a.brief, a.vendor, repo, a.base, lanes_dir,
                  min_free_gb=a.min_free_gb, free_bytes_override=a.free_bytes_override)


if __name__ == "__main__":
    sys.exit(main())
