#!/usr/bin/env python3
"""Fail-closed, clean-runner integration check for install/install.sh --full.

This checks installed outputs and actually invokes each non-interactive
component. It is a technical installer canary, NOT scientific validation.
Never run --full on a personal machine just to satisfy this CI test.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path


RULE_FILES = ("rules.md", "e156.md", "advanced-stats.md", "lessons.md")
CONTEXT_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "CODEX.md")


def verify(home: Path, *, run_canaries: bool = True) -> list[tuple[str, str, str]]:
    """Return (check name, PASS/FAIL, diagnostic) for every installer contract."""
    results: list[tuple[str, str, str]] = []

    def check(name: str, ok: bool, message: str = "") -> None:
        results.append((name, "PASS" if ok else "FAIL", message))

    for agent in (".claude", ".gemini", ".codex"):
        cfg = home / agent
        for filename in RULE_FILES:
            path = cfg / "rules" / filename
            check(f"{agent} rule {filename}", path.is_file(), str(path))
        for filename in CONTEXT_FILES:
            path = cfg / filename
            check(f"{agent} context {filename}", path.is_file(), str(path))

        rules_path = cfg / "rules" / "rules.md"
        if rules_path.is_file():
            text = rules_path.read_text(encoding="utf-8")
            index = str(home / "code" / "ProjectIndex")
            check(f"{agent} ProjectIndex binding",
                  index in text and "{{PROJECTINDEX_ROOT}}" not in text,
                  f"expected {index} in generated rules")

    for agent in (".claude", ".gemini"):
        p = home / agent / "memory" / "MEMORY.md"
        check(f"{agent} memory", p.is_file(), str(p))

    sample_repo = home / "code" / "my-first-repo"
    hook = sample_repo / ".git" / "hooks" / "pre-push"
    hook_text = hook.read_text(encoding="utf-8", errors="replace") if hook.is_file() else ""
    check("Sentinel hook installed", hook.is_file() and "sentinel" in hook_text,
          str(hook))

    key_path = home / ".config" / "e156" / "truthcert-hmac-key"
    key = key_path.read_text(encoding="utf-8").strip() if key_path.is_file() else ""
    check("TruthCert key format", bool(re.fullmatch(r"[0-9a-fA-F]{64}", key)),
          "required: locally generated 32-byte hex key")
    if key_path.is_file() and os.name == "posix":
        check("TruthCert key permissions",
              stat.S_IMODE(key_path.stat().st_mode) & 0o077 == 0,
              "key must not be group/world readable")

    index = home / "code" / "ProjectIndex"
    for rel in ("INDEX.md", "reconcile_counts.py",
                "agent-records/restart-manifest.json"):
        p = index / rel
        check(f"ProjectIndex {rel}", p.is_file(), str(p))

    extractor = home / "code" / "rct-extractor-v2"
    entry = extractor / "scripts" / "build_metakit_config.py"
    check("RCT extractor bridge installed", entry.is_file(), str(entry))

    if run_canaries:
        def canary(name: str, argv: list[str], *, timeout: int = 180) -> None:
            if shutil.which(argv[0]) is None:
                check(name, False, f"{argv[0]} unavailable on PATH")
                return
            try:
                proc = subprocess.run(argv, capture_output=True, text=True,
                                      errors="replace", timeout=timeout, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                check(name, False, str(exc))
                return
            detail = (proc.stderr or proc.stdout or "").strip()[-300:]
            check(name, proc.returncode == 0,
                  f"exit={proc.returncode}; {detail}")

        canary("Sentinel CLI scan", ["sentinel", "scan", "--repo", str(sample_repo)])
        canary("Overmind numerical canary", ["overmind", "meta-verify"], timeout=240)
        canary("ProjectIndex reconcile", [sys.executable, str(index / "reconcile_counts.py"),
                                           "--root", str(index)])
        if entry.is_file():
            probe = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "from rct_extractor import SPECIALTIES, detect_specialty; assert len(SPECIALTIES) == 17; "
                "assert detect_specialty('viral suppression with dolutegravir')[0] == 'hiv'; "
                "assert detect_specialty('empagliflozin type 2 diabetes HbA1c')[0] == 'diabetes'"
            )
            canary("Extractor two-specialty import",
                   [sys.executable, "-c", probe, str(extractor)])
        else:
            check("Extractor two-specialty import", False, "bridge missing")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(),
                        help="fresh CI runner user's home")
    parser.add_argument("--no-canaries", action="store_true",
                        help="artifact-only check for negative-test fixtures")
    args = parser.parse_args(argv)
    outcomes = verify(args.home, run_canaries=not args.no_canaries)
    for name, verdict, detail in outcomes:
        print(f"{verdict:4}  {name}: {detail}")
    failures = [name for name, verdict, _ in outcomes if verdict != "PASS"]
    print(f"Full-chain integration: {len(outcomes)-len(failures)}/{len(outcomes)} passed")
    if failures:
        print("REFUSED: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
