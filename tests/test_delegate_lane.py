"""Tests for the delegated-lane kit: scripts/delegate-lane.py,
scripts/lane-status.py and scripts/cross-vendor-review.py.

No real model is called. A FAKE `codex` / `agy` executable is put first on
PATH; what it does is chosen by the FAKE_VENDOR_MODE environment variable.

House rule: BOTH directions. Each refusal (reuse, low disk, bad brief, lane
commit, a review finding with no failing input, a lane that ended with no
report) is paired with the good case passing, so neither a mechanism that
refuses everything nor one that refuses nothing gets through.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
DELEGATE = SCRIPTS / "delegate-lane.py"
STATUS = SCRIPTS / "lane-status.py"
REVIEW = SCRIPTS / "cross-vendor-review.py"
TEMPLATE = REPO_ROOT / "templates" / "LANE-BRIEF.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dl():
    return _load("delegate_lane", DELEGATE)


@pytest.fixture(scope="module")
def ls():
    return _load("lane_status", STATUS)


@pytest.fixture(scope="module")
def xvr():
    return _load("cross_vendor_review", REVIEW)


# --- fake vendor CLI --------------------------------------------------------

FAKE_VENDOR = r'''
import json, os, sys, time
mode = os.environ.get("FAKE_VENDOR_MODE", "report")
stdin_state = "STDIN-EOF" if sys.stdin is None or sys.stdin.read() == "" else "STDIN-HAD-DATA"
print("model: fake-vendor", flush=True)
print(stdin_state, flush=True)
print("argv:", json.dumps(sys.argv[1:]), flush=True)
if mode == "report":
    with open("LANE_REPORT.json", "w", encoding="utf-8") as f:
        json.dump({"lane": "x", "status": "DONE", "summary": "did it", "files_changed": [],
                   "commands_run": [], "blocked_reason": ""}, f)
    print("tokens used: 42", flush=True)
elif mode == "noreport":
    print("tokens used: 42", flush=True)
elif mode == "badreport":
    open("LANE_REPORT.json", "w").write("{not json")
    print("tokens used: 42", flush=True)
elif mode == "crash":
    sys.stdout.write("Traceback: boom\n")
    sys.exit(0)  # exits 0 on purpose: the status must not be judged from this
elif mode == "sleep":
    time.sleep(float(os.environ.get("FAKE_VENDOR_SLEEP", "30")))
elif mode == "review":
    print(open(os.environ["FAKE_REVIEW_RESPONSE"], encoding="utf-8").read())
elif mode == "garbage":
    print("I looked at it and it seems fine overall.")
'''


@pytest.fixture
def fake_path(tmp_path, monkeypatch):
    """A bin dir holding fake `codex` and `agy`, put first on PATH."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    (bindir / "fake_vendor.py").write_text(FAKE_VENDOR, encoding="utf-8")
    for name in ("codex", "agy"):
        if os.name == "nt":
            (bindir / f"{name}.cmd").write_text(
                f'@"{sys.executable}" "{bindir / "fake_vendor.py"}" %*\r\n', encoding="utf-8")
        else:
            exe = bindir / name
            exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bindir / "fake_vendor.py"}" "$@"\n',
                           encoding="utf-8")
            exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("E156_LANES_DIR", raising=False)
    return bindir


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    _git(r, "init", "-q")
    (r / "pool.py").write_text("def pool(xs):\n    return sum(xs) / len(xs)\n", encoding="utf-8")
    _git(r, "add", "-A")
    assert _git(r, "commit", "-q", "-m", "base").returncode == 0
    return r


@pytest.fixture
def brief(tmp_path):
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("<FILL: one or two sentences: what must be true when you are done>", "pool() handles []")
    text = text.replace("<FILL: list the files or directories, one per line>", "pool.py")
    text = text.replace('<FILL: what is out of scope, e.g. "do not refactor X", "do not touch CI">', "no refactors")
    text = text.replace("<FILL: e.g. python -m pytest tests/ -q>", "python -m pytest -q")
    p = tmp_path / "brief.md"
    p.write_text(text, encoding="utf-8")
    return p


def run_delegate(repo, lanes, brief, *extra, mode="report", vendor="codex"):
    env = dict(os.environ, FAKE_VENDOR_MODE=mode)
    return subprocess.run([sys.executable, str(DELEGATE), "--task", "t1", "--brief", str(brief),
                           "--vendor", vendor, "--repo", str(repo), "--lanes-dir", str(lanes), *extra],
                          capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)


