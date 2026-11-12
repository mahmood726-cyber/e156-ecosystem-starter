"""Reproducible provider-free recovery comparison; see frozen adjacent protocol."""
from __future__ import annotations

import argparse
from contextlib import closing
from hashlib import sha256
from importlib.metadata import distributions, version
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import synthesis_replay as replay

PROTOCOL = Path(__file__).with_name('harness-recovery-protocol.json')
ANCHORS = {
    'stepwise': 'd81086aaf3cee56b8936af0ef617085844718cdb1a200b88870fcfef7812b0d6',
    'strokewalk': '5a2d948a673a0c5ea67b9671a97bb43f0affbb00ec521e5940bf6dfe66cbe2ad',
}


def deny_network(*a, **k):
    raise RuntimeError('network access forbidden during the recovery comparison')


def audit(root, anchor, trace):
    with trace.open('a', encoding='utf-8') as stream:
        stream.write('verify\n')
    return replay.verify(root, anchor)


class State(TypedDict, total=False):
    receipt: dict
    emitted: bool


def child(strategy, phase, workspace, fixture):
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    replay.capture.build_opener = deny_network
    root, trace = workspace/'bundle', workspace/'calls.txt'
    anchor = ANCHORS[fixture]
    if strategy == 'direct_replay':
        receipt = audit(root, anchor, trace)
        return {'outcome': 'PAUSED' if phase == 'start' else 'COMPLETED', 'receipt': receipt}
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.sqlite import SqliteSaver
    builder = StateGraph(State)
    builder.add_node('audit', lambda state: {'receipt': audit(root, anchor, trace)})

    def emit(state):
        if strategy == 'langgraph_revalidated':
            current = audit(root, anchor, trace)
            if current != state['receipt']: raise replay.Refused('checkpoint receipt changed')
        return {'emitted': True}

    builder.add_node('emit', emit)
    builder.add_edge(START, 'audit')
    builder.add_edge('audit', 'emit')
    builder.add_edge('emit', END)
    with closing(sqlite3.connect(str(workspace/'checkpoints.sqlite'), check_same_thread=False)) as connection:
        graph = builder.compile(checkpointer=SqliteSaver(connection), interrupt_before=['emit'])
        result = graph.invoke({} if phase == 'start' else None, {'configurable': {'thread_id': 'development-review'}})
        return {'outcome': 'COMPLETED' if result.get('emitted') else 'PAUSED', 'receipt': result['receipt']}


def invoke(strategy, phase, workspace, fixture):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(('LANGCHAIN_', 'LANGSMITH_', 'OTEL_')): env.pop(key)
    env.update(LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false', PYTHONUTF8='1')
    started = perf_counter()
    try:
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child', strategy,
            '--phase', phase, '--workspace', str(workspace), '--fixture', fixture],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
        result = json.loads(p.stdout)
        if p.returncode not in (0, 2) or not isinstance(result, dict):
            raise RuntimeError('worker did not return a recognized result')
        if result.get('outcome') not in ('PAUSED', 'COMPLETED', 'REFUSED'):
            raise RuntimeError('worker result was incomplete')
        if (p.returncode == 2) != (result['outcome'] == 'REFUSED'):
            raise RuntimeError('worker exit status disagreed with its outcome')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result = {'outcome': 'ERROR', 'reason': type(exc).__name__}
    result['wall_seconds'] = round(perf_counter()-started, 6)
    return result


def calls(path):
    return path.read_text(encoding='utf-8').splitlines().count('verify') if path.exists() else 0


def evaluate():
    protocol_raw = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_raw)
    cases = []
    for fixture in protocol['fixtures']:
        for strategy in protocol['strategies']:
            for scenario in protocol['scenarios']:
                with TemporaryDirectory(prefix='harness-recovery-') as directory:
                    workspace = Path(directory)
                    shutil.copytree(ROOT/'examples'/('synthesis-replay-'+fixture), workspace/'bundle')
                    before = invoke(strategy, 'start', workspace, fixture)
                    before_calls = calls(workspace/'calls.txt')
                    if before['outcome'] != 'PAUSED':
                        cases.append({'fixture': fixture, 'strategy': strategy, 'scenario': scenario,
                                      'initial': before, 'resumed': {'outcome': 'NOT_ATTEMPTED'},
                                      'integrity_contract_satisfied': False})
                        continue
                    if scenario == 'source_bytes_changed':
                        path = next((workspace/'bundle'/'sources').glob('*.xml'))
                        path.write_bytes(path.read_bytes()+b'\n')
                    elif scenario == 'result_bytes_changed':
                        path = workspace/'bundle'/'result.json'
                        path.write_bytes(path.read_bytes()+b' ')
                    after = invoke(strategy, 'resume', workspace, fixture)
                    okay = (after['outcome'] == 'COMPLETED'
                        and after.get('receipt') == before.get('receipt')) if scenario == 'unchanged' else after['outcome'] == 'REFUSED'
                    cases.append({'fixture': fixture, 'strategy': strategy, 'scenario': scenario,
                        'initial': before, 'resumed': after, 'verifier_calls_initial': before_calls,
                        'verifier_calls_resumed': calls(workspace/'calls.txt')-before_calls,
                        'integrity_contract_satisfied': okay})
    return {'schema': 'e156-harness-recovery-measurement-v1', 'protocol_sha256': sha256(protocol_raw).hexdigest(),
        'evaluator_sha256': sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        'replay_verifiers': replay.code_profile(), 'manifest_anchors': ANCHORS,
        'platform': platform.system(), 'python': platform.python_version(),
        'packages': dict(sorted((d.metadata['Name'], d.version) for d in distributions())),
        'held_out': False, 'scientific_accuracy_measured': False, 'model_calls': 0,
        'network_guard': 'APPLICATION_GUARDS_FOR_SOCKET_CONNECT_CREATE_CONNECTION_AND_SOURCE_FETCH_ONLY_NOT_OS_ISOLATION',
        'attempted_cases': len(cases), 'cases': cases,
        'interpretation': 'Strategy ablation using the same replay checker. Cached strategy deliberately omits boundary revalidation; failures are not a LangGraph vulnerability.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path)
    p.add_argument('--child', choices=['direct_replay', 'langgraph_cached', 'langgraph_revalidated'])
    p.add_argument('--phase', choices=['start', 'resume'])
    p.add_argument('--workspace', type=Path)
    p.add_argument('--fixture', choices=ANCHORS)
    args = p.parse_args()
    if args.child:
        try: result = child(args.child, args.phase, args.workspace, args.fixture)
        except replay.Refused as exc:
            print(json.dumps({'outcome': 'REFUSED', 'reason': str(exc)}))
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0
    result = evaluate()
    if args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps({'attempted': result['attempted_cases'], 'outcomes': [
        {'strategy': strategy, 'satisfied': sum(c['integrity_contract_satisfied'] for c in result['cases'] if c['strategy']==strategy),
         'attempted': sum(c['strategy']==strategy for c in result['cases'])}
        for strategy in ('direct_replay', 'langgraph_cached', 'langgraph_revalidated')]}))
    return 2 if any(c['resumed']['outcome'] in ('ERROR','NOT_ATTEMPTED') for c in result['cases']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
