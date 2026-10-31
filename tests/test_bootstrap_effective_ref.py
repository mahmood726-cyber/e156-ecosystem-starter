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
    curl_args = tmp_path / "curl-arguments.txt"
    curl = fake_bin / "curl"
    curl.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$E156_TEST_CURL_ARGS"\nexit 91\n',
        encoding="utf-8",
    )
    curl.chmod(0o755)
    sleep = fake_bin / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
            "REF": env_ref,
            "E156_TEST_CURL_ARGS": str(curl_args),
        }
    )
    outcome = subprocess.run(
        ["bash", str(BOOTSTRAP), *arguments],
        env=env,
        text=True,
        capture_output=True,
        input="",
        timeout=20,
        check=False,
    )

    # Reaches the deliberately failing curl, proving that the warning is
    # evaluated against the ref actually used for download, not the old env.
    assert outcome.returncode == 91, outcome.stdout + outcome.stderr
    assert ("WARNING:" in outcome.stdout) is expect_warning
    assert curl_args.exists(), outcome.stdout + outcome.stderr
    assert archive_path in curl_args.read_text(encoding="utf-8")


def test_help_does_not_warn_or_fetch(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text("#!/bin/sh\nexit 92\n", encoding="utf-8")
    curl.chmod(0o755)

    env = os.environ.copy()
    env.update({"PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}", "REF": "main"})
    outcome = subprocess.run(
        ["bash", str(BOOTSTRAP), "--help"],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert outcome.returncode == 0, outcome.stdout + outcome.stderr
    assert "WARNING:" not in outcome.stdout
    assert "Usage:" in outcome.stdout
