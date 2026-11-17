"""Valida targets/PromQL/Grafana locales; distingue datos ausentes de prueba completa."""
import argparse
import base64
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-apps-stopped', action='store_true')
    args = parser.parse_args()
    private = Path('.local/f51')
    user = (private/'grafana-admin-user').read_text().strip()
    password = (private/'grafana-admin-password').read_text().strip()
    auth = 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()

    def get(base, path, grafana=False):
        request = urllib.request.Request(base+path, headers={'Authorization':auth} if grafana else {})
        with urllib.request.urlopen(request, timeout=35) as response:
            assert response.status == 200
            return json.load(response)

    prom, graf = 'http://127.0.0.1:9091', 'http://127.0.0.1:3001'
    report = {'targets':[], 'queries':[], 'dashboards':[], 'app_metrics_complete':False}
    targets = get(prom, '/api/v1/targets')['data']['activeTargets']
    assert {t['labels']['job'] for t in targets} == {'spring','fastapi','lab','prometheus'}
    for target in targets:
        job, health = target['labels']['job'], target['health']
        report['targets'].append({'job':job,'health':health,'lastError':target['lastError']})
        if job in {'lab','prometheus'} or not args.allow_apps_stopped:
            assert health == 'up', f'Target {job} no está UP'
    report['app_metrics_complete'] = all(t['health']=='up' for t in targets)
    for expression in ['retailops_kubernetes_node_ready', 'retailops_kubernetes_container_memory_working_set_bytes{namespace="retailops-observability"}']:
        value = get(prom, '/api/v1/query?'+urllib.parse.urlencode({'query':expression}))
        assert value['status']=='success' and value['data']['result'], 'Sin series reales: '+expression
        report['queries'].append({'expr':expression,'series':len(value['data']['result'])})
    assert get(graf, '/api/health')['database']=='ok'
    health = get(graf, '/api/datasources/uid/retailops-prometheus/health', True)
    assert health['status']=='OK'
    proxied = get(graf, '/api/datasources/proxy/uid/retailops-prometheus/api/v1/query?query=retailops_kubernetes_node_ready', True)
    assert proxied['data']['result'], 'Grafana no obtiene las series Prometheus'
    report['grafana_datasource_health'] = health['status']
    for path in sorted(Path('infra/helm/retailops-observability/files/dashboards').glob('*.json')):
        source=json.loads(path.read_text())
        stored=get(graf, '/api/dashboards/uid/'+source['uid'], True)['dashboard']
        assert stored['uid']==source['uid'] and stored['title']==source['title']
        assert [t['legendFormat'] for p in source['panels'] for t in p['targets']]==[t['legendFormat'] for p in stored['panels'] for t in p['targets']]
        expressions=[t['expr'] for p in source['panels'] for t in p['targets']]
        assert expressions==[t['expr'] for p in stored['panels'] for t in p['targets']]
        report['dashboards'].append(source['uid'])
        for expression in expressions:
            result=get(prom, '/api/v1/query?'+urllib.parse.urlencode({'query':expression}))
            assert result['status']=='success'
            report['queries'].append({'expr':expression,'series':len(result['data']['result'])})
    if not args.allow_apps_stopped:
        for expression in ['http_server_requests_seconds_count{job="spring"}', 'retailops_ml_http_requests_total', 'retailops_ml_model_loaded == 1', 'retailops_dependency_up']:
            result=get(prom, '/api/v1/query?'+urllib.parse.urlencode({'query':expression}))
            assert result['status']=='success' and result['data']['result'], 'Métrica no verificada: '+expression
    assert password not in json.dumps(report)
    output = private/f'verification-{time.time_ns()}.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');output.chmod(0o600)
    print('Targets:',[(t['job'],t['health']) for t in report['targets']])
    print('Datasource Grafana OK; dashboards reales:',len(report['dashboards']),'consultas ejecutadas:',len(report['queries']))
    print('Validación de métricas app completa:',report['app_metrics_complete'],'Evidencia privada:',output)


if __name__ == '__main__':
    main()