def wait_ended(ls, lane, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = ls.lane_state(lane)
        if st["state"] not in ("RUNNING", "STALE"):
            return st
        time.sleep(0.3)
    raise AssertionError(f"lane {lane} still running after {timeout}s")


# --- template / brief -------------------------------------------------------

def test_template_carries_the_verbatim_rules_block(dl):
    assert dl.RULES_BLOCK in TEMPLATE.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_versions_are_declared(dl, ls, xvr):
    assert dl.VERSION == ls.VERSION == xvr.VERSION == "1.0.0"


def test_unfilled_template_is_refused(dl):
    problems = dl.check_brief(TEMPLATE.read_text(encoding="utf-8"))
    assert any("<FILL:" in p for p in problems)


def test_brief_with_edited_rules_block_is_refused(dl, brief):
    text = brief.read_text(encoding="utf-8").replace("ABORT RULE", "SUGGESTION")
    assert any("verbatim" in p for p in dl.check_brief(text))


def test_filled_brief_is_accepted(dl, brief):
    assert dl.check_brief(brief.read_text(encoding="utf-8")) == []


# --- delegate-lane.py -------------------------------------------------------

def test_good_launch_isolated_clone_stdin_closed_and_reported(fake_path, repo, brief, tmp_path, ls):
    lanes = tmp_path / "lanes"
    r = run_delegate(repo, lanes, brief, mode="report")
    assert r.returncode == 0, r.stderr
    lane = lanes / "t1"
    meta = json.loads((lane / ".lane" / "lane.json").read_text(encoding="utf-8"))
    assert meta["version"] == "1.0.0" and meta["pid"] > 0 and meta["vendor"] == "codex"
    assert meta["base"] == _git(repo, "rev-parse", "HEAD").stdout.strip()
    brief_text = (lane / "LANE_BRIEF.md").read_text(encoding="utf-8")
    assert "{BASE}" not in brief_text and meta["base"] in brief_text
    st = wait_ended(ls, lane)
    assert st["state"] == "ENDED-REPORTED", st
    log = (lane / ".lane" / "lane.log").read_text(encoding="utf-8")
    assert "STDIN-EOF" in log                       # stdin was closed, not inherited
    assert '"exec"' in log and "LANE_BRIEF.md" in log
    # the lane's files do not show up as changes in the clone
    assert _git(lane, "status", "--porcelain").stdout.strip() == ""
    # the source repo was not touched (no hook installed there)
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


def test_agy_vendor_uses_print(fake_path, repo, brief, tmp_path, ls):
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief, vendor="agy").returncode == 0
    st = wait_ended(ls, lanes / "t1")
    assert '"--print"' in (lanes / "t1" / ".lane" / "lane.log").read_text(encoding="utf-8")
    assert st["state"] == "ENDED-REPORTED"


def test_reuse_is_refused(fake_path, repo, brief, tmp_path, ls):
    """PLANTED DEFECT: a second lane pointed at an existing clone."""
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief).returncode == 0
    wait_ended(ls, lanes / "t1")
    before = (lanes / "t1" / ".lane" / "lane.json").read_text(encoding="utf-8")
    r = run_delegate(repo, lanes, brief)
    assert r.returncode == 2 and "never reused" in r.stderr
    assert (lanes / "t1" / ".lane" / "lane.json").read_text(encoding="utf-8") == before


def test_low_disk_is_refused_and_nothing_is_created(fake_path, repo, brief, tmp_path):
    """PLANTED DEFECT: 1 GB free with a 3 GB floor."""
    lanes = tmp_path / "lanes"
    r = run_delegate(repo, lanes, brief, "--free-bytes-override", str(1024 ** 3))
    assert r.returncode == 3 and "< 3 GB" in r.stderr
    assert not (lanes / "t1").exists()


def test_enough_disk_passes_the_floor(fake_path, repo, brief, tmp_path):
    lanes = tmp_path / "lanes"
    r = run_delegate(repo, lanes, brief, "--free-bytes-override", str(4 * 1024 ** 3))
    assert r.returncode == 0, r.stderr


def test_incomplete_brief_is_refused(fake_path, repo, tmp_path):
    lanes = tmp_path / "lanes"
    r = run_delegate(repo, lanes, TEMPLATE)
    assert r.returncode == 5 and "<FILL:" in r.stderr
    assert not (lanes / "t1").exists()


