"""Lectura trainer reutilizada; ninguna consulta a tablas base o auxiliares."""
from datetime import date
from pathlib import Path
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'notebooks'))
from retailops_eda.data import connection,CUTOFF

VERSION='sales-pit-v1'
FIT_DATE=date(2014,10,31)
SPLITS={
 'train':(date(2013,1,7),date(2014,10,27),FIT_DATE),
 'validation':(date(2014,11,1),date(2014,11,23),date(2014,11,30)),
 'evaluation':(date(2014,12,8),date(2014,12,24),CUTOFF)}
CATEGORICAL=['store_nbr','family']
NUMERIC=['horizon','day_of_week','month','is_weekend','lag_7','lag_14','lag_28',
 'lag_7_available','lag_14_available','lag_28_available','rolling_mean_7','rolling_mean_28',
 'rolling_std_28','history_count_28','missing_history_flag']
INPUTS=CATEGORICAL+NUMERIC
COLUMNS=','.join('f.'+c for c in ['issue_date','target_date',*INPUTS])


def validate_temporal(frame,split,plan=None):
    start,end,available=(plan['splits'] if plan else SPLITS)[split]
    issue=pd.to_datetime(frame.issue_date);target=pd.to_datetime(frame.target_date)
    if not (issue.between(pd.Timestamp(start),pd.Timestamp(end))&frame.horizon.between(1,7)&
            target.eq(issue+pd.to_timedelta(frame.horizon,unit='D'))).all():
        raise ValueError('Contrato emisión/objetivo/horizonte incompatible')
    if split=='train' and (not target.le(pd.Timestamp(available)).all() or not issue.dt.day_of_week.eq(0).all()):
        raise ValueError('Etiqueta desconocida en la fecha de ajuste o muestreo no reproducible')


def feature_frame(frame):
    """Lista cerrada de entradas: excluye sales, actual y cualquier etiqueta externa."""
    result=frame.loc[:,INPUTS].copy()
    for c in CATEGORICAL:result[c]=result[c].astype(str)
    for c in NUMERIC:result[c]=pd.to_numeric(result[c]).astype('float32')
    return result


def training_chunks(split,plan=None):
    splits=plan['splits'] if plan else SPLITS
    if split not in splits:raise ValueError('División no autorizada')
    start,end,available=splits[split]
    weekly=" AND extract(isodow FROM f.issue_date)=1 AND f.target_date<=%(available)s" if split=='train' else ''
    query='SELECT '+COLUMNS+''',l.sales::double precision actual
    FROM training.gold_features f LEFT JOIN training.gold_labels l
    ON l.historical_cutoff=f.historical_cutoff AND l.target_date=f.target_date
    AND l.store_nbr=f.store_nbr AND l.family=f.family AND l.target_date<=%(available)s
    WHERE f.feature_version=%(version)s AND f.historical_cutoff=%(cutoff)s
    AND f.issue_date BETWEEN %(start)s AND %(end)s'''+weekly+' ORDER BY f.issue_date,f.store_nbr,f.family,f.horizon'
    if plan:
        query=query.replace('training.gold_features f','training.gold_features_v2 f').replace('training.gold_labels l','training.gold_labels_v2 l')
        query=query.replace('l.historical_cutoff=f.historical_cutoff AND ', 'l.historical_cutoff<=%(cutoff)s AND ')
        query=query.replace('f.historical_cutoff=%(cutoff)s','f.historical_cutoff<=%(cutoff)s')
    maximum=((end-start).days+1)*54*33*7
    count=0
    with connection() as conn:
        with conn.cursor(name='ml_temporal_split') as cur:
            cur.execute(query,{'version':plan['version'] if plan else VERSION,'cutoff':plan['cutoff'] if plan else CUTOFF,'start':start,'end':end,'available':available})
            while rows:=cur.fetchmany(20000):
                count+=len(rows)
                if count>maximum:raise ValueError('Granularidad inesperada: detener lectura')
                frame=pd.DataFrame(rows)
                validate_temporal(frame,split,plan)
                yield frame
    if not count:raise ValueError('División vacía')


def inference_features(issue_date,store_nbr,family):
    with connection() as conn:
        rows=conn.execute('SELECT '+COLUMNS+''' FROM training.gold_features f
        WHERE f.feature_version=%s AND f.historical_cutoff=%s AND f.issue_date=%s
        AND f.store_nbr=%s AND f.family=%s ORDER BY f.horizon LIMIT 8''',
        (VERSION,CUTOFF,issue_date,store_nbr,family)).fetchall()
    if not rows:return None
    frame=pd.DataFrame(rows)
    if len(frame)!=7 or frame.horizon.tolist()!=list(range(1,8)):
        raise ValueError('GOLD incompleto: no devolver un pronóstico parcial')
    if not (pd.to_datetime(frame.target_date)==pd.Timestamp(issue_date)+pd.to_timedelta(frame.horizon,unit='D')).all():
        raise ValueError('Fechas objetivo incompatibles')
    return frame
