#!/usr/bin/env python3
"""Run frozen SciCoQA prompt pairs with an explicitly configured model CLI.

The external command must accept a prompt on stdin and return SciCoQA YAML on stdout.
The caller must verify the command really uses the frozen model and decoding settings.
No model provider or scientific adjudicator is bundled.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from scicoqa_paired_benchmark import BenchmarkError, ARMS, SCHEMA, canonical, digest, read_jsonl


def parse_yaml(text: str) -> list[dict]:
    """Parse a conservative subset of SciCoQA discrepancy-list YAML."""
    lines = text.strip().replace("```yaml", "").replace("```", "").splitlines()
    try:
        at = next(i for i, line in enumerate(lines) if line.strip().startswith("discrepancies:"))
    except StopIteration as exc:
        raise BenchmarkError("no discrepancies key") from exc
    first = lines[at].split(":", 1)[1].strip()
    if first == "[]":
        return []
    if first:
        raise BenchmarkError("unsupported inline YAML")
    items = []
    for line in lines[at+1:]:
        if not line.strip():
            continue
        match = re.match(r"^\s+-\s+(.*)$", line)
        if match:
            value = match.group(1).strip()
            if not value or value in {"|", ">"}:
                raise BenchmarkError("unsupported multiline YAML")
            items.append(value.strip("'\""))
        elif items and line.startswith("    "):
            items[-1] += " " + line.strip()
        else:
            raise BenchmarkError("unrecognized YAML response")
    return [{"finding_id": f"F{i+1}", "text": x} for i, x in enumerate(items)]


def execute(manifest: dict, prompts: dict, command: list[str], timeout: int = 180) -> tuple[list, list]:
    if manifest.get("schema") != SCHEMA or not manifest.get("cases"):
        raise BenchmarkError("invalid manifest")
    if not command or timeout < 1:
        raise BenchmarkError("command and positive timeout required")
    cases = {x["case_id"]: x for x in manifest["cases"]}
    if len(cases) != len(manifest["cases"]):
        raise BenchmarkError("duplicate case ID")
    indexed = {}
    for arm in ARMS:
        rows = prompts[arm]
        if len(rows) != len(cases):
            raise BenchmarkError("missing case arm")
        for row in rows:
            cid = row.get("case_id")
            if cid not in cases or row.get("arm") != arm or (cid, arm) in indexed:
                raise BenchmarkError("invalid or duplicate case arm")
            if digest(row["prompt"]) != cases[cid]["rendered_prompt_sha256"][arm]:
                raise BenchmarkError("prompt digest mismatch")
            indexed[(cid, arm)] = row["prompt"]
    predictions, raw_outputs = [], []
    sha = digest(canonical(manifest))
    for cid in sorted(cases):
        for arm in ARMS:
            status, findings, output, error = "COMPLETE", [], "", None
            try:
                completed = subprocess.run(
                    command, input=indexed[(cid, arm)], text=True,
                    capture_output=True, timeout=timeout, check=False)
                output = completed.stdout
                if completed.returncode:
                    status = "FAILED"
                    error = f"model command exited {completed.returncode}"
                else:
                    findings = parse_yaml(output)
            except (subprocess.TimeoutExpired, OSError) as exc:
                status, error = "FAILED", type(exc).__name__
            except BenchmarkError as exc:
                status, error = "ABSTAIN", str(exc)
            row = {
                "case_id": cid, "arm": arm, "manifest_sha256": sha,
                "rendered_prompt_sha256": cases[cid]["rendered_prompt_sha256"][arm],
                "model": manifest["model"], "model_revision": manifest["model_revision"],
                "decoding_config": manifest["decoding_config"], "status": status,
                "findings": findings}
            predictions.append(row)
            raw_outputs.append({**row, "raw_response": output, "error": error})
    return predictions, raw_outputs


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="external model CLI and its arguments, after --")
    a = p.parse_args()
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not command or a.output.exists():
        p.error("specify a model command and a new output directory")
    manifest = json.loads((a.prepared / "manifest.json").read_text(encoding="utf-8"))
    prompts = {arm: read_jsonl(a.prepared / f"{arm}-prompts.jsonl") for arm in ARMS}
    predictions, outputs = execute(manifest, prompts, command, a.timeout)
    a.output.mkdir(parents=True)
    for filename, rows in (("predictions.jsonl", predictions), ("raw_outputs.jsonl", outputs)):
        (a.output / filename).write_text(
            "".join(canonical(x) + "\n" for x in rows), encoding="utf-8")
    print("Model responses recorded; no independent scientific adjudication performed")
    print(json.dumps({"total": len(predictions),
                      "complete": sum(x["status"] == "COMPLETE" for x in predictions),
                      "abstain": sum(x["status"] == "ABSTAIN" for x in predictions),
                      "failed": sum(x["status"] == "FAILED" for x in predictions)}))


if __name__ == "__main__":
    main()
