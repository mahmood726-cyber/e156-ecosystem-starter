#!/usr/bin/env python3
r"""push-portfolio.py -- auto-discover + push ALL git repos in a directory tree.

Parameterized ecosystem-starter version of Mahmood's push_all_repos.py. NO
hardcoded paths; reads scan dirs from CLI args or `PORTFOLIO_SCAN_DIRS` env.

For each repo found:
  1. If no `origin` remote: create a GitHub repo via `gh` and push
  2. If `origin` already set: fast-forward push

Usage:
    python push-portfolio.py --scan-dir C:\Projects --github-user <you>
    python push-portfolio.py --scan-dir C:\Projects --scan-dir D:\Projects
    python push-portfolio.py --dry-run                  # show what would happen
    python push-portfolio.py --report                   # just scan + print table
    python push-portfolio.py --new-only                 # skip repos with existing remote

Env fallbacks (used when CLI args are missing):
    PORTFOLIO_SCAN_DIRS   -- semicolon-separated list of dirs
    PORTFOLIO_GITHUB_USER -- GitHub username

Exit codes:
    0 = all actions succeeded (or --dry-run / --report completed)
    1 = at least one push failed
    2 = configuration error (no scan dirs, no github user)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoStatus:
    path: Path
    name: str
    has_remote: bool
    remote_url: str
    last_error: str = ""


def find_git_repos(scan_dirs: list[Path], recursive: bool = True) -> list[Path]:
    """Return every `*/.git/` parent under the scan dirs.

    Skips:
      - well-known build/cache dirs (node_modules, venv, dist, ...)
      - any directory whose name starts with `.` (covers `.claude`, `.codex`,
        `.gemini`, `.config`, `.local`, etc.). Hidden config repos are private
        by convention and a student running --report on a broad root should
        not have those leak into the portfolio scan, even if they happen to
        be initialised as git repos. Same rule as the agent-config sentinel.
    """
    skip_names = {
        "node_modules", "venv", "__pycache__",
        "build", "dist", "site-packages",
    }
    repos: list[Path] = []
    for root in scan_dirs:
        if not root.is_dir():
            continue
        for git_dir in root.rglob(".git") if recursive else [p / ".git" for p in root.iterdir() if p.is_dir()]:
            if not git_dir.is_dir():
                continue
            # Path parts BETWEEN root and the .git dir itself. We never want
            # to skip on the literal '.git' segment (that's the marker we're
            # looking for); we DO want to skip on any other dotted ancestor.
            ancestors = git_dir.relative_to(root).parts[:-1]
            if any(part in skip_names for part in ancestors):
                continue
            if any(part.startswith(".") for part in ancestors):
                continue
            # Also reject repos whose own directory name is dotted (e.g. a
            # student scans $HOME and we hit ~/.claude itself as a git repo).
            repo_name = git_dir.parent.name
            if repo_name.startswith("."):
                continue
            repos.append(git_dir.parent)
    return sorted(set(repos))


def get_remote_url(repo: Path) -> str:
    """Return the origin URL for `repo`, or "" if the repo has no remote.

    Important: git walks UP the directory tree to find a parent .git/ if the
    current dir isn't itself a valid repo. We guard against that by first
    asking git for its top-level and rejecting answers that don't match
    `repo` -- otherwise a fake/bare .git subdir would falsely "inherit" the
    home-directory repo's remote.
    """
    try:
        top = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if top.returncode != 0:
            return ""
        actual = Path(top.stdout.strip()).resolve()
        if actual != repo.resolve():
            return ""
        out = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


def push_existing_remote(repo: Path, dry_run: bool) -> tuple[bool, str]:
    if dry_run:
        return True, "(dry-run) git push would run"
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "push", "origin", "HEAD"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()[:200]
        return True, "pushed"
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{type(e).__name__}: {e}"


def create_and_push(repo: Path, github_user: str, dry_run: bool) -> tuple[bool, str]:
    name = repo.name
    if dry_run:
        return True, f"(dry-run) would: gh repo create {github_user}/{name} + git push"
    try:
        # Create the GitHub repo (public by default; --private is power-user opt-in)
        create = subprocess.run(
            ["gh", "repo", "create", f"{github_user}/{name}", "--public", "--source", str(repo), "--push"],
            capture_output=True, text=True, timeout=60,
        )
        if create.returncode != 0:
            return False, (create.stderr or create.stdout).strip()[:200]
        return True, f"created + pushed github.com/{github_user}/{name}"
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{type(e).__name__}: {e}"


def classify_repos(repos: list[Path]) -> list[RepoStatus]:
    out = []
    for r in repos:
        url = get_remote_url(r)
        out.append(RepoStatus(path=r, name=r.name, has_remote=bool(url), remote_url=url))
    return out


def print_report(statuses: list[RepoStatus]) -> None:
    if not statuses:
        print("(no git repos found)")
        return
    width = max(len(s.name) for s in statuses)
    for s in statuses:
        marker = "OK" if s.has_remote else "NEW"
        remote = s.remote_url if s.has_remote else "(no remote)"
        print(f"  {marker:3s}  {s.name:<{width}}  {remote}")
    counts = {"OK": sum(1 for s in statuses if s.has_remote),
              "NEW": sum(1 for s in statuses if not s.has_remote)}
    print(f"\nTotal: {len(statuses)} repos  (OK: {counts['OK']}, NEW: {counts['NEW']})")


def resolve_scan_dirs(args_scan_dirs: list[str] | None) -> list[Path]:
    if args_scan_dirs:
        raw = args_scan_dirs
    else:
        env = os.environ.get("PORTFOLIO_SCAN_DIRS", "")
        if not env:
            return []
        raw = [p for p in env.split(";") if p.strip()]
    return [Path(p).expanduser().resolve() for p in raw]


def resolve_github_user(arg_user: str | None) -> str:
    if arg_user:
        return arg_user
    return os.environ.get("PORTFOLIO_GITHUB_USER", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-dir", action="append", default=None,
                    help="Directory to scan for git repos (repeatable). "
                         "Falls back to PORTFOLIO_SCAN_DIRS env var.")
    ap.add_argument("--github-user", default=None,
                    help="GitHub username. Falls back to PORTFOLIO_GITHUB_USER env var.")
    ap.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    ap.add_argument("--report", action="store_true", help="Scan + print status table, no actions")
    ap.add_argument("--new-only", action="store_true", help="Only repos without existing remote")
    ap.add_argument("--no-recursive", action="store_true", help="Only scan immediate children of each dir")
    args = ap.parse_args()

    scan_dirs = resolve_scan_dirs(args.scan_dir)
    if not scan_dirs:
        print("ERROR: no --scan-dir given and PORTFOLIO_SCAN_DIRS env var empty.", file=sys.stderr)
        return 2

    gh_user = resolve_github_user(args.github_user)
    if not gh_user and not args.report:
        print("ERROR: no --github-user given and PORTFOLIO_GITHUB_USER env var empty.", file=sys.stderr)
        print("       (--report mode does not need it.)", file=sys.stderr)
        return 2

    print(f"Scanning {len(scan_dirs)} dir(s) for git repos...")
    for d in scan_dirs:
        print(f"  - {d}")
    print()

    repos = find_git_repos(scan_dirs, recursive=not args.no_recursive)
    statuses = classify_repos(repos)

    if args.report:
        print_report(statuses)
        return 0

    if args.new_only:
        statuses = [s for s in statuses if not s.has_remote]

    any_failed = False
    for s in statuses:
        if s.has_remote:
            ok, msg = push_existing_remote(s.path, args.dry_run)
            tag = "PUSH"
        else:
            ok, msg = create_and_push(s.path, gh_user, args.dry_run)
            tag = "NEW "
        marker = "OK" if ok else "FAIL"
        print(f"  [{marker}] {tag}  {s.name:<30}  {msg}")
        if not ok:
            any_failed = True

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
