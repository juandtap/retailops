"""Casos mínimos de secuencia y seguridad temporal v2, sin fuentes reales."""
import sys,unittest
from pathlib import Path
from datetime import date
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'pipelines/orchestration'),str(ROOT/'pipelines/ingestion')]
from core import plan
from incremental_gold import QUERY

class OrchestrationTests(unittest.TestCase):
    def test_month_order_and_partial_final(self):
        self.assertEqual(plan('2015-01',date(2014,12,31))['rows'],55242)
        for batch in ('2015-02','2014-12','2017-09'):
            with self.assertRaises(ValueError):plan(batch,date(2014,12,31))
        self.assertEqual(plan('2017-08',date(2017,7,31))['observed_end'],'2017-08-15')
        from core import db,authorization
        from uuid import uuid4
        import psycopg
        with self.assertRaises(ValueError):authorization('2015-01',str(uuid4()))
        with db() as conn:
            with self.assertRaises(psycopg.errors.RaiseException):
                conn.execute("INSERT INTO control.batches(batch_id,kind,entity,period_start,period_end,row_count) VALUES('2015-01','MONTHLY','sales','2015-01-01','2015-01-31',55242)")
    def test_v2_lags_and_rolling_against_extreme_future(self):
        # Solo expresión SQL, fixtures VALUES; las tablas productivas no se modifican.
        import psycopg
        from core import db
        source="(VALUES(DATE '2015-01-01',1::smallint,'X'::text,2::numeric),(DATE '2015-01-02',1::smallint,'X'::text,999999::numeric)) input(date,store_nbr,family,sales)"
        with db('trainer') as conn:
            rows=conn.execute(QUERY.replace('training.sales',source),{'start':date(2015,1,1),'end':date(2015,1,2),'cutoff':date(2015,1,31)}).fetchall()
        selected=[r for r in rows if r['issue_date']==date(2015,1,1)]
        self.assertEqual(len(selected),7)
        self.assertTrue(all(r['rolling_mean_7']==2 and r['history_count_28']==1 for r in selected))
        self.assertEqual(next(r for r in selected if r['horizon']==7)['lag_7'],2)
        self.assertIsNone(next(r for r in selected if r['horizon']==1)['lag_7'])

    def test_gold_write_idempotence_isolated_database(self):
        import os,psycopg
        from psycopg import sql
        from uuid import uuid4
        name='retailops_test_gold_'+uuid4().hex
        password=(ROOT/'.local/secrets/pg_admin_password').read_text().strip()
        options=dict(host='127.0.0.1',port=int(os.environ.get('POSTGRES_PORT','5432')),user='postgres',password=password,autocommit=True)
        admin=psycopg.connect(dbname='postgres',**options)
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            with psycopg.connect(dbname=name,**options) as conn:
                source="(VALUES(DATE '2015-01-01',1::smallint,'X'::text,2::numeric)) input(date,store_nbr,family,sales)"
                query=QUERY.replace('training.sales',source)
                params={'start':date(2015,1,1),'end':date(2015,1,1),'cutoff':date(2015,1,31)}
                conn.execute('CREATE TABLE features AS '+query+' WITH NO DATA',params)
                conn.execute('ALTER TABLE features ADD PRIMARY KEY(feature_version,issue_date,store_nbr,family,horizon)')
                conn.execute('INSERT INTO features '+query,params)
                self.assertEqual(conn.execute('SELECT count(*) FROM features').fetchone()[0],7)
                self.assertFalse(conn.execute('WITH expected AS('+query+') SELECT EXISTS((TABLE expected EXCEPT TABLE features) UNION ALL(TABLE features EXCEPT TABLE expected))',params).fetchone()[0])
                with self.assertRaises(psycopg.errors.UniqueViolation):conn.execute('INSERT INTO features '+query,params)
                self.assertEqual(conn.execute('SELECT lag_7 FROM features WHERE horizon=1').fetchone()[0],None)
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)));admin.close()

if __name__=='__main__':unittest.main()
