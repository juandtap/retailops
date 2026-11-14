"""Casos límite del contrato sin dependencias ni daemon Docker."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from storage_contracts import validate

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract=json.loads((ROOT/'contracts/data-storage-v1.json').read_text())
        self.profile=json.loads((ROOT/'docs/DATA_PROFILING.json').read_text())
        self.manifest=json.loads((ROOT/'docs/DATA_BATCH_MANIFEST.json').read_text())

    def test_current_profile_and_plan_match(self):
        validate(self.contract,self.profile,self.manifest)

    def test_released_or_mutated_plan_rejected(self):
        for field,value in [('release_performed',True),('historical_cutoff','2014-12-31')]:
            with self.subTest(field=field):
                plan=copy.deepcopy(self.manifest);plan[field]=value
                with self.assertRaises(ValueError):validate(self.contract,self.profile,plan)
        self.manifest['incremental_batches'][0]['released']=True
        with self.assertRaises(ValueError):validate(self.contract,self.profile,self.manifest)

    def test_overlap_and_wrong_count_rejected(self):
        plan=copy.deepcopy(self.manifest)
        plan['incremental_batches'][0]['period_start']='2014-12-31'
        with self.assertRaisesRegex(ValueError,'solapados'):validate(self.contract,self.profile,plan)
        self.manifest['incremental_batches'][0]['rows']+=1
        with self.assertRaisesRegex(ValueError,'total'):validate(self.contract,self.profile,self.manifest)

    def test_missing_source_or_new_null_rejected(self):
        self.profile['files']['stores.csv']['status']='faltante'
        with self.assertRaisesRegex(ValueError,'faltante'):validate(self.contract,self.profile,self.manifest)
        self.profile['files']['stores.csv']['status']='analizado'
        self.profile['files']['train.csv']['columns']['sales']['nulls']=1
        with self.assertRaisesRegex(ValueError,'nulabilidad'):validate(self.contract,self.profile,self.manifest)

    def test_compensated_monthly_counts_rejected(self):
        self.manifest['incremental_batches'][0]['rows']+=1
        self.manifest['incremental_batches'][1]['rows']-=1
        with self.assertRaisesRegex(ValueError,'mensual'):validate(self.contract,self.profile,self.manifest)

    def test_source_hash_mismatch_rejected(self):
        self.manifest['source_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'train'):validate(self.contract,self.profile,self.manifest)

if __name__=='__main__':unittest.main()
