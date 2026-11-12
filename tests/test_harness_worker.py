"""Worker boundary contracts; actual containment is mandatory in dedicated Docker CI."""
import hashlib
import json
import os
import subprocess
import sys
import time

import pytest

from scripts import harness_context as context
from scripts import harness_worker as worker


def test_native_transport_accepts_explicit_environment(monkeypatch):
    monkeypatch.setenv("HARNESS_PRIVATE_CANARY", "SYNTHETIC-SECRET")
    clean = {k: v for k, v in os.environ.items() if k != "HARNESS_PRIVATE_CANARY"}
    result = worker.bounded_native.run([sys.executable, "-I", "-c", "import os; print(os.environ.get('HARNESS_PRIVATE_CANARY','ABSENT'))"],
                                      environment=clean, timeout=10)
    assert result.strip() == b"ABSENT"


def test_real_worker_supervisor_status_and_proxy_boundary(bundle, monkeypatch, tmp_path):
    root, graph, policy = real_policy(bundle)
    docker_config = tmp_path / "docker-client"
    docker_config.mkdir()
    (docker_config / "config.json").write_text(json.dumps({"proxies": {"default": {
        "httpProxy": "http://SYNTHETIC-CREDENTIAL-CANARY@example.invalid:3128",
        "httpsProxy": "http://SYNTHETIC-CREDENTIAL-CANARY@example.invalid:3128"}}}), encoding="utf-8")
    monkeypatch.setenv("DOCKER_CONFIG", str(docker_config))
    code = '''import os,signal
from pathlib import Path
assert os.getuid()==65534 and os.getgid()==65534 and not os.getgroups()
assert 'SYNTHETIC-CREDENTIAL-CANARY' not in str(dict(os.environ))
for line in Path('/proc/self/status').read_text().splitlines():
    if line.startswith(('CapEff:', 'CapPrm:', 'CapInh:', 'CapAmb:')): assert int(line.split()[1],16)==0
try: os.kill(os.getppid(),signal.SIGSTOP)
except PermissionError: pass
else: raise RuntimeError('task can stop supervisor')
for path in ('/tmp/control/result.json','/tmp/control/stdout'):
    try: Path(path).write_text('forged')
    except PermissionError: pass
    else: raise RuntimeError('task can forge status/output')
try: os.mkfifo('/tmp/control/fifo')
except PermissionError: pass
else: raise RuntimeError('task can create control FIFO')
print('SUPERVISOR_BOUNDARY_CHECKED')
'''
    result = worker.execute(policy, root, graph, ["paper"], code, timeout=30)
    assert result["stdout"].strip() == "SUPERVISOR_BOUNDARY_CHECKED"


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
    starts = [cmd for cmd in commands if "start" in cmd]
    assert starts, "deadline elapsed before worker execution; containment test was not exercised"
    name = starts[0][starts[0].index("start") + 1]
    result = subprocess.run(["docker", "ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stdout.strip()


def test_real_worker_host_process_loss_expires_container(bundle, tmp_path):
    root, graph, policy = real_policy(bundle)
    marker = tmp_path / "started.json"
    request = tmp_path / "worker-request.json"
    request.write_text(json.dumps({"root": str(root), "graph": graph, "policy": policy, "marker": str(marker)}), encoding="utf-8")
    launcher = '''import json,os,sys
from pathlib import Path
from scripts import harness_worker as w
x=json.loads(Path(sys.argv[1]).read_text())
original=w.bounded_native.run
def terminate_after_start(command,**kwargs):
    result=original(command,**kwargs)
    if 'start' in command:
        Path(x['marker']).write_text(json.dumps({'name':command[command.index('start')+1]}))
        os._exit(19)
    return result
w.bounded_native.run=terminate_after_start
w.execute(x['policy'],Path(x['root']),x['graph'],['paper'],'while True: pass',timeout=10)
'''
    process = subprocess.run([sys.executable, "-c", launcher, str(request)], capture_output=True, timeout=20)
    assert process.returncode == 19 and marker.is_file(), process.stderr.decode(errors="replace")
    name = json.loads(marker.read_text())["name"]
    deadline = time.monotonic() + 18
    present = True
    try:
        while time.monotonic() < deadline:
            result = subprocess.run(["docker", "ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"],
                                    capture_output=True, text=True, timeout=5)
            assert result.returncode == 0
            present = bool(result.stdout.strip())
            if not present: break
            time.sleep(0.2)
        assert not present, "container outlived trusted supervisor TTL after host process loss"
    finally:
        if present:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=5)
