#!/usr/bin/env python3
"""cross-vendor-review.py -- OPT-IN: ask a SECOND vendor's CLI (Codex or
Antigravity) to review `git diff <base>..<head>`, and record what it says as
PROPOSALS. Nothing is ever applied.

WHY. An agent reviewing its own work shares its own blind spots. A model from a
different vendor, shown only the diff, catches a different set of mistakes.
But a reviewer can also invent problems, so a finding is only kept as
PROPOSED if it carries a CONCRETE failing input or reproduction: the exact
input, command or state that makes the code misbehave, plus expected vs actual.
"Could be a problem with edge cases" is rejected and recorded as
REJECTED-NO-REPRO, so you can see what was thrown away and why.

A PROPOSED finding is still not a fact. Reproduce it yourself before you act on
it; until then it is a claim from another model.

WHAT IT DOES
  1. Takes `git diff <base>..<head>` (refuses an empty diff).
  2. Writes the review request to a temp directory and runs the vendor CLI
     there with stdin CLOSED: `codex exec -s read-only --skip-git-repo-check`
     or `agy --print`. The diff goes in a file, not the command line, so a
     large diff is not cut off by the OS argument limit.
  3. Parses the JSON {"findings": [...]} from the CLI's output and checks every
     finding for a concrete failing input.
  4. Appends one "run" row and one row per finding to the JSONL (--out). The
     raw CLI output is saved next to it, by sha256, so the record can be
     re-checked.

It never edits, stages, commits or applies anything in the repo.

    python scripts/cross-vendor-review.py --base main --head HEAD --vendor codex
    python scripts/cross-vendor-review.py --base main --head my-branch --vendor agy --out reviews.jsonl

EXIT CODES
    0   review recorded (findings may be zero)
    2   refused: empty diff, bad revision, or vendor CLI not on PATH
    3   the vendor's output held no parseable {"findings": [...]} -- recorded as
        a run with state NO-PARSEABLE-OUTPUT; nothing was proposed

Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "1.0.0"

EXIT_OK, EXIT_REFUSED, EXIT_UNPARSEABLE = 0, 2, 3
VENDORS = ("codex", "agy")
MAX_DIFF_CHARS = 200_000
REQUIRED_FIELDS = ("file", "severity", "claim", "failing_input", "expected", "actual")
MIN_FAILING_INPUT_CHARS = 8
# A failing_input that is only one of these (case-insensitive, punctuation
# ignored) is not a reproduction.
VAGUE_INPUTS = {
    "", "na", "n a", "none", "null", "unknown", "tbd", "todo", "various", "any", "any input",
    "see above", "see claim", "edge cases", "edge case", "not applicable", "unclear", "general",
    "multiple", "some inputs", "certain inputs", "hypothetical",
}
REQUEST_NAME = "REVIEW_REQUEST.md"

INSTRUCTIONS = """You are an adversarial code reviewer from a different vendor than the author.
Review ONLY the diff below (lines starting '+' are new). Report real defects: wrong results,
crashes, security problems, silent failures, tests that cannot fail.

Every finding MUST carry a concrete failing input or reproduction: the exact input value,
command, file content or state that makes the changed code misbehave, plus what should
happen and what actually happens. A finding without one will be discarded. Do not report
style, naming or "consider adding tests".

Do not edit any file. Reply with ONLY one JSON object, no prose, of this shape:
{"findings": [{"file": "<path>", "severity": "P0|P1|P2", "claim": "<one sentence>",
  "failing_input": "<exact input / command / state>", "expected": "<correct behaviour>",
  "actual": "<what the diff does instead>"}]}
