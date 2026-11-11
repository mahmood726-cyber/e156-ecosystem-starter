"""Shared fail-closed source checkout boundary for research components."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys

if __package__:
    from .component_lock import SHA
else:
    from component_lock import SHA

class InstallRefused(ValueError):
    """A source or execution contract was not satisfied."""


def run(command, *, cwd=None, timeout=90):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    except FileNotFoundError as exc:
        raise InstallRefused("required executable unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise InstallRefused("component command timed out") from exc
    if result.returncode:
        # Native stderr can contain credential-bearing origins. Report the
        # failed operation without copying its arguments or remote response.
        raise InstallRefused(f"component command failed (exit {result.returncode})")
    return result.stdout.strip()


def git(target, *args):
    return run(["git", "-C", str(target), *args])


def linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) &
                                     getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def clean(target):
    hidden = git(target, "ls-files", "-v").splitlines()
    if any(line and (line[0].islower() or line[0] == "S") for line in hidden):
        raise InstallRefused("dirty-check suppression flags (assume-unchanged/skip-worktree) refused")
    if git(target, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise InstallRefused("dirty checkout (including untracked or ignored files); use a clean target")


def existing_repository(target, repository):
    if not (target / ".git").exists():
        raise InstallRefused("target must be a Git repository root")
    if linked(target / ".git"):
        raise InstallRefused("linked Git metadata is refused")
    actual_root = Path(git(target, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != target:
        raise InstallRefused("target must be a Git repository root")
    if git(target, "remote", "get-url", "origin") != repository:
        raise InstallRefused("checkout origin differs from the component lock")
    clean(target)


def prepare(target: Path, component: dict, *, adapter: str, ref=None, skip_clone=False):
    expected = component["commit"] if ref is None else ref
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise InstallRefused("Component requires a full lowercase commit SHA; mutable refs refused")
    if sys.version_info[:2] < tuple(map(int, component["python_min"].split("."))):
        raise InstallRefused("Python is below the component runtime floor")
    platform = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "unknown"
    if platform not in component["platforms"] or component["verification"] != adapter:
        raise InstallRefused("unsupported platform or verification adapter")
    if any(os.environ.get(key) for key in (
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"
    )):
        raise InstallRefused("ambient Git path overrides refused")
    target = target.expanduser().absolute()
    if os.path.lexists(target) and linked(target):
        raise InstallRefused("linked install target refused")
    target = target.resolve()
    repository = component["repository"]
    if target.exists():
        existing_repository(target, repository)
        if git(target, "rev-parse", "--verify", "HEAD") != expected:
            raise InstallRefused("existing checkout identity differs; use a fresh target for a new commit")
    elif skip_clone:
        raise InstallRefused("skip-clone target does not exist")
    else:
        # Ref validation and interpreter checks precede any mutation.
        run(["git", "--version"])
        target.mkdir(parents=True)
        git(target, "init", "--quiet")
        git(target, "remote", "add", "origin", repository)
    if not skip_clone:
        git(target, "fetch", "--quiet", "--depth=1", "origin", expected)
        fetched = git(target, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
        if fetched != expected:
            raise InstallRefused("fetched commit identity mismatch")
        git(target, "checkout", "--quiet", "--detach", expected)
    observed = git(target, "rev-parse", "--verify", "HEAD")
    if observed != expected:
        raise InstallRefused("checkout identity mismatch")
    clean(target)
    return target, expected


def finish(target, component, expected):
    existing_repository(target, component["repository"])
    if git(target, "rev-parse", "--verify", "HEAD") != expected:
        raise InstallRefused("checkout identity changed during verification")


def source_verifier_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
