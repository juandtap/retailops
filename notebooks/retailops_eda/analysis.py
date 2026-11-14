"""Transformaciones descriptivas en memoria; no crean tablas ni features persistidas."""
from pathlib import Path
import json
import math
import os

import matplotlib.pyplot as plt
import pandas as pd

from .data import ROOT,START,CUTOFF

UNIT='Ventas registradas (mezcla de unidades/peso)'
FIGURES=ROOT/'docs/eda_figures'
PRIVATE=ROOT/'.local/eda'


def setup():
    plt.rcParams.update({'figure.figsize':(12,5),'figure.dpi':110,'axes.spines.top':False,
      'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2,'axes.axisbelow':True,'font.size':10})
    pd.set_option('display.max_rows',20)


def finish(fig,name):
    FIGURES.mkdir(parents=True,exist_ok=True)
    if name in {'eda_monthly','ts_trend','ts_segments'}:
        for ax in fig.axes:ax.set_xlim(pd.Timestamp(START),pd.Timestamp(CUTOFF))
    fig.tight_layout()
    fig.savefig(FIGURES/(name+'.png'),dpi=150,bbox_inches='tight')
    return fig


def calendar_series(daily):
    dates=pd.to_datetime(daily['date'])
    if dates.duplicated().any():raise ValueError('Fechas agregadas repetidas')
    if ((dates<pd.Timestamp(START))|(dates>pd.Timestamp(CUTOFF))).any():raise ValueError('Dato fuera del período autorizado')
    series=pd.Series(daily['total_sales'].astype(float).to_numpy(),index=dates).sort_index()
    return series.reindex(pd.date_range(START,CUTOFF,freq='D')).rename('Ventas')


def lag_correlations(series,max_lag=56):
    if not isinstance(series.index,pd.DatetimeIndex) or not series.index.equals(pd.date_range(series.index.min(),series.index.max(),freq='D')):
        raise ValueError('La autocorrelación requiere índice diario completo con ausencias NaN')
    if not 1<=max_lag<=90:raise ValueError('Retardos fuera de límite')
    rows=[]
    for lag in range(1,max_lag+1):
        pair=pd.concat([series,series.shift(lag)],axis=1).dropna()
        correlation=pair.iloc[:,0].corr(pair.iloc[:,1]) if len(pair)>=30 and (pair.std()>0).all() else float('nan')
        rows.append({'lag_days':lag,'correlation':correlation,'pairs':len(pair)})
    return pd.DataFrame(rows)


def monthly_means(monthly):
    frame=monthly.copy()
    if frame['observed_days'].le(0).any():raise ValueError('Mes sin días observados')
    frame['sales_per_observed_day']=frame['total_sales']/frame['observed_days']
    frame['calendar_days']=pd.to_datetime(frame['month']).dt.days_in_month
    frame['missing_days']=frame['calendar_days']-frame['observed_days']
    return frame


def save_summary(name,summary):
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(PRIVATE,0o700)
    # Solo resultados agregados; no credenciales, consultas ni filas originales.
    def clean(value):
        if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
        if isinstance(value,list):return [clean(v) for v in value]
        if hasattr(value,'item'):return clean(value.item())
        if isinstance(value,float) and not math.isfinite(value):return None
        return value
    (PRIVATE/(name+'.json')).write_text(json.dumps(clean(summary),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