If you find nothing, reply {"findings": []}.
"""

VENDOR_PROMPT = (f"Read {REQUEST_NAME} in the current directory and do exactly what it says. "
                 "Do not modify any file. Reply with only the JSON object it asks for.")


def _utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _git(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL)


def vendor_argv(vendor: str, exe: str) -> list[str]:
    if vendor == "codex":
        return [exe, "exec", "-s", "read-only", "--skip-git-repo-check", VENDOR_PROMPT]
    if vendor == "agy":
        return [exe, "--print", VENDOR_PROMPT]
    raise ValueError(f"unknown vendor {vendor!r}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def check_finding(f) -> str | None:
    """None if the finding is acceptable as a PROPOSAL, else the rejection reason."""
    if not isinstance(f, dict):
        return "finding is not a JSON object"
    missing = [k for k in REQUIRED_FIELDS if not isinstance(f.get(k), str) or not f.get(k).strip()]
    if "failing_input" in missing:
        return "no failing_input: a finding must carry a concrete failing input or reproduction"
    fi = f["failing_input"].strip()
    if _norm(fi) in VAGUE_INPUTS or len(fi) < MIN_FAILING_INPUT_CHARS:
        return f"failing_input {fi!r} is not a concrete input or reproduction"
    if missing:
        return f"missing field(s): {', '.join(missing)}"
    if _norm(f["expected"]) == _norm(f["actual"]):
        return "expected and actual are the same: nothing fails"
    return None


def extract_findings(text: str):
    """The last JSON object in `text` that has a "findings" list, or None."""
    dec = json.JSONDecoder()
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("findings"), list):
            found = obj
    return found


def review(repo: Path, base: str, head: str, vendor: str, out: Path, name: str | None = None,
           timeout_s: int = 1800) -> int:
    shas = {}
    for label, rev in (("base", base), ("head", head)):
        r = _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}")
        if r.returncode != 0:
            print(f"REFUSED: {label} {rev!r} is not a commit", file=sys.stderr)
            return EXIT_REFUSED
        shas[label] = r.stdout.decode().strip()
    d = _git(repo, "diff", f"{shas['base']}..{shas['head']}")
    if d.returncode != 0:
        print(f"REFUSED: git diff failed: {d.stderr.decode(errors='replace').strip()}", file=sys.stderr)
        return EXIT_REFUSED
    diff = d.stdout.decode("utf-8", "replace")
    if not diff.strip():
        print(f"REFUSED: git diff {base}..{head} is empty -- nothing to review", file=sys.stderr)
        return EXIT_REFUSED
    exe = shutil.which(vendor)
    if not exe:
        print(f"REFUSED: `{vendor}` not found on PATH", file=sys.stderr)
        return EXIT_REFUSED
    truncated = len(diff) > MAX_DIFF_CHARS
    shown = diff[:MAX_DIFF_CHARS] + ("\n[... diff truncated; the reviewer saw the first part only]\n" if truncated else "")
    request = f"{INSTRUCTIONS}\n=== DIFF {shas['base'][:12]}..{shas['head'][:12]} ===\n{shown}"
    name = name or f"{shas['base'][:9]}..{shas['head'][:9]}"
    argv = vendor_argv(vendor, exe)

    with tempfile.TemporaryDirectory(prefix="xvr-") as td:
        (Path(td) / REQUEST_NAME).write_bytes(request.encode("utf-8"))
        try:
            p = subprocess.run(argv, cwd=td, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_s)
            raw = p.stdout + (b"\n--- stderr ---\n" + p.stderr if p.stderr else b"")
            timed_out = False
        except subprocess.TimeoutExpired as e:
            raw = (e.stdout or b"") + b"\n[TIMEOUT]\n"
            timed_out = True

    out.parent.mkdir(parents=True, exist_ok=True)
    raw_sha = _sha(raw)
    raw_path = out.parent / f"{out.stem}.raw" / f"{raw_sha}.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    parsed = None if timed_out else extract_findings(p.stdout.decode("utf-8", "replace"))
    now = _utc()
    run = {"kind": "run", "name": name, "tool_version": VERSION, "vendor": vendor, "argv": argv,
           "base": shas["base"], "head": shas["head"], "diff_sha256": _sha(diff.encode("utf-8")),
           "diff_truncated": truncated, "request_sha256": _sha(request.encode("utf-8")),
           "raw_output": str(raw_path), "raw_output_sha256": raw_sha, "recorded_utc": now}
    rows = []
    if parsed is None:
        run["state"] = "TIMEOUT" if timed_out else "NO-PARSEABLE-OUTPUT"
    else:
        run["state"] = "REVIEWED"
        for i, f in enumerate(parsed["findings"]):
            reason = check_finding(f)
            row = {"kind": "finding", "id": f"{name}#{i + 1}", "name": name, "vendor": vendor,
                   "base": shas["base"], "head": shas["head"],
                   "status": "PROPOSED" if reason is None else "REJECTED-NO-REPRO",
                   "finding": f, "recorded_utc": now}
            if reason:
                row["reject_reason"] = reason
            rows.append(row)
        run["proposed"] = sum(r["status"] == "PROPOSED" for r in rows)
        run["rejected"] = len(rows) - run["proposed"]
    with out.open("a", encoding="utf-8", newline="\n") as fh:
        for r in [run] + rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    if parsed is None:
        print(f"{run['state']}: {vendor} gave no parseable {{\"findings\": [...]}}; raw output kept at {raw_path}")
        return EXIT_UNPARSEABLE
    for r in rows:
        f = r["finding"] if isinstance(r["finding"], dict) else {}
        print(f"[{r['id']}] {r['status']} {f.get('severity', '?')} {f.get('file', '?')} -- {str(f.get('claim', ''))[:200]}")
        if r["status"] == "PROPOSED":
            print(f"    input: {f['failing_input'][:300]}\n    expected: {f['expected'][:160]} | actual: {f['actual'][:160]}")
        else:
            print(f"    rejected: {r['reject_reason']}")
    print(f"{run['proposed']} PROPOSED, {run['rejected']} REJECTED-NO-REPRO -> {out}. "
          "Nothing was applied; reproduce a proposal before acting on it.")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--vendor", required=True, choices=VENDORS)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--out", type=Path, default=Path("cross-vendor-review.jsonl"),
                    help="JSONL of runs + findings (default ./cross-vendor-review.jsonl)")
    ap.add_argument("--name", help="label for this review (default <base>..<head>)")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds to wait for the vendor CLI")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    a = ap.parse_args(argv)
    return review(a.repo, a.base, a.head, a.vendor, a.out, a.name, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