def test_missing_vendor_is_refused(repo, brief, tmp_path):
    git = shutil.which("git")
    assert git, "git is required for these tests"
    path = os.path.dirname(git)  # git reachable, no fake bin dir: `agy` is not on PATH
    if shutil.which("agy", path=path):
        pytest.skip("a real agy sits next to git on this machine")
    r = subprocess.run([sys.executable, str(DELEGATE), "--task", "t1", "--brief", str(brief),
                        "--vendor", "agy", "--repo", str(repo), "--lanes-dir", str(tmp_path / "lanes")],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env=dict(os.environ, PATH=path))
    assert r.returncode == 4 and "not found on PATH" in r.stderr
    assert not (tmp_path / "lanes" / "t1").exists()


def test_lane_commit_is_refused(fake_path, repo, brief, tmp_path, ls):
    """PLANTED DEFECT: the lane tries to commit its change."""
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief).returncode == 0
    lane = lanes / "t1"
    wait_ended(ls, lane)
    head = _git(lane, "rev-parse", "HEAD").stdout.strip()
    (lane / "pool.py").write_text("def pool(xs):\n    return 0\n", encoding="utf-8")
    _git(lane, "add", "pool.py")
    c = _git(lane, "commit", "-m", "lane commit")
    assert c.returncode != 0 and "lanes never commit" in c.stderr.lower()
    assert _git(lane, "rev-parse", "HEAD").stdout.strip() == head


def test_commit_in_an_ordinary_clone_still_works(repo):
    """The hook is lane-local: the user's own repo commits as before."""
    (repo / "pool.py").write_text("def pool(xs):\n    return sum(xs) / max(len(xs), 1)\n", encoding="utf-8")
    _git(repo, "add", "pool.py")
    assert _git(repo, "commit", "-q", "-m", "user commit").returncode == 0


# --- lane-status.py ---------------------------------------------------------

