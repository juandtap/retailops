"""Control F5.5-B futuro; F5.5-A permite solo consultas/validación. Sin shell genérica."""
import copy
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
NAMESPACE='retailops-incident-lab';RELEASE=NAMESPACE
OWNER='app.kubernetes.io/instance'
MUTABLE={('deployment','spring'),('deployment','ml'),('deployment','gateway'),('networkpolicy','ml-ingress'),('configmap','exercise-control')}
CATALOG=ROOT/'infra/incident-lab/scenarios.json'
PRIVATE=ROOT/'.local/f55/facilitator'


def catalog():return json.loads(CATALOG.read_text())
def catalog_hash():
    paths=[CATALOG,Path(__file__),ROOT/'scripts/incident_lab.py',ROOT/'infra/incident-lab/namespace.yaml',ROOT/'infra/incident-lab/evaluator-guide.template.md']+list((ROOT/'infra/helm/retailops-incident-lab').rglob('*'))
    paths+=[p for base in [ROOT/'infra/helm/retailops-observability/files/incident-lab',ROOT/'infra/helm/retailops-logging/files/incident-lab'] for p in base.rglob('*') if base.exists()]
    paths += [ROOT/p for p in ['infra/helm/retailops-observability/templates/config.yaml','infra/helm/retailops-observability/values.yaml','infra/helm/retailops-logging/templates/workloads.yaml','infra/helm/retailops-logging/templates/rbac.yaml','infra/helm/retailops-logging/values.yaml']]
    h=hashlib.sha256()
    for path in sorted(set(p for p in paths if p.is_file() and p.suffix in {'.py','.yaml','.yml','.json','.md','.tpl'})):h.update(str(path.relative_to(ROOT)).encode()+b'\0'+path.read_bytes())
    return h.hexdigest()
def scenario(identifier):
    found=[s for s in catalog()['scenarios'] if s['id']==identifier]
    if len(found)!=1:raise ValueError('Escenario fuera del catálogo')
    return found[0]


def private_path(path,existing=True):
    path=Path(path)
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('No se permiten symlinks privados ni en sus directorios')
    resolved=path.resolve()
    if PRIVATE.resolve() not in resolved.parents:raise ValueError('Ruta debe estar bajo .local/f55/facilitator, ignorada por Git')
    if existing and (not path.is_file() or path.stat().st_uid!=os.getuid() or path.stat().st_mode & 0o077):raise ValueError('Archivo privado propio 0600 requerido')
    return resolved


def authorization(path,identifier,clock=None):
    clock=time.time() if clock is None else clock
    value=json.loads(private_path(path).read_text())
    required={'stage','action','consent','scenario_id','exercise_id','issued_at','expires_at','namespace_uid','cluster_server','catalog_sha256','backup_id','approved_by','approval_reference'}
    if set(value)!=required:raise ValueError('Autorización incompleta o campos no admitidos')
    if value['stage']!='F5.5-B' or value['action']!='start' or value['consent']!='I_AUTHORIZE_F5.5_B_ONE_SCENARIO':raise ValueError('F5.5-A no autoriza ejecutar; aprobación explícita F5.5-B requerida')
    if value['scenario_id']!=identifier or value['catalog_sha256']!=catalog_hash():raise ValueError('Autorización no corresponde al escenario/catálogo')
    if not(value['issued_at']<=clock<value['expires_at']<=value['issued_at']+900) or clock-value['issued_at']>900:raise ValueError('Autorización vencida o ventana >15min')
    if len(value['exercise_id'])!=32 or any(c not in '0123456789abcdef' for c in value['exercise_id']):raise ValueError('ID opaco inválido')
    if not all(isinstance(value[k],str) and value[k].strip() for k in ['approved_by','approval_reference','namespace_uid','cluster_server','backup_id']):raise ValueError('Falta identidad/referencia operadora o entorno')
    scenario(identifier)
    return value


def write_private(path,value):
    path=private_path(path,existing=False);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    for p in [PRIVATE,path.parent]:
        if p.exists():p.chmod(0o700)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.write-')
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
        os.replace(name,path)
    finally:
        if Path(name).exists():Path(name).unlink()


def public_state(state):
    # Nunca incluir escenario, modo, baseline, autorización o guía de evaluación.
    return {k:state[k] for k in ['exercise_id','phase','deadline'] if k in state}


def require_owned(obj,kind,name,uid=None):
    if (kind,name) not in MUTABLE:raise ValueError('Recurso fuera de allowlist; nunca tocar origen')
    metadata=obj.get('metadata',{})
    if metadata.get('name')!=name or metadata.get('namespace')!=NAMESPACE or metadata.get('labels',{}).get(OWNER)!=RELEASE:raise ValueError('Identidad/namespace/propietario no autorizado')
    if uid and metadata.get('uid')!=uid:raise ValueError('UID cambió; no sobrescribir recurso recreado')


