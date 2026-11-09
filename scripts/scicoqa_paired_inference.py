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
import time
from pathlib import Path

from scicoqa_paired_benchmark import BenchmarkError, ARMS, SCHEMA, canonical, digest, read_jsonl


def parse_yaml(text: str) -> list[dict]:
    """Parse a conservative subset of SciCoQA discrepancy-list YAML."""
    document = text.strip()
    if document.startswith("```"):
        fence = re.fullmatch(r"```(?:yaml|yml)?\s*\n(.*?)\n```", document, re.DOTALL)
        if not fence:
            raise BenchmarkError("response must be one YAML document")
        document = fence.group(1).strip()
    lines = document.splitlines()
    if not lines or not re.fullmatch(r"discrepancies:\s*(?:\[\])?\s*", lines[0]):
        raise BenchmarkError("response must start with discrepancies key; no preamble")
    first = lines[0].split(":", 1)[1].strip()
    if first == "[]":
        if any(line.strip() for line in lines[1:]):
            raise BenchmarkError("unexpected content after empty result")
        return []
    if first:
        raise BenchmarkError("unsupported inline YAML")
    items = []
    for line in lines[1:]:
        if not line.strip():
            continue
        match = re.match(r"^  -\s+(.*)$", line)
        if match:
            value = match.group(1).strip()
            if (not value or value in {"|", ">", "|-", ">-", "null", "~", "true", "false"}
                    or value.startswith(("{", "[", "&", "*", "!", "#"))):
                raise BenchmarkError("unsupported YAML scalar; use plain string list")
            if value.startswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise BenchmarkError("unsupported quoted YAML scalar") from exc
            elif value.startswith("'"):
                if not value.endswith("'") or len(value) < 2:
                    raise BenchmarkError("unclosed YAML scalar")
                value = value[1:-1].replace("''", "'")
            elif ": " in value or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
                raise BenchmarkError("finding must be a YAML string, not a mapping or number")
            if not isinstance(value, str) or not value.strip():
                raise BenchmarkError("finding must be a nonempty string")
            items.append(value)
        elif items and line.startswith("    ") and not line.lstrip().startswith(("-", "#", "discrepancies:")):
            items[-1] += " " + line.strip()
        else:
            raise BenchmarkError("unrecognized YAML response")
    if not items:
        raise BenchmarkError("empty YAML value is not an empty list")
    return [{"finding_id": f"F{i+1}", "text": x} for i, x in enumerate(items)]


def execute(manifest: dict, prompts: dict, command: list[str], timeout: int = 180,
            on_result=None) -> tuple[list, list]:
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
            status, findings, output, error, stderr = "COMPLETE", [], "", None, ""
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    command, input=indexed[(cid, arm)], text=True,
                    capture_output=True, timeout=timeout, check=False)
                output = completed.stdout
                stderr = completed.stderr
                if completed.returncode:
                    status = "FAILED"
                    error = f"model command exited {completed.returncode}"
                else:
                    findings = parse_yaml(output)
            except subprocess.TimeoutExpired as exc:
                output = (exc.stdout or b"")
                stderr = (exc.stderr or b"")
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
                status, error = "FAILED", "TimeoutExpired"
            except (OSError, UnicodeError) as exc:
                status, error = "FAILED", type(exc).__name__
            except BenchmarkError as exc:
                status, error = "ABSTAIN", str(exc)
            row = {
                "case_id": cid, "arm": arm, "manifest_sha256": sha,
                "rendered_prompt_sha256": cases[cid]["rendered_prompt_sha256"][arm],
                "model": manifest["model"], "model_revision": manifest["model_revision"],
                "decoding_config": manifest["decoding_config"], "status": status,
                "findings": findings, "latency_seconds": time.monotonic() - started}
            predictions.append(row)
            raw_outputs.append({**row, "raw_response": output, "raw_response_sha256": digest(output),
                                "stderr": stderr, "error": error})
            if on_result is not None:
                on_result(row, raw_outputs[-1])
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
    a.output.mkdir(parents=True)
    metadata = {"manifest_sha256": digest(canonical(manifest)),
                "command_sha256": digest(canonical(command)),
                "model_settings_verification": "caller-declared; not provider-attested",
                "state": "STARTED"}
    metadata_path = a.output / "execution.json"
    metadata_path.write_text(canonical(metadata) + "\n", encoding="utf-8")
    with (a.output / "predictions.jsonl").open("w", encoding="utf-8") as pred_file, \
            (a.output / "raw_outputs.jsonl").open("w", encoding="utf-8") as raw_file:
        def checkpoint(prediction, raw):
            pred_file.write(canonical(prediction) + "\n")
            pred_file.flush()
            raw_file.write(canonical(raw) + "\n")
            raw_file.flush()

        predictions, outputs = execute(manifest, prompts, command, a.timeout, checkpoint)
    metadata["state"] = "FINISHED"
    metadata["recorded_calls"] = len(predictions)
    metadata_path.write_text(canonical(metadata) + "\n", encoding="utf-8")
    print("Model responses recorded; no independent scientific adjudication performed")
    print(json.dumps({"total": len(predictions),
                      "complete": sum(x["status"] == "COMPLETE" for x in predictions),
                      "abstain": sum(x["status"] == "ABSTAIN" for x in predictions),
                      "failed": sum(x["status"] == "FAILED" for x in predictions)}))


if __name__ == "__main__":
    main()
