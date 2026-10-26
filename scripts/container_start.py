"""Prepare only the runtime mount, then drop privileges before serving requests."""
import os
import sys
from pathlib import Path

runtime = Path('/app/runtime')
runtime.mkdir(exist_ok=True)
if os.geteuid() == 0:
    os.chown(runtime, 10001, 10001)
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)
if not os.access(runtime, os.W_OK):
    raise RuntimeError('The /app/runtime mount must be writable by UID 10001')
os.execv(sys.executable, [sys.executable, '/app/scripts/serve.py'])
