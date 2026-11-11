"""Failure-injection coverage for the shipped docs Bash bootstrap's effective ref.

The curl stub aborts before any network transfer. These tests do not certify
release authenticity, pinned dependencies, or a full ecosystem installation.
"""

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "docs" / "e156-setup.sh"


def run_bootstrap(tmp_path, fake_bin, arguments, env_ref):
    """Prove stub resolution inside Bash before allowing the bootstrap to run.

    Windows PATH separators are not Bash PATH separators. Inject the absolute
    fake directory inside the child shell and fail closed if curl resolves to
    anything else. HOME and the working directory are disposable as a second
    boundary; no test should ever install into the researcher's real home.
    """
    isolated = tmp_path / "isolated-home"
    isolated.mkdir(exist_ok=True)
    wrapper = r'''
set -eu
test_bin=$(cd "$1" && pwd -P)
test_home=$(cd "$2" && pwd -P)
export PATH="$test_bin:$PATH"
export HOME="$test_home"
export E156_TEST_CURL_ARGS="$test_home/curl-arguments.txt"
if [ "$(command -v curl)" != "$test_bin/curl" ]; then
    echo 'REFUSED: curl stub not selected' >&2
    exit 93
fi
shift 2
exec bash "$@"
'''
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", wrapper, "bootstrap-fixture",
         str(fake_bin), str(isolated), str(BOOTSTRAP), *arguments],
        cwd=isolated, env={**os.environ, "REF": env_ref, "BASH_ENV": "", "ENV": ""},
        text=True, capture_output=True, input="", timeout=20, check=False,
    )


@pytest.mark.parametrize(
    ("arguments", "env_ref", "expect_warning", "archive_path"),
    [
        (["--ref", "main"], "v0.8.0", True, "/refs/heads/main.zip"),
        (["--ref", "v0.8.0"], "main", False, "/refs/tags/v0.8.0.zip"),
        ([], "main", True, "/refs/heads/main.zip"),
        ([], "v0.8.0", False, "/refs/tags/v0.8.0.zip"),
        (["--ref", "review-candidate"], "v0.8.0", True, "/refs/heads/review-candidate.zip"),
        (["--ref", "v1notarelease"], "v0.8.0", True, "/refs/tags/v1notarelease.zip"),
        (["--ref", "v0.8.0-rc1"], "v0.8.0", True, "/refs/tags/v0.8.0-rc1.zip"),
        (["--ref", "v10.2.3"], "main", False, "/refs/tags/v10.2.3.zip"),
    ],
)
def test_release_warning_matches_requested_download(
    tmp_path, arguments, env_ref, expect_warning, archive_path
):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl_args = tmp_path / "isolated-home" / "curl-arguments.txt"
    curl = fake_bin / "curl"
    curl.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$E156_TEST_CURL_ARGS"\nexit 91\n',
        encoding="utf-8", newline="\n",
    )
    curl.chmod(0o755)
    sleep = fake_bin / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    sleep.chmod(0o755)

    outcome = run_bootstrap(tmp_path, fake_bin, arguments, env_ref)

    # Reaches the deliberately failing curl, proving that the warning is
    # evaluated against the ref actually used for download, not the old env.
    assert outcome.returncode == 91, outcome.stdout + outcome.stderr
    assert ("WARNING:" in outcome.stdout) is expect_warning
    assert curl_args.exists(), outcome.stdout + outcome.stderr
    assert archive_path in curl_args.read_text(encoding="utf-8")
    assert not (tmp_path / "isolated-home" / ".claude").exists()


def test_help_does_not_warn_or_fetch(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text("#!/bin/sh\nexit 92\n", encoding="utf-8", newline="\n")
    curl.chmod(0o755)

    outcome = run_bootstrap(tmp_path, fake_bin, ["--help"], "main")
    assert outcome.returncode == 0, outcome.stdout + outcome.stderr
    assert "WARNING:" not in outcome.stdout
    assert "Usage:" in outcome.stdout


def test_missing_curl_stub_refuses_before_bootstrap(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    outcome = run_bootstrap(tmp_path, fake_bin, [], "main")
    assert outcome.returncode == 93
    assert "REFUSED: curl stub not selected" in outcome.stderr
    assert "Downloading" not in outcome.stdout
    assert not list((tmp_path / "isolated-home").iterdir())
