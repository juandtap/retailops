import os
import sys
import unittest
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retailops_gold.reference import features,MODEL_INPUTS
from retailops_gold.query import QUERY

class ReferenceTests(unittest.TestCase):
    def test_extreme_future_cannot_change_any_horizon(self):
        issue=date(2014,12,24);past={issue-timedelta(days=i):Decimal(i) for i in range(35)}
        for h in range(1,8):
            contaminated={**past,**{issue+timedelta(days=i):Decimal('1e20') for i in range(1,8)}}
            self.assertEqual(features(past,issue,h),features(contaminated,issue,h))
    def test_christmas_is_unknown_and_zero_is_observed(self):
        issue=date(2014,12,31)
        result=features({issue:Decimal(0)},issue,1)
        self.assertEqual(result['history_count_28'],1)
        self.assertEqual(result['rolling_mean_7'],0)
        self.assertIsNone(result['rolling_std_28'])
        self.assertIsNone(result['lag_7'])
        self.assertFalse(result['lag_7_available'])
        self.assertTrue(result['missing_history_flag'])
    def test_empty_history_and_invalid_horizon(self):
        result=features({},date(2013,1,1),7)
        self.assertIsNone(result['rolling_mean_28']);self.assertEqual(result['history_count_28'],0)
        with self.assertRaises(ValueError):features({},date(2013,1,1),8)
    def test_calendar_and_label_separation(self):
        self.assertNotIn('sales',MODEL_INPUTS)
        result=features({},date(2014,12,31),3)
        self.assertEqual((result['day_of_week'],result['month'],result['is_weekend']),(6,1,True))

@unittest.skipUnless(os.environ.get('RETAILOPS_GOLD_INTEGRATION')=='1','PostgreSQL optativo')
class SyntheticSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from retailops_gold.pipeline import connect
        cls.conn=connect('trainer')
        # VALUES como fuente: nunca escribe fixtures en la base ni necesita TEMP/DDL.
        cls.issue=date(2014,12,31)
        cls.obs={cls.issue-timedelta(days=i):Decimal(i)/Decimal(4) for i in range(45) if i!=6}
        cls.obs[cls.issue]=Decimal(0)
        cls.obs.update({cls.issue+timedelta(days=i):Decimal('1e20') for i in range(1,8)})
        values=','.join("(DATE '%s',1::smallint,'TEST'::text,%s::numeric,'bootstrap-2013-2014'::text)"%(d,v) for d,v in cls.obs.items())
        # Nueva categoría exclusivamente futura: no debe aparecer en emisiones anteriores.
        values+=",(DATE '2015-01-01',2::smallint,'FUTURE',999::numeric,'bootstrap-2013-2014')"
        cls.source='(VALUES '+values+') AS input(date,store_nbr,family,sales,batch_id)'
        query=QUERY.replace('training.sales',cls.source)
        from psycopg.rows import dict_row
        cls.rows=cls.conn.cursor(row_factory=dict_row).execute(query,{'start':cls.issue-timedelta(days=2),'end':cls.issue+timedelta(days=3)}).fetchall()
    @classmethod
    def tearDownClass(cls):cls.conn.close()
    def test_sql_matches_reference_and_no_future_categories(self):
        for row in self.rows:
            if row['issue_date']>self.issue:continue
            self.assertEqual(row['store_nbr'],1)
            expected=features(self.obs,row['issue_date'],row['horizon'])
            for key,value in expected.items():
                actual=row[key]
                if isinstance(value,Decimal) and actual is not None:self.assertAlmostEqual(actual,value,places=12)
                else:self.assertEqual(actual,value,(key,row['issue_date'],row['horizon']))
    def test_missing_christmas_exact_lag(self):
        row=next(r for r in self.rows if r['issue_date']==self.issue and r['horizon']==1)
        self.assertIsNone(row['lag_7']);self.assertFalse(row['lag_7_available'])
        self.assertEqual(row['history_count_28'],27)
    def test_seven_day_horizon_no_first_six_targets(self):
        row=next(r for r in self.rows if r['issue_date']==self.issue and r['horizon']==7)
        self.assertEqual(row['lag_7'],0)
        self.assertLess(row['rolling_mean_7'],100)
    def test_content_comparison_detects_null_zero_and_extra_rows(self):
        for actual in ('VALUES(0::numeric)','VALUES(NULL::numeric),(1::numeric)'):
            sql='WITH expected AS(VALUES(NULL::numeric)), actual AS('+actual+') SELECT EXISTS((TABLE expected EXCEPT TABLE actual) UNION ALL (TABLE actual EXCEPT TABLE expected))'
            self.assertTrue(self.conn.execute(sql).fetchone()[0])
        self.assertFalse(self.conn.execute('WITH expected AS(VALUES(NULL::numeric)),actual AS(VALUES(NULL::numeric)) SELECT EXISTS((TABLE expected EXCEPT TABLE actual) UNION ALL (TABLE actual EXCEPT TABLE expected))').fetchone()[0])
    def test_short_history_sql(self):
        query=QUERY.replace('training.sales',"(VALUES(DATE '2013-01-01',1::smallint,'NEW'::text,0::numeric,'bootstrap-2013-2014'::text)) AS input(date,store_nbr,family,sales,batch_id)")
        from psycopg.rows import dict_row
        rows=self.conn.cursor(row_factory=dict_row).execute(query,{'start':date(2013,1,1),'end':date(2013,1,2)}).fetchall()
        self.assertEqual(len(rows),14)
        self.assertTrue(all(r['history_count_28']==1 and r['rolling_std_28'] is None for r in rows))

if __name__=='__main__':unittest.main()
