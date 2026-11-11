"""Disposable Git fixtures for installer boundaries, not scientific datasets.

No global environment writes, no fake executables on PATH, no network fixtures.
The real locked upstream generator is exercised separately in integration CI.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import component_lock as lock
from scripts import rapidmeta_install as installer

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = '''import argparse, json, shutil
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('config'); p.add_argument('--out')
a=p.parse_args(); c=json.loads(Path(a.config).read_text())
dest=Path(a.out); dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text('<html><head><title>'+c['title']+'</title></head><body>'+str(c['trials'])+'<script src="assets/check.js"></script></body></html>',encoding='utf-8')
shutil.copytree(Path(__file__).parent/'template/assets',dest.parent/'assets')
'''


def git(*args):
    return subprocess.run(["git", *map(str, args)], check=True, capture_output=True,
                          text=True, timeout=20).stdout.strip()


@pytest.fixture
def origin(tmp_path, monkeypatch):
    isolated = tmp_path / "isolated-home"
    isolated.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(isolated))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    monkeypatch.setenv("BASH_ENV", "")
    monkeypatch.setenv("ENV", "")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(key, raising=False)
    source = tmp_path / "origin"
    git("init", "--initial-branch=main", source)
    (source / "template/assets").mkdir(parents=True)
    (source / "template/assets/check.js").write_text("// synthetic install check\n", encoding="utf-8")
    (source / "clone.py").write_text(GENERATOR, encoding="utf-8")
    commit(source)
    component = copy.deepcopy(lock.load_lock()["rapidmeta"])
    component.update(repository=str(source), commit=git("-C", source, "rev-parse", "HEAD"))
    return source, component


def commit(source):
    git("-C", source, "add", ".")
    git("-C", source, "-c", "user.name=Install fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-m", "synthetic fixture")


def test_real_lock_and_installer_mirrors():
    lock.check_mirrors(ROOT, lock.load_lock())


@pytest.mark.parametrize("mutation", ["duplicate", "tag", "missing", "unknown_adapter", "bad_url"])
def test_malformed_locks_refuse(tmp_path, mutation):
    payload=json.loads(lock.DEFAULT_LOCK.read_text(encoding="utf-8"))
    c=payload['components']
    if mutation == "tag": c['rapidmeta']['commit']='v1.1.0'
    elif mutation == "missing": del c['overmind']
    elif mutation == "unknown_adapter": c['rapidmeta']['verification']='execute-shell'
    elif mutation == "bad_url": c['rapidmeta']['repository']='file:///untrusted'
    raw=json.dumps(payload)
    if mutation == "duplicate": raw=raw.replace('"schema":', '"schema":"duplicate", "schema":',1)
    path=tmp_path/'lock.json'; path.write_text(raw,encoding='utf-8')
    with pytest.raises(ValueError): lock.load_lock(path)


def test_lock_disagreement_in_either_installer_is_refused(tmp_path):
    components=lock.load_lock()
    for name in ('sentinel','overmind'):
        for ext in ('sh','ps1'):
            path=tmp_path/'scripts'/f'install-{name}.{ext}'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes((ROOT/'scripts'/path.name).read_bytes())
    lock.check_mirrors(tmp_path,components)
    for name in ('sentinel','overmind'):
        for ext in ('sh','ps1'):
            path=tmp_path/'scripts'/f'install-{name}.{ext}'
            original=path.read_bytes()
            path.write_bytes(original.replace(components[name]['commit'].encode(), b'a'*40))
            with pytest.raises(ValueError,match='differs'): lock.check_mirrors(tmp_path,components)
            path.write_bytes(original)


def test_clean_install_and_skip_clone_bind_requested_commit(tmp_path, origin):
    _, component=origin
    target=tmp_path/'installed'
    report=installer.install(target,component)
    assert report['expected_commit']==report['observed_commit']==component['commit']
    assert report['status']=='verified'
    assert report['smoke']['fixture_kind']=='synthetic_install_check'
    assert report['smoke']['browser_verified'] is False
    assert report['smoke']['output_sha256']
    assert git('-C',target,'status','--porcelain')==''
    assert installer.install(target,component,skip_clone=True)['smoke']==report['smoke']


@pytest.mark.parametrize('ref',['main','v1.1.0','--upload-pack=sh','HEAD','', 'A'*40])
def test_unsafe_ref_refuses_before_target_creation(tmp_path, origin, ref):
    _, component=origin
    target=tmp_path/'no-mutation'
    with pytest.raises(installer.InstallRefused,match='full lowercase commit'):
        installer.install(target,component,ref=ref)
    assert not target.exists()


def test_missing_commit_preserves_existing_head(tmp_path, origin):
    _, component=origin
    target=tmp_path/'installed'
    installer.install(target,component)
    with pytest.raises(installer.InstallRefused): installer.install(target,component,ref='0'*40)
    assert git('-C',target,'rev-parse','HEAD')==component['commit']


def test_new_commit_requires_fresh_target_to_preserve_active_install(tmp_path, origin):
    source, component=origin
    target=tmp_path/'installed'; installer.install(target,component)
    (source/'clone.py').write_text('pass',encoding='utf-8');commit(source)
    candidate=git('-C',source,'rev-parse','HEAD')
    with pytest.raises(installer.InstallRefused,match='fresh target'):
        installer.install(target,component,ref=candidate)
    assert git('-C',target,'rev-parse','HEAD')==component['commit']
    assert (target/'clone.py').read_text()==GENERATOR


@pytest.mark.parametrize('mode',['tracked','untracked','ignored','staged'])
def test_dirty_checkout_refuses_without_changing_user_files(tmp_path, origin, mode):
    _, component=origin
    target=tmp_path/'installed'; installer.install(target,component)
    file=target/('clone.py' if mode=='tracked' else 'work.txt')
    file.write_text('user work',encoding='utf-8')
    if mode=='ignored':
        (target/'.git/info/exclude').write_text('work.txt\n',encoding='utf-8')
    if mode=='staged': git('-C',target,'add','work.txt')
    with pytest.raises(installer.InstallRefused,match='dirty'):
        installer.install(target,component)
    assert file.read_text()=='user work'


def test_wrong_origin_and_nested_target_are_refused(tmp_path, origin):
    source, component=origin
    target=tmp_path/'installed'; installer.install(target,component)
    git('-C',target,'remote','set-url','origin',str(tmp_path/'different'))
    with pytest.raises(installer.InstallRefused,match='origin'):
        installer.install(target,component,skip_clone=True)
    with pytest.raises(installer.InstallRefused,match='repository root'):
        installer.install(source/'template',component,skip_clone=True)


def test_skip_clone_cannot_accept_wrong_commit_or_nonrepo(tmp_path, origin):
    _, component=origin
    target=tmp_path/'installed'; installer.install(target,component)
    with pytest.raises(installer.InstallRefused,match='identity'):
        installer.install(target,component,ref='0'*40,skip_clone=True)
    empty=tmp_path/'fake';empty.mkdir(); (empty/'clone.py').write_text('pass')
    with pytest.raises(installer.InstallRefused): installer.install(empty,component,skip_clone=True)


@pytest.mark.parametrize('code',[
    'raise RuntimeError("broken")', 'pass',
    GENERATOR.replace("c['title']", "'wrong title'"),
    GENERATOR.replace("str(c['trials'])", "str(__import__('time').time_ns())+str(c['trials'])"),
])
def test_generator_failure_cannot_produce_verification_receipt(tmp_path, origin, code):
    source, component=origin
    (source/'clone.py').write_text(code,encoding='utf-8');commit(source)
    component['commit']=git('-C',source,'rev-parse','HEAD')
    with pytest.raises(installer.InstallRefused): installer.install(tmp_path/'installed',component)


def test_missing_local_asset_fails_even_when_generator_exits_zero(tmp_path, origin):
    source, component=origin
    (source/'template/assets/check.js').unlink();commit(source)
    component['commit']=git('-C',source,'rev-parse','HEAD')
    with pytest.raises(installer.InstallRefused): installer.install(tmp_path/'installed',component)


def test_output_path_alias_is_canonicalized_without_allowing_asset_escape(tmp_path):
    output = tmp_path / 'output'
    output.mkdir()
    (output/'check.js').write_text('// synthetic asset',encoding='utf-8')
    page=output/'dashboard.html'
    prefix=installer.SMOKE_TITLE+' fixture-a fixture-b '
    page.write_text(prefix+'<script src="check.js"></script>',encoding='utf-8')
    # Portable alias reproduces the mismatch between a resolved asset and an
    # unresolved output root. Windows CI also exercises a native 8.3 TEMP alias.
    alias=output/'..'/output.name/page.name
    assert installer.inspect_output(alias)==installer.inspect_output(page)
    (tmp_path/'outside.js').write_text('// outside output',encoding='utf-8')
    page.write_text(prefix+'<script src="../outside.js"></script>',encoding='utf-8')
    with pytest.raises(installer.InstallRefused,match='escaping'):
        installer.inspect_output(alias)


def test_missing_git_refuses(tmp_path, origin, monkeypatch):
    _, component=origin
    def missing(*args,**kwargs): raise FileNotFoundError('missing executable')
    monkeypatch.setattr(installer.subprocess,'run',missing)
    with pytest.raises(installer.InstallRefused,match='unavailable'):
        installer.install(tmp_path/'installed',component)


@pytest.mark.parametrize('flag',['--assume-unchanged','--skip-worktree'])
def test_git_flags_cannot_hide_changed_generator(tmp_path, origin, flag):
    _, component=origin
    target=tmp_path/'installed'; installer.install(target,component)
    git('-C',target,'update-index',flag,'clone.py')
    (target/'clone.py').write_text('pass',encoding='utf-8')
    with pytest.raises(installer.InstallRefused,match='suppression'):
        installer.install(target,component,skip_clone=True)


def test_linked_target_refuses_before_git(tmp_path, origin, monkeypatch):
    source, component=origin
    # Portable control also covers Windows junction classification without
    # requiring Developer Mode/admin privileges to create a symlink.
    monkeypatch.setattr(installer,'linked',lambda p: p==source)
    with pytest.raises(installer.InstallRefused,match='linked install target'):
        installer.install(source,component)


def test_runtime_floor_and_ambient_git_path_refuse_before_mutation(tmp_path, origin, monkeypatch):
    source, component=origin
    too_new={**component,'python_min':'3.99'}
    target=tmp_path/'absent'
    with pytest.raises(installer.InstallRefused,match='runtime floor'):
        installer.install(target,too_new)
    monkeypatch.setenv('GIT_DIR',str(source/'.git'))
    with pytest.raises(installer.InstallRefused,match='ambient Git'):
        installer.install(target,component)
    assert not target.exists()


SHELLS = ['bash','powershell'] if os.name=='nt' else ['bash']


def bash_executable():
    executable=shutil.which('bash')
    if os.name=='nt' and (not executable or 'system32' in executable.lower()):
        executable=str(Path(os.environ['ProgramFiles'])/'Git/bin/bash.exe')
    assert executable and Path(executable).is_file(), 'Bash required'
    return executable


def user_path_binding():
    if os.name != 'nt':
        return None
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
        try:
            return winreg.QueryValueEx(key, 'RAPIDMETA_KIT_PATH')
        except FileNotFoundError:
            return None


@pytest.mark.parametrize('shell',SHELLS)
@pytest.mark.parametrize('broken',[False,True])
def test_actual_wrappers_use_same_gate_without_user_env_writes(tmp_path, origin, shell, broken):
    source, component=origin
    if broken:
        (source/'clone.py').write_text('pass',encoding='utf-8');commit(source)
        component['commit']=git('-C',source,'rev-parse','HEAD')
    target=tmp_path/'wrapper-target'
    git('clone',str(source),str(target))
    git('-C',target,'remote','set-url','origin',lock.load_lock()['rapidmeta']['repository'])
    env={**os.environ,'RAPIDMETA_REF':component['commit']}
    if shell=='powershell':
        executable=shutil.which('pwsh') or shutil.which('powershell')
        assert executable, 'Windows wrapper tests require PowerShell'
        command=[executable,'-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/install-rapidmeta.ps1'),
                 '-Target',str(target),'-SkipClone','-SessionOnly']
    else:
        executable=bash_executable()
        command=[executable,'--noprofile','--norc',str(ROOT/'scripts/install-rapidmeta.sh'),
                 '--target',str(target),'--skip-clone','--session-only']
    before=user_path_binding()
    run=subprocess.run(command,env=env,cwd=tmp_path,capture_output=True,text=True,timeout=45)
    assert (run.returncode==0) is (not broken),run.stdout+run.stderr
    assert ('"status": "verified"' in run.stdout) is (not broken)
    assert user_path_binding()==before
    assert not (tmp_path/'isolated-home'/'.bashrc').exists()
    assert not (tmp_path/'isolated-home'/'.zshrc').exists()
    # PowerShell itself may create an AppData cache under the disposable home.


def test_bash_persistence_quotes_paths_and_is_idempotent(tmp_path, origin):
    source, component=origin
    target=tmp_path/'path with spaces $(literal)'
    git('clone',str(source),str(target))
    git('-C',target,'remote','set-url','origin',lock.load_lock()['rapidmeta']['repository'])
    env={**os.environ,'RAPIDMETA_REF':component['commit']}
    command=[bash_executable(),'--noprofile','--norc',str(ROOT/'scripts/install-rapidmeta.sh'),
             '--target',str(target),'--skip-clone']
    for _ in range(2):
        result=subprocess.run(command,env=env,cwd=tmp_path,capture_output=True,text=True,timeout=45)
        assert result.returncode==0,result.stdout+result.stderr
    rc=tmp_path/'isolated-home'/'.bashrc'
    assert rc.read_text().count('export RAPIDMETA_KIT_PATH=')==1
    result=subprocess.run([bash_executable(),'--noprofile','--norc','-c',
                           'source "$1"; test "$RAPIDMETA_KIT_PATH" = "$(cd "$2" && pwd -P)"',
                           'fixture',str(rc),str(target)],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    installed_binding=rc.read_text()
    for prefix in ('',installed_binding):
        conflicting=prefix+'export RAPIDMETA_KIT_PATH=existing-user-setting\n'
        rc.write_text(conflicting,encoding='utf-8',newline='\n')
        result=subprocess.run(command,env=env,cwd=tmp_path,capture_output=True,text=True,timeout=45)
        assert result.returncode!=0
        assert '"status": "verified"' not in result.stdout
        assert rc.read_text()==conflicting
