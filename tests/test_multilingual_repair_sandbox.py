import subprocess
from types import SimpleNamespace

import pytest

from genesis.multilingual_repair_sandbox import run_task

IMAGE='sha256:'+'a'*64


def test_executor_clears_image_environment_and_mounts_task_readonly(tmp_path,monkeypatch):
    calls=[]
    def run(argv,**kwargs):
        calls.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout='[1,2,3]',stderr='')
    monkeypatch.setattr(subprocess,'run',run)
    result=run_task(tmp_path,'python',IMAGE)
    argv,options=calls[0]
    assert argv[argv.index('--network')+1]=='none'
    assert '--read-only' in argv and argv[argv.index('--cap-drop')+1]=='ALL'
    assert argv[argv.index('--mount')+1].endswith(',readonly')
    assert argv[argv.index('--entrypoint')+1]=='/usr/bin/env'
    assert argv[argv.index(IMAGE)+1]=='-i'
    assert options['stdin']==subprocess.DEVNULL
    assert options['timeout']==30
    assert result['returncode']==0


def test_timeout_kills_container_instead_of_only_docker_client(tmp_path,monkeypatch):
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv)
        if len(calls)==1:raise subprocess.TimeoutExpired(argv,1)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess,'run',run)
    result=run_task(tmp_path,'javascript',IMAGE,timeout=1)
    assert result['timed_out'] and result['returncode'] is None
    assert calls[1]==['docker','kill',calls[0][calls[0].index('--name')+1]]


def test_unpinned_image_and_unsupported_language_rejected(tmp_path):
    with pytest.raises(ValueError,match='pin'):
        run_task(tmp_path,'python','latest')
    with pytest.raises(ValueError,match='unsupported'):
        run_task(tmp_path,'shell',IMAGE)
