"""Comprobación real GOLD por vistas training y referencia independiente."""
from datetime import date,timedelta
from decimal import Decimal
import json
from pathlib import Path
from psycopg.rows import dict_row
from retailops_gold.pipeline import ROOT,connect,state
from retailops_gold.reference import features

def verify():
    with connect() as conn:
        state(conn)
        blocks=conn.execute('SELECT count(*),sum(feature_rows),sum(label_rows) FROM gold.materializations').fetchone()
        assert conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid IN ('gold.features'::regclass,'gold.labels'::regclass) AND contype='p'").fetchone()[0]==2
        size=conn.execute("SELECT pg_total_relation_size('gold.features'),pg_total_relation_size('gold.labels')").fetchone()
        assert blocks==(24,9106020,1297296),blocks
    with connect('trainer') as conn:
        cur=conn.cursor(row_factory=dict_row)
        stats=cur.execute('''SELECT count(*) rows,min(issue_date) first_issue,max(issue_date) last_issue,
        min(target_date) first_target,max(target_date) last_target,min(horizon) min_horizon,max(horizon) max_horizon,
        count(*) FILTER(WHERE target_date>historical_cutoff) unlabeled_future_examples,
        count(*) FILTER(WHERE lag_7 IS NULL) missing_lag7,
        count(*) FILTER(WHERE missing_history_flag) incomplete_history
        FROM training.gold_features''').fetchone()
        assert stats['rows']==9106020
        assert stats['first_issue']==date(2013,1,1) and stats['last_issue']==date(2014,12,31)
        labels=cur.execute('SELECT count(*) rows,max(target_date) last_target,sum(sales) total FROM training.gold_labels').fetchone()
        assert labels['rows']==1297296 and labels['last_target']==date(2014,12,31)
        assert labels['total']==Decimal('349893260.2211611')
        assert not cur.execute("SELECT EXISTS(SELECT 1 FROM training.gold_labels WHERE target_date>DATE '2014-12-31' OR target_date IN(DATE '2013-12-25',DATE '2014-12-25')) bad").fetchone()['bad']
        assert not cur.execute("SELECT EXISTS(SELECT 1 FROM training.gold_features WHERE issue_date=DATE '2014-12-31' AND horizon=1 AND lag_7 IS NOT NULL) bad").fetchone()['bad']
        # Selección fija de claves/fechas; no selecciona extremos ni estadísticas del futuro.
        checked=0;example=None
        for store,family in [(1,'GROCERY I'),(28,'BEVERAGES'),(54,'CLEANING')]:
            for issue in (date(2013,1,1),date(2013,12,25),date(2014,12,31)):
                obs={r['date']:r['sales'] for r in cur.execute('SELECT date,sales FROM training.sales WHERE store_nbr=%s AND family=%s AND date BETWEEN %s AND %s',(store,family,issue-timedelta(days=27),issue)).fetchall()}
                rows=cur.execute('SELECT * FROM training.gold_features WHERE store_nbr=%s AND family=%s AND issue_date=%s',(store,family,issue)).fetchall()
                assert len(rows)==7
                for row in rows:
                    for key,value in features(obs,issue,row['horizon']).items():
                        actual=row[key]
                        if isinstance(value,Decimal) and actual is not None:
                            assert abs(value-actual)<=max(Decimal('1e-12'),abs(value)*Decimal('1e-12')),(key,value,actual)
                        else:assert actual==value,(key,value,actual)
                    checked+=1
                if store==1 and issue==date(2014,12,31):example=rows[0]
    result={'status':'VERIFIED','features':stats,'labels':labels,'blocks':blocks[0],
            'reference_rows_checked':checked,'example':example,
            'postgres_table_and_index_bytes':{'features':size[0],'labels':size[1]}}
    (ROOT/'docs/GOLD_VERIFICATION.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(json.dumps(result,default=str))
if __name__=='__main__':verify()
