import os
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from retailops_gold.pipeline import connect,state

@unittest.skipUnless(os.environ.get('RETAILOPS_GOLD_INTEGRATION')=='1','PostgreSQL optativo')
class StorageTests(unittest.TestCase):
    def test_snapshot_exact_and_guard_permissions(self):
        with connect() as conn:state(conn)
        with connect('trainer') as conn:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):conn.execute('SELECT control.require_gold_snapshot()')
    def test_trainer_explicit_surfaces_and_no_writes(self):
        for statement in ('SELECT * FROM gold.features LIMIT 0','SELECT * FROM silver.sales LIMIT 0',
          'CREATE TEMP TABLE leak(id integer)','SET ROLE retailops_ingestor',
          'DELETE FROM training.gold_features',"UPDATE control.historical_state SET released_through='2015-01-01'"):
            with self.subTest(statement=statement),connect('trainer') as conn:
                with self.assertRaises((psycopg.errors.InsufficientPrivilege,psycopg.errors.ObjectNotInPrerequisiteState)):conn.execute(statement)
        with connect('trainer') as conn:
            self.assertFalse(conn.execute("SELECT has_table_privilege(current_user,'training.gold_features','DELETE')").fetchone()[0])
            conn.execute('SELECT * FROM training.gold_features LIMIT 0')
            conn.execute('SELECT * FROM training.gold_labels LIMIT 0')
    def test_ingestor_no_ddl_cutoff_or_overwrite(self):
        for statement in ('CREATE TABLE gold.bypass(id integer)','DELETE FROM gold.features',
          "UPDATE control.historical_state SET released_through='2015-01-01'",'UPDATE gold.features SET lag_7=0'):
            with self.subTest(statement=statement),connect() as conn:
                with self.assertRaises((psycopg.errors.InsufficientPrivilege,psycopg.errors.ObjectNotInPrerequisiteState)):conn.execute(statement)
    def test_future_label_rejected_and_rolled_back(self):
        with connect() as conn:
            with self.assertRaises(psycopg.errors.CheckViolation):
                conn.execute("INSERT INTO gold.labels VALUES('2014-12-31','2015-01-01',1,'TEST',1)")
    def test_no_future_observations_or_auxiliaries(self):
        with connect('trainer') as conn:
            self.assertFalse(conn.execute("SELECT EXISTS(SELECT 1 FROM training.sales WHERE date>DATE '2014-12-31')").fetchone()[0])
            for name in ('stores','families','holidays_events','oil_prices'):
                self.assertEqual(conn.execute('SELECT count(*) FROM training.'+name).fetchone()[0],0)
    def test_synthetic_gold_uniqueness_atomic_rollback(self):
        # Nunca commit: fixture técnica limitada a GOLD.labels, no simula una ingesta.
        conn=connect()
        try:
            conn.execute("INSERT INTO gold.labels VALUES('2014-12-31','2013-01-01',1,'GOLD-TEST-ROLLBACK',0.125)")
            with self.assertRaises(psycopg.errors.UniqueViolation):
                conn.execute("INSERT INTO gold.labels VALUES('2014-12-31','2013-01-01',1,'GOLD-TEST-ROLLBACK',99)")
        finally:conn.rollback();conn.close()
        with connect() as check:
            self.assertEqual(check.execute("SELECT count(*) FROM gold.labels WHERE family='GOLD-TEST-ROLLBACK'").fetchone()[0],0)

if __name__=='__main__':unittest.main()
