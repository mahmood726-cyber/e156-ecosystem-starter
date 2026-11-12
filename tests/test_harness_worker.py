"""Worker boundary contracts; actual containment is mandatory in dedicated Docker CI."""
import hashlib
import os
import subprocess

import pytest

from scripts import harness_context as context
from scripts import harness_worker as worker


@pytest.fixture
def bundle(tmp_path):
    raw = b"SYNTHETIC isolated evidence"
    (tmp_path / "paper.txt").write_bytes(raw)
    graph = {"schema": "e156-harness-context-v1", "nodes": [{"id": "paper", "kind": "source", "file": "paper.txt",
             "sha256": hashlib.sha256(raw).hexdigest(), "parents": [], "expires_at": None, "oa_rights_reference": "synthetic"}]}
    policy = {"image": os.environ.get("HARNESS_DOCKER_IMAGE", "python@sha256:" + "a" * 64),
              "memory_mb": 128, "cpus": 1, "pids": 32, "tmp_mb": 16, "output_bytes": 65536}
    return tmp_path, graph, policy


def test_no_docker_is_a_refusal_without_host_fallback(bundle, monkeypatch):
    root, graph, policy = bundle
    monkeypatch.setattr(worker.shutil, "which", lambda _: None)
    with pytest.raises(context.Refused, match="Docker"):
        worker.execute(policy, root, graph, ["paper"], "print('synthetic')", timeout=10)


@pytest.mark.parametrize("value", ["python:latest", "--privileged", "python@sha256:bad"])
def test_digest_pin_required(bundle, value):
    root, graph, policy = bundle
    policy["image"] = value
    with pytest.raises(context.Refused, match="digest"):
        worker.execute(policy, root, graph, ["paper"], "print('synthetic')", timeout=10)


def real_policy(bundle):
    if not os.environ.get("HARNESS_DOCKER_IMAGE"):
        pytest.skip("real Linux Docker gate runs in dedicated CI")
    return bundle


def test_real_worker_readonly_network_credentials_and_limits(bundle, monkeypatch):
    root, graph, policy = real_policy(bundle)
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-SECRET-CANARY")
    code = '''import os,socket
from pathlib import Path
assert "OPENAI_API_KEY" not in os.environ
assert Path("/inputs/paper.data").read_text()=="SYNTHETIC isolated evidence"
for p in ("/inputs/paper.data", "/root-write-test"):
    try: Path(p).write_text("changed")
    except OSError: pass
    else: raise RuntimeError("write boundary failed")
s=socket.socket(); s.settimeout(0.2)
try: s.connect(("198.51.100.1",443))
except OSError: pass
else: raise RuntimeError("network boundary failed")
assert Path("/sys/fs/cgroup/memory.max").read_text().strip()==str(128*1024*1024)
assert Path("/sys/fs/cgroup/pids.max").read_text().strip()=="32"
print("CONTAINMENT_CHECKED")
'''
    result = worker.execute(policy, root, graph, ["paper"], code, timeout=30)
    assert result["stdout"].strip() == "CONTAINMENT_CHECKED"
    assert result["container_removed"] is True
    assert (root / "paper.txt").read_text() == "SYNTHETIC isolated evidence"


def test_real_worker_output_overflow_refuses(bundle):
    root, graph, policy = real_policy(bundle)
    with pytest.raises(context.Refused):
        worker.execute(policy, root, graph, ["paper"], "print('x'*1000000)", timeout=20)


def test_real_worker_timeout_removes_its_container(bundle, monkeypatch):
    root, graph, policy = real_policy(bundle)
    commands = []
    original = worker.bounded_native.run
    def record(command, **kwargs):
        commands.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(worker.bounded_native, "run", record)
    with pytest.raises(context.Refused):
        worker.execute(policy, root, graph, ["paper"], "while True: pass", timeout=8)
    starts = [cmd for cmd in commands if len(cmd) > 2 and cmd[1] == "start"]
    assert starts, "deadline elapsed before worker execution; containment test was not exercised"
    name = starts[0][2]
    result = subprocess.run(["docker", "ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stdout.strip()
