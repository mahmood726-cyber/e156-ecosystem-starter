"""Shared RapidMeta install verifier for Bash and PowerShell (stdlib only).

Pins source and exercises the generator with synthetic controls. It does not
validate scientific findings, render a browser, or persist user configuration.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

if __package__:
    from .component_lock import DEFAULT_LOCK, load_lock
    from . import component_source as source
else:
    from component_lock import DEFAULT_LOCK, load_lock
    import component_source as source

InstallRefused = source.InstallRefused
run = source.run
linked = source.linked

ADAPTER = "rapidmeta-generator-v1"
SMOKE_TITLE = "SYNTHETIC INSTALL CHECK - NOT RESEARCH EVIDENCE"


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
    target, expected = source.prepare(target, component, adapter=ADAPTER, ref=ref, skip_clone=skip_clone)
    result = smoke(target)
    source.finish(target, component, expected)
    observed = expected
    return {"schema": "e156-component-install-v1", "component": "rapidmeta",
            "status": "verified", "adapter": ADAPTER,
            "source_verifier_sha256": source.source_verifier_hash(),
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
