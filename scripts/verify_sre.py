"""Verificación real de SRE y prueba explícita de alertas sintéticas reversibles."""
import argparse
import base64
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/'.local/f53'
PROM='http://127.0.0.1:9091'
AM='http://127.0.0.1:9094'
RECEIVER='http://127.0.0.1:8091'
GRAFANA='http://127.0.0.1:3001'


def http(base,path,value=None,method=None,grafana=False):
    headers={}
    if value is not None: headers['Content-Type']='application/json'
    if grafana:
        user=(ROOT/'.local/f51/grafana-admin-user').read_text().strip()
        password=(ROOT/'.local/f51/grafana-admin-password').read_text().strip()
        headers['Authorization']='Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode()
    request=urllib.request.Request(base+path,data=json.dumps(value).encode() if value is not None else None,headers=headers,method=method)
    with urllib.request.urlopen(request,timeout=40) as response:
        body=response.read()
        return json.loads(body) if body else None


def query(expr):
    value=http(PROM,'/api/v1/query?'+urllib.parse.urlencode({'query':expr}))
    assert value['status']=='success'
    return value['data']['result']


def until(check,description,timeout=210):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=check()
        if value:return value
        time.sleep(2)
    raise AssertionError('Timeout: '+description)


def state(mode):
    subprocess.run(['python',str(ROOT/'scripts/sre_state.py'),mode],check=True,cwd=ROOT)


def save(name,value):
    path=PRIVATE/name;path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');path.chmod(0o600)


def live():
    targets=http(PROM,'/api/v1/targets')['data']['activeTargets']
    assert {t['labels']['job'] for t in targets}=={'prometheus','spring','fastapi','lab','alertmanager','alert-receiver'}
    assert all(t['health']=='up' for t in targets)
    groups=http(PROM,'/api/v1/rules')['data']['groups']
    assert len(groups)==3 and all(r['health']=='ok' for g in groups for r in g['rules'])
    assert len(http(PROM,'/api/v1/alertmanagers')['data']['activeAlertmanagers'])==1
    dashboard=http(GRAFANA,'/api/dashboards/uid/retailops-sre',grafana=True)['dashboard']
    source=json.loads((ROOT/'infra/helm/retailops-observability/files/alerting/dashboard.json').read_text())
    assert [p['targets'][0]['expr'] for p in source['panels']]==[p['targets'][0]['expr'] for p in dashboard['panels']]
    queries=[]
    for panel in source['panels']:
        expr=panel['targets'][0]['expr'];values=query(expr)
        proxied=http(GRAFANA,'/api/datasources/proxy/uid/retailops-prometheus/api/v1/query?'+urllib.parse.urlencode({'query':expr}),grafana=True)
        assert proxied['status']=='success'
        queries.append({'title':panel['title'],'expr':expr,'series':len(values),'values':[v['value'][1] for v in values]})
    availability=query('retailops:sli_availability:ratio')
    assert {r['metric']['service'] for r in availability}=={'api','ml'}
    assert all(float(v['value'][1])==1 for v in availability)
    for uid in ['retailops-logs','retailops-http']:
        assert http(GRAFANA,'/api/dashboards/uid/'+uid,grafana=True)['dashboard']['uid']==uid
    expr='{environment="local"}'
    logs=http(GRAFANA,'/api/datasources/proxy/uid/retailops-loki/loki/api/v1/query_range?'+urllib.parse.urlencode({'query':expr,'since':'15m','limit':3}),grafana=True)
    assert logs['status']=='success' and logs['data']['result']
    operational=query('ALERTS{scope="operational",alertstate="firing"}')
    save('live-verification.json',{'targets':[(t['labels']['job'],t['health']) for t in targets],'rules':sum(len(g['rules']) for g in groups),'queries':queries,'operational_firing':operational,'navigation':'Dashboards destino, URLs de enlaces y proxy verificados por API; sin prueba visual navegador'})
    print('Targets UP, reglas saludables, dashboard/consultas y navegación API verificadas',flush=True)


