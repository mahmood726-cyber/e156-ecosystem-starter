#!/usr/bin/env python3
"""refresh-ecosystem-pins.py -- keep the starter's install-layer pins current.

The ecosystem-starter installs each system (extractor, Sentinel, Overmind,
RapidMeta, Pairwise70, AACT cockpit, AACT kit) by cloning / pip-installing the
source repo at a PINNED 40-hex commit SHA, for reproducible supply-chain-safe
installs. When Mahmood pushes new work to one of those repos, the pin goes stale.

This is the author-side updater (the counterpart to the user-side
update-ecosystem.ps1). For each layer it queries the latest pushed commit on the
source repo's default branch (`git ls-remote <url> HEAD`) and rewrites the pin in
BOTH the .sh and .ps1 installer -- and the short-SHA mention in README.md.

Design guarantees:
  * PINS ONLY. It moves 40-hex SHAs forward and nothing else. It never reads or
    writes memory, secrets, rules, or any private content -- so it is safe to run
    against the PUBLIC starter. (The private memory/settings sync is a separate
    tool: claude-ecosystem-sync / ecosync.ps1.)
  * IDEMPOTENT. No-op when every pin already matches its remote HEAD.
  * NON-DESTRUCTIVE. Edits tracked files in place; you review the diff. --commit
    makes a normal commit; --push uses fast-forward-only push (rejected, never
    forced, if the remote moved).
  * Tag-pinned layers (e.g. long-term-plan @ v0.7.0) are left alone -- only
    layers carrying a 40-hex SHA are bumped.

Usage:
  python scripts/refresh-ecosystem-pins.py            # dry-run: report drift
  python scripts/refresh-ecosystem-pins.py --check    # report drift, exit 1 if any (CI)
  python scripts/refresh-ecosystem-pins.py --apply    # rewrite stale pins in place
  python scripts/refresh-ecosystem-pins.py --apply --layer extractor,sentinel
  python scripts/refresh-ecosystem-pins.py --apply --commit          # + git commit
  python scripts/refresh-ecosystem-pins.py --apply --commit --push   # + ff-only push
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_OWNER = "mahmood726-cyber"

# One entry per pinned install layer. `files` are relative to the repo root; the
# first must be the .sh installer (the authoritative source of the current pin).
LAYERS = [
    {"name": "extractor",  "repo": "rct-extractor-v2",
     "files": ["scripts/install-extractor.sh",  "scripts/install-extractor.ps1"]},
    {"name": "sentinel",   "repo": "Sentinel",
     "files": ["scripts/install-sentinel.sh",   "scripts/install-sentinel.ps1"]},
    {"name": "overmind",   "repo": "overmind",
     "files": ["scripts/install-overmind.sh",   "scripts/install-overmind.ps1"]},
    {"name": "rapidmeta",  "repo": "rapidmeta-kit",
     "files": ["scripts/install-rapidmeta.sh",  "scripts/install-rapidmeta.ps1"]},
    {"name": "pairwise70", "repo": "pairwise70-workbench",
     "files": ["scripts/install-pairwise70.sh", "scripts/install-pairwise70.ps1"]},
    {"name": "aact",       "repo": "aact-cockpit",
     "files": ["scripts/install-aact.sh",       "scripts/install-aact.ps1"]},
    {"name": "aact-kit",   "repo": "aact-kit",
     "files": ["scripts/install-aact-kit.sh",   "scripts/install-aact-kit.ps1"]},
]

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_PIN_RE = re.compile(r"DEFAULT_REF[^\n]*?([0-9a-f]{40})", re.IGNORECASE)

# Files (beyond each layer's own installers) that also reference the pinned SHA
# and must stay in sync: the README short-SHA mentions and the layer tests that
# assert the pinned ref. The old SHA is globally unique, so a literal swap is safe.
EXTRA_TARGETS = ["README.md", "tests/test-new-layers.bash"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def extract_pin(sh_text: str) -> str | None:
    """Return the 40-hex SHA the .sh installer pins, or None (e.g. tag-pinned)."""
    m = _PIN_RE.search(sh_text)
    if m:
        return m.group(1)
    m = _SHA_RE.search(sh_text)  # fallback: first 40-hex anywhere
    return m.group(0) if m else None


def remote_head(repo: str) -> str | None:
    """Latest pushed commit on the repo's default branch, via git ls-remote."""
    url = f"https://github.com/{REPO_OWNER}/{repo}.git"
    try:
        out = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    line = out.strip().splitlines()[0] if out.strip() else ""
    m = _SHA_RE.match(line)
    return m.group(0) if m else None


def apply_bump(text: str, old: str, new: str) -> str:
    """Replace the full 40-hex pin and any `<short>` backtick mention."""
    text = text.replace(old, new)
    text = text.replace(f"`{old[:7]}`", f"`{new[:7]}`")
    return text


