#!/usr/bin/env python3
"""Gate the local Overmind verifier-health canary on its *result*, not exit 0.

The pinned Overmind CLI emits JSON and returns exit 0 even when
meta-verify reports {"passed": false, ...}. This checks the synthetic
TruthCert fixture verdict; it is NOT a signature-verification or a
full Sentinel/Overmind/E156/Meta-Harness ecosystem canary.
"""
from __future__ import annotations

import json
import re
import sys


def _unique_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def is_certified(payload: object) -> bool:
    """Require an unambiguous successful verifier-health result."""
    return (
        type(payload) is dict
        and payload.get("passed") is True
        and payload.get("verdict") == "CERTIFIED"
        and isinstance(payload.get("bundle_hash"), str)
        # Overmind cert_bundle.py uses the first 16 lowercase SHA256 hex chars.
        and re.fullmatch(r"[0-9a-f]{16}", payload["bundle_hash"]) is not None
        and "alarm_written" not in payload
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin, object_pairs_hook=_unique_members)
    except (UnicodeError, ValueError):
        print("REFUSED: meta-verify output is not unambiguous JSON", file=sys.stderr)
        return 1
    if not is_certified(payload):
        print("REFUSED: meta-verify did not return passed=true, verdict=CERTIFIED and a valid bundle hash", file=sys.stderr)
        return 1
    print("meta-verify: CERTIFIED local verifier-health fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
