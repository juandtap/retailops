"""Referencia independiente en Decimal, fechas de calendario, sin SQL ni pandas."""
from datetime import timedelta
from decimal import Decimal, localcontext

def features(observations, issue_date, horizon):
    if not 1<=horizon<=7:raise ValueError('Horizonte fuera de 1..7')
    target=issue_date+timedelta(days=horizon)
    result={'day_of_week':target.isoweekday(),'month':target.month,'is_weekend':target.weekday()>=5}
    for lag in (7,14,28):
        d=target-timedelta(days=lag)
        value=observations.get(d) if d<=issue_date else None
        result[f'lag_{lag}']=value
        result[f'lag_{lag}_available']=value is not None
    for n in (7,28):
        values=[observations[d] for offset in range(n) if (d:=issue_date-timedelta(days=offset)) in observations]
        mean=sum(values,Decimal(0))/len(values) if values else None
        result[f'rolling_mean_{n}']=mean
        if n==28:
            with localcontext() as ctx:
                ctx.prec=40
                result['rolling_std_28']=(sum((x-mean)**2 for x in values)/(len(values)-1)).sqrt() if len(values)>=2 else None
            result['history_count_28']=len(values)
            result['missing_history_flag']=len(values)<28
    return result

# Interfaz futura: seleccionar exclusivamente estas entradas, nunca SELECT * con etiquetas.
MODEL_INPUTS=('day_of_week','month','is_weekend','lag_7','lag_14','lag_28',
 'lag_7_available','lag_14_available','lag_28_available','rolling_mean_7',
 'rolling_mean_28','rolling_std_28','history_count_28','missing_history_flag')
BASELINE_INPUTS={'seasonal_naive_7':('lag_7','lag_7_available'),
                 'retrospective_mean':('rolling_mean_7','history_count_28')}
