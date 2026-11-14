"""Baselines sin ajuste y backtest por bloques; únicamente vistas GOLD de training."""
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from retailops_eda.data import connection,ROOT,CUTOFF

FOLDS={'2014-07':(date(2014,7,1),date(2014,7,31)),
       '2014-09':(date(2014,9,1),date(2014,9,30)),
       '2014-11':(date(2014,11,1),date(2014,11,30))}
MODELS=('seasonal_naive_7','rolling_mean_7','rolling_mean_28')
SQL='''SELECT f.issue_date,f.target_date,f.horizon,f.store_nbr,f.family,
 f.lag_7::double precision,f.lag_7_available,
 f.rolling_mean_7::double precision,f.rolling_mean_28::double precision,
 l.sales::double precision actual
 FROM training.gold_features f LEFT JOIN training.gold_labels l
 ON l.historical_cutoff=f.historical_cutoff AND l.target_date=f.target_date
 AND l.store_nbr=f.store_nbr AND l.family=f.family AND l.target_date<=%(cutoff)s
 WHERE f.feature_version='sales-pit-v1' AND f.historical_cutoff=%(cutoff)s
 AND f.issue_date BETWEEN %(start)s AND %(end)s'''
FEATURES=('lag_7','lag_7_available','rolling_mean_7','rolling_mean_28')

def predict(features):
    """No consume etiquetas ni estima parámetros; NULL se mantiene como NaN."""
    values=features.loc[:,list(FEATURES)]
    result=pd.DataFrame(index=features.index)
    result['seasonal_naive_7']=values['lag_7'].where(values['lag_7_available'].eq(True)).astype(float)
    for model in MODELS[1:]:result[model]=values[model].astype(float)
    array=result.to_numpy()
    if np.isinf(array).any() or (array<0).any():raise ValueError('Predicciones fuera del dominio no negativo; no recortar automáticamente')
    return result

def eligible_labels(frame,fold):
    if fold not in FOLDS:raise ValueError('Fold no autorizado')
    start,end=map(pd.Timestamp,FOLDS[fold])
    issue=pd.to_datetime(frame['issue_date']);target=pd.to_datetime(frame['target_date'])
    horizon=frame['horizon']
    if not (issue.between(start,end)&horizon.between(1,7)&(target==issue+pd.to_timedelta(horizon,unit='D'))).all():
        raise ValueError('Emisión/objetivo fuera del contrato temporal del fold')
    return frame['actual'].notna() & target.le(pd.Timestamp(CUTOFF))

def metric_sums(actual,prediction):
    y=np.asarray(actual,dtype=float);p=np.asarray(prediction,dtype=float)
    if y.shape!=p.shape:raise ValueError('Longitudes incompatibles')
    if np.isinf(y).any() or np.isinf(p).any() or (y<0).any() or (p<0).any():raise ValueError('Métricas requieren valores finitos no negativos o ausentes')
    mask=np.isfinite(y)&np.isfinite(p);y=y[mask];p=p[mask]
    return np.array([len(y),np.abs(p-y).sum(),y.sum(),np.square(np.log1p(p)-np.log1p(y)).sum()],dtype=float)

def metrics(sums):
    n,absolute,volume,log_squared=map(float,sums)
    return {'n':int(n),'mae':absolute/n if n else None,
      'wape':absolute/volume if n and volume>0 else None,
      'rmsle':float(np.sqrt(log_squared/n)) if n else None,
      'zero_wape_denominator':bool(n and volume==0)}

def fold_chunks(fold):
    if fold not in FOLDS:raise ValueError('Fold no autorizado')
    start,end=FOLDS[fold];maximum=((end-start).days+1)*54*33*7
    count=0
    with connection() as conn:
        session=conn.execute("SELECT current_user role,current_setting('transaction_read_only') read_only").fetchone()
        if session!={'role':'retailops_trainer','read_only':'on'}:raise ValueError('Sesión no restringida')
        with conn.cursor(name='baseline_fold') as cur:
            cur.execute(SQL,{'start':start,'end':end,'cutoff':CUTOFF})
            while rows:=cur.fetchmany(20000):
                count+=len(rows)
                if count>maximum:raise ValueError('Granularidad excede el máximo contractual; revisar join')
                yield pd.DataFrame(rows)
    if count==0:raise ValueError('Fold sin datos: no declarar evaluación exitosa')

def evaluate():
    started=time.monotonic()
    totals=defaultdict(lambda:np.zeros(4,dtype=float));coverage=[];examples=[]
    for fold in FOLDS:
        counts={'fold':fold,'examples':0,'missing_label':0,'future_target':0,'labeled':0,'common':0,
                **{m+'_available':0 for m in MODELS},**{m+'_scored':0 for m in MODELS}}
        for frame in fold_chunks(fold):
            pred=predict(frame.loc[:,list(FEATURES)]) # Ninguna etiqueta entra al predictor.
            valid=eligible_labels(frame,fold)
            common=valid&pred.notna().all(axis=1)
            counts['examples']+=len(frame);counts['labeled']+=int(valid.sum())
            counts['missing_label']+=int((~valid).sum())
            counts['future_target']+=int(pd.to_datetime(frame['target_date']).gt(pd.Timestamp(CUTOFF)).sum())
            counts['common']+=int(common.sum())
            for model in MODELS:
                mask=valid&pred[model].notna()
                counts[model+'_available']+=int(pred[model].notna().sum())
                counts[model+'_scored']+=int(mask.sum())
                totals[('individual',fold,model)]+=metric_sums(frame.loc[mask,'actual'],pred.loc[mask,model])
                totals[('individual','all',model)]+=metric_sums(frame.loc[mask,'actual'],pred.loc[mask,model])
                totals[('global','all',model)]+=metric_sums(frame.loc[common,'actual'],pred.loc[common,model])
                totals[('fold',fold,model)]+=metric_sums(frame.loc[common,'actual'],pred.loc[common,model])
                # Estadísticas suficientes por grupo; nunca promediar WAPEs/RMSLE de bloques.
                subset=frame.loc[common,['horizon','family','store_nbr','actual']].copy()
                y=subset['actual'].to_numpy(dtype=float);p=pred.loc[common,model].to_numpy()
                subset['absolute']=np.abs(p-y);subset['volume']=y
                subset['log_squared']=np.square(np.log1p(p)-np.log1p(y));subset['n']=1
                for scope,column in [('horizon','horizon'),('family','family'),('store','store_nbr')]:
                    grouped=subset.groupby(column,sort=False)[['n','absolute','volume','log_squared']].sum()
                    for key,row in grouped.iterrows():totals[(scope,str(key),model)]+=row.to_numpy(dtype=float)
            # Ejemplo prefijado, no elegido por errores: tienda1/GROCERY I, emisión 2014-07-15.
            selected=(frame['store_nbr']==1)&frame['family'].eq('GROCERY I')&pd.to_datetime(frame['issue_date']).eq(pd.Timestamp('2014-07-15'))
            if selected.any():
                example=frame.loc[selected,['issue_date','target_date','horizon','store_nbr','family','actual']].copy()
                for model in MODELS:example[model]=pred.loc[selected,model]
                examples.extend(example.to_dict('records'))
        coverage.append(counts)
        print(f"{fold}: {counts['examples']} ejemplos, {counts['common']} comparables; sin ajuste de parámetros.",flush=True)
    table=pd.DataFrame([{'scope':scope,'segment':segment,'model':model,**metrics(sums)} for (scope,segment,model),sums in totals.items()])
    result={'feature_version':'sales-pit-v1','cutoff':str(CUTOFF),
      'folds':{k:[str(d) for d in v] for k,v in FOLDS.items()},'coverage':coverage,
      'metrics':table.astype(object).where(pd.notna(table),None).to_dict('records'),'examples':sorted(examples,key=lambda x:x['horizon']),
      'seconds':round(time.monotonic()-started,3),'comparison':'common labeled intersection, no imputation'}
    folder=ROOT/'.local/baselines';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Solo resumen por grupo y un ejemplo prefijado; ninguna credencial ni descarga completa.
    (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
    return result

def plots(result):
    import matplotlib.pyplot as plt
    from retailops_eda.analysis import setup
    setup();folder=ROOT/'docs/baseline_figures';folder.mkdir(parents=True,exist_ok=True)
    table=pd.DataFrame(result['metrics']);global_=table[table.scope.eq('global')].set_index('model').reindex(MODELS)
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,metric,label in zip(axes,['mae','wape','rmsle'],['MAE (cantidades registradas)','WAPE (%)','RMSLE (log1p, adimensional)']):
        values=global_[metric]*(100 if metric=='wape' else 1)
        ax.bar(['Semanal','Media 7','Media 28'],values);ax.set_title(label)
    fig.suptitle('Baselines · mismas observaciones · julio, septiembre y noviembre 2014')
    figures=[(fig,'global')]
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for model in MODELS:
        data=table[table.scope.eq('horizon')&table.model.eq(model)].copy();data['h']=data.segment.astype(int);data=data.sort_values('h')
        axes[0].plot(data.h,data.mae,marker='o',label=model)
        axes[1].plot(data.h,data.wape*100,marker='o',label=model)
    axes[0].set_ylabel('MAE · cantidades registradas');axes[1].set_ylabel('WAPE (%)')
    for ax in axes:ax.set_xlabel('Horizonte (días)');ax.set_xticks(range(1,8));ax.legend(fontsize=8)
    fig.suptitle('Error por horizonte · intersección común');figures.append((fig,'horizon'))
    family=table[table.scope.eq('family')].pivot(index='segment',columns='model',values='mae')
    family=family.sort_values('seasonal_naive_7')
    fig,ax=plt.subplots(figsize=(10,11));family.reindex(columns=MODELS).plot.barh(ax=ax,width=.8)
    ax.set_xlabel('MAE · cantidades registradas, escala distinta por familia');ax.set_ylabel('Familia')
    ax.set_title('Las 33 familias · ordenadas por MAE semanal, sin excluir ceros');ax.legend(fontsize=8)
    figures.append((fig,'families'))
    example=pd.DataFrame(result['examples']);example['target_date']=pd.to_datetime(example['target_date'])
    fig,ax=plt.subplots(figsize=(11,4));ax.plot(example.target_date,example.actual,marker='o',color='black',label='Real')
    for model in MODELS:ax.plot(example.target_date,example[model],marker='.',label=model)
    ax.set_title('Ejemplo prefijado · tienda 1 / GROCERY I · emisión 2014-07-15')
    ax.set_ylabel('Ventas registradas (cantidades)');ax.set_xlabel('Fecha objetivo');ax.legend(fontsize=8)
    fig.autofmt_xdate();figures.append((fig,'example'))
    for fig,name in figures:
        fig.tight_layout();fig.savefig(folder/(name+'.png'),dpi=150,bbox_inches='tight')
    return [fig for fig,_ in figures]
