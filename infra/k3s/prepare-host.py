#!/usr/bin/env python3
"""Etapa administrativa autorizada: UFW acotado, install.sh y arranque K3s.

El usuario la ejecuta con sudo local; no elimina reglas ni datos. Rechaza
cualquier deriva respecto al informe revisado antes de modificar el host.
"""
from pathlib import Path
import hashlib
import fcntl
import ipaddress
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.local/f4'
ADDRESS = '192.168.0.121'
SERVER = 'https://' + ADDRESS + ':6443'
TAG = 'sha-abd1044fc28d6be41e7a274183cc675899370aa8'
# Solo las seis excepciones descritas en FIREWALL_PROPOSAL.md.
RULES = [
    ['allow', 'in', 'on', 'cni0', 'proto', 'tcp', 'from', '10.42.0.0/16', 'to', ADDRESS, 'port', '6443', 'comment', 'RetailOps K3s pods API'],
    ['allow', 'in', 'on', 'cni0', 'proto', 'tcp', 'from', '10.42.0.0/16', 'to', ADDRESS, 'port', '10250', 'comment', 'RetailOps K3s pods kubelet'],
    ['allow', 'in', 'on', 'cni0', 'proto', 'tcp', 'from', '10.42.0.0/16', 'to', '10.42.0.1', 'port', '15432,15000,19000,18081', 'comment', 'RetailOps Compose bridge'],
    ['route', 'allow', 'in', 'on', 'cni0', 'out', 'on', 'cni0', 'from', '10.42.0.0/16', 'to', '10.42.0.0/16', 'comment', 'RetailOps same-node pods'],
    ['route', 'allow', 'in', 'on', 'cni0', 'out', 'on', 'enp6s0', 'proto', 'udp', 'from', '10.42.0.0/16', 'to', '192.168.0.1', 'port', '53', 'comment', 'RetailOps pod DNS UDP'],
    ['route', 'allow', 'in', 'on', 'cni0', 'out', 'on', 'enp6s0', 'proto', 'tcp', 'from', '10.42.0.0/16', 'to', '192.168.0.1', 'port', '53', 'comment', 'RetailOps pod DNS TCP'],
]


def require(condition, message="Condición de seguridad incumplida"):
    if not condition:
        raise RuntimeError(message)


def normalize_rules(value):
    return '\n'.join(re.sub(r'\[\d+:\d+\]', '[0:0]', line)
                     for line in value.splitlines() if line and not line.startswith('#')) + '\n'


def run(args, timeout=60):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout)


def save(path, content, uid, gid):
    # No seguir symlinks ni sobrescribir evidencia previa.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
    os.chown(path, uid, gid)


def connectivity():
    socket.getaddrinfo('get.helm.sh', 443)
    with urllib.request.urlopen('https://get.helm.sh/helm-v3.17.3-linux-amd64.tar.gz.sha256sum', timeout=20) as response:
        require(response.status == 200)
    run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    # Imagen existente, contenedor efímero sin privilegios, verifica DNS Docker.
    run(['docker', 'run', '--rm', '--pull=never', '--read-only', '--cap-drop=ALL',
         '--security-opt=no-new-privileges', '--network=bridge', 'alpine:3.23',
         'sh', '-c', 'nslookup get.helm.sh >/dev/null'], timeout=40)


