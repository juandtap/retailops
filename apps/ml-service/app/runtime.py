"""Carga una versión explícita del registro y consulta GOLD para cada petición."""
from pathlib import Path
import hashlib
import os
import numpy as np
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from threadpoolctl import threadpool_limits
from .data import ROOT,VERSION,CUTOFF,FIT_DATE,INPUTS,feature_frame,inference_features

MODEL_NAME='retailops-sales-global'

class ModelRuntime:
    def __init__(self,model,version,run_id,metadata,metrics=None):
        self.model=model;self.version=str(version);self.run_id=run_id;self.metadata=metadata;self.metrics=metrics or {}

    @classmethod
    def load(cls,version):
        if not str(version).isdigit() or int(version)<1:raise ValueError('Versión de modelo inválida')
        mlflow.set_tracking_uri(os.environ.get('MLFLOW_TRACKING_URI','http://127.0.0.1:5000'))
        uri=f'models:/{MODEL_NAME}/{version}'
        registered=MlflowClient().get_model_version(MODEL_NAME,str(version))
        info=mlflow.models.get_model_info(uri);metadata=info.metadata or {}
        expected=hashlib.sha256((ROOT/'contracts/gold-features-v1.json').read_bytes()).hexdigest()
        if metadata.get('feature_version')!=VERSION or metadata.get('historical_cutoff')!=str(CUTOFF) or metadata.get('fit_date')!=str(FIT_DATE) or metadata.get('contract_sha256')!=expected or metadata.get('inputs')!=INPUTS:
            raise ValueError('Modelo y contrato temporal incompatibles')
        cache=ROOT/'.local/mlops/models'/str(version);cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        model=mlflow.sklearn.load_model(uri,dst_path=str(cache))
        run_metrics=MlflowClient().get_run(registered.run_id).data.metrics
        allowed={f'{split}_{method}_{metric}' for split in ('validation','evaluation') for method in ('hgb','seasonal_naive_7') for metric in ('mae','wape','rmsle')}
        metrics={k:float(v) for k,v in run_metrics.items() if k in allowed and np.isfinite(v)}
        return cls(model,version,registered.run_id,metadata,metrics)

    def information(self):
        return {'name':MODEL_NAME,'version':self.version,'run_id':self.run_id,
          'feature_version':VERSION,'historical_cutoff':str(CUTOFF),'fit_date':str(FIT_DATE),
          'purpose':'candidate_local_preview','production_approved':False,'metrics':self.metrics}

    def predict(self,frame):
        # Selección explícita: nunca consume etiquetas ni features recibidas por HTTP.
        with threadpool_limits(limits=2):values=np.asarray(self.model.predict(feature_frame(frame)))
        if len(values)!=7 or not (np.isfinite(values)&(values>=0)).all():raise ValueError('Modelo produjo valores inválidos')
        return values
