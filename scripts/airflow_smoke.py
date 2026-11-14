"""Ejecuta solo el DAG seguro; nunca publica, entrena ni registra candidatos."""
from datetime import datetime,timezone
import json,os,time
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:'+os.environ.get('AIRFLOW_PORT','8081')

def main():
    credentials=json.loads((ROOT/'.local/secrets/airflow_users.json').read_text())
    def request(path,data=None,method=None,token=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        with urlopen(req,timeout=30) as response:
            body=response.read()
            return json.loads(body) if body else {}
    token=request('/auth/token',{'username':'admin','password':credentials['admin']},'POST')['access_token']
    health=request('/api/v2/monitor/health',token=token)
    dags=request('/api/v2/dags?limit=100',token=token)['dags']
    ours=[d for d in dags if d['dag_id'].startswith('retailops_')]
    if len(ours)!=4:raise ValueError('No están registrados los cuatro DAGs')
    run_id='safe-f2-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    dag='retailops_validate_existing';route='/api/v2/dags/'+dag
    request(route,{'is_paused':False},'PATCH',token)
    request(route+'/dagRuns',{'dag_run_id':run_id,'logical_date':None,'conf':{}},'POST',token)
    print('DAG seguro lanzado: '+run_id,flush=True)
    previous=None
    for _ in range(90):
        run=request(route+'/dagRuns/'+run_id,token=token)
        state=run['state']
        if state!=previous:print('Estado: '+state,flush=True);previous=state
        if state in ('success','failed'):break
        time.sleep(2)
    tasks=request(route+'/dagRuns/'+run_id+'/taskInstances?limit=100',token=token)['task_instances']
    result={'dag_id':dag,'dag_run_id':run_id,'state':state,'health':health,
      'registered_dags':[d['dag_id'] for d in ours],
      'tasks':[{'task_id':t['task_id'],'state':t['state'],'try_number':t['try_number']} for t in tasks],
      'release_performed':False,'training_performed':False,'model_registration_performed':False}
    folder=ROOT/'.local/airflow';folder.mkdir(exist_ok=True,parents=True)
    (folder/'execution.json').write_text(json.dumps(result,indent=2)+'\n')
    if state!='success' or len(tasks)!=4 or any(t['state']!='success' for t in tasks):raise ValueError('DAG seguro no completado; revisar logs en Airflow')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
