"""Formato privado F5.4: cifrado con MAC, manifiestos íntegros y extracción cerrada."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
FORMAT='retailops-backup-v1'
CIPHER=['openssl','enc','-aes-256-cbc','-pbkdf2','-iter','200000','-md','sha256']


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def outside_repo(path):
    path=Path(path).expanduser().resolve()
    if path==ROOT or ROOT in path.parents:raise ValueError('Backups y restores deben estar fuera del repositorio')
    return path


def private_dir(path,new=False):
    path=Path(path)
    path.mkdir(mode=0o700,parents=True,exist_ok=not new)
    if path.stat().st_uid!=os.getuid() or path.stat().st_mode & 0o077:raise ValueError('Directorio debe ser privado 0700 y propio')
    return path


def write_json(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
    Path(path).chmod(0o600)


def file_inventory(base):
    base=Path(base)
    result={}
    for path in sorted(base.rglob('*')):
        if path.is_symlink():raise ValueError('Symlink no permitido')
        if path.is_file():result[str(path.relative_to(base))]={'bytes':path.stat().st_size,'sha256':digest(path)}
    return result


def check_files(base,manifest):
    actual=file_inventory(base)
    expected=manifest['files']
    actual.pop('manifest.json',None)
    if actual!=expected:raise ValueError('Archivos faltantes/adicionales, tamaño o SHA-256 inválido')


def safe_extract(archive,destination):
    destination=Path(destination)
    with tarfile.open(archive) as tar:
        members=tar.getmembers();seen=set()
        for member in members:
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts or path.as_posix() in seen or not(member.isfile() or member.isdir()):
                raise ValueError('Entrada tar insegura o duplicada')
            seen.add(path.as_posix())
        tar.extractall(destination,members=members,filter='data')


def crypt(source,destination,key,decrypt=False):
    # Passphrase por FD anónimo, nunca argumentos, env, logs o archivo compartible.
    fd=os.memfd_create('retailops-backup-passphrase')
    try:
        os.write(fd,hmac.new(key,b'retailops-encryption-v1',hashlib.sha256).hexdigest().encode()+b'\n');os.lseek(fd,0,0)
        with Path(destination).open('xb') as output:
            subprocess.run(CIPHER+(['-d'] if decrypt else [])+['-pass',f'fd:{fd}','-in',str(source)],stdout=output,stderr=subprocess.PIPE,pass_fds=(fd,),check=True)
        Path(destination).chmod(0o600)
    finally:os.close(fd)


def mac(path,key):
    tag=hmac.new(hmac.new(key,b'retailops-authentication-v1',hashlib.sha256).digest(),digestmod=hashlib.sha256)
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):tag.update(block)
    return tag.hexdigest()


def verify_envelope(backup,keyfile):
    backup=outside_repo(backup);keyfile=Path(keyfile).resolve()
    if keyfile.stat().st_mode & 0o077:raise ValueError('Clave debe ser privada 0600')
    key=keyfile.read_bytes()
    if len(key)!=64:raise ValueError('Clave de formato inválido')
    envelope=json.loads((backup/'manifest.json').read_text())
    if envelope['format']!=FORMAT or envelope['status']!='complete':raise ValueError('Backup incompleto/formato inválido')
    payload=backup/'payload.enc'
    if payload.is_symlink() or digest(payload)!=envelope['sha256'] or not hmac.compare_digest(mac(payload,key),envelope['hmac_sha256']):
        raise ValueError('SHA-256/MAC inválido; no descifrar/restaurar')
    return envelope,key
