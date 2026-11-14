"""Transacciones Silver e inventario recuperable. No abre archivos SOURCE."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pyarrow.parquet as pq

from .extract import ConflictError, FIELDS, TRACE, canonical_hash, schema, sha256
from .storage import QUARANTINE, RELEASED, copy_immutable, upload_immutable, verify_object

LOCK_KEY=729130031
ORDER=['stores','families','sales','holidays_events','oil_prices','store_transactions','observation_gaps']

class SimulatedFailure(RuntimeError):pass

@contextmanager
def exclusive(settings):
    with settings.db('ingestor') as conn:
        if not conn.execute('SELECT pg_try_advisory_lock(%s) AS locked',(LOCK_KEY,)).fetchone()['locked']:
            raise RuntimeError('Otra ingesta/publicación incompatible está activa')
        yield conn


def objects(conn,batch_id):
    return conn.execute('SELECT * FROM control.publication_objects WHERE batch_id=%s ORDER BY object_key',(batch_id,)).fetchall()


def validate_local(workspace,prepared):
    expected=canonical_hash([{k:v for k,v in obj.items() if k!='local_path'} for obj in prepared['objects']])
    if expected!=prepared['inventory_sha256']:raise ConflictError('Inventario local alterado')
    for obj in prepared['objects']:
        path=(workspace/obj['local_path']).resolve()
        if workspace.resolve() not in path.parents:raise ConflictError('Archivo fuera del workspace')
        if path.stat().st_size!=obj['size_bytes'] or sha256(path)!=obj['sha256']:raise ConflictError('Contenido local conflictivo')
        if obj['layer']=='BRONZE':
            parquet=pq.ParquetFile(path)
            if parquet.metadata.num_rows!=obj['row_count'] or not parquet.schema_arrow.equals(schema(obj['entity']),check_metadata=True):
                raise ConflictError('Esquema/conteo BRONZE incorrecto')


def register(conn,prepared,contract):
    batch=contract['batch_id']
    with conn.transaction():
        for source in prepared['sources']:
            conn.execute('INSERT INTO control.source_files(sha256,filename,size_bytes) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(source['sha256'],source['file'],source['bytes']))
            actual=conn.execute('SELECT filename,size_bytes FROM control.source_files WHERE sha256=%s',(source['sha256'],)).fetchone()
            if actual!={'filename':source['file'],'size_bytes':source['bytes']}:raise ConflictError('Procedencia conflictiva')
        conn.execute("INSERT INTO control.batches(batch_id,kind,entity,period_start,period_end,row_count) VALUES(%s,'BOOTSTRAP','sales',%s,%s,%s) ON CONFLICT(batch_id) DO NOTHING",(batch,contract['period_start'],contract['period_end'],contract['expected_sales']))
        existing=conn.execute('SELECT * FROM control.batches WHERE batch_id=%s',(batch,)).fetchone()
        if existing['period_start'].isoformat()!=contract['period_start'] or existing['period_end'].isoformat()!=contract['period_end'] or existing['row_count']!=contract['expected_sales']:
            raise ConflictError('Lote existente incompatible')
        conn.execute('INSERT INTO control.publications(batch_id,contract_sha256,ingested_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(batch,canonical_hash(contract),prepared['ingested_at']))
        publication=conn.execute('SELECT * FROM control.publications WHERE batch_id=%s',(batch,)).fetchone()
        if publication['ingested_at']!=datetime.fromisoformat(prepared['ingested_at']):raise ConflictError('Timestamp de procedencia incompatible')
        if publication['contract_sha256']!=prepared['contract_sha256'] or publication['contract_sha256']!=canonical_hash(contract):raise ConflictError('Contrato existente incompatible')
        if publication['inventory_sha256'] is not None and publication['inventory_sha256']!=prepared['inventory_sha256']:raise ConflictError('Inventario existente incompatible')
        if publication['status']=='STAGING':
            for source in prepared['sources']:
                conn.execute('INSERT INTO control.batch_sources VALUES(%s,%s) ON CONFLICT DO NOTHING',(batch,source['sha256']))
            for obj in prepared['objects']:
                conn.execute('''INSERT INTO control.publication_objects(batch_id,object_key,entity,layer,sha256,source_sha256,size_bytes,row_count,publishable)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(batch,*[obj[k] for k in ('object_key','entity','layer','sha256','source_sha256','size_bytes','row_count','publishable')]))
            conn.execute('UPDATE control.publications SET inventory_sha256=%s,expected_counts=%s,object_count=%s WHERE batch_id=%s',(prepared['inventory_sha256'],Jsonb(prepared['counts']),len(prepared['objects']),batch))
        actual=objects(conn,batch)
        expected={o['object_key']:o for o in prepared['objects']}
        if len(actual)!=len(expected):raise ConflictError('Número de objetos conflictivo')
        for item in actual:
            if any(item[k]!=expected[item['object_key']][k] for k in ('entity','layer','sha256','source_sha256','size_bytes','row_count','publishable')):
                raise ConflictError('Contenido declarado conflictivo')
    return publication


def validate_silver(conn,prepared,contract):
    batch=contract['batch_id']
    actual={entity:conn.execute(sql.SQL('SELECT count(*) AS n FROM silver.{} WHERE batch_id=%s').format(sql.Identifier(entity)),(batch,)).fetchone()['n'] for entity in ORDER}
    if actual!=prepared['counts']:raise ConflictError('Conteos SILVER incompatibles: '+str(actual))
    stats=conn.execute('''SELECT min(date) lo,max(date) hi,sum(sales) sales_sum,sum(onpromotion) onpromotion_sum,
        count(*) FILTER(WHERE sales=0) sales_zero,count(*) FILTER(WHERE sales<>trunc(sales)) sales_fractional
        FROM silver.sales WHERE batch_id=%s''',(batch,)).fetchone()
    if stats['lo']<date.fromisoformat(contract['period_start']) or stats['hi']>date.fromisoformat(contract['period_end']):raise ConflictError('Datos fuera del corte')
    for key,value in prepared['totals'].items():
        if Decimal(str(stats[key]))!=Decimal(str(value)):raise ConflictError('Totales/decimales SILVER alterados: '+key)
    monthly={r['period']:r['n'] for r in conn.execute("SELECT to_char(date,'YYYY-MM') period,count(*) n FROM silver.sales WHERE batch_id=%s GROUP BY 1",(batch,))}
    if monthly!=prepared['monthly_sales']:raise ConflictError('Conteos mensuales incorrectos')
    gaps=[r['date'].isoformat() for r in conn.execute("SELECT date FROM silver.observation_gaps WHERE batch_id=%s AND entity='sales' ORDER BY date",(batch,))]
    if gaps!=sorted(contract['accepted_missing_dates']):raise ConflictError('Ausencias no conservadas')
    return actual


def load_silver(conn,workspace,prepared,contract):
    batch=contract['batch_id']
    publication=conn.execute('SELECT * FROM control.publications WHERE batch_id=%s',(batch,)).fetchone()
    if publication['silver_loaded']:
        return validate_silver(conn,prepared,contract)
    with conn.transaction():
        # Una sola transacción: caída durante COPY no deja media carga.
        for entity in ORDER:
            if conn.execute(sql.SQL('SELECT count(*) n FROM silver.{} WHERE batch_id=%s').format(sql.Identifier(entity)),(batch,)).fetchone()['n']:
                raise ConflictError('Carga parcial inesperada; no sobrescribir')
            columns=[c for c,_ in FIELDS[entity]+TRACE]
            statement=sql.SQL('COPY silver.{} ({}) FROM STDIN').format(sql.Identifier(entity),sql.SQL(',').join(map(sql.Identifier,columns)))
            with conn.cursor().copy(statement) as writer:
                for obj in prepared['objects']:
                    if obj['layer']!='BRONZE' or obj['entity']!=entity:continue
                    for part in pq.ParquetFile(workspace/obj['local_path']).iter_batches(batch_size=32768):
                        for row in part.to_pylist():writer.write_row(tuple(row[c] for c in columns))
        validate_silver(conn,prepared,contract)
        conn.execute('UPDATE control.publications SET silver_loaded=true WHERE batch_id=%s',(batch,))


def verify_inventory(settings,conn,batch_id,require_published):
    s3=settings.s3('releaser')
    for item in objects(conn,batch_id):
        if not item['quarantine_version']:raise ConflictError('Objeto de cuarentena pendiente')
        version=verify_object(s3,QUARANTINE,item['object_key'],item['sha256'],item['size_bytes'],item['quarantine_version'])
        current=verify_object(s3,QUARANTINE,item['object_key'],item['sha256'],item['size_bytes'])
        if version!=current:raise ConflictError('Versión actual de cuarentena diferente de la autorizada')
        if item['publishable'] and require_published:
            if not item['released_version']:raise ConflictError('Publicación pendiente')
            version=verify_object(s3,RELEASED,item['object_key'],item['sha256'],item['size_bytes'],item['released_version'])
            current=verify_object(s3,RELEASED,item['object_key'],item['sha256'],item['size_bytes'])
            if version!=current:raise ConflictError('Versión released cambió')


def execute(settings,workspace,contract,*,failure=None,prepare_callback=None):
    workspace=Path(workspace)
    with exclusive(settings) as ingest:
        if prepare_callback:prepare_callback(ingest)
        prepared=json.loads((workspace/'prepared.json').read_text())
        validate_local(workspace,prepared)
        publication=register(ingest,prepared,contract)
        batch=contract['batch_id'];run_id=uuid4()
        ingest.execute("UPDATE control.ingestion_runs SET status='FAILED',finished_at=clock_timestamp(),error_code='INTERRUPTED' WHERE batch_id=%s AND status='RUNNING'",(batch,))
        ingest.execute("INSERT INTO control.ingestion_runs(run_id,batch_id,status,started_at) VALUES(%s,%s,'RUNNING',clock_timestamp())",(run_id,batch))
        try:
            with settings.db('releaser') as release:
                if publication['status']!='COMPLETE':
                    if publication['status']=='STAGING':
                        local={o['object_key']:o for o in prepared['objects']}
                        s3=settings.s3('ingestor')
                        for item in objects(ingest,batch):
                            version=upload_immutable(s3,QUARANTINE,item['object_key'],workspace/local[item['object_key']]['local_path'],item['sha256'],item['size_bytes'])
                            if item['quarantine_version'] and item['quarantine_version']!=version:raise ConflictError('Versión de cuarentena conflictiva')
                            if not item['quarantine_version']:
                                with ingest.transaction():
                                    ingest.execute('UPDATE control.publication_objects SET quarantine_version=%s WHERE batch_id=%s AND object_key=%s',(version,batch,item['object_key']))
                                    ingest.execute('INSERT INTO control.objects(bucket,object_key,version_id,batch_id,layer,sha256,size_bytes) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(QUARANTINE,item['object_key'],version,batch,item['layer'],item['sha256'],item['size_bytes']))
                        load_silver(ingest,workspace,prepared,contract)
                        verify_inventory(settings,release,batch,False)
                        if failure=='before-authorization':raise SimulatedFailure('Antes de autorización')
                        with release.transaction():
                            release.execute("UPDATE control.batches SET state='RELEASED',released_at=clock_timestamp() WHERE batch_id=%s",(batch,))
                            release.execute("UPDATE control.publications SET status='AUTHORIZED',authorized_at=clock_timestamp() WHERE batch_id=%s",(batch,))
                    validate_silver(release,prepared,contract)
                    if failure=='after-authorization':raise SimulatedFailure('Después de autorización, antes de copiar')
                    count=0
                    for item in objects(release,batch):
                        if not item['publishable']:continue
                        version=copy_immutable(settings.s3('releaser'),item)
                        if item['released_version'] and item['released_version']!=version:raise ConflictError('Versión released conflictiva')
                        if not item['released_version']:
                            if failure=='after-copy-before-record':raise SimulatedFailure('Copia S3 existente sin confirmación SQL')
                            with release.transaction():
                                release.execute('UPDATE control.publication_objects SET released_version=%s,published_at=clock_timestamp() WHERE batch_id=%s AND object_key=%s',(version,batch,item['object_key']))
                                release.execute('INSERT INTO control.objects(bucket,object_key,version_id,batch_id,layer,sha256,size_bytes) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(RELEASED,item['object_key'],version,batch,item['layer'],item['sha256'],item['size_bytes']))
                        count+=1
                        if failure=='partial' and count==1:raise SimulatedFailure('Publicación parcial')
                    verify_inventory(settings,release,batch,True)
                    with release.transaction():
                        release.execute("UPDATE control.publications SET status='COMPLETE',completed_at=clock_timestamp() WHERE batch_id=%s",(batch,))
                        release.execute('UPDATE control.historical_state SET released_through=%s,last_batch_id=%s,updated_at=clock_timestamp() WHERE singleton',(contract['period_end'],batch))
                else:
                    validate_silver(release,prepared,contract);verify_inventory(settings,release,batch,True)
                    state=release.execute('SELECT * FROM control.historical_state').fetchone()
                    if state['last_batch_id']!=batch or state['released_through'].isoformat()!=contract['period_end']:raise ConflictError('Corte incompatible con publicación completa')
            ingest.execute("UPDATE control.ingestion_runs SET status='SUCCEEDED',finished_at=clock_timestamp(),processed_rows=%s WHERE run_id=%s",(contract['expected_sales'],run_id))
            return {'batch_id':batch,'run_id':str(run_id),'status':'SUCCEEDED','idempotent':publication['status']=='COMPLETE','counts':prepared['counts'],'objects':len(prepared['objects'])}
        except Exception as exc:
            ingest.execute("UPDATE control.ingestion_runs SET status='FAILED',finished_at=clock_timestamp(),error_code=%s WHERE run_id=%s",(type(exc).__name__,run_id))
            raise
