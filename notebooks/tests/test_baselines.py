"""Pruebas mínimas: métricas, ausencias y separación temporal/predictor."""
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retailops_baselines import predict,metric_sums,metrics,eligible_labels

class BaselineTests(unittest.TestCase):
    def test_metrics_known_values_missing_and_zero_denominator(self):
        result=metrics(metric_sums([0,3,10,np.nan],[0,1,np.nan,50]))
        self.assertEqual(result['n'],2);self.assertEqual(result['mae'],1)
        self.assertAlmostEqual(result['wape'],2/3)
        self.assertAlmostEqual(result['rmsle'],math.log(2)/math.sqrt(2))
        zero=metrics(metric_sums([0,0],[0,2]))
        self.assertIsNone(zero['wape']);self.assertTrue(zero['zero_wape_denominator'])
        self.assertIsNone(metrics(metric_sums([1],[np.nan]))['mae'])
        with self.assertRaises(ValueError):metric_sums([1],[-1])
    def test_predictor_ignores_labels_and_preserves_missing(self):
        features=pd.DataFrame({'lag_7':[0,99,np.nan],'lag_7_available':[True,False,False],
          'rolling_mean_7':[2,3,np.nan],'rolling_mean_28':[4,5,6],
          'actual':[1,2,3]})
        expected=predict(features)
        changed=features.assign(actual=[1e20,1e20,1e20],future_sales=[1e30]*3)
        pd.testing.assert_frame_equal(expected,predict(changed))
        self.assertEqual(expected.iloc[0,0],0);self.assertTrue(expected.iloc[1:].seasonal_naive_7.isna().all())
        self.assertTrue(math.isnan(expected.iloc[2].rolling_mean_7))
    def test_temporal_fold_and_cutoff(self):
        frame=pd.DataFrame({'issue_date':['2014-07-31']*2,'target_date':['2014-08-01','2014-08-07'],
          'horizon':[1,7],'actual':[10,np.nan]})
        self.assertEqual(eligible_labels(frame,'2014-07').tolist(),[True,False])
        with self.assertRaises(ValueError):eligible_labels(frame,'2014-09')
        invalid=frame.copy();invalid.loc[0,'target_date']='2015-01-01'
        with self.assertRaises(ValueError):eligible_labels(invalid,'2014-07')
        # El máximo objetivo de los folds autorizados es 2014-12-07, nunca 2015.
        invalid.loc[0,'target_date']='2014-08-08'
        with self.assertRaises(ValueError):eligible_labels(invalid,'2014-07')

if __name__=='__main__':unittest.main()
