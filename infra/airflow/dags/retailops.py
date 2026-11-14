"""DAGs manuales: solo adaptadores; transformaciones en módulos existentes."""
from datetime import datetime,timedelta,timezone
import json
import os
import subprocess
from airflow.sdk import DAG,get_current_context
from airflow.providers.standard.operators.python import PythonOperator

ROOT='/opt/retailops'

def invoke(action):
    context=get_current_context();conf=context['dag_run'].conf or {}
    allowed={'batch','authorization_id','cutoff','confirm_training','logical_id'}
    if set(conf)-allowed:raise ValueError('Configuración desconocida')
    if action in ('train','snapshot') or context['dag'].dag_id=='retailops_full_pipeline':
        if conf.get('confirm_training') is not True:raise ValueError('Se requiere confirm_training=true explícito')
    if context['dag'].dag_id=='retailops_full_pipeline' and not conf.get('cutoff'):
        raise ValueError('El flujo completo exige cutoff explícito antes de publicar')
    logical=conf.get('logical_id') or (context['dag'].dag_id+':'+context['run_id'])
    env={**os.environ,'PYTHONPATH':ROOT+'/pipelines/orchestration:'+ROOT+'/pipelines/ingestion:'+ROOT+'/apps/ml-service',
       'RETAILOPS_PG_HOST':'postgres','POSTGRES_PORT':'5432','EDA_PG_HOST':'postgres','EDA_PG_PORT':'5432',
       'MINIO_ENDPOINT':'minio:9000','MLFLOW_TRACKING_URI':'http://mlflow:5000'}
    if action=='train':
        cmd=[ROOT+'/ml-venv/bin/python','-m','app.orchestrated','--cutoff',str(conf.get('cutoff','')),'--logical-id',logical]
    else:
        cmd=[ROOT+'/ingestion-venv/bin/python',ROOT+'/pipelines/orchestration/core.py',action]
        for key in ('batch','authorization_id','cutoff'):
            if key in conf:cmd.extend(['--'+key.replace('_','-'),str(conf[key])])
        cmd.extend(['--logical-id',logical])
    subprocess.run(cmd,env=env,check=True)


def make(identifier,actions):
    with DAG(identifier,schedule=None,start_date=datetime(2026,1,1,tzinfo=timezone.utc),catchup=False,
       max_active_runs=1,default_args={'retries':1,'retry_delay':timedelta(seconds=10)},tags=['retailops','manual']) as dag:
        previous=None
        for task_id,action in actions:
            task=PythonOperator(task_id=task_id,python_callable=invoke,op_args=[action],pool='retailops_serial',execution_timeout=timedelta(minutes=30))
            if previous:previous>>task
            previous=task
    return dag

monthly=make('retailops_monthly_release',[('authorize','check'),('ingest_publish','release'),('verify','verify'),('gold','gold'),('record','record')])
training=make('retailops_train_candidate',[('verify_snapshot','snapshot'),('train_evaluate_register','train'),('record','record')])
full=make('retailops_full_pipeline',[('authorize','check'),('ingest_publish','release'),('verify','verify'),('gold','gold'),('train_evaluate_register','train'),('record','record')])
validation=make('retailops_validate_existing',[('historical_state','state'),('gold_contract','safe'),('registered_model','registry'),('dependencies','dependencies')])
