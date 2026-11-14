"""Adaptadores de orquestación: ningún SQL de features dentro de los DAGs."""
from datetime import date,datetime,timezone,timedelta
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'pipelines/ingestion')]
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from retailops_bootstrap.extract import canonical_hash
from retailops_bootstrap.storage import Settings
from retailops_bootstrap.pipeline import execute


def db(role='ingestor',database=None):
    if role not in ('ingestor','trainer','api'):raise ValueError('Rol no permitido')
    path=ROOT/'.local/secrets'/f'pg_{role}_password'
    if path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('Secreto inseguro')
    return psycopg.connect(host=os.environ.get('RETAILOPS_PG_HOST','127.0.0.1'),port=int(os.environ.get('POSTGRES_PORT','5432')),
       dbname=database or os.environ.get('POSTGRES_DB','retailops'),user='retailops_'+role,password=path.read_text().strip(),
       autocommit=True,row_factory=dict_row,options='-c statement_timeout=300000 -c lock_timeout=5000')

def snapshot():
    with db() as conn:
        row=conn.execute('''SELECT h.released_through,h.last_batch_id,b.state,p.status FROM control.historical_state h
        JOIN control.batches b ON b.batch_id=h.last_batch_id JOIN control.publications p USING(batch_id)''').fetchone()
    if not row or row['state']!='RELEASED' or row['status']!='COMPLETE':raise ValueError('Estado histórico incompleto')
    return row

def plan(batch,cutoff):
    cutoff=date.fromisoformat(str(cutoff))
    manifest=json.loads((ROOT/'docs/DATA_BATCH_MANIFEST.json').read_text())
    item=next((b for b in manifest['incremental_batches'] if b['batch_id']==batch),None)
    if not item or batch!=(cutoff+timedelta(days=1)).strftime('%Y-%m'):raise ValueError('Mes fuera de secuencia')
    return item

def authorize(batch):
    state=snapshot();item=plan(batch,state['released_through'])
    with db('api') as conn:
        auth=conn.execute('SELECT control.authorize_month(%s,%s,%s,%s,%s) id',
          (batch,uuid4(),state['released_through'],item['observed_end'],item['rows'])).fetchone()['id']
    return {'batch':batch,'authorization_id':str(auth)}

def authorization(batch,identifier):
    with db() as conn:
        row=conn.execute('SELECT * FROM control.monthly_authorizations WHERE batch_id=%s AND authorization_id=%s',(batch,identifier)).fetchone()
    if not row:raise ValueError('Falta autorización explícita del mes')
    active=snapshot()['released_through']
    if active not in (row['previous_cutoff'],row['period_end']):raise ValueError('Autorización/corte incompatible')
    return row

def workspace(batch):return ROOT/'.local/airflow/monthly'/batch

def prepare(batch,identifier):
    auth=authorization(batch,identifier);item=plan(batch,auth['previous_cutoff'])
    contract={**json.loads((ROOT/'contracts/bootstrap-v1.json').read_text()),'kind':'MONTHLY','batch_id':batch,
      'period_start':str(auth['previous_cutoff']+timedelta(days=1)),'period_end':str(auth['period_end']),
      'expected_sales':item['rows'],'calendar_complete':item['calendar_complete'],'expected_batch_complete':item['observed_grid_complete'],'accepted_missing_dates':[d for d in item['missing_dates'] if d<=str(auth['period_end'])]}
    folder=workspace(batch);folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=folder/'contract.json'
    if path.exists() and json.loads(path.read_text())!=contract:raise ValueError('Contrato local conflictivo')
    path.write_text(json.dumps(contract,indent=2)+'\n')
    prepared=folder/'prepared.json'
    stamp=json.loads(prepared.read_text())['ingested_at'] if prepared.exists() else datetime.now(timezone.utc).isoformat()
    cmd=[sys.executable,'-m','retailops_bootstrap.extract','--source',str(ROOT/'data/source/favorita'),'--workspace',str(folder),
       '--contract',str(path),'--inventory',str(ROOT/'docs/DATA_INVENTORY.json'),'--ingested-at',stamp]
    if prepared.exists():cmd.append('--verify-only')
    subprocess.run(cmd,cwd=ROOT/'pipelines/ingestion',check=True)
    return {'batch':batch,'prepared':True}

