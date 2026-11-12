"""Transport contracts without network access or real credentials."""
import json

import pytest

from scripts import harness_provider as provider


def test_key_gate_before_transport(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(provider.Refused, match="paid"):
        provider.Responses()
    with pytest.raises(provider.Refused, match="unavailable"):
        provider.Responses(allow_paid=True)


def test_count_payload_and_child_transport_never_include_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-CREDENTIAL-CANARY")
    observed = []
    def native(command, timeout, input):
        observed.append((command, timeout, input))
        return b'{"input_tokens":23}'
    monkeypatch.setattr(provider.bounded_native, "run", native)
    client = provider.Responses(allow_paid=True)
    result = client.count({"model": "synthetic", "input": "synthetic task", "tools": [],
                           "instructions": "synthetic", "max_output_tokens": 20, "store": False}, 3)
    assert result["input_tokens"] == 23
    command, timeout, payload = observed[0]
    assert "SYNTHETIC-CREDENTIAL-CANARY" not in str(command) + payload.decode()
    assert timeout == 3
    assert set(json.loads(payload)["payload"]) == {"model", "input", "tools", "instructions"}


def test_redirect_and_arbitrary_endpoint_refused(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-CREDENTIAL-CANARY")
    with pytest.raises(provider.Refused, match="redirect"):
        provider.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")
    with pytest.raises(provider.Refused, match="endpoint"):
        provider.Responses(allow_paid=True)._direct_post("arbitrary", {}, 3)
