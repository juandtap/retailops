"""Smoke HTTP K3s de solo lectura y rechazo de operaciones sin consentimiento."""
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5174'
evidence = {}


def request(path, payload=None, expected=200):
    req = urllib.request.Request(BASE + path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read()
        if response.status != expected:
            raise RuntimeError(f'{path}: HTTP {response.status}, esperado {expected}')
        value = json.loads(body) if path.startswith('/api/') else body.decode()
    evidence[path + (f':{expected}' if expected != 200 else '')] = value
    print(path, expected)
    return value


html = request('/')
assert '<html' in html.lower()
asset = re.search(r'<script[^>]+src="([^"]+)"', html)
assert asset and len(request(asset.group(1))) > 1000
assert request('/api/actuator/health')['status'] == 'UP'
platform = request('/api/v1/platform')
assert platform['history']['cutoff'] == '2014-12-31'
assert all(item['status'] == 'UP' for item in platform['services'])
batches = request('/api/v1/history/batches')
assert len(batches) == 1 and batches[0]['rows'] == 1297296
assert len(request('/api/v1/catalog/stores')) == 54
assert len(request('/api/v1/catalog/families')) == 33
sales_path = '/api/v1/sales?storeNbr=1&family=GROCERY%20I&from=2014-12-01&to=2014-12-31'
sales = request(sales_path)
assert sales['total'] == 30 and len(sales['items']) == 30
assert '2014-12-25' not in [row['date'] for row in sales['items']]
request(sales_path.replace('to=2014-12-31', 'to=2015-01-01'), expected=400)
model = request('/api/v1/models/active')
assert model['status'] == 'NO_APPROVED_MODEL'
assert model['candidate']['version'] == '1'
assert model['candidate']['production_approved'] is False
assert model['candidate']['run_id'] == '55257fc2ce414793b73b9d0df4c95fbb'
assert len(request('/api/v1/pipelines')['dags']) == 4
request('/api/v1/predictions', {'storeNbr': 1, 'family': 'GROCERY I', 'issueDate': '2014-12-31'}, expected=409)
# Comparar respuestas API con secretos locales sin imprimirlos. No guardar el bundle JS.
evidence.pop(asset.group(1))
serialized = json.dumps(evidence)
for path in Path('.local/secrets').iterdir():
    if not path.is_file():
        continue
    raw = path.read_text().strip()
    values = [raw]
    if path.suffix == '.json':
        item = json.loads(raw)
        if isinstance(item, dict):
            values += [v for k, v in item.items() if isinstance(v, str) and k != 'username']
    assert all(len(v) < 12 or v not in serialized for v in values), 'Respuesta contiene secreto local'
output = Path('.local/f4') / f'smoke-{time.time_ns()}.json'
output.write_text(json.dumps(evidence, indent=2) + '\n')
output.chmod(0o600)
print('Smoke integrado correcto; evidencia privada:', output)
