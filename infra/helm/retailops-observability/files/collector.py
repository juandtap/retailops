"""Adaptador de las APIs Kubernetes/metrics-server; sin acceso al host o Secrets."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.request

TOKEN = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
CA = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
NAMESPACE = os.environ.get('APPLICATION_NAMESPACE', 'retailops')
API = 'https://kubernetes.default.svc'


def quantity(value, cpu=False):
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)([A-Za-z]*)', str(value))
    if not match:
        raise ValueError('Cantidad Kubernetes inválida')
    scales = {'': 1, 'n': 1e-9, 'u': 1e-6, 'm': .001} if cpu else {'': 1, 'Ki': 2**10, 'Mi': 2**20, 'Gi': 2**30, 'Ti': 2**40, 'K': 1000, 'M': 1000**2, 'G': 1000**3}
    return float(match[1]) * scales[match[2]]


def get(path):
    request = urllib.request.Request(API + path, headers={'Authorization': 'Bearer ' + TOKEN.read_text().strip()})
    with urllib.request.urlopen(request, context=ssl.create_default_context(cafile=CA), timeout=4) as response:
        return json.load(response)


def sample(name, value, **labels):
    text = ','.join(key + '=' + json.dumps(str(item)) for key, item in sorted(labels.items()))
    return name + ('{' + text + '}' if text else '') + ' ' + str(float(value)) + '\n'


def kubernetes(fetch=get, namespace=NAMESPACE, include_nodes=True):
    text = ''
    for section, path in [
        ('nodes', '/api/v1/nodes'),
        ('pods', f'/api/v1/namespaces/{namespace}/pods'),
        ('deployments', f'/apis/apps/v1/namespaces/{namespace}/deployments'),
        ('usage', f'/apis/metrics.k8s.io/v1beta1/namespaces/{namespace}/pods'),
    ]:
        if section == 'nodes' and not include_nodes:
            continue
        try:
            data = fetch(path)
            for item in data['items']:
                name = item['metadata']['name']
                if section == 'nodes':
                    ready = any(c['type'] == 'Ready' and c['status'] == 'True' for c in item['status'].get('conditions', []))
                    text += sample('retailops_kubernetes_node_ready', ready, node=name)
                elif section == 'deployments':
                    for suffix, value in [('desired', item['spec'].get('replicas', 1)), ('available', item.get('status', {}).get('availableReplicas', 0))]:
                        text += sample(f'retailops_kubernetes_deployment_{suffix}_replicas', value, namespace=namespace, deployment=name)
                elif section == 'pods':
                    ready = any(c['type'] == 'Ready' and c['status'] == 'True' for c in item.get('status', {}).get('conditions', []))
                    text += sample('retailops_kubernetes_pod_ready', ready, namespace=namespace, pod=name)
                    for container in item['spec']['containers']:
                        labels = {'namespace': namespace, 'pod': name, 'container': container['name']}
                        for group in ['requests', 'limits']:
                            values = container.get('resources', {}).get(group, {})
                            if 'cpu' in values:
                                text += sample(f'retailops_kubernetes_container_cpu_{group}_cores', quantity(values['cpu'], True), **labels)
                            if 'memory' in values:
                                text += sample(f'retailops_kubernetes_container_memory_{group}_bytes', quantity(values['memory']), **labels)
                else:
                    for container in item['containers']:
                        labels = {'namespace': namespace, 'pod': name, 'container': container['name']}
                        text += sample('retailops_kubernetes_container_cpu_cores', quantity(container['usage']['cpu'], True), **labels)
                        text += sample('retailops_kubernetes_container_memory_working_set_bytes', quantity(container['usage']['memory']), **labels)
            text += sample('retailops_collector_section_success', 1, section=section, namespace='cluster' if section == 'nodes' else namespace)
        except (OSError, ValueError, KeyError, TypeError):
            text += sample('retailops_collector_section_success', 0, section=section, namespace='cluster' if section == 'nodes' else namespace)
    return text


def collect():
    text = kubernetes() + kubernetes(namespace='retailops-observability', include_nodes=False)
    # /platform realiza SQL read-only y probes HTTP. No confundir UP con modelo aprobado.
    try:
        url = f'http://api.{NAMESPACE}.svc:8080/v1/platform'
        with urllib.request.urlopen(url, timeout=8) as response:
            platform = json.load(response)
        text += sample('retailops_dependency_up', 1, service='postgresql', probe='sql')
        allowed = {'fastapi', 'mlflow', 'minio', 'airflow'}
        for service in platform['services']:
            if service['name'] in allowed:
                text += sample('retailops_dependency_up', service['status'] == 'UP', service=service['name'], probe='http')
        text += sample('retailops_collector_section_success', 1, section='dependencies')
    except (OSError, ValueError, KeyError, TypeError):
        # No inventar estados de dependencias que no se pudieron observar.
        text += sample('retailops_collector_section_success', 0, section='dependencies')
    return text + sample('retailops_collector_scrape_timestamp_seconds', time.time())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            body, code = b'ok\n', 200
        elif self.path == '/metrics':
            body, code = collect().encode(), 200
        else:
            body, code = b'not found\n', 404
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8088), Handler).serve_forever()
