"""Shared RapidMeta install verifier for Bash and PowerShell (stdlib only).

Pins source and exercises the generator with synthetic controls. It does not
validate scientific findings, render a browser, or persist user configuration.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

if __package__:
    from .component_lock import DEFAULT_LOCK, SHA, load_lock
else:
    from component_lock import DEFAULT_LOCK, SHA, load_lock

ADAPTER = "rapidmeta-generator-v1"
SMOKE_TITLE = "SYNTHETIC INSTALL CHECK - NOT RESEARCH EVIDENCE"


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


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        key = "src" if tag == "script" else "href" if tag == "link" else None
        if key and attributes.get(key):
            self.urls.append(attributes[key])


def inspect_output(path):
    # Use one spelling for both containment and relative asset names. In
    # particular, Windows TEMP may use an 8.3 alias that resolve() expands.
    path = path.resolve(strict=True)
    raw = path.read_bytes()
    html = raw.decode("utf-8")
    for marker in (SMOKE_TITLE, "fixture-a", "fixture-b"):
        if marker not in html:
            raise InstallRefused("generator output lacks synthetic fixture markers")
    parser = Assets()
    parser.feed(html)
    local_assets = []
    external = []
    for url in parser.urls:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            if parts.scheme != "data":
                external.append(url)
            continue
        if not parts.path:
            continue
        asset = (path.parent / unquote(parts.path)).resolve()
        if not asset.is_relative_to(path.parent.resolve()) or not asset.is_file():
            raise InstallRefused("missing or escaping local generator asset")
        local_assets.append(asset.relative_to(path.parent).as_posix())
    if not local_assets:
        raise InstallRefused("generator output has no verified local assets")
    manifest = []
    for name in sorted(set(local_assets)):
        manifest.append([name, hashlib.sha256((path.parent / name).read_bytes()).hexdigest()])
    return {
        "fixture_kind": "synthetic_install_check",
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "local_assets": manifest,
        "external_resource_count": len(set(external)),
        "browser_verified": False,
        "scientific_accuracy_measured": False,
    }


def smoke(target):
    entrypoint = target / "clone.py"
    if not entrypoint.is_file() or linked(entrypoint):
        raise InstallRefused("missing or linked clone.py")
    cfg = {
        "drug": "SyntheticAgent", "condition": "SyntheticCondition",
        "slug": "synthetic_install_check", "title": SMOKE_TITLE,
        "trials": [
            {"nct": "fixture-a", "name": "Synthetic fixture A", "year": 2000,
             "sourceUrl": "https://example.invalid/fixture-a", "tE": 2, "tN": 10, "cE": 3, "cN": 10},
            {"nct": "fixture-b", "name": "Synthetic fixture B", "year": 2000,
             "sourceUrl": "https://example.invalid/fixture-b", "tE": 4, "tN": 20, "cE": 5, "cN": 20},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="rapidmeta-install-check-") as temp:
        root = Path(temp)
        config = root / "synthetic.json"
        config.write_text(json.dumps(cfg), encoding="utf-8")
        reports = []
        for label in ("first", "repeat"):
            output = root / label / "dashboard.html"
            run([sys.executable, "-B", str(entrypoint), str(config), "--out", str(output)],
                cwd=target, timeout=60)
            if not output.is_file():
                raise InstallRefused("generator exited without an output file")
            reports.append(inspect_output(output))
        if reports[0] != reports[1]:
            raise InstallRefused("generator output is not deterministic")
        return reports[0]


def install(target: Path, component: dict, *, ref=None, skip_clone=False):
    expected = component["commit"] if ref is None else ref
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise InstallRefused("RapidMeta requires a full lowercase commit SHA; mutable refs refused")
    if sys.version_info[:2] < tuple(map(int, component["python_min"].split("."))):
        raise InstallRefused("Python is below the component runtime floor")
    platform = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "unknown"
    if platform not in component["platforms"] or component["verification"] != ADAPTER:
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
    result = smoke(target)
    existing_repository(target, repository)
    if git(target, "rev-parse", "--verify", "HEAD") != expected:
        raise InstallRefused("checkout identity changed during verification")
    return {"schema": "e156-component-install-v1", "component": "rapidmeta",
            "status": "verified", "adapter": ADAPTER,
            "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "component_spec_sha256": hashlib.sha256(json.dumps(component, sort_keys=True).encode()).hexdigest(),
            "expected_commit": expected, "observed_commit": observed,
            "uses_locked_default": expected == component["commit"], "smoke": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--ref", help="explicit full commit override (not a reviewed default)")
    parser.add_argument("--skip-clone", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = install(args.target, load_lock(DEFAULT_LOCK)["rapidmeta"],
                         ref=args.ref, skip_clone=args.skip_clone)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
