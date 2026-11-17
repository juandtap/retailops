"""Inferencia local: versión explícita del registro y features autorizadas del servidor."""
from contextlib import asynccontextmanager
from datetime import date
import os
from typing import Annotated
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StringConstraints,field_validator
from .data import CUTOFF,FIT_DATE,inference_features
from .metrics import instrument

class PredictionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    issue_date:date
    store_nbr:Annotated[int,Field(strict=True,ge=1,le=32767)]
    family:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=120)]
    @field_validator('issue_date')
    @classmethod
    def authorized_issue(cls,value):
        if not FIT_DATE<=value<=CUTOFF:raise ValueError('issue_date fuera del período autorizado del modelo: 2014-10-31..2014-12-31')
        return value

class HorizonPrediction(BaseModel):
    target_date:date
    horizon:Annotated[int,Field(ge=1,le=7)]
    prediction:Annotated[float,Field(ge=0,allow_inf_nan=False)]

class PredictionResponse(BaseModel):
    store_nbr:int
    family:str
    issue_date:date
    model_name:str
    model_version:str
    feature_version:str
    historical_cutoff:date
    predictions:list[HorizonPrediction]=Field(min_length=7,max_length=7)

def create_app(loader=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.model=None
        if loader is not None:app.state.model=loader()
        elif version:=os.environ.get('ML_MODEL_VERSION'):
            from .runtime import ModelRuntime
            app.state.model=ModelRuntime.load(version)
        app.state.model_metric.clear()
        if app.state.model is not None:
            info=app.state.model.information()
            app.state.model_metric.labels(*(str(info[key]) for key in ('name','version','feature_version','purpose'))).set(1)
        yield
        app.state.model=None
        app.state.model_metric.clear()
    app=FastAPI(title='RetailOps — Servicio ML',version='0.2.0',lifespan=lifespan)
    instrument(app)
    @app.get('/health',tags=['salud'])
    def health():return {'status':'ok'}
    @app.get('/model',tags=['modelo'])
    def model_info():
        if app.state.model is None:raise HTTPException(503,'Configurar ML_MODEL_VERSION para cargar una versión registrada')
        return app.state.model.information()
    @app.post('/predict',response_model=PredictionResponse,tags=['predicción'])
    def predict(request:PredictionRequest):
        runtime=app.state.model
        if runtime is None:raise HTTPException(503,'Modelo no cargado')
        try:frame=inference_features(request.issue_date,request.store_nbr,request.family)
        except Exception:raise HTTPException(503,'No se pudieron consultar features autorizadas; revisar servicio y contrato') from None
        if frame is None:raise HTTPException(404,'Sin features para la tienda/familia/emisión solicitada')
        try:values=runtime.predict(frame)
        except Exception:raise HTTPException(503,'No se pudo generar un pronóstico válido') from None
        return {'store_nbr':request.store_nbr,'family':request.family,'issue_date':request.issue_date,
          'model_name':runtime.information()['name'],'model_version':runtime.version,
          'feature_version':'sales-pit-v1','historical_cutoff':CUTOFF,
          'predictions':[{'target_date':row.target_date,'horizon':int(row.horizon),'prediction':float(value)}
             for row,value in zip(frame.itertuples(),values,strict=True)]}
    return app

app=create_app()