def main():
    require(os.geteuid() == 0 and os.environ.get('SUDO_UID'), 'Ejecutar con sudo desde la cuenta operadora')
    os.environ['LC_ALL'] = 'C'
    uid, gid = int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID'])
    require(not PRIVATE.is_symlink() and PRIVATE.is_dir())
    require(PRIVATE.stat().st_uid == uid and PRIVATE.stat().st_mode & 63 == 0)
    lock = os.open(PRIVATE / 'host-stage.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.chown(PRIVATE / 'host-stage.lock', uid, gid)
    reviewed = json.loads((PRIVATE / 'firewall-reviewed.json').read_text())
    original = ROOT / reviewed['report']
    require(hashlib.sha256(original.read_bytes()).hexdigest() == reviewed['sha256'], 'Informe revisado cambió')
    # No usar una revisión antigua para sobreescribir nuevas reglas de terceros.
    require(normalize_rules(run(['iptables-save'])) == reviewed['ipv4_normalized'], 'Deriva de reglas IPv4; detener y revisar')
    require(normalize_rules(run(['ip6tables-save'])) == reviewed['ipv6_normalized'], 'Deriva de reglas IPv6; detener y revisar')
    status = run(['ufw', 'status', 'verbose'])
    require('Status: active' in status and 'deny (incoming), allow (outgoing), deny (routed)' in status)
    require(not Path('/usr/local/bin/k3s').exists() and (not Path('/etc/rancher/k3s/config.yaml').exists()), 'K3s ya existe; inspeccionar antes de reutilizar')
    require(not (PRIVATE / 'kubeconfig').exists(), 'Conservar kubeconfig existente y revisar')
    run([sys.executable, 'infra/k3s/validate_config.py', str(PRIVATE / 'k3s-config.yaml')])
    require((PRIVATE / 'k3s-config.yaml').read_bytes() == (ROOT / 'infra/k3s/config.yaml.example').read_bytes(), 'Configuración no coincide con la revisada')
    spec = json.loads((ROOT / 'scripts/ci/tools.lock.json').read_text())['k3s-install']
    require(spec['version'] == 'v1.37.2+k3s1')
    require(hashlib.sha256((PRIVATE / 'tools/k3s-install').read_bytes()).hexdigest() == spec['sha256'])
    addresses = json.loads(run(['ip', '-j', 'address', 'show', 'dev', 'enp6s0']))
    require(any((a.get('local') == ADDRESS and a.get('prefixlen') == 24 for a in addresses[0]['addr_info'])))
    require('UP' in addresses[0]['flags'])
    defaults = json.loads(run(['ip', '-j', 'route', 'show', 'default']))
    preferred = min(defaults, key=lambda r: r.get('metric', 0))
    require(preferred['dev'] == 'enp6s0' and preferred['gateway'] == '192.168.0.1')
    require('nameserver 192.168.0.1' in Path('/run/systemd/resolve/resolv.conf').read_text())
    routes = json.loads(run(['ip', '-j', 'route']))
    for route in routes:
        if route.get('dst') != 'default':
            network = ipaddress.ip_network(route['dst'], strict=False)
            require(not any((network.overlaps(ipaddress.ip_network(c)) for c in ['10.42.0.0/16', '10.43.0.0/16'])), 'CIDR ocupado')
    for line in run(['ss', '-H', '-lntu']).splitlines():
        require(int(line.split()[4].rsplit(':', 1)[-1]) not in [6443, 6444, 8472, 10248, 10249, 10250, 10256, 10257, 10258, 10259, 15432, 15000, 19000, 18081], 'Puerto ocupado')
    require({'cpu', 'memory', 'pids'} <= set(Path('/sys/fs/cgroup/cgroup.controllers').read_text().split()))
    require(run(['systemctl', 'is-active', 'docker']).strip() == 'active')
    for name in ['web', 'api', 'ml-service']:
        run(['docker', 'image', 'inspect', f'retailops-{name}:{TAG}', '--format', '{{.Id}}'])
    connectivity()
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    evidence = PRIVATE / ('host-stage-' + stamp)
    evidence.mkdir(mode=0o700)
    os.chown(evidence, uid, gid)
    def record(name, value):
        save(evidence / name, value, uid, gid)
    record('before-ipv4.txt', run(['iptables-save']))
    record('before-ipv6.txt', run(['ip6tables-save']))
    record('before-routes.json', run(['ip', '-j', 'route']))
    record('before-ufw.txt', status)
    record('revert-proposed.txt', '\n'.join(shlex.join(['sudo', 'ufw'] + (['route', 'delete'] + r[1:] if r[0] == 'route' else ['delete'] + r)) for r in reversed(RULES)) + '\n')
    applied = []
    started = False
    try:
        for index, rule in enumerate(RULES):
            # Baseline verificada: no hay reglas equivalentes; UFW además evita duplicados exactos.
            output = run(['ufw'] + rule)
            record(f'ufw-{index + 1}.txt', output)
            require('Rule added' in output or 'Rules added' in output, 'Resultado UFW inesperado; revisar antes de continuar')
            applied.append(shlex.join(['ufw'] + rule))
            record(f'applied-{index + 1}.json', json.dumps(applied, indent=2) + '\n')
        after = run(['iptables-save'])
        require(':INPUT DROP ' in after and ':FORWARD DROP ' in after)
        record('after-ufw.txt', run(['ufw', 'status', 'verbose']))
        connectivity()
        print('Seis excepciones internas añadidas; Docker y conectividad comprobados.', flush=True)
        result = subprocess.run(['bash', 'infra/k3s/install.sh'], cwd=ROOT,
                                env={**os.environ, 'AUTHORIZE_HOST_INSTALL': 'install-k3s'},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=900)
        record('install.log', result.stdout)
        require(result.returncode == 0, 'Instalador falló; revisar install.log privado')
        enabled = subprocess.run(['systemctl', 'is-enabled', 'k3s'], capture_output=True, text=True)
        require(enabled.stdout.strip() == 'disabled', 'Estado de habilitación inesperado; detener sin modificarlo')
        run(['systemctl', 'daemon-reload'])
        started = True
        run(['systemctl', 'start', 'k3s'], timeout=180)
        client = ['/usr/local/bin/k3s', 'kubectl', '--server', SERVER]
        for _ in range(120):
            result = subprocess.run(client + ['get', 'nodes', '-o', 'json'], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                nodes = json.loads(result.stdout)['items']
                if len(nodes) == 1 and any(c['type'] == 'Ready' and c['status'] == 'True' for c in nodes[0]['status']['conditions']):
                    break
            time.sleep(2)
        else:
            raise RuntimeError('Nodo no está Ready; conservar evidencia y detener servicio')
        record('nodes-ready.json', result.stdout)
        kubeconfig = Path('/etc/rancher/k3s/k3s.yaml').read_text()
        kubeconfig = kubeconfig.replace('https://127.0.0.1:6443', SERVER)
        save(PRIVATE / 'kubeconfig', kubeconfig, uid, gid)
        archive = evidence / 'images.tar'
        run(['docker', 'save', '-o', str(archive)] + [f'retailops-{n}:{TAG}' for n in ['web', 'api', 'ml-service']], timeout=300)
        os.chmod(archive, 0o600)
        os.chown(archive, uid, gid)
        record('import-images.log', run(['/usr/local/bin/k3s', 'ctr', 'images', 'import', str(archive)], timeout=300))
        connectivity()
        final_v4 = run(['iptables-save'])
        final_v6 = run(['ip6tables-save'])
        require(':INPUT DROP ' in final_v4 and ':FORWARD DROP ' in final_v4, 'Políticas IPv4 cambiaron')
        require(':INPUT DROP ' in final_v6 and ':FORWARD DROP ' in final_v6, 'Políticas IPv6 cambiaron')
        require(set(reviewed['ipv4_normalized'].splitlines()) <= set(normalize_rules(final_v4).splitlines()), 'Reglas IPv4 preexistentes alteradas')
        require(set(reviewed['ipv6_normalized'].splitlines()) <= set(normalize_rules(final_v6).splitlines()), 'Reglas IPv6 preexistentes alteradas')
        new_defaults = json.loads(run(['ip', '-j', 'route', 'show', 'default']))
        fields = lambda rows: sorted((r.get('gateway'), r.get('dev'), r.get('metric', 0)) for r in rows)
        require(fields(defaults) == fields(new_defaults), 'Rutas por defecto cambiaron')
        record('after-ipv4.txt', final_v4)
        record('after-ipv6.txt', final_v6)
        record('after-routes.json', run(['ip', '-j', 'route']))
        record('after-services.txt', run(['systemctl', 'is-active', 'docker', 'ufw', 'k3s']))
        record('success.json', json.dumps({'ready': True, 'image_tag': TAG, 'k3s_auto_enabled': False, 'rules_added': len(applied), 'app_deployed': False}, indent=2) + '\n')
        print(f'K3s Ready e imágenes importadas. Evidencia privada: {evidence}\nServicio iniciado para continuar F4; aplicación todavía sin desplegar.', flush=True)
    except BaseException:
        if started:
            subprocess.run(['systemctl', 'stop', 'k3s'], timeout=180)
        # Conservar reglas añadidas y su registro: no borrar ni revertir automáticamente.
        print(f'Etapa detenida. Revisar evidencia privada: {evidence}; no repetir sin revisar el estado parcial.', flush=True)
        raise


if __name__ == '__main__':
    main()
