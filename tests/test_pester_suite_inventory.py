"""Fail-closed inventory for Windows Pester suites.

The Windows Pester job uses an explicit $files list. Without this independently
collected Ubuntu pytest check, a new *.tests.ps1 suite can be added to the tree
and omitted from that list without failing CI. This is a static coverage guard,
NOT a PowerShell execution test or a live ecosystem canary.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = Path('.github/workflows/test.yml')
_LIST = re.compile(r'^\s*\$files\s*=\s*@\(\s*\n(?P<rows>.*?)^\s*\)\s*$', re.MULTILINE | re.DOTALL)
_ROW = re.compile(r"'([^']+\.tests\.ps1)'\s*,?", re.IGNORECASE)


def _path_key(raw: str) -> str:
    normalized = raw.replace('\\', '/')
    path = PurePosixPath(normalized)
    if path.is_absolute() or ':' in normalized or '..' in path.parts or '.' in path.parts or len(path.parts) < 2:
        raise AssertionError(f'Unsafe Pester suite path in CI: {raw!r}')
    return str(path).casefold()


def assert_pester_inventory_complete(root: Path, workflow: str) -> None:
    """Refuse omitted, missing, duplicate or nonliteral Pester suite declarations."""
    blocks = list(_LIST.finditer(workflow))
    if len(blocks) != 1:
        raise AssertionError('Exactly one explicit Pester $files array is required')
    declared = []
    for row in blocks[0].group('rows').splitlines():
        row = row.strip()
        if not row:
            continue
        match = _ROW.fullmatch(row)
        if match is None:
            raise AssertionError(f'Nonliteral Pester suite entry: {row!r}')
        declared.append(_path_key(match.group(1)))
    if not declared or len(set(declared)) != len(declared):
        raise AssertionError('Missing or duplicate Pester suite declarations')
    discovered = [
        _path_key(p.relative_to(root).as_posix())
        for p in root.rglob('*')
        if p.is_file() and p.name.casefold().endswith('.tests.ps1')
        and '.git' not in p.relative_to(root).parts
    ]
    if len(set(discovered)) != len(discovered):
        raise AssertionError('Case-colliding Pester test file paths')
    unlisted = sorted(set(discovered) - set(declared))
    nonexistent = sorted(set(declared) - set(discovered))
    if unlisted or nonexistent:
        raise AssertionError(f'Pester suite inventory drift: unlisted={unlisted}, nonexistent={nonexistent}')


def _fixture(tmp_path: Path) -> str:
    path = tmp_path / 'scripts' / 'pester.existing.tests.ps1'
    path.parent.mkdir(parents=True)
    path.write_text("Describe 'fixture' {}\n", encoding='utf-8')
    return "$files = @(\n  'scripts\\pester.existing.tests.ps1'\n)\n"


def test_all_existing_pester_suites_are_explicitly_required():
    assert_pester_inventory_complete(ROOT, (ROOT / WORKFLOW).read_text(encoding='utf-8'))


def test_planted_new_unlisted_suite_fails(tmp_path):
    workflow = _fixture(tmp_path)
    assert_pester_inventory_complete(tmp_path, workflow)
    (tmp_path / 'scripts' / 'pester.new.tests.ps1').write_text("Describe 'planted' {}\n", encoding='utf-8')
    with pytest.raises(AssertionError, match='unlisted='):
        assert_pester_inventory_complete(tmp_path, workflow)


def test_missing_or_duplicate_declared_suite_fails(tmp_path):
    workflow = _fixture(tmp_path)
    with pytest.raises(AssertionError, match='nonexistent='):
        assert_pester_inventory_complete(tmp_path, workflow.replace('existing', 'removed'))
    duplicate = workflow.replace("\n)\n", "\n  'scripts\\pester.existing.tests.ps1'\n)\n")
    with pytest.raises(AssertionError, match='duplicate'):
        assert_pester_inventory_complete(tmp_path, duplicate)


def test_malformed_nonliteral_declaration_fails(tmp_path):
    workflow = _fixture(tmp_path)
    with pytest.raises(AssertionError, match='Nonliteral'):
        assert_pester_inventory_complete(tmp_path, workflow.replace("'scripts\\pester.existing.tests.ps1'", '$env:SOME_FILE'))
