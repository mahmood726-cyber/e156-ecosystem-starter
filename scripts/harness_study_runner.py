"""Serial, durable development runner; no scientific validation or invoices.

Reservations are conservative configured ceilings, retained in full for the study.
E156 and the constrained native Pydantic path share task-scoped evidence tools.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import sysconfig
import tempfile
import threading
import time

if __package__:
    from scripts import harness_context as c, harness_runtime as runtime, harness_trace as trace
    from scripts import bounded_native, synthesis_study_preflight as preflight, synthesis_matched_eval as matched
else:
    import harness_context as c
    import harness_runtime as runtime
    import harness_trace as trace
    import bounded_native
    import synthesis_study_preflight as preflight
    import synthesis_matched_eval as matched

require, Refused, digest = c.require, c.Refused, c.digest
CONFIG_FIELDS = {"schema", "project_id", "context_sha256", "selected", "skills", "task", "task_kind",
                 "routes", "models", "limits", "worker", "request_policy"}
MODEL_FIELDS = {"model", "max_output_tokens", "input_microusd_per_million", "output_microusd_per_million",
                "price_reference", "price_expires_at"}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return c.strict_json(c.read_bytes(path))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_new(path, raw, *, temporary_dir=None):
    """Publish complete bytes without replacing an existing artifact."""
    path = c.guard(path)
    require(len(raw) <= c.MAX_FILE, "artifact exceeds bounded read size")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=c.guard(temporary_dir) if temporary_dir is not None else path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.link(temporary, path)  # Atomic, exclusive publication on supported filesystems.
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


def new_json(path, value):
    atomic_new(path, (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def case_id(protocol_sha256, arm_id, claim_id):
    return digest({"protocol_sha256": protocol_sha256, "arm_id": arm_id, "claim_id": claim_id})


def profile():
    extra = ("harness_study_runner.py", "harness_study_records.py", "harness_native_pydantic.py", "harness_native_environment.py", "synthesis_study_preflight.py", "synthesis_matched_eval.py")
    return {**runtime.profile(), **{n: sha((Path(__file__).parent / n).read_bytes()) for n in extra},
            "interpreter": {"implementation": sys.implementation.name, "version": list(sys.version_info),
                            "cache_tag": sys.implementation.cache_tag, "platform": sys.platform}}


def native_adapter():
    if __package__: from scripts import harness_native_pydantic
    else: import harness_native_pydantic
    return harness_native_pydantic


def native_loader(configs):
    """Private, explicit local loader binding; no site/.pth execution in children."""
    adapter = native_adapter()
    environment = adapter.environment()
    environment_sha256 = digest(environment)
    require(all(cfg["native_runtime"]["environment_sha256"] == environment_sha256 for cfg in configs), "native environment differs from frozen descriptor")
    executable = c.guard(sys.executable).resolve()
    prefix = c.guard(sys.prefix).resolve()
    purelib = c.guard(sysconfig.get_path("purelib")).resolve()
    require(sys.prefix != sys.base_prefix and executable.parent == prefix / "Scripts"
            and purelib == prefix / "Lib" / "site-packages" and purelib.is_dir(), "native runtime requires the supported Windows virtualenv layout")
    return {"schema": "e156-native-loader-v1", "python": str(executable), "prefix": str(prefix),
            "purelib": str(purelib), "environment_sha256": environment_sha256, "environment": environment}


def verify_native_loader(plan, *, child=False):
    loader = plan.get("native_loader")
    require(isinstance(loader, dict) and set(loader) == {"schema", "python", "prefix", "purelib", "environment_sha256", "environment"}
            and loader["schema"] == "e156-native-loader-v1", "native loader binding missing")
    require(digest(loader["environment"]) == loader["environment_sha256"], "native environment evidence changed")
    executable, prefix, purelib = (c.guard(loader[k]).resolve() for k in ("python", "prefix", "purelib"))
    require(executable == c.guard(sys.executable).resolve() and executable.parent == prefix / "Scripts"
            and (prefix / "pyvenv.cfg").is_file() and purelib == prefix / "Lib" / "site-packages" and purelib.is_dir(), "native loader path/interpreter changed")
    if child:
        require(sys.flags.isolated and sys.flags.no_site, "native child must retain isolated/no-site startup")
        require(str(purelib) not in sys.path, "native package path was loaded before verification")
        # Append after trusted scripts and stdlib; do not run site.addsitedir,
        # .pth files, user site packages or sitecustomize.
        sys.path.append(str(purelib))
    require(digest(native_adapter().environment()) == loader["environment_sha256"], "native installed environment changed")


@contextmanager
def lease(path):
    """OS lock, never reclaimed by PID or age; child owns its case lock."""
    path = c.guard(path)
    with path.open("a+b") as f:
        if f.seek(0, 2) == 0:
            f.write(b"0"); f.flush(); os.fsync(f.fileno())
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise Refused("study/case is already executing") from exc
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt": msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def model_contract(configs):
    return {cid: {"models": cfg["models"], "routes": cfg["routes"], "task_kind": cfg["task_kind"],
                  "request_policy": cfg["request_policy"], "parallel_tool_calls": False, "store": False,
                  "include": ["reasoning.encrypted_content"],
                  "omitted_provider_defaults": ["temperature", "top_p", "reasoning", "text", "prompt_cache_retention"]}
            for cid, cfg in configs.items()}


def tools_contract(configs, graphs, inputs):
    result = {}
    for cid, cfg in configs.items():
        nodes, _ = c.index(graphs[cid])
        packed = c.pack(inputs, graphs[cid], cfg["selected"], cfg["skills"], max_chars=cfg["limits"]["context_chars"])
        result[cid] = {"schemas": runtime.tool_schemas(packed["tools"]), "worker": cfg["worker"],
            "skills": [nodes[k] for k in sorted(cfg["skills"])], "limits": cfg["limits"],
            "system_sha256": sha(runtime.SYSTEM.encode()), "task_instruction_sha256": sha(cfg["task"].encode())}
    return result


def _config(cfg, graph, task, arm, protocol):
    require(isinstance(cfg, dict) and CONFIG_FIELDS <= set(cfg) <= CONFIG_FIELDS | {"progress_policy", "native_runtime"}, "unsupported concrete config fields")
    if arm["runtime"] == "pydantic": native_adapter().validate_config(cfg)
    else: require("native_runtime" not in cfg, "E156 arm cannot claim a native runtime")
    runtime.configuration(cfg, graph)
    require(cfg["worker"] is None, "first study runner supports read-only tools; worker must be null")
    require(cfg["request_policy"] == {"service_tier": "default"}, "explicit default service tier required")
    require(len(cfg["models"]) == 1 and len(cfg["routes"]) == 1
            and cfg["routes"][cfg["task_kind"]] == list(cfg["models"]), "one frozen model/route required")
    model = next(iter(cfg["models"].values()))
    require(set(model) == MODEL_FIELDS and model["model"] == arm["model_snapshot"], "model identity/settings mismatch")
    limits = cfg["limits"]
    require(limits["wall_ms"] > 0 and limits["wall_ms"] <= 300000, "case wall deadline must be 1..300000 ms")
    for field, cap in (("model_tokens", protocol["limits"]["model_tokens"]), ("tool_calls", protocol["limits"]["tool_calls"]),
                       ("wall_ms", int(Decimal(str(protocol["limits"]["wall_seconds"])) * 1000)),
                       ("cost_microusd", int(Decimal(str(protocol["limits"]["api_cost_usd"])) * 1000000))):
        require(limits[field] <= cap, "runtime exceeds common protocol cap")
    require(cfg["selected"] == [task["node_id"]] and isinstance(cfg["skills"], list)
            and len(cfg["skills"]) == len(set(cfg["skills"])), "task selection mismatch")
    nodes, _ = c.index(graph)
    require(all(set(nodes[key].get("tools", [])) <= {"read_evidence"} for key in cfg["skills"] if key in nodes),
            "first study runner supports read_evidence only")
    if arm["runtime"] == "pydantic":
        require({tool for key in cfg["skills"] if key in nodes for tool in nodes[key].get("tools", [])} == {"read_evidence"},
                "native comparator requires exactly read_evidence access")
    needed, pending = set(cfg["skills"]), list(cfg["selected"])
    while pending:
        key = pending.pop()
        require(key in nodes, "selected node missing")
        if key not in needed:
            needed.add(key); pending.extend(nodes[key]["parents"])
    require(needed == set(nodes), "context must contain only this task closure and authorized skills")


def _separate(work, *roots):
    work = c.guard(work).resolve()
    for value in roots:
        root = c.guard(value).resolve()
        require(work != root and work not in root.parents and root not in work.parents, "work and input/evidence roots must be separate")
    return work


def prepare(manifest, protocol, inventory, inputs, evidence, work, budget, mode, fixtures=None):
    ready = preflight.preflight(manifest, protocol, inventory, inputs, evidence)
    require(c.timestamp(protocol["frozen_at"]) <= datetime.now(timezone.utc), "protocol freeze is in the future")
    require(protocol["purpose"] in {"development", "synthetic_contract"}, "first runner path is development only")
    require(mode in {"LIVE", "SYNTHETIC_CONTRACT"}, "explicit execution mode required")
    require((fixtures is None) == (mode == "LIVE"), "live execution cannot consume scripted fixtures")
    runtime._numbers(budget)
    work = _separate(work, inputs, evidence)
    require(not work.exists(), "new work directory required")
    graphs = {}
    for task in inventory["tasks"]:
        raw = c.read_bytes(c.artifact(evidence, task["context_file"]))
        require(sha(raw) == task["context_sha256"], "context changed after preflight")
        graphs[task["claim_id"]] = c.strict_json(raw)
    tasks = {t["claim_id"]: t for t in inventory["tasks"]}
    configs, cases, native_configs = {}, {}, []
    for arm in protocol["arms"]:
        require(arm["runtime"] in {"e156", "pydantic"}, "unsupported runtime")
        expected_profile = runtime.profile() if arm["runtime"] == "e156" else native_adapter().profile()
        require(arm["runtime_version"] == digest(expected_profile), "unsupported runtime/version")
        mapping = next(a for a in inventory["arms"] if a["arm_id"] == arm["arm_id"])
        artifact = read(c.artifact(evidence, mapping["config_file"]))
        require(digest(artifact) == arm["config_sha256"], "arm config changed after preflight")
        require(set(artifact) == {"schema", "runtime_profile", "configurations"}
                and artifact["schema"] == "e156-study-arm-configs-v1" and artifact["runtime_profile"] == runtime.profile(), "arm configuration schema/profile mismatch")
        cfgs = artifact["configurations"]
        require(isinstance(cfgs, dict) and set(cfgs) == set(tasks), "concrete case config inventory mismatch")
        for cid, cfg in cfgs.items(): _config(cfg, graphs[cid], tasks[cid], arm, protocol)
        require(digest(model_contract(cfgs)) == arm["model_config_sha256"], "actual model contract mismatch")
        require(digest(tools_contract(cfgs, graphs, inputs)) == arm["tools_sha256"], "actual tools/instruction/cap contract mismatch")
        configs[arm["arm_id"]] = cfgs
        if arm["runtime"] == "pydantic": native_configs.extend(cfgs.values())
        for cid, cfg in cfgs.items():
            key = case_id(digest(protocol), arm["arm_id"], cid)
            cases[key] = {"arm_id": arm["arm_id"], "claim_id": cid, "runtime": arm["runtime"], "config": cfg, "context": graphs[cid]}
    loader = native_loader(native_configs) if native_configs else None
    schedule = [case_id(digest(protocol), r["arm_id"], r["claim_id"]) for r in matched.prepare(manifest, protocol, inputs)["schedule"]]
    require(0 < len(schedule) <= 1000, "study case bound exceeded")
    if fixtures is not None:
        require(isinstance(fixtures, dict) and set(fixtures) == set(cases), "scripted fixture inventory mismatch")
        for fixture in fixtures.values():
            require(isinstance(fixture, dict) and set(fixture) == {"input_tokens", "responses"}
                    and isinstance(fixture["responses"], list) and fixture["responses"], "invalid scripted fixture")
            c.integer(fixture["input_tokens"], "synthetic input tokens")
    plan = {"schema": "e156-study-plan-v1", "status": "PREPARED_NOT_RUN", "manifest": manifest, "protocol": protocol,
        "preflight_sha256": digest(ready), "inventory_sha256": digest(inventory), "budget": budget, "mode": mode,
        "profile": profile(), "cases": cases, "schedule": schedule, "created_at": now(),
        "budget_basis": "FULL_CASE_CEILINGS_NEVER_REFUNDED_NOT_INVOICES", "scientific_results": None}
    if loader is not None: plan["native_loader"] = loader
    work.mkdir()
    for key, case in cases.items():
        directory = work / "cases" / key; (directory / "inputs").mkdir(parents=True)
        files = {}
        for node in case["context"]["nodes"]:
            files[node["file"]] = node["sha256"]
            if "derivation" in node:
                for kind in ("recipe", "receipt"):
                    files[node["derivation"][kind + "_file"]] = node["derivation"][kind + "_sha256"]
        for name, expected in files.items():
            raw = c.read_bytes(c.artifact(inputs, name))
            require(sha(raw) == expected, "source changed while staging")
            dest = c.artifact(directory / "inputs", name); dest.parent.mkdir(parents=True, exist_ok=True)
            atomic_new(dest, raw)
        case["files"] = files
        for name, value in (("config.json", case["config"]), ("context.json", case["context"])):
            new_json(directory / name, value)
        if fixtures is not None:
            new_json(directory / "fixture.json", fixtures[key])
            case["fixture_sha256"] = digest(fixtures[key])
    require(profile() == plan["profile"], "producer changed during preparation")
    new_json(work / "plan.json", plan)
    new_json(work / "state.json", {"schema": "e156-study-state-v1", "plan_sha256": digest(plan), "cases": {}, "frozen": False})
    return plan


def _load(work):
    work = c.guard(work)
    plan, state = read(work / "plan.json"), read(work / "state.json")
    require(plan.get("schema") == "e156-study-plan-v1" and state.get("schema") == "e156-study-state-v1"
            and digest(plan) == state["plan_sha256"] and plan["profile"] == profile(), "study/code binding mismatch")
    require(not state["frozen"], "study is frozen")
    require(set(state["cases"]) <= set(plan["cases"]), "unknown case state")
    require(type(state["frozen"]) is bool, "invalid freeze state")
    for key, item in state["cases"].items():
        require(isinstance(item, dict) and item.get("status") in {"RESERVED", "DISPATCHED", "UNRESOLVED", "FINISHED"}, "invalid case state")
        c.integer(item.get("dispatches"), "dispatches")
        runtime._numbers(item["reserved"])
        limits = plan["cases"][key]["config"]["limits"]
        expected = {k: limits[k] for k in runtime.RESOURCES}
        require(item["reserved"] == expected or (item["dispatches"] == 0 and item["status"] == "FINISHED"
                and item["reserved"] == runtime.units()), "case reservation mismatch")
        began = c.timestamp(item["started_at"])
        require(c.timestamp(item["deadline_at"]) == began + timedelta(milliseconds=limits["wall_ms"]), "case deadline changed")
        if item["status"] in {"FINISHED", "UNRESOLVED"}:
            require({"record_file", "record_sha256"} <= set(item), "settled case lacks record")
    require(all(sum(row["reserved"][k] for row in state["cases"].values()) <= plan["budget"][k]
                for k in runtime.RESOURCES), "aggregate reservation exceeds cap")
    return work, plan, state


def _case_files(work, key, case):
    directory = c.artifact(work, "cases/" + key)
    require(read(directory / "config.json") == case["config"] and read(directory / "context.json") == case["context"], "case configuration changed")
    for name, expected in case["files"].items():
        require(sha(c.read_bytes(c.artifact(directory / "inputs", name))) == expected, "staged input changed")
    if "fixture_sha256" in case:
        require(digest(read(directory / "fixture.json")) == case["fixture_sha256"], "script changed")
    return directory


def _case_record(plan, key, item, ended, outcome):
    case = plan["cases"][key]
    return {"schema": "e156-study-case-v1", "case_id": key, "protocol_sha256": digest(plan["protocol"]),
            "arm_id": case["arm_id"], "claim_id": case["claim_id"], "config_sha256": digest(case["config"]),
            "context_sha256": digest(case["context"]), "started_at": item["started_at"], "ended_at": ended,
            "dispatches": item["dispatches"], "outcome": outcome, "execution_mode": plan["mode"]}


def _retain(work, plan, state, key, item, report, outcome, ended=None):
    ended = ended or now()
    case = _case_record(plan, key, item, ended, outcome)
    value = {"case": case, "report": report}
    name = f"cases/{key}/record-{digest(value)}.json"
    path = c.artifact(work, name)
    if path.exists(): require(read(path) == value, "immutable record changed")
    else: new_json(path, value)
    item["record_file"], item["record_sha256"] = name, digest(value)
    item["status"] = "UNRESOLVED" if outcome == "RETURNED" and report and report["status"] == "UNRESOLVED" else "FINISHED"
    c.atomic_json(work / "state.json", state)
    return {"status": "CASE_RECORDED", "case_id": key, "runtime_status": report["status"] if report else outcome}


def _settle(work, plan, state, key, item, directory):
    value = read(directory / f"attempt-{item['dispatches']}.json")
    require(set(value) == {"report", "ended_at"}, "child result mismatch")
    report = value["report"]; trace.validate(report)
    cfg, graph = plan["cases"][key]["config"], plan["cases"][key]["context"]
    if "native_runtime" in cfg: native_adapter().validate_report(report, cfg)
    journal = runtime.Journal(directory / "run.sqlite", cfg, graph, directory / "inputs")
    require(report["events"] == journal.events(), "child result is not the current journal")
    ended = c.timestamp(value["ended_at"])
    require(c.timestamp(item["started_at"]) <= ended <= datetime.now(timezone.utc), "invalid child end time")
    outcome = "RETURNED" if ended <= c.timestamp(item["deadline_at"]) else "DEADLINE"
    return _retain(work, plan, state, key, item, report, outcome, value["ended_at"])


def settle(work, key):
    """Retain a completed child result after parent loss, without executing code."""
    with lease(c.guard(work) / "study.lock"):
        work, plan, state = _load(work)
        require(key in state["cases"] and state["cases"][key]["status"] == "DISPATCHED", "no unsettled dispatch")
        directory = _case_files(work, key, plan["cases"][key])
        with lease(directory / "case.lock"):
            return _settle(work, plan, state, key, state["cases"][key], directory)


def execute(work, *, allow_paid=False, resume=None):
    with lease(c.guard(work) / "study.lock"):
        work, plan, state = _load(work)
        if plan["mode"] == "LIVE":
            runtime.Responses(allow_paid=allow_paid)  # Gate before reserving or launching.
        pending = [k for k, row in state["cases"].items() if row["status"] != "FINISHED"]
        if pending and resume is None:
            return {"status": "EXECUTION_UNKNOWN", "case_id": pending[0]}
        if resume is not None:
            require(pending == [resume], "resume must name the single unresolved case")
            key = resume
        else:
            key = next((k for k in plan["schedule"] if k not in state["cases"]), None)
            if key is None: return {"status": "EXECUTION_COMPLETE"}
        case = plan["cases"][key]; directory = _case_files(work, key, case)
        if case["runtime"] == "pydantic": verify_native_loader(plan)
        with lease(directory / "case.lock"):
            if resume is not None:
                item = state["cases"][key]
                if item["status"] == "DISPATCHED" and (directory / f"attempt-{item['dispatches']}.json").exists():
                    return _settle(work, plan, state, key, item, directory)
                require(item["dispatches"] == 0 or (directory / "run.sqlite").is_file(), "unknown dispatch without journal cannot be retried")
            else:
                reserve = {k: case["config"]["limits"][k] for k in runtime.RESOURCES}
                used = {k: sum(row["reserved"][k] for row in state["cases"].values()) for k in runtime.RESOURCES}
                if any(used[k] + reserve[k] > plan["budget"][k] for k in used): return {"status": "STUDY_BUDGET_STOP"}
                started = now()
                item = {"started_at": started, "deadline_at": (c.timestamp(started) + timedelta(milliseconds=reserve["wall_ms"])).isoformat(),
                        "reserved": reserve, "dispatches": 0, "status": "RESERVED"}
                state["cases"][key] = item
                c.atomic_json(work / "state.json", state)  # Durable before any dispatch.
            remaining = (c.timestamp(item["deadline_at"]) - datetime.now(timezone.utc)).total_seconds()
            require(remaining > 0, "original case deadline expired; abort or retain evidence")
            item["dispatches"] += 1; item["status"] = "DISPATCHED"
            c.atomic_json(work / "state.json", state)
            output = directory / f"attempt-{item['dispatches']}.json"
        # The child obtains the same case lock and holds it for its actual life.
        launcher = "import sys; sys.path.insert(0,sys.argv.pop(1)); from scripts import harness_study_runner; harness_study_runner.main()"
        command = [sys.executable, "-I", "-S", "-c", launcher, str(Path(__file__).absolute().parent.parent), "_child", "--work", str(directory),
                   "--mode", plan["mode"], "--deadline", item["deadline_at"], "--output", str(output)]
        if plan["mode"] == "LIVE": command.append("--allow-paid")
        env_keys = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "COMSPEC", "LOCALAPPDATA", "APPDATA"}
        environment = {k: v for k, v in os.environ.items() if k.upper() in env_keys}
        if plan["mode"] == "LIVE": environment["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        try:
            bounded_native.run(command, timeout=remaining, environment=environment)
        except bounded_native.Refused:
            # No result is never an implicit permission to dispatch again.
            return {"status": "EXECUTION_UNKNOWN", "case_id": key}
        with lease(directory / "case.lock"):
            return _settle(work, plan, state, key, item, directory)


class _Script:
    def __init__(self, fixture, position): self.fixture, self.position = fixture, position
    def count(self, payload, timeout): return {"input_tokens": self.fixture["input_tokens"]}
    def respond(self, payload, timeout):
        require(self.position < len(self.fixture["responses"]), "script exhausted")
        value = self.fixture["responses"][self.position]; self.position += 1
        if value == {"synthetic_timeout": True}: raise TimeoutError("synthetic unknown response")
        if isinstance(value, dict) and set(value) == {"synthetic_sleep_ms", "response"}:
            c.integer(value["synthetic_sleep_ms"], "synthetic delay")
            require(value["synthetic_sleep_ms"] <= 10000, "synthetic delay exceeds test bound")
            time.sleep(value["synthetic_sleep_ms"] / 1000)
            value = value["response"]
        return value


class _Deadline:
    def __init__(self, provider, deadline): self.provider, self.deadline = provider, c.timestamp(deadline)
    def _call(self, name, payload, timeout):
        remaining = (self.deadline - datetime.now(timezone.utc)).total_seconds()
        require(remaining > 0, "original deadline expired")
        result = getattr(self.provider, name)(payload, min(timeout, remaining))
        if name == "respond":
            if not isinstance(result, dict) or result.get("model") != payload["model"] or result.get("service_tier") != "default":
                raise runtime.ReceivedInvalid(result)
        return result
    def count(self, payload, timeout): return self._call("count", payload, timeout)
    def respond(self, payload, timeout): return self._call("respond", payload, timeout)


def child(directory, mode, deadline, output, *, allow_paid=False):
    remaining = (c.timestamp(deadline) - datetime.now(timezone.utc)).total_seconds()
    require(remaining > 0, "original deadline expired")
    # Arm before opening snapshots. The timer survives parent loss and bounds
    # validation too. Provider children separately own their transport deadline.
    watchdog = threading.Timer(remaining, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    try:
        return _child_checked(directory, mode, deadline, output, allow_paid=allow_paid)
    finally:
        watchdog.cancel()


def _child_checked(directory, mode, deadline, output, *, allow_paid=False):
    directory = c.guard(directory)
    require(mode in {"LIVE", "SYNTHETIC_CONTRACT"}, "child execution mode required")
    require(c.guard(output).parent.resolve() == directory.resolve(), "child output must stay inside case directory")
    with lease(directory / "case.lock"):
        work, plan, state = _load(directory.parent.parent)
        key = directory.name
        require(key in state["cases"] and state["cases"][key]["status"] == "DISPATCHED", "child dispatch is no longer authorized")
        item = state["cases"][key]
        require(mode == plan["mode"] and deadline == item["deadline_at"] and c.guard(output).name == f"attempt-{item['dispatches']}.json",
                "stale child dispatch")
        case = plan["cases"][key]
        require(directory.resolve() == _case_files(work, key, case).resolve(), "child case directory mismatch")
        cfg, graph = case["config"], case["context"]
        db = directory / "run.sqlite"
        position = 0
        if db.exists():
            journal = runtime.Journal(db, cfg, graph, directory / "inputs")
            position = sum(k.startswith("model:") and op["finish"] is not None and op["finish"]["kind"] in {"FINISHED", "RECONCILED"}
                           for k, op in journal.operations(journal.events()).items())
        provider = runtime.Responses(allow_paid=allow_paid) if mode == "LIVE" else _Script(read(directory / "fixture.json"), position)
        executor = runtime.run
        if case["runtime"] == "pydantic":
            verify_native_loader(plan, child=True)
            executor = native_adapter().run
        report = executor(cfg, graph, directory / "inputs", db, provider=_Deadline(provider, deadline), create=not db.exists())
        new_json(output, {"report": report, "ended_at": now()})


def reconcile(work, key, receipt):
    with lease(c.guard(work) / "study.lock"):
        work, plan, state = _load(work)
        require(key in state["cases"] and state["cases"][key]["status"] != "FINISHED", "case is not unresolved")
        case = plan["cases"][key]; directory = _case_files(work, key, case)
        with lease(directory / "case.lock"):
            item = state["cases"][key]
            if item["status"] == "DISPATCHED" and (directory / f"attempt-{item['dispatches']}.json").exists():
                _settle(work, plan, state, key, item, directory)
                require(item["status"] == "UNRESOLVED", "settled case does not require reconciliation")
            require(isinstance(receipt, dict) and isinstance(receipt.get("response"), dict)
                    and receipt["response"].get("model") == next(iter(case["config"]["models"].values()))["model"]
                    and receipt["response"].get("service_tier") == "default", "recovered model/tier mismatch")
            return runtime.Journal(directory / "run.sqlite", case["config"], case["context"], directory / "inputs").reconcile(receipt)


def abort(work):
    """Explicitly retain unfinished slots; no new calls and no lost denominator."""
    with lease(c.guard(work) / "study.lock"):
        work, plan, state = _load(work)
        for key in plan["schedule"]:
            if key in state["cases"] and state["cases"][key]["status"] == "FINISHED": continue
            directory = _case_files(work, key, plan["cases"][key])
            with lease(directory / "case.lock"):
                item = state["cases"].get(key)
                if item is None:
                    started = now()
                    item = {"started_at": started, "reserved": runtime.units(), "dispatches": 0,
                            "deadline_at": (c.timestamp(started) + timedelta(milliseconds=plan["cases"][key]["config"]["limits"]["wall_ms"])).isoformat()}
                    state["cases"][key] = item
                if item.get("status") == "DISPATCHED" and (directory / f"attempt-{item['dispatches']}.json").exists():
                    _settle(work, plan, state, key, item, directory)
                    if item["status"] == "FINISHED": continue
                report = None
                if (directory / "run.sqlite").exists():
                    case = plan["cases"][key]
                    report = runtime.Journal(directory / "run.sqlite", case["config"], case["context"], directory / "inputs").report("UNRESOLVED")
                    if case["runtime"] == "pydantic":
                        report = native_adapter().describe_report(report, case["config"], termination="INTERRUPTED")
                outcome = "NOT_ATTEMPTED" if item["dispatches"] == 0 else (
                    "DEADLINE" if datetime.now(timezone.utc) >= c.timestamp(item["deadline_at"]) else "INTERRUPTED")
                _retain(work, plan, state, key, item, report, outcome)
        return {"status": "STUDY_ABORT_RECORDED"}


def _records(work, plan, state):
    if __package__: from scripts import harness_study_records as bridge
    else: import harness_study_records as bridge
    require(set(state["cases"]) == set(plan["cases"]), "all planned slots must have execution or abort records")
    result = {}
    for key, case in plan["cases"].items():
        item = state["cases"][key]
        require("record_file" in item, "case evidence is incomplete")
        value = read(c.artifact(work, item["record_file"]))
        require(digest(value) == item["record_sha256"], "case record changed")
        require(value["case"] == _case_record(plan, key, item, value["case"]["ended_at"], value["case"]["outcome"]), "case lifecycle binding mismatch")
        directory = _case_files(work, key, case)
        with lease(directory / "case.lock"):
            if (directory / "run.sqlite").exists():
                require(value["report"] is not None and value["report"]["events"] == runtime.Journal(
                    directory / "run.sqlite", case["config"], case["context"], directory / "inputs").events(), "record differs from current journal")
            else: require(value["report"] is None, "record journal missing")
        arm = next(a for a in plan["protocol"]["arms"] if a["arm_id"] == case["arm_id"])
        task = next(t for t in plan["protocol"]["tasks"] if t["claim_id"] == case["claim_id"])
        args = (value["case"], value["report"], case["config"], case["context"], arm, task, digest(plan["protocol"]))
        result[key] = (args, bridge.draft(*args))
    return result


def records(work):
    with lease(c.guard(work) / "study.lock"):
        work, plan, state = _load(work)
        return {k: d for k, (_, d) in _records(work, plan, state).items()}


def exact_export_inventory(bundle, file_hashes):
    """Reject every unmanifested entry, including empty directories and links."""
    bundle = c.guard(bundle)
    expected_directories = set()
    for name in file_hashes:
        expected_directories.update(p.as_posix() for p in Path(name).parents if p != Path("."))
    seen_files, seen_directories = set(), set()
    pending = [bundle]
    while pending:
        for candidate in pending.pop().iterdir():
            entry = c.guard(candidate)
            name = entry.relative_to(bundle).as_posix()
            if entry.is_dir():
                require(name in expected_directories, "unexpected export entry")
                seen_directories.add(name); pending.append(entry)
            else:
                require(entry.is_file() and name in file_hashes, "unexpected export entry")
                require(sha(c.read_bytes(entry)) == file_hashes[name], "export bytes changed")
                seen_files.add(name)
    require(seen_files == set(file_hashes) and seen_directories == expected_directories, "export inventory incomplete")


def freeze(work, measurements):
    if __package__: from scripts import harness_study_records as bridge
    else: import harness_study_records as bridge
    with lease(c.guard(work) / "study.lock"):
        work, plan, state = _load(work)
        rows = _records(work, plan, state)
        require(isinstance(measurements, dict) and set(measurements) == set(rows), "complete measured review inventory required")
        require(all(row["status"] == "FINISHED" for row in state["cases"].values()), "unresolved case cannot be frozen")
        final = [bridge.finalize(*args, measurements[key]) for key, (args, _) in rows.items()]
        generation = digest({"plan_sha256": digest(plan), "measurements": measurements,
                             "records": {key: row["record_sha256"] for key, row in state["cases"].items()}})
        staging = c.artifact(work, "exports/" + generation)
        destination = work / "frozen"
        adopting = destination.exists()
        if adopting:
            require(read(destination / "receipt.json")["generation"] == generation, "different export already published")
        staging.mkdir(parents=True, exist_ok=True)
        intent_path = staging / "intent.json"
        if not intent_path.exists():
            require(not adopting, "published export lacks original intent")
            new_json(intent_path, {"generation": generation, "frozen_at": now()})
        intent = read(intent_path)
        require(set(intent) == {"generation", "frozen_at"} and intent["generation"] == generation, "freeze intent mismatch")
        frozen_at = c.timestamp(intent["frozen_at"])
        require(frozen_at <= datetime.now(timezone.utc), "freeze intent is in the future")
        require(all(c.timestamp(m["observed_at"]) <= frozen_at for m in measurements.values()), "measurement postdates freeze")
        runs = {"schema": "synthesis-matched-runs-v1", "protocol_sha256": digest(plan["protocol"]),
                "frozen_at": intent["frozen_at"], "records": [row["record"] for row in final]}
        bundle = destination if adopting else staging / "bundle"
        bundle.mkdir(exist_ok=True)
        file_hashes = {}
        def retain(name, raw):
            path = c.artifact(bundle, name)
            if path.exists(): require(c.read_bytes(path) == raw, "partial/frozen export changed")
            else:
                require(not adopting, "published export file missing")
                path.parent.mkdir(parents=True, exist_ok=True)
                # Interrupted temporary writes remain outside the publication.
                atomic_new(path, raw, temporary_dir=staging)
            file_hashes[name] = sha(raw)
        # Matched validation reads only already checked per-case snapshots.
        for key, case in plan["cases"].items():
            directory = _case_files(work, key, case)
            for task in plan["protocol"]["tasks"]:
                if task["claim_id"] != case["claim_id"]: continue
                for row in [{"file": task["input_file"], "sha256": task["input_sha256"]}, *task["source_files"]]:
                    raw = c.read_bytes(c.artifact(directory / "inputs", row["file"]))
                    require(sha(raw) == row["sha256"], "freeze source mismatch")
                    retain("inputs/" + row["file"], raw)
        masked = matched.mask(plan["manifest"], plan["protocol"], runs, bundle / "inputs")
        comparison = matched.compare(plan["manifest"], plan["protocol"], runs, bundle / "inputs")
        for row in final:
            raw = bridge.canonical_bytes(row["package"])
            require(sha(raw) == row["record"]["record_evidence_sha256"], "record evidence serialization mismatch")
            retain(row["record"]["record_evidence_reference"], raw)
        for name, value in (("runs.json", runs), ("masked.json", masked), ("comparison.json", comparison),
                            ("manifest.json", plan["manifest"]), ("protocol.json", plan["protocol"])):
            retain(name, bridge.canonical_bytes(value))
        if "native_loader" in plan:
            environment = plan["native_loader"]["environment"]
            require(digest(environment) == plan["native_loader"]["environment_sha256"], "native environment evidence changed")
            retain("native-environment.json", bridge.canonical_bytes(environment))
        receipt = {"schema": "e156-study-export-v1", "generation": generation, "plan_sha256": digest(plan),
                   "measurements_sha256": digest(measurements), "files": dict(file_hashes), "scientific_results": None}
        retain("receipt.json", bridge.canonical_bytes(receipt))
        exact_export_inventory(bundle, file_hashes)
        if not adopting:
            # Both resolved targets are inside this work directory. Rename only
            # this completed private generation; never replace a publication.
            require(work.resolve() in bundle.resolve().parents and destination.resolve().parent == work.resolve()
                    and not destination.exists(), "invalid export publication target")
            bundle.rename(destination)
        state["frozen"] = {"runs_sha256": digest(runs), "masked_sha256": digest(masked), "receipt_sha256": digest(receipt)}
        c.atomic_json(work / "state.json", state)
        return {"status": "DEVELOPMENT_LEDGER_FROZEN", "runs": runs, "masked": masked, "comparison": comparison, "scientific_results": None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("prepare", "run", "resume", "settle", "reconcile", "records", "abort", "freeze", "_child"))
    p.add_argument("--work", type=Path, required=True)
    for field in ("manifest", "protocol", "inventory", "inputs", "evidence", "budget", "fixtures", "receipt", "measurements", "output"):
        p.add_argument("--" + field, type=Path)
    p.add_argument("--mode", choices=("LIVE", "SYNTHETIC_CONTRACT")); p.add_argument("--case-id"); p.add_argument("--deadline")
    p.add_argument("--allow-paid", action="store_true")
    a = p.parse_args()
    try:
        if a.action == "_child":
            child(a.work, a.mode, a.deadline, a.output, allow_paid=a.allow_paid); return
        if a.output is not None:
            target, work = c.guard(a.output).resolve(), c.guard(a.work).resolve()
            require(not target.exists() and work not in target.parents and target != work, "public output must be new and outside work controls")
        if a.action in {"resume", "settle", "reconcile"}: require(a.case_id is not None, "case-id required")
        if a.action == "prepare":
            require(all(getattr(a, f) is not None for f in ("manifest", "protocol", "inventory", "inputs", "evidence", "budget", "mode")), "preparation arguments missing")
            result = prepare(read(a.manifest), read(a.protocol), read(a.inventory), a.inputs, a.evidence, a.work,
                             read(a.budget), a.mode, read(a.fixtures) if a.fixtures else None)
            result = {"status": result["status"], "cases": len(result["schedule"]), "scientific_results": None}
        elif a.action in {"run", "resume"}: result = execute(a.work, allow_paid=a.allow_paid, resume=a.case_id if a.action == "resume" else None)
        elif a.action == "settle": result = settle(a.work, a.case_id)
        elif a.action == "reconcile": result = reconcile(a.work, a.case_id, read(a.receipt))
        elif a.action == "records": result = records(a.work)
        elif a.action == "abort": result = abort(a.work)
        else: result = freeze(a.work, read(a.measurements))
        if a.output: c.atomic_json(a.output, result, exclusive=True)
        else: print(json.dumps({"status": result.get("status", "RECORDS_AVAILABLE"), "scientific_results": None}))
    except (Refused, matched.Refused, OSError, ValueError, TypeError, KeyError, RecursionError, sqlite3.Error) as exc:
        p.error("study runner refused (" + type(exc).__name__ + "); inspect private inputs locally")


if __name__ == "__main__": main()
