"""Entrenamiento lógico recuperable: no duplica runs/modelos ante reintentos."""
import argparse,fcntl,hashlib,json,os
from pathlib import Path
import mlflow
from mlflow.tracking import MlflowClient
from .data import ROOT,connection
from .plan import for_cutoff
from .training import train,EXPERIMENT

def execute(cutoff,logical_id):
    plan=for_cutoff(cutoff)
    folder=ROOT/'.local/airflow/ml'/hashlib.sha256(logical_id.encode()).hexdigest()
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (folder/'execution.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        candidate=folder/'candidate.json'
        if candidate.exists():
            result=json.loads(candidate.read_text())
            if result['metadata']['historical_cutoff']!=str(cutoff):raise ValueError('ID lógico reutilizado con otro corte')
            return result
        with connection() as conn:
            latest=conn.execute('SELECT max(historical_cutoff) cutoff FROM training.gold_features_v2').fetchone()['cutoff']
        if str(latest)!=str(cutoff):raise ValueError('GOLD no materializado al corte solicitado')
        mlflow.set_tracking_uri(os.environ.get('MLFLOW_TRACKING_URI','http://127.0.0.1:5000'))
        client=MlflowClient();experiment=mlflow.set_experiment(EXPERIMENT)
        key=hashlib.sha256(logical_id.encode()).hexdigest()
        runs=client.search_runs([experiment.experiment_id],filter_string=f"tags.retailops_logical_id = '{key}'")
        if len(runs)>1:raise ValueError('Runs ambiguos: no crear otro automáticamente')
        if runs:
            run=runs[0]
            if run.data.tags.get('retailops_cutoff')!=str(cutoff):raise ValueError('Corte lógico conflictivo')
        else:
            run=client.create_run(experiment.experiment_id,tags={'retailops_logical_id':key,'retailops_cutoff':str(cutoff)})
        if client.search_logged_models(experiment_ids=[experiment.experiment_id],filter_string=f"source_run_id = '{run.info.run_id}'") and not (folder/'logged_model.json').exists():
            raise ValueError('Modelo logueado sin checkpoint: recuperar asociación antes de reintentar')
        if not (folder/'fit.joblib').exists() and run.data.metrics.get('fit_seconds') is not None:
            raise ValueError('Ajuste previo sin checkpoint: investigar antes de volver a entrenar')
        return train(plan=plan,logical_id=logical_id,run_id=run.info.run_id)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cutoff',required=True);p.add_argument('--logical-id',required=True);a=p.parse_args()
    print(json.dumps(execute(a.cutoff,a.logical_id),default=str))
