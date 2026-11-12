"""Optional Linux Docker worker; never falls back to executing task code on the host."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid

if __package__:
    from scripts import bounded_native, harness_context as context
else:
    import bounded_native
    import harness_context as context

Refused, require = context.Refused, context.require

# The supervisor is a trusted file. Submitted code is a separate Python process
# in the container, never interpolated into host commands or evaluated here.
SUPERVISOR = '''import json,os,resource,subprocess,sys,time
from pathlib import Path
settings=json.loads(Path('/inputs/_settings.json').read_text())
resource.setrlimit(resource.RLIMIT_FSIZE,(settings['output_bytes'],settings['output_bytes']))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
started=time.monotonic()
with open('/tmp/stdout','wb') as out, open('/tmp/stderr','wb') as err:
    child=subprocess.Popen([sys.executable,'-I','-B','/inputs/_task.py'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
    try: code=child.wait(timeout=settings['lifetime'])
    except subprocess.TimeoutExpired:
        child.kill(); child.wait(); code=124
Path('/tmp/result.json').write_text(json.dumps({'exit_code':code}))
# Keep tmpfs available for bounded retrieval, then exit even if the host dies.
time.sleep(max(0,settings['lifetime']+2-(time.monotonic()-started)))
'''


def policy_check(policy):
    require(isinstance(policy, dict) and set(policy) == {"image", "memory_mb", "cpus", "pids", "tmp_mb", "output_bytes"}, "worker policy fields mismatch")
    require(isinstance(policy["image"], str) and re.fullmatch(r"[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}", policy["image"]), "worker image requires exact digest")
    for key, low, high in (("memory_mb", 64, 4096), ("cpus", 1, 8), ("pids", 8, 256),
                           ("tmp_mb", 4, 256), ("output_bytes", 1024, 1048576)):
        context.integer(policy[key], key, low, high)


def execute(policy, root, manifest, selected, code, *, timeout=30):
    policy_check(policy)
    require(isinstance(code, str) and 0 < len(code.encode("utf-8")) <= 65536, "worker code limit")
    require(isinstance(timeout, (int, float)) and math.isfinite(timeout) and 1 <= timeout <= 300, "worker deadline invalid")
    executable = shutil.which("docker")
    require(executable is not None, "Docker is unavailable; host execution is forbidden")
    end = time.monotonic() + timeout
    work_end = end - min(2.0, timeout / 4)
    def docker(args, *, cleanup=False):
        remaining = (end if cleanup else work_end) - time.monotonic()
        require(remaining > 0, "worker deadline exceeded")
        try:
            return bounded_native.run([executable, *args], timeout=remaining)
        except bounded_native.Refused as exc:
            raise Refused("Docker operation refused or timed out") from exc
    info = context.strict_json(docker(["info", "--format", "{{json .}}"] ))
    require(info.get("OSType") == "linux" and info.get("MemoryLimit") is True
            and info.get("PidsLimit") is True and info.get("CpuCfsQuota") is True,
            "Linux Docker resource enforcement required")
    endpoint = context.strict_json(docker(["context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"] ))
    require(isinstance(endpoint, str) and endpoint.startswith(("unix://", "npipe://")), "remote Docker endpoint refused")
    digests = context.strict_json(docker(["image", "inspect", policy["image"], "--format", "{{json .RepoDigests}}"] ))
    require(isinstance(digests, list) and any(d.endswith(policy["image"].split("@", 1)[1]) for d in digests), "worker image unavailable or digest differs")
    nodes, _ = context.index(manifest)
    states = context.inspect(root, manifest)
    require(isinstance(selected, list) and selected and len(set(selected)) == len(selected), "worker selection required")
    name = "e156-worker-" + uuid.uuid4().hex
    created, removed = False, False
    with tempfile.TemporaryDirectory(prefix="e156-worker-") as directory:
        snapshot = Path(directory)
        require("," not in str(snapshot), "unsupported snapshot path")
        snapshot.chmod(0o755)
        total = 0
        for key in selected:
            require(key in nodes and nodes[key]["kind"] != "skill" and states[key]["status"] == "CURRENT", "worker evidence not current/allowed")
            raw = context.read_bytes(context.artifact(root, nodes[key]["file"]))
            require(hashlib.sha256(raw).hexdigest() == nodes[key]["sha256"], "worker evidence changed during snapshot")
            total += len(raw)
            require(total <= 32 * 1024 * 1024, "worker snapshot exceeds limit")
            target = snapshot / (key + ".data")
            target.write_bytes(raw)
            target.chmod(0o444)
        for filename, text in (("_task.py", code), ("_supervisor.py", SUPERVISOR),
                               ("_settings.json", json.dumps({"output_bytes": policy["output_bytes"], "lifetime": max(1, work_end - time.monotonic())}))):
            path = snapshot / filename
            path.write_text(text, encoding="utf-8")
            path.chmod(0o444)
        args = ["create", "--name", name, "--label", "e156-harness-worker=true", "--rm", "--init", "--pull=never",
                "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--user=65534:65534", "--memory=" + str(policy["memory_mb"]) + "m",
                "--memory-swap=" + str(policy["memory_mb"]) + "m", "--cpus=" + str(policy["cpus"]),
                "--pids-limit=" + str(policy["pids"]), "--log-driver=none", "--no-healthcheck",
                "--tmpfs=/tmp:rw,noexec,nosuid,nodev,mode=1777,nr_inodes=128,size=" + str(policy["tmp_mb"]) + "m",
                "--mount=type=bind,source=" + str(snapshot) + ",target=/inputs,readonly",
                "--env=PYTHONDONTWRITEBYTECODE=1", "--workdir=/tmp", "--entrypoint=python",
                policy["image"], "-I", "-B", "/inputs/_supervisor.py"]
        try:
            # Cleanup is attempted even if creation succeeded but its reply was lost.
            created = True
            docker(args)
            details = context.strict_json(docker(["inspect", name]))[0]
            host = details["HostConfig"]
            require(host["ReadonlyRootfs"] is True and host["NetworkMode"] == "none"
                    and host["Memory"] == policy["memory_mb"] * 1024 * 1024
                    and host["PidsLimit"] == policy["pids"] and host["NanoCpus"] == policy["cpus"] * 10**9,
                    "Docker did not apply required containment")
            docker(["start", name])
            status = None
            probe = "from pathlib import Path; p=Path('/tmp/result.json'); print(p.read_text() if p.exists() else '{}')"
            while time.monotonic() < work_end:
                status = context.strict_json(docker(["exec", name, "python", "-I", "-c", probe]))
                if "exit_code" in status:
                    break
                time.sleep(0.05)
            require(status is not None and status.get("exit_code") == 0, "worker failed or exceeded deadline")
            output = {}
            for stream in ("stdout", "stderr"):
                reader = "import sys; sys.stdout.buffer.write(open('/tmp/" + stream + "','rb').read(" + str(policy["output_bytes"] + 1) + "))"
                raw = docker(["exec", name, "python", "-I", "-c", reader])
                require(len(raw) < policy["output_bytes"], "worker output limit reached")
                output[stream] = raw.decode("utf-8", errors="replace")
        finally:
            if created:
                try:
                    docker(["rm", "--force", name], cleanup=True)
                except Refused:
                    # An exited --rm container may already be absent. Prove absence.
                    pass
                present = docker(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"], cleanup=True)
                require(not present.strip(), "worker cleanup could not be verified")
                removed = True
    return {"trust": "UNTRUSTED_WORKER_OUTPUT", "image": policy["image"], "container_removed": removed,
            "input_hashes": {key: nodes[key]["sha256"] for key in selected},
            "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(), **output}
