"""Read-only, network-disabled execution for authored multilingual repair tasks."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess
import time

from genesis.trust_root import digest_of


def run_task(directory: Path, language: str, image: str, *, timeout: int = 30) -> dict:
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir() or directory == Path.home() or directory == Path('/'):
        raise ValueError('isolated task directory required')
    if not image.startswith('sha256:') or len(image) != 71:
        raise ValueError('pin executor to a local image ID')
    commands = {
        'python': ['python3', '-B', '/task/runner.py'],
        'javascript': ['node', '/task/runner.js'],
        'java': ['/bin/sh', '-c',
                 'mkdir /tmp/classes && javac -d /tmp/classes /task/src/Subject.java /task/Runner.java && java -XX:ActiveProcessorCount=1 -Xmx128m -cp /tmp/classes Runner'],
    }
    if language not in commands:
        raise ValueError('unsupported language')
    name = 'genesis-repair-transfer-' + secrets.token_hex(8)
    argv = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
            '--memory', '512m', '--memory-swap', '512m', '--cpus', '1',
            '--user', f'{os.getuid()}:{os.getgid()}',
            '--tmpfs', '/tmp:rw,exec,nosuid,nodev,size=128m',
            '--mount', f'type=bind,source={directory},target=/task,readonly',
            '--workdir', '/tmp', '--entrypoint', '/usr/bin/env', image,
            '-i', 'PATH=/usr/bin:/bin', 'HOME=/tmp', 'LANG=C.UTF-8', *commands[language]]
    started = time.monotonic(); timed_out = False
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
        code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired:
        timed_out = True; code = None; stdout = ''; stderr = 'timeout'
        subprocess.run(['docker', 'kill', name], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    body = dict(language=language, image=image, returncode=code, stdout=stdout[:16000],
                stderr=stderr[:16000], timed_out=timed_out,
                seconds=round(time.monotonic()-started, 3), command=argv,
                isolation_requested=dict(network='none', root_readonly=True, task_readonly=True,
                    capabilities='none', no_new_privileges=True, environment_cleared=True,
                    user=f'{os.getuid()}:{os.getgid()}', memory_megabytes=512,
                    cpus=1, processes=128, timeout_seconds=timeout))
    return {**body, 'run_digest': digest_of(body)}
