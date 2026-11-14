"""Reglas de calidad con fuentes sintéticas pequeñas; ningún CSV original se escribe."""
import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retailops_profiling.core import (SCHEMAS, ColumnSummary, analyze, checksum,
    exact_quantiles, inferred_type, month_status, profile_file, value_kind)
from retailops_profiling.__main__ import safe_output
from retailops_profiling.report import render_report


class ProfilingTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        self.conn = sqlite3.connect(self.root/'work.sqlite3')
        self.conn.create_function('kind',1,value_kind,deterministic=True)

    def tearDown(self):
        self.conn.close()
        self.scratch.cleanup()

    def write_csv(self,name,rows,header=None):
        path=self.root/name
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(header if header is not None else SCHEMAS[name])
            writer.writerows(rows)
        return path

    def test_inference_and_non_finite_values(self):
        cases={'':'null','  ':'null','True':'boolean','false':'boolean','2016-02-29':'date',
               '2015-02-29':'text','1':'integer','1.25':'decimal','1e2':'decimal',
               'NaN':'non_finite','Infinity':'non_finite','NA':'text'}
        for value,kind in cases.items():
            with self.subTest(value=value): self.assertEqual(value_kind(value),kind)
        self.assertEqual(inferred_type(Counter(integer=2,decimal=1)),'decimal')
        self.assertEqual(inferred_type(Counter(null=2)),'desconocido (solo nulos)')

    def test_numeric_summary_zeros_negatives_fractional(self):
        column=ColumnSummary()
        for value in ['0','-1','2.5',None,'NaN']:
            column.add(value)
        stats=column.numeric()
        self.assertEqual(stats['count'],3)
        self.assertAlmostEqual(stats['mean'],.5)
        self.assertEqual((stats['zero'],stats['negative'],stats['fractional']),(1,1,1))

    def test_duplicates_across_batches_ignore_id_for_sales_key(self):
        path=self.write_csv('train.csv',[
            [1,'2014-01-01',1,'A','1.5',0],
            [2,'2014-01-01',1,'A','2.5',1],
            [2,'2014-01-01',1,'A','2.5',1]])
        original=checksum(path)
        profile=profile_file(self.conn,path,batch_size=1)
        self.assertEqual(profile['duplicate_rows_excess'],1)
        self.assertEqual(profile['duplicate_keys_excess'],2)
        self.assertEqual(profile['rows'],3)
        self.assertEqual(profile['columns']['sales']['numeric']['fractional'],3)
        self.assertEqual(profile['columns']['sales']['numeric']['quantiles']['0.5'],2.5)
        self.assertEqual(checksum(path),original)

    def test_nulls_malformed_rows_and_invalid_recommended_types(self):
        path=self.write_csv('oil.csv',[
            ['2014-01-01',''],['2014-01-02','NaN'],['not-a-date','oops'],
            ['2014-01-04','1.5'],['2014-01-05']])
        profile=profile_file(self.conn,path,2)
        self.assertEqual(profile['rows'],5)
        self.assertEqual(profile['valid_rows'],4)
        self.assertEqual(profile['malformed_rows'],1)
        self.assertEqual(profile['columns']['dcoilwtico']['nulls'],1)
        self.assertEqual(profile['columns']['dcoilwtico']['invalid_for_recommended_type'],2)
        self.assertEqual(profile['columns']['date']['invalid_for_recommended_type'],1)
        self.assertEqual(profile['columns']['dcoilwtico']['numeric']['quantiles']['0.99'],1.5)

    def test_quantiles_interpolate_and_exclude_invalid_numbers(self):
        path=self.write_csv('oil.csv',[
            ['2015-01-01',0],['2015-01-02',2],['2015-01-03','NaN'],['2015-01-04','']])
        profile=profile_file(self.conn,path,1)
        quantiles=profile['columns']['dcoilwtico']['numeric']['quantiles']
        self.assertEqual(quantiles['0.25'],.5)
        self.assertAlmostEqual(quantiles['0.95'],1.9)
        self.assertEqual(profile['columns']['dcoilwtico']['invalid_for_recommended_type'],1)

    def test_negative_sales_and_promotions_are_measured_without_rewriting(self):
        path=self.write_csv('train.csv',[[1,'2014-01-01',1,'A',-2.5,-1]])
        before=checksum(path)
        profile=profile_file(self.conn,path)
        self.assertEqual(profile['columns']['sales']['numeric']['negative'],1)
        self.assertEqual(profile['columns']['onpromotion']['numeric']['negative'],1)
        self.assertEqual(profile['columns']['sales']['invalid_for_recommended_type'],0)
        self.assertEqual(checksum(path),before)

    def test_header_only_and_bad_header(self):
        path=self.write_csv('stores.csv',[])
        profile=profile_file(self.conn,path)
        self.assertEqual(profile['rows'],0)
        self.assertEqual(profile['duplicate_rows_excess'],0)
        self.assertEqual(profile['columns']['city']['cardinality'],0)
        bad=self.write_csv('oil.csv',[],header=['date','date'])
        with self.assertRaisesRegex(ValueError,'Cabecera'):
            profile_file(self.conn,bad)

    def test_empty_file_and_invalid_batch_size(self):
        path=self.root/'oil.csv';path.write_text('')
        with self.assertRaisesRegex(ValueError,'Cabecera'):
            profile_file(self.conn,path)
        with self.assertRaisesRegex(ValueError,'positivo'):
            profile_file(self.conn,path,0)

    def test_leap_month_complete_and_duplicate_calendar_rows(self):
        dates={f'2016-02-{day:02}' for day in range(1,30)}
        complete=month_status(date(2016,2,1),dates,58,2,58)
        self.assertEqual(complete['completeness'],'COMPLETE')
        self.assertEqual(complete['calendar_days'],29)
        duplicate=month_status(date(2016,2,1),dates,59,2,58)
        self.assertEqual(duplicate['completeness'],'INCOMPLETE')
        self.assertFalse(complete['released'])

    def test_missing_holiday_and_partial_final_month(self):
        dates={f'2014-12-{day:02}' for day in range(1,32)}-{'2014-12-25'}
        holiday=month_status(date(2014,12,1),dates,30,1,30)
        self.assertEqual(holiday['missing_dates'],['2014-12-25'])
        self.assertEqual(holiday['completeness'],'INCOMPLETE')
        final=month_status(date(2017,8,1),{f'2017-08-{d:02}' for d in range(1,16)},15,1,15)
        self.assertEqual(final['observed_end'],'2017-08-15')
        self.assertEqual(len(final['missing_dates']),16)

    def test_missing_files_are_reported_and_sources_unchanged(self):
        path=self.write_csv('stores.csv',[[1,'Quito','Pichincha','D',1]])
        before=checksum(path)
        result,manifest=analyze(self.root,self.conn,1)
        self.assertEqual(result['files']['train.csv']['status'],'faltante')
        self.assertIsNone(manifest['bootstrap'])
        self.assertFalse(manifest['release_performed'])
        self.assertEqual(checksum(path),before)
        report=render_report(result,manifest)
        self.assertIn('FALTANTE',report)
        json.dumps(result,allow_nan=False)

    def test_relationships_bootstrap_and_incremental_are_plan_only(self):
        self.write_csv('stores.csv',[[1,'Quito','Pichincha','D',1]])
        self.write_csv('train.csv',[[1,'2014-12-31',1,'A',2,0],[2,'2015-01-01',1,'A',0,0]])
        self.write_csv('test.csv',[[3,'2015-01-02',2,'B',1]])
        self.write_csv('sample_submission.csv',[[4,0]])
        self.write_csv('oil.csv',[['2014-12-31',''],['2015-01-01',50]])
        self.write_csv('transactions.csv',[['2015-01-01',1,1]])
        self.write_csv('holidays_events.csv',[
            ['2015-01-01','Holiday','National','Ecuador','A','False'],
            ['2015-01-01','Additional','Local','Quito','B','False']])
        result,manifest=analyze(self.root,self.conn,1)
        relations=result['relationships']
        self.assertEqual(relations['test.csv.orphan_store_rows'],1)
        self.assertEqual(relations['test.unknown_families'],1)
        self.assertEqual(relations['test.ids_missing_submission'],1)
        self.assertEqual(relations['submission.ids_missing_test'],1)
        self.assertEqual(relations['train.positive_store_days_missing_transactions'],1)
        self.assertEqual(relations['oil.train_days_with_null'],1)
        self.assertEqual(len(relations['holidays.multi_event_dates']),1)
        self.assertEqual(manifest['bootstrap']['rows'],1)
        self.assertEqual(manifest['incremental_batches'][0]['batch_id'],'2015-01')
        self.assertFalse(manifest['incremental_batches'][0]['released'])
        self.assertIsNone(manifest['historical_cutoff'])
        self.assertEqual(result['sales_coverage']['observed_series'],1)
        self.assertIn('2015-01',render_report(result,manifest))

    def test_invalid_sales_key_prevents_false_coverage_certification(self):
        self.write_csv('train.csv',[[1,'bad-date','invalid','A','NaN',-1]])
        result,manifest=analyze(self.root,self.conn,1)
        self.assertNotIn('first_date',result['sales_coverage'])
        self.assertIsNone(manifest['bootstrap'])
        self.assertIn('no se certifica',result['sales_coverage']['status'])
        self.assertIn('No se certifica cobertura',render_report(result,manifest))

    def test_mismatched_auxiliary_schema_does_not_break_sales_coverage(self):
        self.write_csv('train.csv',[[1,'2014-12-31',1,'A',1,0]])
        self.write_csv('transactions.csv',[[1]],header=['wrong_column'])
        result,manifest=analyze(self.root,self.conn,1)
        self.assertFalse(result['files']['transactions.csv']['schema_matches'])
        self.assertEqual(result['sales_coverage']['first_date'],'2014-12-31')
        self.assertEqual(manifest['bootstrap']['rows'],1)

    def test_all_null_numeric_values_do_not_crash_report(self):
        self.write_csv('train.csv',[[1,'2014-12-31',1,'A','','']])
        result,manifest=analyze(self.root,self.conn,1)
        self.assertEqual(result['files']['train.csv']['columns']['sales']['nulls'],1)
        self.assertIn('No hay suficientes valores numéricos',render_report(result,manifest))

    def test_month_distinguishes_calendar_and_observed_grid(self):
        dates={f'2015-12-{d:02}' for d in range(1,32)}-{'2015-12-25'}
        month=month_status(date(2015,12,1),dates,60,2,60)
        self.assertFalse(month['calendar_complete'])
        self.assertTrue(month['observed_grid_complete'])
        self.assertEqual(month['missing_expected_rows'],2)
        self.assertEqual(month['duplicate_key_rows'],0)

    def test_reject_output_inside_source_including_symlink(self):
        source=self.root/'source';source.mkdir()
        for output in [source,source/'reports']:
            with self.assertRaisesRegex(ValueError,'SOURCE'):
                safe_output(source,output)
        alias=self.root/'alias';alias.symlink_to(source,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'SOURCE'):
            safe_output(source,alias)
        output=self.root/'docs';output.mkdir()
        (output/'DATA_PROFILING.json').symlink_to(source/'original.csv')
        with self.assertRaisesRegex(ValueError,'SOURCE'):
            safe_output(source,output)

    def test_detect_source_mutation_between_checksums(self):
        path=self.write_csv('stores.csv',[[1,'Quito','Pichincha','D',1]])
        with patch('retailops_profiling.core.checksum',side_effect=['before','after']):
            with self.assertRaisesRegex(RuntimeError,'cambió'):
                profile_file(self.conn,path)


if __name__=='__main__':
    unittest.main()
