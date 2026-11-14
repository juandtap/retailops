"""Controles mínimos temporal/modelo/API; sin infraestructura de fixtures adicional."""
from datetime import date,timedelta
import hashlib
from types import SimpleNamespace
import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.data import INPUTS,NUMERIC,ROOT,VERSION,FIT_DATE,SPLITS,feature_frame,validate_temporal
from app.model import build_model
from app.main import create_app
from app.runtime import ModelRuntime


def frame(issue=date(2014,12,31),n=7):
    rows=[]
    for i in range(n):
        h=i%7+1
        values={c:1 for c in NUMERIC}
        values.update(store_nbr=1,family='TEST',horizon=h,lag_7=np.nan,lag_7_available=False,
          rolling_mean_7=2.5,issue_date=issue,target_date=issue+timedelta(days=h))
        rows.append(values)
    return pd.DataFrame(rows)

def test_temporal_labels_and_inputs():
    valid=frame(date(2014,10,27),4).assign(actual=2)
    validate_temporal(valid,'train')
    with pytest.raises(ValueError):validate_temporal(frame(date(2014,10,27),5),'train')
    x=feature_frame(valid)
    pd.testing.assert_frame_equal(x,feature_frame(valid.assign(actual=1e20,future_sales=1e30)))
    assert x.lag_7.isna().all() and list(x.columns)==INPUTS
    assert SPLITS['evaluation'][0]>date(2014,12,7) # Último objetivo observado en F1-05.
    assert SPLITS['train'][2]<SPLITS['validation'][0]

def test_model_load_and_inference_contract(tmp_path,monkeypatch):
    x=feature_frame(frame(n=40));x.loc[0,'lag_7']=0.0;y=np.arange(40,dtype=float)%5
    model=build_model().fit(x,y)
    path=tmp_path/'model.joblib';joblib.dump(model,path)
    metadata={'feature_version':VERSION,'historical_cutoff':'2014-12-31','fit_date':str(FIT_DATE),
      'contract_sha256':hashlib.sha256((ROOT/'contracts/gold-features-v1.json').read_bytes()).hexdigest(),'inputs':INPUTS}
    monkeypatch.setattr('app.runtime.MlflowClient',lambda:SimpleNamespace(get_model_version=lambda *args:SimpleNamespace(run_id='test-run')))
    monkeypatch.setattr('app.runtime.mlflow.models.get_model_info',lambda uri:SimpleNamespace(metadata=metadata))
    monkeypatch.setattr('app.runtime.mlflow.sklearn.load_model',lambda *args,**kwargs:joblib.load(path))
    runtime=ModelRuntime.load('1')
    monkeypatch.setattr('app.main.inference_features',lambda *args:frame())
    with TestClient(create_app(loader=lambda:runtime)) as client:
        assert client.get('/health').status_code==200
        assert client.get('/model').json()['version']=='1'
        request={'issue_date':'2014-12-31','store_nbr':1,'family':'TEST'}
        response=client.post('/predict',json=request)
        assert response.status_code==200,response.text
        result=response.json();assert len(result['predictions'])==7
        assert [r['horizon'] for r in result['predictions']]==list(range(1,8))
        assert result['predictions'][-1]['target_date']=='2015-01-07'
        assert all(r['prediction']>=0 for r in result['predictions'])
        assert client.post('/predict',json={**request,'features':{'lag_7':1e20}}).status_code==422
        for issue in ('2013-01-01','2015-01-01'):
            assert client.post('/predict',json={**request,'issue_date':issue}).status_code==422
        monkeypatch.setattr('app.main.inference_features',lambda *args:None)
        assert client.post('/predict',json=request).status_code==404
    metadata['feature_version']='wrong'
    with pytest.raises(ValueError):ModelRuntime.load('1')
