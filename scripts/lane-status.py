#!/usr/bin/env python3
"""lane-status.py -- OPT-IN: say what a delegated lane (delegate-lane.py) is
doing, judged from the evidence it leaves on disk -- NEVER from an exit code.

A CLI that was left reading stdin exits 0 having done nothing; a wrapper that
"returned successfully" says nothing about the work. So a lane's state is read
from three things only: the report artefact, whether its pid is alive, and
whether its log is still growing.

STATES
    RUNNING          process alive and the log moved within --stale-seconds
                     (also: report written but the process is still closing)
    STALE            process alive but the log has not moved for --stale-seconds.
                     Investigate it; do not silently replace it.
    ENDED-REPORTED   process gone and LANE_REPORT.json parses with status
                     DONE or BLOCKED. Only this state means "there is a result".
    ENDED-NO-REPORT  process gone, the vendor CLI got to its end (codex: a
                     "tokens used" line; a vendor with no known end line: any
                     log output), but no valid report. Not done.
    DIED             process gone, no report, and no sign the CLI finished.

A report file that exists but is empty, unparseable, or lacks a DONE/BLOCKED
status counts as NO report.

THE LEDGER. Every lane that reaches a terminal state (ENDED-REPORTED,
ENDED-NO-REPORT, DIED) gets one row appended to a JSONL harvest ledger
(default <lanes-dir>/harvest-ledger.jsonl), once per lane and state. Rows for
lanes without a report carry the last 20 log lines, so the reason survives the
clone being deleted.

    python scripts/lane-status.py --lanes-dir ../<repo>-lanes
    python scripts/lane-status.py ../<repo>-lanes/fix-parser --json

Exit code: 0 when the lanes were read (whatever their states), 2 when a named
lane directory has no .lane/lane.json. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

VERSION = "1.0.0"

STATE_DIR = ".lane"
REPORT_NAME = "LANE_REPORT.json"
DEFAULT_STALE_SECONDS = 900
TERMINAL = ("ENDED-REPORTED", "ENDED-NO-REPORT", "DIED")
REPORT_STATUSES = ("DONE", "BLOCKED")
# A line each vendor CLI prints only when it has finished a run. A vendor not
# listed here has no known end line: any log output counts as "got to its end".
END_MARKERS = {"codex": ("tokens used",)}
TAIL_LINES = 20


def _utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pid_alive(pid: int) -> bool:
    """Is a process with this pid running? (A liveness probe, not an exit code.)"""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie (exited, not yet reaped) still answers kill(0): it has ended.
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as f:
            if f.read().rpartition(")")[2].split()[0] == "Z":
                return False
    except (OSError, IndexError):
        pass
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == 0
    except ChildProcessError:
        return True


def read_report(path: Path) -> tuple[bool, str]:
    """(valid, status-or-reason)."""
    if not path.exists():
        return False, "absent"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, f"unparseable: {e.__class__.__name__}"
    if not isinstance(data, dict):
        return False, "not a JSON object"
    status = data.get("status")
    if status not in REPORT_STATUSES:
        return False, f"status {status!r} is not one of {'/'.join(REPORT_STATUSES)}"
    return True, status


def lane_state(lane_dir: Path, stale_seconds: int = DEFAULT_STALE_SECONDS,
               alive_fn=pid_alive, now: float | None = None) -> dict:
    meta = json.loads((lane_dir / STATE_DIR / "lane.json").read_text(encoding="utf-8"))
    log = Path(meta.get("log") or lane_dir / STATE_DIR / "lane.log")
    report = Path(meta.get("report") or lane_dir / REPORT_NAME)
    pid = int(meta.get("pid") or 0)
    alive = alive_fn(pid)
    now = time.time() if now is None else now
    log_text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    log_age = (now - log.stat().st_mtime) if log.exists() else None
    report_ok, report_status = read_report(report)
    vendor = meta.get("vendor", "")
    markers = END_MARKERS.get(vendor)
    cli_finished = (any(m in log_text for m in markers) if markers is not None
                    else bool(log_text.strip()))
    if alive:
        state = "STALE" if (log_age is None or log_age > stale_seconds) and not report_ok else "RUNNING"
    elif report_ok:
        state = "ENDED-REPORTED"
    elif cli_finished:
        state = "ENDED-NO-REPORT"
    else:
        state = "DIED"
    return {
        "lane": meta.get("lane", lane_dir.name), "state": state, "vendor": vendor, "pid": pid,
        "pid_alive": alive, "clone": str(lane_dir), "log": str(log),
        "log_bytes": len(log_text.encode("utf-8")), "log_age_s": None if log_age is None else round(log_age),
        "report": str(report), "report_valid": report_ok, "report_status": report_status,
        "log_tail": log_text.splitlines()[-TAIL_LINES:] if state in ("ENDED-NO-REPORT", "DIED") else [],
    }


def _ledgered(ledger: Path) -> set[tuple[str, str, str]]:
    seen = set()
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            seen.add((row.get("clone", ""), row.get("lane", ""), row.get("state", "")))
    return seen


def append_ledger(ledger: Path, rows: list[dict]) -> int:
    seen = _ledgered(ledger)
    new = [r for r in rows if r["state"] in TERMINAL and (r["clone"], r["lane"], r["state"]) not in seen]
    if new:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8", newline="\n") as f:
            for r in new:
                f.write(json.dumps(dict(r, harvested_utc=_utc(), tool_version=VERSION), ensure_ascii=False) + "\n")
    return len(new)


def find_lanes(lanes_dir: Path) -> list[Path]:
    if not lanes_dir.is_dir():
        return []
    return sorted(p for p in lanes_dir.iterdir() if (p / STATE_DIR / "lane.json").exists())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lanes", nargs="*", type=Path, help="lane clone directories")
    ap.add_argument("--lanes-dir", type=Path, help="read every lane under this directory")
    ap.add_argument("--ledger", type=Path, help="harvest ledger (default <lanes-dir>/harvest-ledger.jsonl)")
    ap.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS)
    ap.add_argument("--json", action="store_true", help="print one JSON object per lane")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    a = ap.parse_args(argv)
    lanes = list(a.lanes)
    for lane in lanes:
        if not (lane / STATE_DIR / "lane.json").exists():
            print(f"ERROR: {lane} has no {STATE_DIR}/lane.json -- not a delegate-lane.py clone", file=sys.stderr)
            return 2
    if a.lanes_dir:
        lanes += find_lanes(a.lanes_dir)
    if not lanes:
        ap.error("name lane directories or --lanes-dir")
    ledger = a.ledger or ((a.lanes_dir or lanes[0].parent) / "harvest-ledger.jsonl")
    rows = [lane_state(p, a.stale_seconds) for p in lanes]
    added = append_ledger(ledger, rows)
    for r in rows:
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            extra = f" report={r['report_status']}" if r["state"] == "ENDED-REPORTED" else ""
            print(f"{r['state']:<16} {r['lane']} pid={r['pid']} log={r['log_bytes']}B{extra}")
    if not a.json:
        print(f"ledger: {ledger} (+{added} row(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