def controlled():
    started=time.time()
    try:
        state('validation-on')
        firing=until(lambda:[e for e in http(RECEIVER,'/events') if e['timestamp']>=started and e['status']=='firing' and {a['labels'].get('case') for a in e['alerts'] if a['labels'].get('alertname')=='RetailOpsValidationSignal'}=={'api','ml'}], 'notificación firing agrupada')
        save('notification-firing.json',firing)
        print('Dos señales sintéticas agrupadas recibidas desde Prometheus/Alertmanager',flush=True)
        count=len(firing)
        time.sleep(25)
        repeated=[e for e in http(RECEIVER,'/events') if e['timestamp']>=started and e['status']=='firing' and any(a['labels'].get('alertname')=='RetailOpsValidationSignal' for a in e['alerts'])]
        assert len(repeated)==count,'Repetición inesperada en ventana de deduplicación'
        state('validation-off')
        resolved=until(lambda:[e for e in http(RECEIVER,'/events') if e['timestamp']>=started and e['status']=='resolved' and {a['labels'].get('case') for a in e['alerts'] if a['labels'].get('alertname')=='RetailOpsValidationSignal'}=={'api','ml'}], 'notificación resolved agrupada')
        save('notification-resolved.json',resolved)
        print('Resolución agrupada recibida, sin repetición en ventana de 25s',flush=True)
    finally:
        state('validation-off')
    now=datetime.now(timezone.utc)
    def stamp(value):return value.isoformat().replace('+00:00','Z')
    alerts=[{'labels':{'alertname':name,'service':'api','scope':'validation','environment':'local','category':'validation','severity':'info'},'startsAt':stamp(now),'endsAt':stamp(now+timedelta(minutes=5)),'annotations':{'summary':'Prueba sintética de inhibición, no incidente'}} for name in ['RetailOpsServiceUnavailable','RetailOpsHttp5xx']]
    try:
        http(AM,'/api/v2/alerts',alerts)
        inhibited=until(lambda:[a for a in http(AM,'/api/v2/alerts') if a['labels'].get('alertname')=='RetailOpsHttp5xx' and a['labels'].get('scope')=='validation' and a['status']['inhibitedBy']], 'inhibición efectiva')
        save('inhibition.json',inhibited)
    finally:
        for a in alerts:a['endsAt']=stamp(datetime.now(timezone.utc))
        http(AM,'/api/v2/alerts',alerts)
    silence={'matchers':[{'name':'scope','value':'validation','isRegex':False,'isEqual':True},{'name':'alertname','value':'RetailOpsSilenceProbe','isRegex':False,'isEqual':True}],'startsAt':stamp(now),'endsAt':stamp(now+timedelta(minutes=20)),'createdBy':'retailops-local-validation','comment':'Prueba reversible F5.3, sin notificaciones externas'}
    identity=http(AM,'/api/v2/silences',silence)['silenceID']
    probe={'labels':{'alertname':'RetailOpsSilenceProbe','scope':'validation','environment':'local','category':'validation','severity':'info'},'startsAt':stamp(now),'endsAt':stamp(now+timedelta(minutes=5))}
    try:
        http(AM,'/api/v2/alerts',[probe])
        suppressed=until(lambda:[a for a in http(AM,'/api/v2/alerts') if a['labels'].get('alertname')=='RetailOpsSilenceProbe' and identity in a['status']['silencedBy']], 'silencio efectivo')
        save('silence-proof.json',{'silence_id':identity,'suppressed':suppressed})
    finally:
        probe['endsAt']=stamp(datetime.now(timezone.utc));http(AM,'/api/v2/alerts',[probe])
    # Conservar solo el silencio de prueba para verificar persistencia después del restart.
    save('controlled-result.json',{'grouped':True,'resolved':True,'dedup_observed_seconds':25,'inhibition':True,'silence_id':identity,'scope':'validation','no_service_failures':True})
    print('Inhibición y silencio efectivos; silencio de prueba listo para verificar persistencia',flush=True)


def persistence():
    proof=json.loads((PRIVATE/'controlled-result.json').read_text());identity=proof['silence_id']
    silence=http(AM,'/api/v2/silence/'+identity)
    assert silence['status']['state']=='active'
    old=json.loads((PRIVATE/'notification-firing.json').read_text())
    stored=http(RECEIVER,'/events');ids={e['id'] for e in stored}
    assert all(e['id'] in ids for e in old)
    http(AM,'/api/v2/silence/'+identity,method='DELETE')
    save('persistence-result.json',{'silence_survived':True,'receiver_events_survived':True,'silence_expired_after_test':True})
    print('Silencio y eventos persistieron; silencio de prueba expirado',flush=True)


def dedup():
    started=time.time()
    now=datetime.now(timezone.utc)
    stamp=lambda value:value.isoformat().replace('+00:00','Z')
    alerts=[{'labels':{'alertname':'RetailOpsDedupProbe','case':case,'scope':'validation','environment':'local','category':'validation','severity':'info'},'startsAt':stamp(now),'endsAt':stamp(now+timedelta(minutes=5))} for case in ['api','ml']]
    def events(status):
        return [e for e in http(RECEIVER,'/events') if e['timestamp']>=started and e['status']==status and {a['labels'].get('case') for a in e['alerts'] if a['labels'].get('alertname')=='RetailOpsDedupProbe'}=={'api','ml'}]
    try:
        http(AM,'/api/v2/alerts',alerts)
        first=until(lambda:events('firing'),'primera entrega dedup')
        http(AM,'/api/v2/alerts',alerts)
        http(AM,'/api/v2/alerts',alerts)
        time.sleep(25)
        assert len(events('firing'))==len(first),'Duplicado notificado antes del repeat_interval'
    finally:
        for alert in alerts:alert['endsAt']=stamp(datetime.now(timezone.utc))
        http(AM,'/api/v2/alerts',alerts)
    resolved=until(lambda:events('resolved'),'resolución dedup')
    save('dedup-proof.json',{'duplicate_submissions':2,'observed_seconds':25,'firing_notifications':len(first),'resolved_notifications':len(resolved),'events':first+resolved,'scope':'validation'})
    print('Dos reenvíos idénticos: una entrega agrupada y resolución verificadas',flush=True)


def inactive():
    state('inactive')
    until(lambda:query('retailops:lab_active == 0'), 'señal de cierre observada')
    until(lambda:not query('ALERTS{scope="operational"}'),'reglas operativas inactivas')
    assert not query('retailops_alert_test_signal == 1')
    save('inactive-proof.json',{'lab_active':0,'operational_alerts':0,'validation_signals':0})
    print('Cierre planificado observado; sin alertas operativas antes de escalar a cero',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['live','controlled','persistence','dedup','inactive']);args=parser.parse_args()
    globals()[args.mode]()


if __name__=='__main__':main()
