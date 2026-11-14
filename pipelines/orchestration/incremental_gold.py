"""GOLD v2 append-only, reutiliza SQL v1 sin alterar su código/hash ni snapshot."""
from datetime import timedelta
import hashlib
from pathlib import Path
from core import db,authorization
from retailops_gold.query import QUERY as BOOTSTRAP_QUERY,COLUMNS

QUERY=BOOTSTRAP_QUERY.replace("batch_id='bootstrap-2013-2014' AND ",'').replace("'sales-pit-v1'::text", "'sales-pit-v2'::text").replace("DATE '2014-12-31' historical_cutoff",'%(cutoff)s::date historical_cutoff')
LABEL_QUERY='''SELECT %(cutoff)s::date,date,store_nbr,family,sales FROM training.sales
 WHERE date BETWEEN %(start)s AND %(end)s'''

def materialize(batch,identifier):
    auth=authorization(batch,identifier)
    with db() as conn:
        if not conn.execute('SELECT pg_try_advisory_lock(729130031) locked').fetchone()['locked']:raise ValueError('Operación incompatible activa')
        params={'start':auth['previous_cutoff']+timedelta(days=1),'end':auth['period_end'],'cutoff':auth['period_end']}
        digest=hashlib.sha256((QUERY+LABEL_QUERY).encode()).hexdigest()
        with conn.transaction():
            conn.execute('SELECT control.require_released_snapshot(%s)',(auth['period_end'],))
            old=conn.execute('SELECT * FROM gold.incremental_materializations WHERE issue_start=%s',(params['start'],)).fetchone()
            if old and old['code_sha256']!=digest:raise ValueError('Conflicto de versión GOLD')
            if old:
                mismatch=conn.execute('WITH expected AS ('+QUERY+'), actual AS (SELECT '+COLUMNS+''' FROM gold.incremental_features WHERE issue_date BETWEEN %(start)s AND %(end)s)
                 SELECT EXISTS((TABLE expected EXCEPT TABLE actual) UNION ALL (TABLE actual EXCEPT TABLE expected)) bad''',params).fetchone()['bad']
                if mismatch:raise ValueError('Conflicto de contenido GOLD')
            else:
                conn.execute('INSERT INTO gold.incremental_features('+COLUMNS+') '+QUERY,params)
                conn.execute('INSERT INTO gold.incremental_labels '+LABEL_QUERY,params)
            bad=conn.execute('WITH expected AS ('+LABEL_QUERY+'''), actual AS(SELECT * FROM gold.incremental_labels WHERE target_date BETWEEN %(start)s AND %(end)s)
             SELECT EXISTS((TABLE expected EXCEPT TABLE actual) UNION ALL(TABLE actual EXCEPT TABLE expected)) bad''',params).fetchone()['bad']
            if bad:raise ValueError('Conflicto de etiquetas')
            counts=conn.execute('''SELECT (SELECT count(*) FROM gold.incremental_features WHERE issue_date BETWEEN %(start)s AND %(end)s) features,
             (SELECT count(*) FROM gold.incremental_labels WHERE target_date BETWEEN %(start)s AND %(end)s) labels''',params).fetchone()
            if not old:conn.execute('INSERT INTO gold.incremental_materializations(issue_start,issue_end,historical_cutoff,code_sha256,feature_rows,label_rows) VALUES(%s,%s,%s,%s,%s,%s)',(params['start'],params['end'],params['cutoff'],digest,counts['features'],counts['labels']))
            conn.execute('SELECT gold.confirm_incremental(%s)',(params['end'],))
    return {'batch':batch,'cutoff':str(params['cutoff']),'idempotent':bool(old),**counts}
