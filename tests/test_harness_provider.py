"""Transport contracts without network access or real credentials."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from scripts import harness_provider as provider


def test_key_gate_before_transport(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(provider.Refused, match="paid"):
        provider.Responses()
    with pytest.raises(provider.Refused, match="unavailable"):
        provider.Responses(allow_paid=True)


@pytest.mark.parametrize("input_settings", [
    {},
    {"parallel_tool_calls": False, "reasoning": {"effort": "low", "context": "current_turn"},
     "text": {"format": {"type": "text"}, "verbosity": "low"}, "tool_choice": "auto"},
])
def test_count_payload_and_child_transport_never_include_key(monkeypatch, input_settings):
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-CREDENTIAL-CANARY")
    observed = []
    def native(command, timeout, input):
        observed.append((command, timeout, input))
        return b'{"input_tokens":23}'
    monkeypatch.setattr(provider.bounded_native, "run", native)
    client = provider.Responses(allow_paid=True)
    expected = {"model": "synthetic", "input": "synthetic task", "tools": [],
                "instructions": "synthetic", **input_settings}
    began = time.monotonic()
    result = client.count({**expected, "max_output_tokens": 20, "store": False,
                           "service_tier": "default", "include": ["reasoning.encrypted_content"]}, 3)
    assert result["input_tokens"] == 23
    command, timeout, payload = observed[0]
    assert "SYNTHETIC-CREDENTIAL-CANARY" not in str(command) + payload.decode()
    assert timeout == 3
    request = json.loads(payload)
    assert set(request) == {"endpoint", "payload", "timeout", "deadline"}
    assert began + 3 <= request["deadline"] <= time.monotonic() + 3
    assert request["endpoint"] == "responses/input_tokens"
    assert request["payload"] == expected


def test_redirect_and_arbitrary_endpoint_refused(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-CREDENTIAL-CANARY")
    with pytest.raises(provider.Refused, match="redirect"):
        provider.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")
    with pytest.raises(provider.Refused, match="endpoint"):
        provider.Responses(allow_paid=True)._direct_post("arbitrary", {}, 3)


def child_process(request, handler, monkeypatch):
    """Run main directly, without bounded_native or a study supervisor."""
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-CREDENTIAL-CANARY")
    script = """
import socket,sys,time
sys.path.insert(0, sys.argv[1])
import harness_provider as provider
def no_network(*args, **kwargs):
    raise AssertionError('provider test must not contact network')
socket.socket.connect = no_network
socket.create_connection = no_network
""" + handler + "\nprovider.Responses._direct_post = fake_post\nprovider.main()\n"
    # This timeout only fails/cleans up a broken test. Exit 124 must come from
    # the child's own watchdog, not from any supervising transport implementation.
    return subprocess.run([sys.executable, "-I", "-S", "-c", script, str(Path(provider.__file__).parent)],
                          input=json.dumps(request).encode(), capture_output=True, timeout=8)


def test_provider_child_owns_total_deadline_without_parent_supervisor(monkeypatch):
    request = {"endpoint": "responses", "payload": {"model": "synthetic"},
               "timeout": 30, "deadline": time.monotonic() + 1}
    result = child_process(request, """
def fake_post(self, endpoint, payload, timeout):
    print('SYNTHETIC_HANDLER_ENTERED', flush=True)
    time.sleep(30)
    raise AssertionError('blocked handler outlived its child deadline')
""", monkeypatch)
    assert result.returncode == 124
    assert result.stdout.splitlines() == [b'SYNTHETIC_HANDLER_ENTERED']
    assert not result.stderr


def test_provider_child_caps_timeout_and_keeps_envelope_out_of_http_payload(monkeypatch):
    request = {"endpoint": "responses/input_tokens", "payload": {"model": "synthetic"},
               "timeout": 30, "deadline": time.monotonic() + 2}
    result = child_process(request, """
def fake_post(self, endpoint, payload, timeout):
    return {'endpoint': endpoint, 'payload': payload, 'timeout': timeout}
""", monkeypatch)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["endpoint"] == request["endpoint"]
    assert observed["payload"] == request["payload"]
    assert 0 < observed["timeout"] < 2
    assert b'SYNTHETIC-CREDENTIAL-CANARY' not in result.stdout + result.stderr


@pytest.mark.parametrize("defect", ["expired", "missing_deadline", "invalid_timeout", "extra_field"])
def test_provider_child_refuses_invalid_or_expired_request_before_transport(monkeypatch, defect):
    request = {"endpoint": "responses", "payload": {"model": "synthetic"},
               "timeout": 3, "deadline": time.monotonic() + 3}
    if defect == "expired": request["deadline"] = time.monotonic() - 1
    elif defect == "missing_deadline": del request["deadline"]
    elif defect == "invalid_timeout": request["timeout"] = True
    else: request["unrecognized"] = "SYNTHETIC"
    result = child_process(request, """
def fake_post(self, endpoint, payload, timeout):
    print('TRANSPORT_MUST_NOT_RUN', flush=True)
    return {}
""", monkeypatch)
    assert result.returncode == 2
    assert not result.stdout
    assert not result.stderr
