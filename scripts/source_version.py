"""Identidad de contenido local, incluyendo archivos F4 todavía sin commit."""
import hashlib
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root).split(b'\0')
digest = hashlib.sha1()
for name in sorted(set(names)):
    if not name:
        continue
    path = root / name.decode()
    if path.is_file():
        digest.update(name + b'\0' + path.read_bytes() + b'\0')
print('sha-' + digest.hexdigest())
