"""Strict, offline source lock for four research components.

RapidMeta and AACT-kit consume this lock. Sentinel/Overmind retain their existing
installer defaults; --check validates both mirrors. Other layers are not locked
here yet. A commit identifies source; it is not a signature or dependency lock.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

DEFAULT_LOCK = Path(__file__).with_name("component-lock.json")
SCHEMA = "e156-component-lock-v1"
COMPONENTS = {"sentinel", "overmind", "rapidmeta", "aact-kit"}
SHA = re.compile(r"[0-9a-f]{40}")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate lock key: {key}")
        result[key] = value
    return result


def load_lock(path: Path = DEFAULT_LOCK) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    if not isinstance(payload, dict) or set(payload) != {"schema", "components"} or payload["schema"] != SCHEMA:
        raise ValueError("unsupported component lock schema")
    components = payload["components"]
    if not isinstance(components, dict) or set(components) != COMPONENTS:
        raise ValueError("component lock inventory mismatch")
    fields = {"repository", "commit", "python_min", "platforms", "verification", "source_note"}
    for name, entry in components.items():
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError(f"invalid lock fields: {name}")
        if not isinstance(entry["commit"], str) or not SHA.fullmatch(entry["commit"]):
            raise ValueError(f"not a full lowercase commit: {name}")
        if not isinstance(entry["repository"], str) or not re.fullmatch(
            r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", entry["repository"]
        ):
            raise ValueError(f"invalid repository URL: {name}")
        if not isinstance(entry["python_min"], str) or not re.fullmatch(r"3\.\d+", entry["python_min"]):
            raise ValueError(f"invalid Python floor: {name}")
        if (not isinstance(entry["platforms"], list) or not entry["platforms"]
                or any(p not in ("linux", "windows", "macos") for p in entry["platforms"])
                or len(set(entry["platforms"])) != len(entry["platforms"])):
            raise ValueError(f"invalid platforms: {name}")
        expected = {"rapidmeta": "rapidmeta-generator-v1", "aact-kit": "aact-source-and-backends-v1"}.get(name, "legacy-installer-pin-mirrors")
        if entry["verification"] != expected or not isinstance(entry["source_note"], str) or not entry["source_note"].strip():
            raise ValueError(f"invalid verification metadata: {name}")
    return components


def check_mirrors(root: Path, components: dict) -> None:
    for name in ("sentinel", "overmind"):
        patterns = {
            "sh": rf'(?m)^{name.upper()}_DEFAULT_REF="([0-9a-f]{{40}})"\s*$',
            "ps1": rf"(?m)^\$script:{name.capitalize()}DefaultRef = '([0-9a-f]{{40}})'\s*$",
        }
        for suffix, pattern in patterns.items():
            path = root / "scripts" / f"install-{name}.{suffix}"
            if re.findall(pattern, path.read_text(encoding="utf-8")) != [components[name]["commit"]]:
                raise ValueError(f"component lock differs from {path.name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--check", action="store_true", help="validate schema and frozen installer mirrors")
    parser.add_argument("--component", choices=sorted(COMPONENTS))
    parser.add_argument("--field", choices=("commit", "repository"))
    args = parser.parse_args(argv)
    try:
        components = load_lock(args.lock)
        if args.check:
            check_mirrors(args.lock.resolve().parent.parent, components)
            print("PASS: component lock schema and Sentinel/Overmind pin mirrors")
        elif args.component and args.field:
            print(components[args.component][args.field])
        else:
            parser.error("use --check or --component with --field")
    except (OSError, ValueError, TypeError) as exc:
        print(f"REFUSED: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