def process_layer(layer: dict, apply: bool, root: Path) -> dict:
    """Check (and optionally bump) one layer. Returns a result dict."""
    sh_rel = layer["files"][0]
    sh_path = root / sh_rel
    if not sh_path.exists():
        return {"name": layer["name"], "status": "missing", "detail": sh_rel}
    old = extract_pin(sh_path.read_text(encoding="utf-8", errors="replace"))
    if old is None:
        return {"name": layer["name"], "status": "skip", "detail": "no 40-hex pin (tag-pinned?)"}
    new = remote_head(layer["repo"])
    if new is None:
        return {"name": layer["name"], "status": "error", "detail": "ls-remote failed", "old": old}
    if new == old:
        return {"name": layer["name"], "status": "current", "old": old, "new": new}

    changed = []
    if apply:
        # Read/write as bytes so original line endings (LF for .sh, possibly
        # CRLF for .ps1) are preserved -- we only swap a 40-hex substring.
        targets = list(layer["files"]) + EXTRA_TARGETS
        for rel in targets:
            p = root / rel
            if not p.exists():
                continue
            raw = p.read_bytes()
            txt = raw.decode("utf-8", errors="replace")
            new_txt = apply_bump(txt, old, new)
            if new_txt != txt:
                p.write_bytes(new_txt.encode("utf-8"))
                changed.append(rel)
    return {"name": layer["name"], "status": "drift", "old": old, "new": new, "changed": changed}


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="rewrite stale pins in place")
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 if any layer is stale (CI mode)")
    ap.add_argument("--layer", default=None,
                    help="comma list of layer names to limit to (default: all)")
    ap.add_argument("--commit", action="store_true", help="git add+commit the bumps (implies --apply)")
    ap.add_argument("--push", action="store_true", help="git push (ff-only) after commit")
    args = ap.parse_args(argv)

    if args.commit:
        args.apply = True
    root = repo_root()

    wanted = {s.strip() for s in args.layer.split(",")} if args.layer else None
    layers = [l for l in LAYERS if wanted is None or l["name"] in wanted]
    if wanted:
        unknown = wanted - {l["name"] for l in LAYERS}
        if unknown:
            ap.error(f"unknown layer(s): {', '.join(sorted(unknown))}; "
                     f"known: {', '.join(l['name'] for l in LAYERS)}")

    print(f"ecosystem pin refresh ({'apply' if args.apply else 'check' if args.check else 'dry-run'})")
    print(f"  repo: {root}\n")

    results = [process_layer(l, args.apply, root) for l in layers]

    drift, errors, all_changed = 0, 0, []
    for r in results:
        name = r["name"]
        if r["status"] == "current":
            print(f"  [ok]      {name:12s} {r['old'][:12]} (current)")
        elif r["status"] == "drift":
            drift += 1
            arrow = f"{r['old'][:12]} -> {r['new'][:12]}"
            if args.apply:
                print(f"  [bumped]  {name:12s} {arrow}  ({len(r['changed'])} file(s))")
                all_changed += r["changed"]
            else:
                print(f"  [stale]   {name:12s} {arrow}")
        elif r["status"] == "skip":
            print(f"  [skip]    {name:12s} {r['detail']}")
        elif r["status"] == "missing":
            print(f"  [missing] {name:12s} {r['detail']}")
        else:
            errors += 1
            print(f"  [error]   {name:12s} {r.get('detail', '')}")

    print()
    if args.check:
        if drift or errors:
            print(f"DRIFT: {drift} layer(s) stale, {errors} error(s). "
                  f"Fix: python scripts/refresh-ecosystem-pins.py --apply")
            return 1
        print("OK: all pins current.")
        return 0

    if not args.apply:
        if drift:
            print(f"{drift} layer(s) stale. Re-run with --apply to update.")
        else:
            print("All pins current; nothing to do.")
        return 0

    # --apply path
    if errors:
        print(f"WARNING: {errors} layer(s) could not be checked (ls-remote failed).")
    if not all_changed:
        print("All pins already current; no files changed.")
        return 0

    uniq = sorted(set(all_changed))
    print(f"Updated {len(uniq)} file(s): {', '.join(uniq)}")
    print("  NOTE: install/install.{ps1,sh} were not touched, but if you edited")
    print("        them re-run scripts/regen-hashes.sh before committing.")

    if args.commit:
        g = git(root, "add", *uniq)
        if g.returncode != 0:
            print(f"git add failed:\n{g.stderr}", file=sys.stderr)
            return 1
        bumped = [r for r in results if r["status"] == "drift"]
        body = "\n".join(f"- {r['name']}: {r['old'][:12]} -> {r['new'][:12]}" for r in bumped)
        msg = "chore: refresh ecosystem install-layer pins\n\n" + body
        g = git(root, "commit", "-m", msg)
        if g.returncode != 0:
            print(f"git commit failed:\n{g.stdout}\n{g.stderr}", file=sys.stderr)
            return 1
        print("Committed pin refresh.")
        if args.push:
            g = git(root, "push")  # ff-only by default; never forced
            if g.returncode != 0:
                print(f"git push failed (pull --rebase then retry):\n{g.stderr}", file=sys.stderr)
                return 1
            print("Pushed.")
    else:
        print("Review the diff, then commit (or re-run with --commit).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
