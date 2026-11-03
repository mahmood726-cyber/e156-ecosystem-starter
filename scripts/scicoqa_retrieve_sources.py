#!/usr/bin/env python3
"""Retrieve SciCoQA's versioned sources without executing third-party code.

Requires the v1.1 JSONL datasets from the pinned upstream source tree. Records
every download failure and hashes complete payloads; never fabricates contexts,
model responses or scientific labels. Resume rechecks every cached file hash.
Raw third-party assets belong outside the public repository.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

from scicoqa_paired_benchmark import BenchmarkError, canonical, read_jsonl

UPSTREAM_REF = "463162906459be508ed4a2294fcaede9fa072036"
DATASET_SHA256 = {
    "real": "78e1138f0b034ae8b52d5a60806c763f9ad2b1e1cdee55546d6db0721f195dc7",
    "synthetic": "7fccd1267c09ea8dc944cee996341e57931dcddcf086c600c1f8bc8c0f94fbdb"}
PINNED_CODE = re.compile(r"https://github.com/([^/]+)/([^/]+)/tree/([0-9a-fA-F]{40})/?")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(dataset_dir: Path, verify_hashes: bool = True) -> tuple[list[dict], dict]:
    assets: dict[str, dict] = {}
    datasets = {}
    for split in ("real", "synthetic"):
        path = dataset_dir / f"scicoqa-{split}-v1.1.jsonl"
        rows = read_jsonl(path)
        content_hash = sha256(path.read_bytes())
        if verify_hashes and content_hash != DATASET_SHA256[split]:
            raise BenchmarkError(f"{split} dataset bytes differ from pinned upstream release")
        datasets[split] = {"filename": path.name, "sha256": content_hash,
                           "reference_records": len(rows),
                           "paper_versions": len({r["paper_url_versioned"] for r in rows}),
                           "code_versions": len({r["code_url_versioned"] for r in rows})}
        for row in rows:
            paper = row["paper_url_versioned"]
            match = PINNED_CODE.fullmatch(row["code_url_versioned"])
            if not match or not isinstance(paper, str) or not paper.startswith("https://"):
                raise BenchmarkError("benchmark has an invalid versioned source URL")
            owner, repo, commit = match.groups()
            code = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{commit}"
            for kind, url in (("paper", paper), ("code", code)):
                key = sha256(url.encode())
                record = assets.setdefault(key, {
                    "asset_id": key, "kind": kind, "url": url,
                    "relative_path": f"assets/{key}." + ("pdf" if kind == "paper" else "tar.gz"),
                    "splits": [], "reference_record_count": 0})
                if split not in record["splits"]:
                    record["splits"].append(split)
                record["reference_record_count"] += 1
                if kind == "code":
                    record["code_commit"] = commit.lower()
    return sorted(assets.values(), key=lambda r: (r["kind"], r["url"])), datasets


def validate_payload(path: Path, asset: dict) -> None:
    if asset["kind"] == "paper":
        with path.open("rb") as stream:
            if not stream.read(1024).lstrip().startswith(b"%PDF-"):
                raise BenchmarkError("download is not a PDF")
    else:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise BenchmarkError("empty repository archive")
            roots = {PurePosixPath(m.name).parts[0] for m in members}
            if len(roots) != 1 or not next(iter(roots)).lower().endswith("-" + asset["code_commit"]):
                raise BenchmarkError("repository archive does not identify the pinned commit")
            if any(PurePosixPath(m.name).is_absolute() or ".." in PurePosixPath(m.name).parts
                   for m in members):
                raise BenchmarkError("unsafe repository archive path")


def retrieve(asset: dict, output: Path, timeout: int, max_bytes: int,
             previous: dict | None = None) -> dict:
    path = output / asset["relative_path"]
    started = datetime.now(timezone.utc).isoformat()
    if previous and previous.get("status") == "RETRIEVED" and path.is_file():
        if sha256(path.read_bytes()) == previous.get("sha256"):
            validate_payload(path, asset)
            return previous
        raise BenchmarkError(f"cached asset changed: {asset['asset_id']}")
    part = path.with_suffix(path.suffix + ".part")
    download_url = asset["url"]
    # Some upstream "versioned paper" fields link to an arXiv abstract page.
    # Resolve the same explicit edition to its PDF, never to the latest version.
    arxiv_abs = re.fullmatch(r"https://arxiv.org/abs/(\d{4}\.\d{4,5}v\d+)", download_url)
    if asset["kind"] == "paper" and arxiv_abs:
        download_url = "https://arxiv.org/pdf/" + arxiv_abs.group(1) + ".pdf"
    asset = {**asset, "download_url": download_url}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([
            "curl", "--fail", "--location", "--silent", "--show-error",
            "--max-time", str(timeout), "--max-filesize", str(max_bytes),
            "--user-agent", "SciCoQA-source-retrieval/1", "--output", str(part), download_url
        ], capture_output=True, text=True, timeout=timeout + 5, check=False)
        if result.returncode:
            raise BenchmarkError(f"curl exit {result.returncode}: {result.stderr.strip()}")
        total = part.stat().st_size
        if total > max_bytes:
            raise BenchmarkError("payload exceeds declared byte limit")
        validate_payload(part, asset)
        content_hash = sha256(part.read_bytes())
        part.replace(path)
        return {**asset, "status": "RETRIEVED", "bytes": total, "sha256": content_hash,
                "retrieved_at_utc": started}
    except (OSError, ValueError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        part.unlink(missing_ok=True)
        return {**asset, "status": "FAILED", "error": type(exc).__name__ + ": " + str(exc),
                "attempted_at_utc": started}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--timeout", type=int, default=45)
    p.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    args = p.parse_args()
    if not 1 <= args.workers <= 12 or args.timeout < 1 or args.max_bytes < 1:
        p.error("require 1..12 workers, positive timeout and byte limit")
    assets, datasets = inventory(args.dataset_dir)
    args.output.mkdir(parents=True, exist_ok=True)
    receipt_path = args.output / "retrieval.jsonl"
    previous = {}
    if receipt_path.exists() and receipt_path.stat().st_size:
        previous = {r["asset_id"]: r for r in read_jsonl(receipt_path)}
    (args.output / "inventory.json").write_text(json.dumps({
        "upstream_ref": UPSTREAM_REF, "dataset_version": "v1.1", "datasets": datasets,
        "assets": assets, "inference_calls": 0, "independent_human_reviews": 0}, indent=2) + "\n")
    # Append and flush each result so interruption cannot erase completed work.
    with receipt_path.open("a", encoding="utf-8") as receipt, ThreadPoolExecutor(args.workers) as pool:
        jobs = {pool.submit(retrieve, a, args.output, args.timeout, args.max_bytes,
                            previous.get(a["asset_id"])): a for a in assets}
        for i, job in enumerate(as_completed(jobs), 1):
            try:
                result = job.result()
            except BenchmarkError as exc:
                result = {**jobs[job], "status": "FAILED", "error": str(exc),
                          "attempted_at_utc": datetime.now(timezone.utc).isoformat()}
            receipt.write(canonical(result) + "\n")
            receipt.flush()
            print(f"{i}/{len(jobs)} {result['kind']} {result['status']} {result['url']}", flush=True)


if __name__ == "__main__":
    main()
