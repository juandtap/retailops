"""Materialización mensual transaccional, bloqueada y sin DDL/administración."""
import calendar
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import resource
import time
import psycopg
from .query import QUERY,COLUMNS,LABEL_QUERY

ROOT=Path(__file__).resolve().parents[3]

def connect(role='ingestor',database=None):
    if role not in ('ingestor','trainer'):raise ValueError('Rol no autorizado')
    secret=ROOT/'.local/secrets'/f'pg_{role}_password'
    if secret.is_symlink() or secret.stat().st_mode & 0o077:raise ValueError('Secreto inseguro')
    return psycopg.connect(host='127.0.0.1',port=int(os.environ.get('POSTGRES_PORT','5432')),
        dbname=database or os.environ.get('POSTGRES_DB','retailops'),user='retailops_'+role,
        password=secret.read_text().strip(),connect_timeout=5,
        options='-c statement_timeout=300000 -c lock_timeout=5000 -c work_mem=16MB')

def code_hash():
    digest=hashlib.sha256()
    for name in ('query.py','pipeline.py'):
        digest.update((Path(__file__).parent/name).read_bytes())
    return digest.hexdigest()

def state(conn):
    if conn.execute('SELECT control.require_gold_snapshot()').fetchone()[0]!=date(2014,12,31):
        raise ValueError('Estado histórico incompatible; no materializar')

def materialize():
    started=time.monotonic();blocks=[]
    with connect() as conn:
        if not conn.execute('SELECT pg_try_advisory_lock(729130031)').fetchone()[0]:
            raise ValueError('Otra ingesta/publicación/GOLD incompatible está activa')
        conn.commit()
        for year in (2013,2014):
            for month in range(1,13):
                start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
                params={'start':start,'end':end}
                t=time.monotonic()
                with conn.transaction():
                    state(conn)
                    old=conn.execute('SELECT code_sha256 FROM gold.materializations WHERE feature_version=%s AND historical_cutoff=%s AND issue_start=%s',('sales-pit-v1',date(2014,12,31),start)).fetchone()
                    if old and old[0]!=code_hash():raise ValueError('Conflicto de código: nueva versión requerida')
                    # EXCEPT bidireccional comprueba todos los valores, incluidos NULL; no oculta conflictos.
                    if old:
                        mismatch=conn.execute('WITH expected AS ('+QUERY+'''), actual AS (
                         SELECT '''+COLUMNS+''' FROM gold.features WHERE issue_date BETWEEN %(start)s AND %(end)s)
                         SELECT EXISTS((SELECT * FROM expected EXCEPT SELECT * FROM actual)
                         UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected))''',params).fetchone()[0]
                        if mismatch:raise ValueError('Conflicto de contenido GOLD')
                    else:
                        conn.execute('INSERT INTO gold.features ('+COLUMNS+') '+QUERY,params)
                        conn.execute('INSERT INTO gold.labels '+LABEL_QUERY,params)
                    label_mismatch=conn.execute('WITH expected AS ('+LABEL_QUERY+'''), actual AS (
                     SELECT * FROM gold.labels WHERE target_date BETWEEN %(start)s AND %(end)s)
                     SELECT EXISTS((SELECT * FROM expected EXCEPT SELECT * FROM actual)
                     UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected))''',params).fetchone()[0]
                    if label_mismatch:raise ValueError('Conflicto de etiquetas')
                    counts=conn.execute('''SELECT (SELECT count(*) FROM gold.features WHERE issue_date BETWEEN %(start)s AND %(end)s),
                    (SELECT count(*) FROM gold.labels WHERE target_date BETWEEN %(start)s AND %(end)s)''',params).fetchone()
                    if not old:
                        conn.execute('INSERT INTO gold.materializations(feature_version,historical_cutoff,issue_start,issue_end,code_sha256,feature_rows,label_rows) VALUES(%s,%s,%s,%s,%s,%s,%s)',('sales-pit-v1',date(2014,12,31),start,end,code_hash(),*counts))
                blocks.append({'start':str(start),'end':str(end),'features':counts[0],'labels':counts[1],'reused':bool(old),'seconds':round(time.monotonic()-t,3)})
                print(json.dumps(blocks[-1]),flush=True)
        with conn.transaction():state(conn)
    evidence={'version':'sales-pit-v1','historical_cutoff':'2014-12-31','blocks':blocks,
      'feature_rows':sum(b['features'] for b in blocks),'label_rows':sum(b['labels'] for b in blocks),
      'seconds':round(time.monotonic()-started,3),'client_max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      'code_sha256':code_hash(),'status':'SUCCEEDED'}
    output=ROOT/'docs/GOLD_EXECUTION.json';output.write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence
