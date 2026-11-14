"""Smoke HTTP F3; no ingesta, entrenamiento, registro ni disparo de DAGs."""
import argparse
import json
import subprocess
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '-f', str(ROOT/'infra/docker/compose.yaml'),
           '--profile', 'app', '--profile', 'mlops', '--profile', 'airflow']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:5173')
    parser.add_argument('--check-ml-outage', action='store_true',
                        help='Detiene solo FastAPI y lo restaura en finally; requiere Docker')
    args = parser.parse_args()
    evidence = {}

    def request(path, payload=None, expected=200):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(args.base_url+'/api/v1'+path, data=body,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                status, value = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status, value = error.code, json.load(error)
        assert status == expected, (path, status, expected)
        evidence[path if payload is None else f'{path}:{expected}'] = value
        return value

    platform = request('/platform')
    assert platform['history']['cutoff'] == '2014-12-31'
    assert all(s['status'] == 'UP' for s in platform['services'])
    batches = request('/history/batches')
    assert len(batches) == 1 and batches[0]['rows'] == 1297296
    assert len(request('/catalog/stores')) == 54
    assert len(request('/catalog/families')) == 33
    sales_path = '/sales?storeNbr=1&family=GROCERY%20I&from=2014-12-01&to=2014-12-31'
    sales = request(sales_path)
    assert sales['total'] == 30 and len(sales['items']) == 30
    assert '2014-12-25' not in [r['date'] for r in sales['items']]
    request(sales_path.replace('to=2014-12-31', 'to=2015-01-01'), expected=400)
    model = request('/models/active')
    assert model['status'] == 'NO_APPROVED_MODEL'
    assert model['candidate']['version'] == '1' and not model['candidate']['production_approved']
    assert model['candidate']['metrics']['evaluation_hgb_mae'] > model['candidate']['metrics']['evaluation_seasonal_naive_7_mae']
    pipelines = request('/pipelines')
    assert len(pipelines['dags']) == 4
    payload = {'storeNbr': 1, 'family': 'GROCERY I', 'issueDate': '2014-12-31'}
    request('/predictions', payload, expected=409)
    payload['candidateDemo'] = True
    forecast = request('/predictions', payload)
    assert not forecast['productionApproved'] and forecast['mode'] == 'CANDIDATE_DEMO'
    assert len(forecast['predictions']) == 7
    for horizon, point in enumerate(forecast['predictions'], 1):
        assert point['horizon'] == horizon
        assert point['targetDate'] == (date(2014, 12, 31)+timedelta(days=horizon)).isoformat()
        assert point['prediction'] >= 0
    request('/predictions', {**payload, 'issueDate': '2015-01-01'}, expected=400)
    if args.check_ml_outage:
        try:
            subprocess.run(COMPOSE+['stop', 'ml-service'], check=True)
            failure = request('/predictions', payload, expected=503)
            assert failure['code'] == 'ML_UNAVAILABLE'
        finally:
            subprocess.run(COMPOSE+['up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', 'ml-service'], check=True)
        assert request('/models/active')['candidate']['version'] == '1'
        evidence['ml_outage_recovery'] = 'verified'
    # Comparación privada: nunca imprimir valores de credenciales.
    serialized = json.dumps(evidence)
    for secret in (ROOT/'.local/secrets').iterdir():
        if not secret.is_file():
            continue
        raw = secret.read_text().strip()
        values = [raw]
        if secret.suffix == '.json':
            value = json.loads(raw)
            if isinstance(value, dict):
                values += [v for k, v in value.items() if isinstance(v, str) and k not in ('username',)]
        assert all(len(v) < 12 or v not in serialized for v in values), 'Respuesta contiene secreto local'
    destination = ROOT/'.local/application/smoke.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2)+'\n')
    print('Smoke F3 correcto; evidencia privada en .local/application/smoke.json')


if __name__ == '__main__':
    main()