def test_ended_no_report_is_detected_and_ledgered(fake_path, repo, brief, tmp_path, ls):
    """PLANTED DEFECT: the CLI finishes ('tokens used') and exits 0 without a report."""
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief, mode="noreport").returncode == 0
    st = wait_ended(ls, lanes / "t1")
    assert st["state"] == "ENDED-NO-REPORT"
    r = subprocess.run([sys.executable, str(STATUS), "--lanes-dir", str(lanes)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 0 and "ENDED-NO-REPORT" in r.stdout
    rows = [json.loads(x) for x in (lanes / "harvest-ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["state"] == "ENDED-NO-REPORT"
    assert any("tokens used" in line for line in rows[0]["log_tail"])
    # a second look does not duplicate the row
    subprocess.run([sys.executable, str(STATUS), "--lanes-dir", str(lanes)], capture_output=True,
                   stdin=subprocess.DEVNULL)
    assert len((lanes / "harvest-ledger.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_unparseable_report_is_not_a_report(fake_path, repo, brief, tmp_path, ls):
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief, mode="badreport").returncode == 0
    st = wait_ended(ls, lanes / "t1")
    assert st["state"] == "ENDED-NO-REPORT" and not st["report_valid"]


def test_crash_that_exits_zero_is_died(fake_path, repo, brief, tmp_path, ls):
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief, mode="crash").returncode == 0
    assert wait_ended(ls, lanes / "t1")["state"] == "DIED"


def test_live_lane_is_running(fake_path, repo, brief, tmp_path, ls, monkeypatch):
    monkeypatch.setenv("FAKE_VENDOR_SLEEP", "20")
    lanes = tmp_path / "lanes"
    assert run_delegate(repo, lanes, brief, mode="sleep").returncode == 0
    lane = lanes / "t1"
    try:
        assert ls.lane_state(lane)["state"] == "RUNNING"
    finally:
        meta = json.loads((lane / ".lane" / "lane.json").read_text(encoding="utf-8"))
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(meta["pid"]), "/T", "/F"], capture_output=True)
        else:
            os.killpg(meta["pid"], 9)


def _fake_lane(tmp_path, vendor="codex", log="", report=None):
    lane = tmp_path / "lane"
    (lane / ".lane").mkdir(parents=True)
    (lane / ".lane" / "lane.log").write_text(log, encoding="utf-8")
    if report is not None:
        (lane / "LANE_REPORT.json").write_text(report, encoding="utf-8")
    (lane / ".lane" / "lane.json").write_text(json.dumps({
        "lane": "lane", "vendor": vendor, "pid": 999999,
        "log": str(lane / ".lane" / "lane.log"), "report": str(lane / "LANE_REPORT.json")}), encoding="utf-8")
    return lane


def test_silent_live_lane_is_stale(ls, tmp_path):
    lane = _fake_lane(tmp_path, log="model: x\n")
    log = lane / ".lane" / "lane.log"
    old = time.time() - 2000
    os.utime(log, (old, old))
    assert ls.lane_state(lane, stale_seconds=900, alive_fn=lambda pid: True)["state"] == "STALE"
    assert ls.lane_state(lane, stale_seconds=900, alive_fn=lambda pid: True,
                         now=old + 10)["state"] == "RUNNING"


def test_report_with_wrong_status_is_not_reported(ls, tmp_path):
    lane = _fake_lane(tmp_path, log="tokens used: 1\n", report='{"status": "PROBABLY-FINE"}')
    assert ls.lane_state(lane, alive_fn=lambda pid: False)["state"] == "ENDED-NO-REPORT"


def test_dead_pid_is_not_alive(ls):
    p = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL)
    p.wait()
    assert ls.pid_alive(p.pid) is False
    assert ls.pid_alive(os.getpid()) is True


# --- cross-vendor-review.py -------------------------------------------------

def _two_commits(repo):
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "pool.py").write_text("def pool(xs):\n    return sum(xs) / (len(xs) - 1)\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    return base, _git(repo, "rev-parse", "HEAD").stdout.strip()


GOOD = {"file": "pool.py", "severity": "P0", "claim": "Divides by n-1, so the mean is wrong.",
        "failing_input": "pool([2, 4])", "expected": "3.0", "actual": "6.0"}


def run_review(repo, base, head, out, response=None, mode="review"):
    env = dict(os.environ, FAKE_VENDOR_MODE=mode)
    if response is not None:
        rp = out.parent / "resp.json"
        rp.write_text(json.dumps(response), encoding="utf-8")
        env["FAKE_REVIEW_RESPONSE"] = str(rp)
    return subprocess.run([sys.executable, str(REVIEW), "--base", base, "--head", head, "--vendor", "codex",
                           "--repo", str(repo), "--out", str(out)],
                          capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)


def test_review_rejects_finding_without_failing_input(fake_path, repo, tmp_path):
    """PLANTED DEFECT: one finding with no reproduction, one with 'n/a', one good."""
    base, head = _two_commits(repo)
    out = tmp_path / "rev" / "review.jsonl"
    out.parent.mkdir()
    no_input = {k: v for k, v in GOOD.items() if k != "failing_input"}
    vague = dict(GOOD, failing_input="n/a")
    r = run_review(repo, base, head, out, {"findings": [GOOD, no_input, vague]})
    assert r.returncode == 0, r.stderr
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    run, findings = rows[0], rows[1:]
    assert run["kind"] == "run" and run["state"] == "REVIEWED" and run["base"] == base and run["head"] == head
    assert [f["status"] for f in findings] == ["PROPOSED", "REJECTED-NO-REPRO", "REJECTED-NO-REPRO"]
    assert "failing input" in findings[1]["reject_reason"]
    assert Path(run["raw_output"]).exists()
    # never applies anything
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head


@pytest.mark.parametrize("bad", ["", "   ", "N/A", "edge cases", "unknown", "tbd", "x"])
def test_vague_failing_inputs_are_rejected(xvr, bad):
    assert xvr.check_finding(dict(GOOD, failing_input=bad)) is not None


def test_concrete_finding_is_accepted(xvr):
    assert xvr.check_finding(GOOD) is None


def test_expected_equals_actual_is_rejected(xvr):
    assert xvr.check_finding(dict(GOOD, actual="3.0")) is not None


def test_unparseable_review_output_is_recorded_not_proposed(fake_path, repo, tmp_path):
    base, head = _two_commits(repo)
    out = tmp_path / "review.jsonl"
    r = run_review(repo, base, head, out, mode="garbage")
    assert r.returncode == 3
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["state"] == "NO-PARSEABLE-OUTPUT"


def test_empty_diff_is_refused(fake_path, repo, tmp_path):
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    out = tmp_path / "review.jsonl"
    r = run_review(repo, head, head, out, {"findings": []})
    assert r.returncode == 2 and "empty" in r.stderr
    assert not out.exists()


def test_extract_findings_takes_the_json_after_prose(xvr):
    text = 'thinking... {"note": 1}\n{"findings": [{"file": "a"}]}\ntokens used: 9'
    assert xvr.extract_findings(text) == {"findings": [{"file": "a"}]}