def release(batch,identifier):
    authorization(batch,identifier)
    folder=workspace(batch)
    contract=json.loads((folder/'contract.json').read_text())
    # No callback extractor: Airflow no recibe ni monta SOURCE.
    settings=Settings(ROOT,os.environ.get('POSTGRES_DB','retailops'),int(os.environ.get('POSTGRES_PORT','5432')),
       os.environ.get('MINIO_ENDPOINT','127.0.0.1:9000'))
    return execute(settings,folder,contract)

def verify_release(batch):
    state=snapshot()
    if state['last_batch_id']!=batch:raise ValueError('El lote solicitado no es el corte activo')
    return {'batch':batch,'cutoff':str(state['released_through']),'released':True}

def safe():
    state=snapshot()
    with db('trainer') as conn:
        gold=conn.execute('SELECT count(*) n FROM training.gold_features WHERE historical_cutoff=%s',(state['released_through'],)).fetchone()['n']
        future=conn.execute('SELECT EXISTS(SELECT 1 FROM training.gold_labels WHERE target_date>%s) bad',(state['released_through'],)).fetchone()['bad']
    if future or gold!=9106020 or state['released_through']!=date(2014,12,31):raise ValueError('La validación segura exige bootstrap sin cambios')
    return {'cutoff':str(state['released_through']),'batch':state['last_batch_id'],'features':gold,'future_labels':False}

def record(logical_id,cutoff,result):
    with db() as conn:
        old=conn.execute('SELECT snapshot FROM control.orchestration_runs WHERE logical_id=%s',(logical_id,)).fetchone()
        if old and str(old['snapshot'])!=str(cutoff):raise ValueError('Identificador lógico con corte conflictivo')
        conn.execute("INSERT INTO control.orchestration_runs(logical_id,snapshot,status,result) VALUES(%s,%s,'SUCCEEDED',%s) ON CONFLICT(logical_id) DO UPDATE SET status='SUCCEEDED',result=EXCLUDED.result,updated_at=clock_timestamp()",(logical_id,cutoff,Jsonb(result)))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['authorize','prepare','release','gold','verify','safe','record','check','state','snapshot','registry','dependencies'])
    p.add_argument('--batch');p.add_argument('--authorization-id');p.add_argument('--logical-id');p.add_argument('--cutoff');p.add_argument('--confirm',action='store_true')
    a=p.parse_args()
    if a.action=='authorize':
        if not a.confirm:p.error('Se requiere --confirm: autoriza solo un mes explícito')
        result=authorize(a.batch)
    elif a.action=='check':
        result=authorization(a.batch,a.authorization_id)
        if a.cutoff and a.cutoff!=str(result['period_end']):raise ValueError('Corte GOLD/ML distinto del mes autorizado')
    elif a.action=='state':result=snapshot()
    elif a.action=='snapshot':
        result=snapshot()
        if str(result['released_through'])!=a.cutoff:raise ValueError('Corte solicitado distinto del publicado')
    elif a.action=='registry':
        from urllib.request import urlopen
        url=os.environ.get('MLFLOW_TRACKING_URI','http://127.0.0.1:5000')+'/api/2.0/mlflow/model-versions/get?name=retailops-sales-global&version=1'
        with urlopen(url,timeout=15) as response:result=json.load(response)['model_version']
        if result['status']!='READY' or result['run_id']!='55257fc2ce414793b73b9d0df4c95fbb':raise ValueError('Modelo v1 incompatible')
        result={'model':'retailops-sales-global','version':'1','status':'READY'}
    elif a.action=='dependencies':
        with db('trainer') as conn:
            count=conn.execute('SELECT count(*) n FROM training.gold_features_v2').fetchone()['n']
        if count!=9106020:raise ValueError('Dependencias GOLD incompatibles')
        result={'safe':True,'features_v2':count,'release_performed':False,'training_performed':False}
    elif a.action=='prepare':result=prepare(a.batch,a.authorization_id)
    elif a.action=='release':result=release(a.batch,a.authorization_id)
    elif a.action=='verify':result=verify_release(a.batch)
    elif a.action=='safe':result=safe()
    elif a.action=='gold':
        from incremental_gold import materialize
        result=materialize(a.batch,a.authorization_id)
    else:result=record(a.logical_id,a.cutoff or str(snapshot()['released_through']),{'status':'SUCCEEDED'})
    print(json.dumps(result,default=str))
