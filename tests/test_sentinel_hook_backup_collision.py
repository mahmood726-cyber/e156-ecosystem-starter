"""Regression tests for collision-safe Sentinel pre-push hook backups.

These run the actual Bash installer helper against isolated temporary Git hook
files. No Sentinel bypass, network calls, or live installs are involved.
"""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-sentinel.sh"
FIXED_TIME = "20261026-020000"


def run_helper(repo: Path, body: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TEST_REPO=str(repo), SENTINEL_INSTALLER=str(INSTALLER))
    script = (
        'set -euo pipefail\n'
        'source "$SENTINEL_INSTALLER" --import\n'
        "date() { printf '%s\\n' '20261026-020000'; }\n"
        + body
    )
    return subprocess.run(["bash", "-c", script], env=env, text=True,
                          capture_output=True, check=False)


def test_same_second_backup_keeps_both_user_hooks(tmp_path: Path) -> None:
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "pre-push"
    hook.write_text("#!/bin/sh\necho first\n")
    hook.chmod(0o755)

    result = run_helper(tmp_path, """
first="$(backup_existing_pre_push_hook "$TEST_REPO")"
printf '#!/bin/sh\\necho second\\n' > "$TEST_REPO/.git/hooks/pre-push"
second="$(backup_existing_pre_push_hook "$TEST_REPO")"
printf '%s\\n%s\\n' "$first" "$second"
""")
    assert result.returncode == 0, result.stderr
    names = result.stdout.splitlines()
    assert names == [str(hook) + ".user-" + FIXED_TIME,
                     str(hook) + ".user-" + FIXED_TIME + ".1"]
    assert Path(names[0]).read_text() == "#!/bin/sh\necho first\n"
    assert Path(names[1]).read_text() == "#!/bin/sh\necho second\n"
    assert Path(names[0]).stat().st_mode & 0o111  # executable rollback copy


def test_existing_backup_symlink_not_followed(tmp_path: Path) -> None:
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-push").write_text("#!/bin/sh\necho custom\n")
    protected = tmp_path / "protected.txt"
    protected.write_text("do not change")
    (hooks / ("pre-push.user-" + FIXED_TIME)).symlink_to(protected)

    result = run_helper(tmp_path,
        'backup_existing_pre_push_hook "$TEST_REPO"')
    assert result.returncode == 0, result.stderr
    assert result.stdout == str(hooks / ("pre-push.user-" + FIXED_TIME + ".1"))
    assert protected.read_text() == "do not change"
    assert Path(result.stdout).read_text() == "#!/bin/sh\necho custom\n"


def test_backup_link_failure_is_not_silent_success(tmp_path: Path) -> None:
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-push").write_text("#!/bin/sh\necho custom\n")

    result = run_helper(tmp_path, """
ln() { return 1; }
if backup_existing_pre_push_hook "$TEST_REPO"; then
    echo "unexpected success" >&2
    exit 98
fi
""")
    assert result.returncode == 0, result.stderr
    assert "cannot create a unique" in result.stderr
    assert (hooks / "pre-push").read_text() == "#!/bin/sh\necho custom\n"
    assert not list(hooks.glob("pre-push.user-*"))


def test_backup_temp_reservation_failure_keeps_original_hook(tmp_path: Path) -> None:
    """A failed mktemp must refuse the backup without claiming installation."""
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "pre-push"
    hook.write_text("#!/bin/sh\necho original\n")
    hook.chmod(0o755)

    result = run_helper(tmp_path, """
mktemp() { return 73; }
if backup_existing_pre_push_hook "$TEST_REPO"; then
    echo "unexpected success" >&2
    exit 98
fi
printf 'refused\n'
""")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "refused\n"
    assert "cannot reserve a temporary pre-push hook backup" in result.stderr
    assert hook.read_text() == "#!/bin/sh\necho original\n"
    assert hook.stat().st_mode & 0o111
    assert not list(hooks.glob("pre-push.user-*"))


def test_backup_copy_failure_does_not_publish_partial_backup(tmp_path: Path) -> None:
    """A staged copy failure must clean up the staging path and refuse."""
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "pre-push"
    hook.write_text("#!/bin/sh\necho original\n")

    result = run_helper(tmp_path, """
cp() { return 77; }
if backup_existing_pre_push_hook "$TEST_REPO"; then
    echo "unexpected success" >&2
    exit 98
fi
printf 'refused\n'
""")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "refused\n"
    assert "cannot stage a pre-push hook backup copy" in result.stderr
    assert hook.read_text() == "#!/bin/sh\necho original\n"
    assert not list(hooks.glob("pre-push.user-*"))
