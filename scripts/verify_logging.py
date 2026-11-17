"""Comprueba LogQL real, datasource Grafana y correlación sin generar inferencias."""
import base64
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local/f52'
LOKI = 'http://127.0.0.1:3101'
GRAFANA = 'http://127.0.0.1:3001'


def get(base, path, grafana=False):
    headers = {}
    if grafana:
        user = (ROOT/'.local/f51/grafana-admin-user').read_text().strip()
        password = (ROOT/'.local/f51/grafana-admin-password').read_text().strip()
        headers['Authorization'] = 'Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode()
    with urllib.request.urlopen(urllib.request.Request(base+path, headers=headers), timeout=40) as response:
        return json.load(response)


def query(expression, base=LOKI, grafana=False):
    prefix = '/api/datasources/proxy/uid/retailops-loki' if grafana else ''
    params = urllib.parse.urlencode({'query': expression, 'since': '1h', 'limit': 500})
    result = get(base, prefix+'/loki/api/v1/query_range?'+params, grafana)
    assert result['status'] == 'success'
    return result['data']['result']


def main():
    report = {'services': {}, 'queries': [], 'correlation': None}
    assert get(GRAFANA, '/api/datasources/uid/retailops-loki/health', True)['status'] == 'OK'
    dashboard = get(GRAFANA, '/api/dashboards/uid/retailops-logs', True)['dashboard']
    source = json.loads((ROOT/'infra/helm/retailops-observability/files/logs-dashboard.json').read_text())
    assert [p['targets'][0]['expr'] for p in dashboard['panels']] == [p['targets'][0]['expr'] for p in source['panels']]
    lines = []
    for service in ['api', 'ml', 'web']:
        result = query('{environment="local",service="'+service+'"}')
        assert result, 'Sin logs reales: '+service
        assert all({'service', 'namespace', 'container', 'environment'} <= set(stream['stream']) <= {'service', 'namespace', 'container', 'environment', 'service_name'} for stream in result)
        assert all(stream['stream'].get('service_name', service) == service for stream in result)
        count = sum(len(stream['values']) for stream in result)
        report['services'][service] = count
        lines += [value[1] for stream in result for value in stream['values']]
    for panel in source['panels']:
        expr = panel['targets'][0]['expr'].replace('${request_id:regex}', '.*')
        for base, proxy in [(LOKI, False), (GRAFANA, True)]:
            result = query(expr, base, proxy)
            report['queries'].append({'title': panel['title'], 'via': 'grafana' if proxy else 'loki', 'streams': len(result)})
    # Metadatos reales del modelo: GET sin predicción ni mutaciones.
    with urllib.request.urlopen('http://127.0.0.1:5174/api/v1/models/active', timeout=30) as response:
        response.read()
        identity = response.headers.get('X-Request-ID')
    assert identity and re.fullmatch('[a-f0-9]{32}', identity)
    expr = '{environment="local"} | json | request_id="'+identity+'"'
    for attempt in range(20):
        result = query(expr)
        services = {stream['stream']['service'] for stream in result}
        if {'api', 'ml', 'web'} <= services:
            break
        time.sleep(1)
    assert {'api', 'ml', 'web'} <= services, 'Correlación incompleta: '+str(services)
    report['correlation'] = {'request_id': identity, 'services': sorted(services)}
    serialized = '\n'.join(lines)
    # Comparación privada, sin imprimir contenido ni secretos al fallar.
    for path in (ROOT/'.local/secrets').iterdir():
        if not path.is_file(): continue
        try: value = path.read_text().strip()
        except UnicodeError: continue
        if len(value) >= 8:
            assert value not in serialized, 'Secreto encontrado en logs; no compartir evidencia'
    assert not re.search(r'(?i)(authorization|password|access_token|jdbc:|postgresql://)', serialized)
    report['secret_scan'] = 'Muestra de hasta 500 líneas/servicio, secretos locales y patrones; no auditoría exhaustiva'
    output = PRIVATE / ('verification-'+str(time.time_ns())+'.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    output.chmod(0o600)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
