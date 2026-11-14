"""Integración de solo lectura con credenciales trainer, sin administrador ni fixtures persistidas."""
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retailops_eda.data import query,validate_bootstrap,connection

@unittest.skipUnless(os.environ.get('RETAILOPS_EDA_INTEGRATION')=='1','Requiere PostgreSQL local')
class ConnectionTests(unittest.TestCase):
    def test_restricted_role_readonly_and_bootstrap(self):
        overview=validate_bootstrap()
        self.assertEqual(int(overview.records),1297296)
        self.assertEqual(int(overview.negative_sales),0)
    def test_queries_agree_without_future_data(self):
        total=query('overview').iloc[0]
        daily=query('daily');monthly=query('monthly')
        self.assertEqual(int(daily.records.sum()),int(total.records))
        self.assertEqual(int(monthly.records.sum()),int(total.records))
        self.assertEqual(len(daily),728);self.assertEqual(len(monthly),24)
        self.assertFalse(bool(query('future_visible').iloc[0].future_visible))
    def test_hidden_auxiliary_views_remain_hidden(self):
        visible=query('availability')
        self.assertEqual(int(visible.records.sum()),0)
        self.assertEqual(len(query('gaps')),2)
    def test_configured_server_limits(self):
        with connection() as conn:
            row=conn.execute("SELECT current_setting('statement_timeout') timeout,current_setting('lock_timeout') lock_timeout").fetchone()
            self.assertEqual(row['timeout'],'30s');self.assertEqual(row['lock_timeout'],'3s')

if __name__=='__main__':unittest.main()
