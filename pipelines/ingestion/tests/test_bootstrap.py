"""Contratos de extracción y BRONZE sin servicios ni escritura en SOURCE real."""
import csv
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retailops_bootstrap.extract import ConflictError,decimal_value,prepare,sha256,source_records
from retailops_bootstrap.pipeline import validate_local
import pyarrow.parquet as pq
from bootstrap_fixture import fixture, STAMP

class BootstrapExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.contract,self.inventory=fixture(self.root/'source')
    def tearDown(self):self.temp.cleanup()
    def prepare(self,name='workspace'):
        return prepare(self.root/'source',self.root/name,self.contract,self.inventory,STAMP)
    def test_temporal_decimals_promotions_and_trace(self):
        result=self.prepare()
        obj=next(o for o in result['objects'] if o['entity']=='sales' and o['layer']=='BRONZE')
        records=pq.read_table(self.root/'workspace'/obj['local_path']).to_pylist()
        self.assertEqual(len(records),4)
        self.assertEqual(records[0]['sales'],Decimal('1.1250001'))
        self.assertEqual([r['onpromotion'] for r in records],[2,0,1,3])
        self.assertEqual([r['source_row_number'] for r in records],[1,2,3,4])
        self.assertNotIn('FUTURE',{r['family'] for r in records})
        self.assertEqual(result['monthly_sales'],{'2014-12':4})
        self.assertEqual(Decimal(result['totals']['sales_sum']),Decimal('7.1250003'))
        validate_local(self.root/'workspace',result)
    def test_raw_bytes_and_unchanged_sources(self):
        result=self.prepare()
        obj=next(o for o in result['objects'] if o['entity']=='sales' and o['layer']=='RAW')
        original=(self.root/'source/train.csv').read_bytes().splitlines(keepends=True)
        self.assertEqual((self.root/'workspace'/obj['local_path']).read_bytes(),b''.join(original[:5]))
        self.assertTrue(all(sha256(self.root/'source'/e['file'])==e['sha256'] for e in self.inventory))
    def test_christmas_and_auxiliary_restrictions(self):
        result=self.prepare()
        self.assertEqual(result['counts']['observation_gaps'],1)
        for obj in result['objects']:
            if obj['entity'] in ('stores','families','holidays_events','oil_prices'):
                self.assertFalse(obj['publishable'])
                if obj['layer']=='BRONZE':
                    for r in pq.ParquetFile(self.root/'workspace'/obj['local_path']).read().to_pylist():
                        self.assertIsNone(r['known_from']);self.assertIsNone(r['availability_evidence'])
        gap=next(o for o in result['objects'] if o['entity']=='observation_gaps')
        self.assertIsNone(pq.ParquetFile(self.root/'workspace'/gap['local_path']).read().to_pylist()[0]['source_row_number'])
    def test_wrong_hash_rejected(self):
        self.inventory[0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SHA-256'):self.prepare()
    def test_unapproved_calendar_gap_or_count_rejected(self):
        self.contract['accepted_missing_dates']=[]
        with self.assertRaisesRegex(ValueError,'Ausencias'):self.prepare()
        self.contract['accepted_missing_dates']=['2014-12-25'];self.contract['expected_sales']=5
        with self.assertRaisesRegex(ValueError,'Conteo'):self.prepare('other')
    def test_deterministic_inventory_and_local_conflict(self):
        a=self.prepare();b=self.prepare('other')
        self.assertEqual(a['inventory_sha256'],b['inventory_sha256'])
        obj=a['objects'][0];(self.root/'workspace'/obj['local_path']).write_bytes(b'wrong')
        with self.assertRaises(ConflictError):validate_local(self.root/'workspace',a)
    def test_nonfinite_negative_or_excessive_scale_rejected(self):
        for value in ['NaN','Infinity','-1','0.0000000000000000001']:
            with self.subTest(value=value),self.assertRaises(ValueError):decimal_value(value)
    def test_workspace_inside_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'SOURCE'):
            prepare(self.root/'source',self.root/'source/work',self.contract,self.inventory,STAMP)

if __name__=='__main__':unittest.main()