def begin(backend,approval,ready,state_path):
    selected=scenario(approval['scenario_id']);deadline=min(time.time()+selected['max_duration_seconds'],approval['expires_at'])
    if not ready.get('ready_for_execution'):raise ValueError('Preflight no listo; no activar escenario')
    if (ready['namespace_uid'],ready['cluster_server'],ready['backup_id'])!=(approval['namespace_uid'],approval['cluster_server'],approval['backup_id']):raise ValueError('Aprobación no corresponde a cluster/namespace/backup')
    if state_path.exists():
        previous=json.loads(private_path(state_path).read_text())
        if previous.get('phase')=='active' and previous.get('exercise_id')==approval['exercise_id']:return previous
        if previous.get('phase') in ['active','preparing']:raise ValueError('Ya hay ejercicio pendiente; detener antes de otro')
        if previous.get('exercise_id')==approval['exercise_id']:raise ValueError('Aprobación ya consumida; no replay')
    consumed=PRIVATE/'consumed'/(approval['exercise_id']+'.json')
    if consumed.exists():raise ValueError('Autorización consumida; no replay')
    snapshots={}
    for kind,name in [('deployment','spring'),('deployment','ml'),('deployment','gateway'),('networkpolicy','ml-ingress'),('configmap','exercise-control')]:
        obj=backend.get(kind,name);require_owned(obj,kind,name);snapshots[kind+'/'+name]=obj
    control=json.loads(snapshots['configmap/exercise-control']['data']['state.json'])
    if control!={'mode':'normal','deadline':0} or snapshots['deployment/spring']['spec']['replicas']!=1:raise ValueError('Baseline no normal; no encadenar ejercicios')
    state={'exercise_id':approval['exercise_id'],'phase':'preparing','deadline':deadline,'namespace_uid':approval['namespace_uid'],'cluster_server':approval['cluster_server'],'scenario_id':selected['id'],'mode':selected['mode'],'snapshots':snapshots}
    write_private(consumed,{'exercise_id':approval['exercise_id'],'consumed_at':time.time()})
    write_private(state_path,state)
    try:
        if selected['mode']=='scale_spring':backend.change('deployment','spring','/spec/replicas',0,snapshots['deployment/spring']['metadata']['uid'])
        elif selected['mode']=='block_ml':
            spec=copy.deepcopy(snapshots['networkpolicy/ml-ingress']['spec'])
            spec['ingress'][0]['from'][0]['podSelector']['matchLabels']['retailops.io/ml-client']='blocked'
            backend.change('networkpolicy','ml-ingress','/spec',spec,snapshots['networkpolicy/ml-ingress']['metadata']['uid'])
        backend.change('configmap','exercise-control','/data/state.json',json.dumps({'mode':selected['mode'],'deadline':deadline}),snapshots['configmap/exercise-control']['metadata']['uid'])
        guide=(ROOT/'infra/incident-lab/evaluator-guide.template.md').read_text().format(exercise_id=state['exercise_id'],scenario_id=selected['id'],**selected)
        guide_path=PRIVATE/'exercises'/state['exercise_id']/'evaluation.md';guide_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);guide_path.write_text(guide);guide_path.chmod(0o600)
        state['phase']='active';write_private(state_path,state);write_private(PRIVATE/'exercises'/state['exercise_id']/'state.json',state);return state
    except Exception:
        end(backend,state_path)
        raise


def end(backend,state_path):
    if not state_path.exists():return {'phase':'not_started'}
    state=json.loads(private_path(state_path).read_text())
    if state['phase'] in ['stopped','cleaned']:return public_state(state)
    backend.check_namespace(state['namespace_uid'])
    if backend.server()!=state['cluster_server']:raise ValueError('Cluster distinto; no revertir aquí')
    # Revertir solo campos propios y solo si su valor sigue dentro del cambio autorizado.
    for kind,name,path,value in [('deployment','spring','/spec/replicas',state['snapshots']['deployment/spring']['spec']['replicas']),('networkpolicy','ml-ingress','/spec',state['snapshots']['networkpolicy/ml-ingress']['spec']),('configmap','exercise-control','/data/state.json',state['snapshots']['configmap/exercise-control']['data']['state.json'])]:
        old=state['snapshots'][kind+'/'+name];current=backend.get(kind,name);require_owned(current,kind,name,old['metadata']['uid'])
        if kind=='deployment':
            if current['spec']['replicas'] not in (0,1):raise ValueError('Cambio concurrente de réplicas; no sobrescribir')
        elif kind=='networkpolicy':
            injected=copy.deepcopy(value);injected['ingress'][0]['from'][0]['podSelector']['matchLabels']['retailops.io/ml-client']='blocked'
            if current['spec'] not in (value,injected):raise ValueError('Política cambió fuera del ejercicio; revisión manual')
        else:
            parsed=json.loads(current['data']['state.json'])
            if parsed not in ({'mode':'normal','deadline':0},{'mode':state['mode'],'deadline':state['deadline']}):raise ValueError('Estado concurrente; no sobrescribir')
        backend.change(kind,name,path,value,old['metadata']['uid'])
    state['phase']='stopped';write_private(state_path,state);write_private(PRIVATE/'exercises'/state['exercise_id']/'state.json',state);return public_state(state)
