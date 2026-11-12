"""Explicit, non-retrying OpenAI Responses transport. Credentials never enter traces."""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

if __package__:
    from scripts.harness_context import Refused, require, strict_json
    from scripts import bounded_native
else:
    from harness_context import Refused, require, strict_json
    import bounded_native


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refused("provider redirect refused")


class Responses:
    def __init__(self, *, allow_paid=False):
        require(allow_paid, "paid execution requires explicit --allow-paid")
        self.key = os.environ.get("OPENAI_API_KEY")
        require(bool(self.key), "OPENAI_API_KEY is unavailable")
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _post(self, endpoint, payload, timeout):
        # A socket timeout alone is not a total deadline (a server can drip bytes).
        # The existing process-group/Windows Job Object transport bounds the child.
        launcher = "import sys; sys.path.insert(0,sys.argv[1]); import harness_provider; harness_provider.main()"
        raw = bounded_native.run([sys.executable, "-I", "-S", "-c", launcher, str(Path(__file__).parent)],
            timeout=timeout, input=json.dumps({"endpoint": endpoint, "payload": payload, "timeout": timeout}).encode("utf-8"))
        return strict_json(raw)

    def _direct_post(self, endpoint, payload, timeout):
        require(endpoint in {"responses", "responses/input_tokens"}, "unsupported provider endpoint")
        request = urllib.request.Request("https://api.openai.com/v1/" + endpoint,
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}, method="POST")
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                require(len(raw) <= 8 * 1024 * 1024, "provider output exceeds limit")
                result = strict_json(raw)
                require(isinstance(result, dict), "provider response must be object")
                # Copy only the provider request identifier, never other headers.
                result["_request_id"] = response.headers.get("x-request-id")
                return result
        except (urllib.error.URLError, OSError) as exc:
            # Do not echo response bodies, URLs, credentials or arbitrary exceptions.
            raise Refused("provider transport failed; outcome may be unknown") from exc

    def count(self, payload, timeout):
        return self._post("responses/input_tokens", {k: payload[k] for k in
                          ("model", "input", "instructions", "tools") if k in payload}, timeout)

    def respond(self, payload, timeout):
        return self._post("responses", payload, timeout)


def main():
    try:
        raw = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
        require(len(raw) <= 8 * 1024 * 1024, "request oversized")
        request = strict_json(raw)
        result = Responses(allow_paid=True)._direct_post(**request)
        sys.stdout.write(json.dumps(result, allow_nan=False))
    except Exception:
        raise SystemExit(2) from None
