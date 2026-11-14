"""Casos de calendario y lag sin datos de producción."""
import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retailops_eda.analysis import calendar_series,lag_correlations,monthly_means
from retailops_eda.data import query,Config

class AnalysisTests(unittest.TestCase):
    def test_missing_dates_stay_nan_and_real_zeros_survive(self):
        data=pd.DataFrame({'date':pd.to_datetime(['2014-12-24','2014-12-26']),'total_sales':[0,2]},index=[6,12])
        series=calendar_series(data)
        self.assertEqual(series.loc['2014-12-24'],0)
        self.assertTrue(np.isnan(series.loc['2014-12-25']))
        self.assertEqual(series.loc['2014-12-26'],2)
        self.assertEqual(len(series),730)
    def test_future_and_duplicate_dates_are_rejected(self):
        for dates in [['2015-01-01'],['2013-01-01','2013-01-01']]:
            with self.subTest(dates=dates),self.assertRaises(ValueError):
                calendar_series(pd.DataFrame({'date':pd.to_datetime(dates),'total_sales':[1]*len(dates)}))
    def test_lag_does_not_compress_missing_calendar_day(self):
        series=pd.Series(np.arange(80,dtype=float),index=pd.date_range('2013-01-01',periods=80))
        series.iloc[30]=np.nan
        result=lag_correlations(series,7)
        self.assertEqual(int(result.iloc[0].pairs),77)
        self.assertEqual(int(result.iloc[-1].pairs),71)
        self.assertAlmostEqual(result.iloc[-1].correlation,1)
    def test_compressed_calendar_rejected(self):
        series=pd.Series(range(40),index=pd.date_range('2013-01-01',periods=40).delete(20).append(pd.DatetimeIndex(['2013-03-01'])))
        with self.assertRaisesRegex(ValueError,'índice'):lag_correlations(series)
    def test_monthly_normalization_uses_observed_days(self):
        frame=pd.DataFrame({'month':pd.to_datetime(['2013-12-01']),'total_sales':[300.],'observed_days':[30]})
        result=monthly_means(frame)
        self.assertEqual(result.iloc[0].sales_per_observed_day,10)
        self.assertEqual(result.iloc[0].missing_days,1)
    def test_unknown_queries_and_overrides_rejected_before_connect(self):
        for name,kwargs in [('arbitrary',{}),('daily',{'end':'2017-01-01'}),('store_daily',{'stores':[1,2,3,4]}),('family_daily',{'families':[]}),('extremes',{'threshold':-1})]:
            with self.subTest(name=name),self.assertRaises(ValueError):query(name,**kwargs)
    def test_notebook_save_removes_outputs_and_execution_state(self):
        from retailops_eda.runtime import strip_outputs_on_save
        model={'type':'notebook','content':{'cells':[{'cell_type':'code','source':'print(1)','outputs':[{'text':'dato privado'}],'execution_count':1,'metadata':{'execution':{}}},{'cell_type':'markdown','source':'Texto'}]}}
        strip_outputs_on_save(model,'test.ipynb',None)
        cell=model['content']['cells'][0]
        self.assertEqual(cell['outputs'],[]);self.assertIsNone(cell['execution_count'])
        self.assertNotIn('execution',cell['metadata']);self.assertEqual(cell['source'],'print(1)')

    def test_admin_secret_or_remote_host_rejected(self):
        with self.assertRaises(ValueError):Config(host='remote.example').validate()
        with self.assertRaises(ValueError):Config(password_file=Path('/tmp/pg_admin_password')).validate()

if __name__=='__main__':unittest.main()
