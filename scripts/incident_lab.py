"""F5.5-A: consultas; start futuro requiere aprobación F5.5-B privada y preflight vivo."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import base64

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import importlib.util
spec=importlib.util.spec_from_file_location('incident_controller',ROOT/'infra/incident-lab/controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

TOOLS=ROOT/'.local/f4/tools';STATE=c.PRIVATE/'active/state.json'


def mem_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):return int(line.split()[1])*1024
    raise ValueError('Sin lectura fiable de margen RAM')


class Backend:
    def __init__(self,kubeconfig,context='default',writable=False):
        if context!='default':raise ValueError('Solo contexto local default revisado; no clúster arbitrario')
        self.context=context;self.kubeconfig=str(Path(kubeconfig).resolve());self.writable=writable
        self.base=[str(TOOLS/'kubectl'),'--kubeconfig',self.kubeconfig,'--context',context]
    def call(self,args):
        return subprocess.run(self.base+args,capture_output=True,text=True,check=True).stdout
    def server(self):return self.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']).strip()
    def namespace(self):
        raw=self.call(['get','namespace',c.NAMESPACE,'-o','json','--ignore-not-found'])
        return json.loads(raw) if raw.strip() else None
    def check_namespace(self,uid=None):
        ns=self.namespace()
        if not ns or ns['metadata'].get('labels',{}).get('retailops.io/purpose')!='incident-training':raise ValueError('Namespace exclusivo no provisionado/autorizado')
        if uid and ns['metadata']['uid']!=uid:raise ValueError('Namespace recreado: UID distinto')
        return ns['metadata']['uid']
    def get(self,kind,name):return json.loads(self.call(['-n',c.NAMESPACE,'get',kind,name,'-o','json']))
    def change(self,kind,name,path,value,uid):
        if not self.writable:raise ValueError('Backend de solo lectura; F5.5-A no ejecuta')
        if (kind,name) not in c.MUTABLE:raise ValueError('Recurso fuera de allowlist')
        if kind=='deployment' and value not in (0,1):raise ValueError('Solo réplicas cero/uno')
        self.check_namespace()
        obj=self.get(kind,name);c.require_owned(obj,kind,name,uid)
        allowed={('deployment','/spec/replicas'),('networkpolicy','/spec'),('configmap','/data/state.json')}
        if (kind,path) not in allowed:raise ValueError('Mutación no permitida')
        patch=[{'op':'test','path':'/metadata/uid','value':uid},{'op':'test','path':'/metadata/resourceVersion','value':obj['metadata']['resourceVersion']},{'op':'replace','path':path,'value':value}]
        self.call(['-n',c.NAMESPACE,'patch',kind,name,'--type=json','-p',json.dumps(patch)])


def render():
    import yaml
    data=subprocess.run([str(TOOLS/'helm'),'template',c.RELEASE,str(ROOT/'infra/helm/retailops-incident-lab'),'-n',c.NAMESPACE],capture_output=True,text=True,check=True).stdout
    return [v for v in yaml.safe_load_all(data) if v]


def subset(expected,actual):
    if isinstance(expected,dict):return isinstance(actual,dict) and all(k in actual and subset(v,actual[k]) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(expected)==len(actual) and all(subset(a,b) for a,b in zip(expected,actual))
    return expected==actual


def safety(objects):
    allowed={'ResourceQuota','ConfigMap','Service','Deployment','NetworkPolicy'}
    names=set()
    for obj in objects:
        if obj['kind'] not in allowed:raise ValueError('Tipo de recurso no permitido (sin PVC/Secrets/RBAC/Jobs)')
        if obj['metadata'].get('namespace',c.NAMESPACE)!=c.NAMESPACE:raise ValueError('Namespace ajeno')
        pair=(obj['kind'],obj['metadata']['name'])
        if pair in names:raise ValueError('Recursos duplicados')
        names.add(pair)
        if obj['kind']=='Service' and obj['spec'].get('type')!='ClusterIP':raise ValueError('Servicio debe ser ClusterIP')
        if obj['kind']=='Deployment':
            pod=obj['spec']['template']['spec']
            if any(pod.get(key) for key in ['hostNetwork','hostPID','hostIPC','initContainers','hostAliases','imagePullSecrets']):raise ValueError('Privilegios/host o contenedores adicionales no permitidos')
            if pod.get('automountServiceAccountToken') is not False:raise ValueError('Token Kubernetes no permitido')
            for volume in pod['volumes']:
                if set(volume)-{'name','emptyDir','configMap'} or ('emptyDir' not in volume and 'configMap' not in volume):raise ValueError('Montaje persistente/host/secret denegado')
            if len(pod['containers'])!=1:raise ValueError('Solo contenedor declarado')
            container=pod['containers'][0]
            if container.get('envFrom') or any('valueFrom' in e for e in container.get('env',[])):raise ValueError('Credenciales/configuración externa denegadas')
            if any(e['name'] in {'ML_MODEL_VERSION','SPRING_PROFILES_ACTIVE','MLFLOW_TRACKING_URI'} for e in container.get('env',[])):raise ValueError('Sin modelo, perfiles integrados o almacenes')
            security=container['securityContext']
            if security.get('allowPrivilegeEscalation') is not False or security.get('capabilities')!={'drop':['ALL']} or security.get('privileged',False):raise ValueError('Contenedor privilegiado denegado')
    if sum(o['kind']=='Deployment' for o in objects)!=3:raise ValueError('Deben existir solo tres réplicas sin datos')
    return objects


def http(base,path,grafana=False):
    if base not in ['http://127.0.0.1:9091','http://127.0.0.1:3001','http://127.0.0.1:9094']:raise ValueError('Solo forwards loopback conocidos')
    headers={}
    if grafana:
        user=(ROOT/'.local/f51/grafana-admin-user').read_text().strip();password=(ROOT/'.local/f51/grafana-admin-password').read_text().strip()
        headers['Authorization']='Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode()
    with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=10) as response:return json.load(response)


def monitoring():
    prom=http('http://127.0.0.1:9091','/api/v1/targets')['data']['activeTargets'];wanted={'incident-spring','incident-ml','incident-gateway','prometheus','lab','alertmanager','alert-receiver'}
    healthy={t['labels']['job'] for t in prom if t['health']=='up'}
    if not wanted<=healthy:raise ValueError('Targets de entrenamiento/observabilidad no saludables')
    sample=http('http://127.0.0.1:9091','/api/v1/query?'+urllib.parse.urlencode({'query':'incident_lab_requests_total{status="200"} >= 5'}))['data']['result']
    if {v['metric'].get('component') for v in sample}!={'spring','ml','storage'}:raise ValueError('Faltan cinco probes saludables por componente')
    errors=http('http://127.0.0.1:9091','/api/v1/query?'+urllib.parse.urlencode({'query':'sum(increase(incident_lab_requests_total{status!="200"}[1m])) > 0'}))['data']['result']
    if errors:raise ValueError('Errores recientes; esperar estabilización baseline')
    groups=http('http://127.0.0.1:9091','/api/v1/rules')['data']['groups']
    training=[g for g in groups if g['name']=='retailops-incident-training']
    if not training or any(r['health']!='ok' for g in training for r in g['rules']):raise ValueError('Reglas propias no evaluadas')
    if http('http://127.0.0.1:3001','/api/datasources/uid/retailops-loki/health',True)['status']!='OK':raise ValueError('Datasource Loki no saludable')
    logql='{namespace="retailops-incident-lab",environment="incident-lab"}'
    logs=http('http://127.0.0.1:3001','/api/datasources/proxy/uid/retailops-loki/loki/api/v1/query_range?'+urllib.parse.urlencode({'query':logql,'since':'10m','limit':1}),True)
    if not logs['data']['result']:raise ValueError('Sin logs propios reales; no sustituir por logs origen')
    http('http://127.0.0.1:9094','/api/v2/status')
    return True


def preflight(args,backend=None):
    objects=safety(render());checks={'configuration':True};blockers=[]
    from infra.backup.core import verify_envelope
    envelope,_=verify_envelope(args.backup,args.key)
    report_path=Path(args.recovery_report)
    if report_path.is_symlink() or report_path.stat().st_mode & 0o077:raise ValueError('Informe de recuperación privado requerido')
    recovery=json.loads(report_path.read_text())
    if recovery.get('status')!='validated' or recovery.get('backup_id')!=envelope['id'] or recovery.get('model_version')!='1' or recovery.get('model_artifact_load') is not True:raise ValueError('Falta restauración validada del mismo backup/modelo')
    point=datetime.fromisoformat(envelope['started_utc'].replace('Z','+00:00')).timestamp()
    if not 0<=time.time()-point<=24*3600:raise ValueError('Backup mayor de 24h/futuro; renovar manualmente sin eludir quiescencia')
    checks['backup_authenticated']=True
    b=backend or Backend(args.kubeconfig,args.context)
    result={'stage':'F5.5-A','ready_for_execution':False,'checks':checks,'blockers':blockers,'backup_id':envelope['id'],'mutations_performed':0}
    try:
        result['cluster_server']=b.server()
        nodes=json.loads(b.call(['get','nodes','-o','json']))['items']
        checks['node_ready']=bool(nodes) and all(any(v['type']=='Ready' and v['status']=='True' for v in n['status']['conditions']) for n in nodes)
        checks['memory_margin']=mem_available()>=4*1024**3
        original=json.loads(b.call(['-n','retailops','get','deployments','-o','json']))['items']
        checks['original_apps_closed']=all(d['spec']['replicas']==0 for d in original)
        # Docker solo se consulta; nunca inicia dependencias ni modifica volúmenes.
        running=subprocess.run(['docker','ps','--filter','label=com.docker.compose.project=retailops-data','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.strip()
        checks['original_compose_closed']=not running
        result['namespace_uid']=b.check_namespace()
        pvcs=json.loads(b.call(['-n',c.NAMESPACE,'get','pvc','-o','json']))['items']
        checks['no_training_pvc']=not pvcs
        deployments=json.loads(b.call(['-n',c.NAMESPACE,'get','deployments','-o','json']))['items']
        checks['exclusive_deployments']={d['metadata']['name'] for d in deployments}=={'spring','ml','gateway'} and len(deployments)==3
        policies=json.loads(b.call(['-n',c.NAMESPACE,'get','networkpolicies','-o','json']))['items']
        expected_policies=[o for o in objects if o['kind']=='NetworkPolicy']
        checks['exact_network_policies']=len(policies)==len(expected_policies) and all(any(a['metadata']['name']==e['metadata']['name'] and subset(e['spec'],a['spec']) for a in policies) for e in expected_policies)
        for expected in objects:
            if expected['kind']!='Deployment':continue
            actual=b.get('deployment',expected['metadata']['name']);c.require_owned(actual,'deployment',expected['metadata']['name'])
            safety([actual]+[o for o in objects if o['kind']=='Deployment' and o['metadata']['name']!=actual['metadata']['name']])
            checks['healthy_'+actual['metadata']['name']]=actual['spec']['replicas']==1 and actual.get('status',{}).get('availableReplicas',0)==1 and subset(expected['spec']['template']['spec'],actual['spec']['template']['spec'])
        checks['normal_state']=json.loads(b.get('configmap','exercise-control')['data']['state.json'])=={'mode':'normal','deadline':0}
        checks['monitoring']=monitoring()
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
        blockers.append('Entorno B no listo: '+(str(error) if isinstance(error,ValueError) else type(error).__name__))
    blockers.extend(key for key,value in checks.items() if value is not True)
    result['ready_for_execution']=not blockers and all(checks.get(k) is True for k in ['configuration','backup_authenticated','node_ready','memory_margin','original_apps_closed','original_compose_closed','no_training_pvc','exclusive_deployments','exact_network_policies','healthy_spring','healthy_ml','healthy_gateway','normal_state','monitoring'])
    return result


def lock():
    c.PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700);c.PRIVATE.chmod(0o700)
    stream=(c.PRIVATE/'controller.lock').open('a');os.chmod(stream.name,0o600);fcntl.flock(stream,fcntl.LOCK_EX);return stream


def execute_start(args):
    approval=c.authorization(args.authorization,args.scenario) # Antes de llamadas o escrituras.
    if STATE.exists():
        state=json.loads(c.private_path(STATE).read_text())
        if state.get('phase')=='active' and state.get('exercise_id')==approval['exercise_id']:return c.public_state(state)
    b=Backend(args.kubeconfig,args.context);ready=preflight(args,b)
    b.writable=True
    with lock():state=c.begin(b,approval,ready,STATE)
    try:
        while time.time()<state['deadline']:
            time.sleep(2)
            current=json.loads(c.private_path(STATE).read_text())
            if current['phase']!='active':return c.public_state(current)
            if mem_available()<2*1024**3:break
    finally:
        with lock():result=c.end(b,STATE)
    return result


def main():
    if not __debug__:raise ValueError('No usar Python -O')
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['preflight','list','start','status','stop','verify','cleanup'])
    parser.add_argument('--kubeconfig',default=str(ROOT/'.local/f4/kubeconfig'));parser.add_argument('--context',default='default')
    parser.add_argument('--backup');parser.add_argument('--key');parser.add_argument('--recovery-report');parser.add_argument('--require-ready',action='store_true')
    parser.add_argument('--authorization');parser.add_argument('--scenario')
    args=parser.parse_args()
    if args.command=='list':result=[{k:s[k] for k in ['id','title','objective']} for s in c.catalog()['scenarios']]
    elif args.command in ['preflight','verify']:
        if not all([args.backup,args.key,args.recovery_report]):raise ValueError('Indicar backup, clave e informe F5.4; no se generan ni modifican')
        result=preflight(args)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if (args.require_ready or args.command=='verify') and not result['ready_for_execution']:raise SystemExit(2)
        return
    elif args.command=='start':
        if not all([args.authorization,args.scenario,args.backup,args.key,args.recovery_report]):raise ValueError('Autorización explícita F5.5-B y preflight requeridos; no ejecutar en F5.5-A')
        result=execute_start(args)
    elif args.command=='status':
        result=c.public_state(json.loads(c.private_path(STATE).read_text())) if STATE.exists() else {'phase':'not_started','incidents_executed':0}
    else:
        if not STATE.exists():result={'phase':'not_started','persistent_data_deleted':False}
        else:
            existing=json.loads(c.private_path(STATE).read_text())
            if existing['phase']=='cleaned':
                print(json.dumps(c.public_state(existing)));return
            b=Backend(args.kubeconfig,args.context,writable=True)
            with lock():
                result=c.end(b,STATE)
                if args.command=='cleanup':
                    state=json.loads(c.private_path(STATE).read_text());b.check_namespace(state['namespace_uid'])
                    if b.server()!=state['cluster_server']:raise ValueError('Cluster distinto; no limpiar')
                    deadline=time.monotonic()+150
                    while True:
                        observed=http('http://127.0.0.1:9091','/api/v1/query?'+urllib.parse.urlencode({'query':'incident_lab_watch_enabled == 0'}))
                        if observed['data']['result']:break
                        if time.monotonic()>=deadline:raise ValueError('Cierre no observado por Prometheus; no escalar aún')
                        time.sleep(2)
                    for name in ['spring','ml','gateway']:
                        obj=b.get('deployment',name);c.require_owned(obj,'deployment',name,state['snapshots']['deployment/'+name]['metadata']['uid'])
                        b.change('deployment',name,'/spec/replicas',0,state['snapshots']['deployment/'+name]['metadata']['uid'])
                    state['phase']='cleaned';c.write_private(STATE,state);result=c.public_state(state)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print('Operación rechazada: '+(str(error) if isinstance(error,ValueError) else type(error).__name__),file=sys.stderr);sys.exit(2)
