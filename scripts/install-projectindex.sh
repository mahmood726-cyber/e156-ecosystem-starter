#!/usr/bin/env bash
# install-projectindex.sh -- bash parallel of scripts/install-projectindex.ps1.
#
# Creates an INDEX.md + parameterised reconcile_counts.py at a target dir.
# The Python script is identical to the Windows one -- same regex for
# scraping "## Active projects" links + comment-stripping -- so
# reconcile_counts.py is cross-platform once written.
#
# Usage:
#   ./scripts/install-projectindex.sh --root $HOME/ProjectIndex
#   ./scripts/install-projectindex.sh --root . --force
#   ./scripts/install-projectindex.sh --import

set -euo pipefail

ROOT=""
FORCE=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)    ROOT="$2"; shift 2 ;;
        --force)   FORCE=1; shift ;;
        --import)  IMPORT=1; shift ;;
        -h|--help) grep -E '^#' "$0" | head -15; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

get_default_projectindex_root() {
    printf '%s' "${HOME}/ProjectIndex"
}

write_index_markdown_template() {
    local path="$1"
    cat > "$path" <<'EOF'
# Project Portfolio Index

> One line per project. Keep under 200 lines. Drop stale.
>
> This is the authoritative source for **dev status**. Submission status lives
> in your E156 workbook.

## Active projects

<!--
Format: - [Name](../path-to-repo) -- one-line hook. Status: active / WIP / blocked
Example:
  - [my-first-paper](../my-first-paper) -- sacubitril/valsartan in HFrEF meta-analysis. Status: active
-->

## Submission-ready

<!--
Projects that have passed Overmind verification + reconcile and are ready for
journal submission or pre-print.
-->

## Shipped

<!--
Submitted / published. Record the DOI or pre-print URL.
-->

## Triage

<!--
Projects in limbo: missing path, failed Overmind verdict, or registry mismatch.
Run reconcile_counts.py to detect drift.
-->
EOF
}

write_reconcile_script() {
    local path="$1"
    cat > "$path" <<'PYEOF'
r"""Portfolio reconcile -- lightweight ecosystem-starter version.

Cross-checks:
  1. Every project listed under `## Active projects` in INDEX.md actually
     has a directory on disk at the linked path.
  2. Optional: if a `registry.json` exists in the same dir, its project
     count agrees with INDEX.md.

Exit codes:
  0 = all registries agree, all paths exist
  1 = drift (count mismatch or missing paths)
  2 = INDEX.md unreadable / missing

Usage:
  python reconcile_counts.py --root ~/ProjectIndex
  python reconcile_counts.py           (uses PROJECTINDEX_ROOT env var or cwd)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"^\s*-\s+\[([^\]]+)\]\(([^)]+)\)")


def load_projects_from_index(index_path: Path) -> list[tuple[str, str]]:
    """Return [(name, link)] under `## Active projects`, stripping HTML comments."""
    if not index_path.is_file():
        raise FileNotFoundError(f"INDEX.md not found at {index_path}")
    raw_text = index_path.read_text(encoding="utf-8")
    stripped = re.sub(r"<!--.*?-->", "", raw_text, flags=re.DOTALL)
    projects: list[tuple[str, str]] = []
    in_section = False
    for raw in stripped.splitlines():
        line = raw.rstrip()
        if line.startswith("## Active projects"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            m = LINK_RE.match(line)
            if m:
                projects.append((m.group(1), m.group(2)))
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("PROJECTINDEX_ROOT") or os.getcwd())
    args = ap.parse_args()

    root = Path(args.root).resolve()
    index_path = root / "INDEX.md"
    try:
        projects = load_projects_from_index(index_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    missing: list[tuple[str, str, Path]] = []
    for name, link in projects:
        candidate = (root / link).resolve() if not Path(link).is_absolute() else Path(link)
        if not candidate.exists():
            missing.append((name, link, candidate))

    if missing:
        print(f"FAIL: {len(missing)} project(s) in INDEX.md have missing paths:", file=sys.stderr)
        for name, link, resolved in missing:
            print(f"  - {name} -> {link}  (resolved to {resolved}, not found)", file=sys.stderr)
        return 1

    registry = root / "registry.json"
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            registry_count = len(data.get("projects", []))
            if registry_count != len(projects):
                print(f"FAIL: INDEX.md lists {len(projects)} projects but registry.json has {registry_count}", file=sys.stderr)
                return 1
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARN: registry.json unreadable: {e}", file=sys.stderr)

    print(f"OK: {len(projects)} project(s) in INDEX.md, all paths resolve, registries agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYEOF
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$ROOT" ]] || ROOT="$(get_default_projectindex_root)"

echo
echo "ProjectIndex installer"
echo "Target: $ROOT"
echo

log_step "Creating directory"
mkdir -p "$ROOT"
log_ok "exists: $ROOT"

index_path="$ROOT/INDEX.md"
if [[ -f "$index_path" && "$FORCE" -eq 0 ]]; then
    log_ok "INDEX.md already exists; skipping (use --force to overwrite)"
else
    log_step "Writing INDEX.md template"
    write_index_markdown_template "$index_path"
    log_ok "wrote $index_path"
fi

reconcile_path="$ROOT/reconcile_counts.py"
if [[ -f "$reconcile_path" && "$FORCE" -eq 0 ]]; then
    log_ok "reconcile_counts.py already exists; skipping (use --force to overwrite)"
else
    log_step "Writing reconcile_counts.py"
    write_reconcile_script "$reconcile_path"
    log_ok "wrote $reconcile_path"
fi

echo
echo "====================================================="
echo "  ProjectIndex scaffolded at $ROOT"
echo "  Add your projects as markdown links under"
echo "    ## Active projects"
echo "  Then run:"
echo "    python \"$reconcile_path\" --root \"$ROOT\""
echo "====================================================="
