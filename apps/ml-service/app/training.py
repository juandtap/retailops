"""Un ajuste fijo; validación y holdout posteriores, registro sin promoción automática."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import time

import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits
from .data import ROOT,INPUTS,VERSION,FIT_DATE,SPLITS,feature_frame,training_chunks
from .model import build_model,PARAMETERS
from retailops_baselines import metric_sums,metrics

MODEL_NAME='retailops-sales-global'
EXPERIMENT='retailops-sales-pit-v1'

def score(model,split,plan=None):
    sums={name:np.zeros(4) for name in ('hgb','seasonal_naive_7')}
    individual={name:np.zeros(4) for name in sums}
    counts={'examples':0,'missing_labels':0,'common':0,'model_available':0,'baseline_available':0}
    for frame in training_chunks(split,plan):
        y=frame.actual.to_numpy(dtype=float)
        with threadpool_limits(limits=2):p=model.predict(feature_frame(frame))
        baseline=frame.lag_7.where(frame.lag_7_available.eq(True)).to_numpy(dtype=float)
        if not (np.isfinite(p)&(p>=0)).all():raise ValueError('Predicción no finita o negativa')
        common=np.isfinite(y)&np.isfinite(p)&np.isfinite(baseline)
        for name,values in [('hgb',p),('seasonal_naive_7',baseline)]:
            sums[name]+=metric_sums(y[common],values[common])
            individual[name]+=metric_sums(y,values)
        counts['examples']+=len(frame);counts['missing_labels']+=int(np.isnan(y).sum())
        counts['common']+=int(common.sum());counts['model_available']+=int(np.isfinite(p).sum())
        counts['baseline_available']+=int(np.isfinite(baseline).sum())
    if not counts['common']:raise ValueError('Sin ejemplos comparables')
    return {'coverage':counts,'common_metrics':{k:metrics(v) for k,v in sums.items()},
            'individual_metrics':{k:metrics(v) for k,v in individual.items()}}

def train(*,plan=None,logical_id=None,run_id=None):
    version=plan['version'] if plan else VERSION
    cutoff=str(plan['cutoff']) if plan else '2014-12-31'
    fit_date=plan['fit_date'] if plan else FIT_DATE
    splits=plan['splits'] if plan else SPLITS
    started=time.monotonic()
    mlflow.set_tracking_uri(os.environ.get('MLFLOW_TRACKING_URI','http://127.0.0.1:5000'))
    mlflow.set_experiment(EXPERIMENT)
    contract=ROOT/'contracts'/(plan['contract'] if plan else 'gold-features-v1.json')
    contract_hash=hashlib.sha256(contract.read_bytes()).hexdigest()
    code_hash=hashlib.sha256(b''.join((Path(__file__).parent/f).read_bytes() for f in ['data.py','model.py','training.py'])).hexdigest()
    with mlflow.start_run(run_id=run_id,run_name=None if run_id else 'hgb-poisson-fixed-temporal') as run:
        mlflow.log_params({**PARAMETERS,'feature_version':version,'historical_cutoff':cutoff,
          'fit_date':str(fit_date),'training_sampling':'Monday issues only; all stores/families/horizons',
          'validation':str(splits['validation'][:2]),'evaluation':str(splits['evaluation'][:2]),
          'threads':2,'code_sha256':code_hash,'contract_sha256':contract_hash})
        mlflow.set_tags({'purpose':'candidate_local_preview','promotion':'not_approved',
          'trained_at':datetime.now(timezone.utc).isoformat(),'labels_available_by':str(fit_date)})
        folder=(ROOT/'.local/airflow/ml'/hashlib.sha256(logical_id.encode()).hexdigest() if logical_id else ROOT/'.local/mlops');folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        checkpoint=folder/'fit.joblib'
        fit_key=hashlib.sha256(b''.join((Path(__file__).parent/f).read_bytes() for f in ['data.py','model.py'])+(ROOT/'apps/ml-service/uv.lock').read_bytes()+contract.read_bytes()+cutoff.encode()+json.dumps(splits,default=str,sort_keys=True).encode()).hexdigest()
        cached=joblib.load(checkpoint) if checkpoint.exists() else None
        reused=bool(cached and cached.get('fit_key')==fit_key)
        if logical_id and (folder/'fit_started').exists() and not reused:
            raise ValueError('Ajuste previo sin checkpoint compatible: recuperación manual requerida')
        if reused:
            model=cached['model'];signature=cached['signature'];training_rows=cached['training_rows']
            missing=cached['missing'];fit_seconds=cached['fit_seconds'];results=cached['results']
            print('Checkpoint de ajuste y evaluación compatible reutilizado, sin reentrenar.',flush=True)
        else:
            xs=[];ys=[];missing=0
            for frame in training_chunks('train',plan):
                valid=frame.actual.notna();missing+=int((~valid).sum())
                xs.append(feature_frame(frame.loc[valid]));ys.append(frame.loc[valid,'actual'].to_numpy(dtype=float))
            x=pd.concat(xs,ignore_index=True);y=np.concatenate(ys);del xs,ys
            if len(x)==0 or not np.isfinite(y).all() or (y<0).any():raise ValueError('Datos de ajuste inválidos')
            print(f'Ajuste único: {len(x)} ejemplos; {missing} etiquetas ausentes excluidas.',flush=True)
            model=build_model();fit_start=time.monotonic()
            if logical_id:(folder/'fit_started').write_text(run.info.run_id)
            with threadpool_limits(limits=2):model.fit(x,y)
            fit_seconds=round(time.monotonic()-fit_start,3)
            print(f'Ajuste terminado en {fit_seconds}s; evaluando sin reentrenar.',flush=True)
            with threadpool_limits(limits=2):signature=infer_signature(x.head(8),model.predict(x.head(8)))
            training_rows=len(x);del x,y
            results={s:score(model,s,plan) for s in ('validation','evaluation')}
            joblib.dump({'fit_key':fit_key,'model':model,'signature':signature,'training_rows':training_rows,
              'missing':missing,'fit_seconds':fit_seconds,'results':results},checkpoint)
            os.chmod(checkpoint,0o600)
        mlflow.log_param('fit_checkpoint_reused',reused)
        metadata={'feature_version':version,'historical_cutoff':cutoff,'fit_date':str(fit_date),
          'contract_sha256':contract_hash,'code_sha256':code_hash,'inputs':INPUTS,'training_rows':training_rows}
        metrics_flat={'training_rows':training_rows,'training_missing_labels':missing,'fit_seconds':fit_seconds}
        for split,value in results.items():
            for name,values in value['common_metrics'].items():
                for metric in ('mae','wape','rmsle'):
                    if values[metric] is not None:metrics_flat[f'{split}_{name}_{metric}']=values[metric]
        mlflow.log_metrics(metrics_flat)
        mlflow.log_dict({'splits':{k:[str(d) for d in v] for k,v in splits.items()},'results':results,'metadata':metadata},'evaluation.json')
        mlflow.log_artifact(str(contract),artifact_path='contracts')
        mlflow.log_artifact(str(ROOT/'apps/ml-service/uv.lock'),artifact_path='environment')
        mlflow.log_dict({'sha256':code_hash,'files':['app/data.py','app/model.py','app/training.py']},'code.json')
        logged_marker=folder/('logged_model.json' if logical_id else 'logged_model-'+run.info.run_id+'.json')
        if logged_marker.exists():
            info=type('LoggedModel',(),json.loads(logged_marker.read_text()))()
        else:
            info=mlflow.sklearn.log_model(model,name='sales_model',signature=signature,
          skops_trusted_types=['functools.partial','sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor','sklearn.utils.validation.check_array'],
          pip_requirements=[f'scikit-learn=={sklearn.__version__}',f'pandas=={pd.__version__}',f'numpy=={np.__version__}'],metadata=metadata)
        # Registrar una única versión del algoritmo entrenado, sin alias de producción.
            logged_marker.write_text(json.dumps({'model_uri':info.model_uri}))
        client=MlflowClient()
        found=[v for v in client.search_model_versions("name='"+MODEL_NAME+"'") if v.run_id==run.info.run_id]
        if len(found)>1:raise ValueError('Registro ambiguo: investigar, no duplicar')
        registered=found[0] if found else mlflow.register_model(info.model_uri,MODEL_NAME)
        for key,value in [('feature_version',version),('fit_date',str(fit_date)),('contract_sha256',contract_hash),('purpose','candidate_local_preview')]:
            client.set_model_version_tag(MODEL_NAME,registered.version,key,value)
        result={'status':'SUCCEEDED','model_name':MODEL_NAME,'model_version':registered.version,'run_id':run.info.run_id,
          'experiment_id':run.info.experiment_id,'model_uri':f'models:/{MODEL_NAME}/{registered.version}',
          'metadata':metadata,'fit_checkpoint_reused':reused,'training_missing_labels':missing,'fit_seconds':fit_seconds,
          'results':results,'elapsed_seconds':round(time.monotonic()-started,3),
          'client_max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    folder=(ROOT/'.local/airflow/ml'/hashlib.sha256(logical_id.encode()).hexdigest() if logical_id else ROOT/'.local/mlops');folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=folder/'candidate.json';temp=folder/'candidate.tmp';temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(target)
    print(json.dumps(result,indent=2),flush=True)
    return result

if __name__=='__main__':train()
