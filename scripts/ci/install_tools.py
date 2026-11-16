"""Descarga herramientas Linux amd64 con versiones y SHA256 revisados."""
from pathlib import Path
import hashlib
import io
import json
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / '.local/f4/tools'
DEST.mkdir(parents=True, exist_ok=True)
for name, spec in json.loads((Path(__file__).with_name('tools.lock.json')).read_text()).items():
    data = urllib.request.urlopen(spec['url'], timeout=60).read()
    if hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise SystemExit(f'Hash inválido: {name}')
    if spec['member']:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            data = archive.extractfile(spec['member']).read()
    target = DEST / name
    target.write_bytes(data)
    target.chmod(0o755)
    print(f'{name} {spec["version"]}')
