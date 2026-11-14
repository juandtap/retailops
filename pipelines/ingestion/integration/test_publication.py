"""Integración real aislada: DB temporal propia y objetos con batch UUID, nunca volúmenes borrados."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'pipelines/ingestion'),str(ROOT/'pipelines/ingestion/tests'),str(ROOT/'scripts')]
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from minio.error import S3Error
from retailops_bootstrap.extract import ConflictError,prepare
from retailops_bootstrap.pipeline import execute,exclusive,objects,SimulatedFailure
from retailops_bootstrap.storage import Settings,QUARANTINE,RELEASED
from bootstrap_fixture import fixture,STAMP
import data_infra

@unittest.skipUnless(os.environ.get('RETAILOPS_INTEGRATION')=='1','Integración optativa: requiere servicios locales')
class PublicationIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.database='retailops_test_'+uuid4().hex
        self.settings=Settings.project(ROOT,self.database)
        self.batch='test-bootstrap-'+uuid4().hex
        self.contract,inventory=fixture(self.folder/'source',self.batch)
        self.workspace=self.folder/'workspace'
        self.prepared=prepare(self.folder/'source',self.workspace,self.contract,inventory,STAMP)
        self.admin=psycopg.connect(host='127.0.0.1',port=self.settings.pg_port,dbname='postgres',user='postgres',password=self.settings.secret('pg_admin_password'),autocommit=True)
        self.admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.database)))
        with psycopg.connect(host='127.0.0.1',port=self.settings.pg_port,dbname=self.database,user='postgres',password=self.settings.secret('pg_admin_password'),autocommit=True) as conn:
            conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(self.database)))
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO retailops_control_migrator,retailops_data_migrator,retailops_ingestor,retailops_releaser,retailops_trainer,retailops_api').format(sql.Identifier(self.database)))
            conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
            for schema,owner in [('control','retailops_control_migrator'),*[(s,'retailops_data_migrator') for s in ['data_meta','silver','gold','training']]]:
                conn.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION {}').format(sql.Identifier(schema),sql.Identifier(owner)))
        env={**os.environ,'DB_JDBC_URL':f'jdbc:postgresql://127.0.0.1:{self.settings.pg_port}/{self.database}','RETAILOPS_SECRETS_DIR':str(ROOT/'.local/secrets')}
        result=subprocess.run(['java','-jar',str(ROOT/'apps/api/target/api-0.0.1-SNAPSHOT.jar'),'--spring.profiles.active=storage','--spring.main.web-application-type=none'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError(result.stdout[-6000:])

    def tearDown(self):
        # Solo recursos creados por este test; no tablas/objetos de bootstrap ni volúmenes.
        root_client=__import__('minio').Minio(self.settings.minio_endpoint,access_key=self.settings.secret('minio_root_user'),secret_key=self.settings.secret('minio_root_password'),secure=False)
        for bucket in (QUARANTINE,RELEASED):
            for item in root_client.list_objects(bucket,recursive=True,include_version=True):
                if '/batch='+self.batch+'/' in item.object_name:
                    root_client.remove_object(bucket,item.object_name,version_id=item.version_id)
        if not self.database.startswith('retailops_test_'):raise AssertionError('No eliminar una DB ajena')
        self.admin.close()
        with psycopg.connect(host='127.0.0.1',port=self.settings.pg_port,dbname='postgres',user='postgres',password=self.settings.secret('pg_admin_password'),autocommit=True) as cleanup:
            cleanup.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(self.database)))
        self.temp.cleanup()

    def scalar(self,query,role='ingestor'):
        with self.settings.db(role) as conn:return next(iter(conn.execute(query).fetchone().values()))
    def trainer_rows(self):return self.scalar('SELECT count(*) FROM training.sales','trainer')
    def snapshot(self):
        with self.settings.db('ingestor') as conn:
            return [tuple(r[k] for k in ('object_key','quarantine_version','released_version')) for r in objects(conn,self.batch)]
    def test_01_success_idempotence_permissions_and_lock(self):
        with exclusive(self.settings):
            with self.assertRaisesRegex(RuntimeError,'incompatible'):execute(self.settings,self.workspace,self.contract)
        result=execute(self.settings,self.workspace,self.contract)
        self.assertEqual(result['status'],'SUCCEEDED');self.assertEqual(self.trainer_rows(),4)
        self.assertEqual(self.scalar('SELECT sales FROM silver.sales WHERE source_id=0'),__import__('decimal').Decimal('1.1250001'))
        self.assertEqual(self.scalar('SELECT sum(onpromotion) FROM silver.sales'),6)
        before=self.snapshot();again=execute(self.settings,self.workspace,self.contract)
        self.assertTrue(again['idempotent']);self.assertEqual(before,self.snapshot())
        self.assertEqual(self.scalar('SELECT count(*) FROM silver.sales'),4)
        self.assertEqual(self.scalar("SELECT count(*) FROM training.sales WHERE date>'2014-12-26'",'trainer'),0)
        self.assertEqual(self.scalar('SELECT count(*) FROM training.stores','trainer'),0)
        self.assertEqual(self.scalar('SELECT count(*) FROM training.oil_prices','trainer'),0)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):self.scalar('SELECT count(*) FROM silver.sales','trainer')
        obj=next(o for o in self.prepared['objects'] if not o['publishable'])
        with self.assertRaises(S3Error) as error:self.settings.s3('trainer').get_object(QUARANTINE,obj['object_key'])
        self.assertEqual(error.exception.code,'AccessDenied')
        published=next(o for o in self.prepared['objects'] if o['publishable'])
        response=self.settings.s3('trainer').get_object(RELEASED,published['object_key']);response.close();response.release_conn()
    def test_02_resume_authorization_partial_and_unrecorded_copy(self):
        for phase in ['before-authorization','after-authorization','after-copy-before-record','partial']:
            with self.subTest(phase=phase),self.assertRaises(SimulatedFailure):execute(self.settings,self.workspace,self.contract,failure=phase)
            self.assertEqual(self.trainer_rows(),0)
            self.assertEqual(self.scalar('SELECT released_through IS NULL FROM control.historical_state'),True)
            self.assertEqual(self.scalar("SELECT count(*) FROM control.ingestion_runs WHERE status='SUCCEEDED'"),0)
        with self.settings.db('ingestor') as conn:
            with self.assertRaises(psycopg.errors.CheckViolation):conn.execute("INSERT INTO control.batches(batch_id,kind,entity,period_start,period_end) VALUES('next','MONTHLY','sales','2015-01-01','2015-01-31')")
        result=execute(self.settings,self.workspace,self.contract)
        self.assertFalse(result['idempotent']);self.assertEqual(self.trainer_rows(),4)
        self.assertEqual(self.scalar("SELECT count(*) FROM control.ingestion_runs WHERE status='FAILED'"),4)
        self.assertEqual(self.scalar('SELECT count(*) FROM silver.sales'),4)
    def test_03_conflicting_s3_content_is_not_overwritten(self):
        with self.assertRaises(SimulatedFailure):execute(self.settings,self.workspace,self.contract,failure='after-authorization')
        obj=next(o for o in self.prepared['objects'] if o['publishable'])
        payload=b'conflict-do-not-overwrite'
        inserted=self.settings.s3('releaser').put_object(RELEASED,obj['object_key'],io.BytesIO(payload),len(payload))
        with self.assertRaises(ConflictError):execute(self.settings,self.workspace,self.contract)
        info=self.settings.s3('releaser').stat_object(RELEASED,obj['object_key']);self.assertEqual(info.version_id,inserted.version_id)
        self.assertEqual(self.trainer_rows(),0)
    def test_04_duplicate_natural_key_rolls_back_all_silver(self):
        # Duplicar una fila preservando los conteos contractuales debe fallar en el COPY/PK.
        import csv
        path=self.folder/'source/train.csv'
        with path.open(newline='') as stream:rows=list(csv.reader(stream))
        rows[2]=rows[1].copy();rows[2][0]='1'
        with path.open('w',newline='') as stream:csv.writer(stream).writerows(rows)
        # La cobertura por familia también detecta el problema antes de cargar: no relajar contrato.
        from retailops_bootstrap.extract import sha256
        inventory=[{'file':p.name,'sha256':sha256(p),'bytes':p.stat().st_size} for p in (self.folder/'source').iterdir()]
        with self.assertRaises(ValueError):prepare(self.folder/'source',self.folder/'bad',self.contract,inventory,STAMP)
        with self.assertRaises(SimulatedFailure):execute(self.settings,self.workspace,self.contract,failure='before-authorization')
        with self.settings.db('ingestor') as conn:
            with self.assertRaises(psycopg.errors.UniqueViolation):
                conn.execute('INSERT INTO silver.sales SELECT * FROM silver.sales WHERE source_id=0')
        self.assertEqual(self.scalar('SELECT count(*) FROM silver.sales'),4)
    def test_05_restart_preserves_completed_publication(self):
        execute(self.settings,self.workspace,self.contract)
        before=self.snapshot()
        data_infra.compose('stop','postgres','minio')
        data_infra.compose('up','-d','--wait','--wait-timeout','120','postgres','minio')
        self.assertEqual(self.trainer_rows(),4);self.assertEqual(before,self.snapshot())
        self.assertTrue(execute(self.settings,self.workspace,self.contract)['idempotent'])

if __name__=='__main__':unittest.main()
