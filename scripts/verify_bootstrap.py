"""Evidencia del bootstrap real y reinicio conservador opcional; no ingiere datos."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipelines/ingestion'))
from retailops_bootstrap.extract import canonical_hash,sha256
from retailops_bootstrap.pipeline import validate_silver,verify_inventory,objects
from retailops_bootstrap.storage import Settings,QUARANTINE,RELEASED
import data_infra


def collect(settings,workspace,contract):
    prepared=json.loads((workspace/'prepared.json').read_text())
    batch=contract['batch_id']
    with settings.db('releaser') as conn:
        counts=validate_silver(conn,prepared,contract)
        batch_record=conn.execute('SELECT * FROM control.batches WHERE batch_id=%s',(batch,)).fetchone()
        sources=conn.execute('SELECT filename,sha256,size_bytes FROM control.source_files ORDER BY filename').fetchall()
        publication=conn.execute('SELECT * FROM control.publications WHERE batch_id=%s',(batch,)).fetchone()
        historical=conn.execute('SELECT * FROM control.historical_state').fetchone()
        runs=conn.execute('SELECT run_id,status,processed_rows,error_code,started_at,finished_at FROM control.ingestion_runs WHERE batch_id=%s ORDER BY requested_at',(batch,)).fetchall()
        inventory=objects(conn,batch)
        if publication['status']!='COMPLETE' or historical['released_through'].isoformat()!=contract['period_end'] or historical['last_batch_id']!=batch:
            raise ValueError('Bootstrap sin finalización/corte esperado')
        if conn.execute("SELECT count(*) n FROM control.batches WHERE kind='MONTHLY' AND state='RELEASED'").fetchone()['n']:
            raise ValueError('Se liberó un lote mensual')
        uniqueness=conn.execute('SELECT count(*) n,count(DISTINCT (date,store_nbr,family)) unique_keys,min(date) first_date,max(date) last_date FROM silver.sales').fetchone()
        if uniqueness['n']!=uniqueness['unique_keys'] or uniqueness['n']!=contract['expected_sales']:raise ValueError('Granularidad o conteos inválidos')
        aux={}
        for entity in ['stores','families','holidays_events','oil_prices']:
            from psycopg import sql
            aux[entity]=conn.execute(sql.SQL('SELECT count(*) n,count(known_from) with_known_from,count(availability_evidence) with_evidence FROM silver.{}').format(sql.Identifier(entity))).fetchone()
        verify_inventory(settings,conn,batch,True)
    trainer=settings.s3('trainer');released=settings.s3('releaser')
    from minio.error import S3Error
    from retailops_bootstrap.storage import verify_object
    restricted=next(o for o in inventory if not o['publishable'])
    try:
        response=trainer.get_object(QUARANTINE,restricted['object_key'])
    except S3Error as exc:
        if exc.code!='AccessDenied':raise
    else:
        response.close();response.release_conn();raise ValueError('Entrenador accedió a auxiliar restringido')
    readable=next(o for o in inventory if o['publishable'])
    verify_object(trainer,RELEASED,readable['object_key'],readable['sha256'],readable['size_bytes'],readable['released_version'])
    actual_keys={o.object_name for o in released.list_objects(RELEASED,recursive=True)}
    expected={o['object_key'] for o in inventory if o['publishable']}
    if actual_keys!=expected:raise ValueError('Released contiene objetos ajenos al inventario autorizado')
    with settings.db('trainer') as conn:
        visible=conn.execute('SELECT count(*) n,min(date) first_date,max(date) last_date FROM training.sales').fetchone()
        if visible['n']!=contract['expected_sales'] or visible['last_date'].isoformat()>contract['period_end']:raise ValueError('Datos visibles incompatibles con corte')
        visible_aux={}
        for entity in ['stores','families','holidays_events','oil_prices','store_transactions','observation_gaps']:
            from psycopg import sql
            visible_aux[entity]=conn.execute(sql.SQL('SELECT count(*) n FROM training.{}').format(sql.Identifier(entity))).fetchone()['n']
    execution=json.loads((workspace/'last_execution.json').read_text())
    return {'batch_id':batch,'counts_silver':counts,'sales_granularity':uniqueness,'auxiliary_availability':aux,
       'visible_training_sales':visible,'visible_training_auxiliaries':visible_aux,
       'batch':batch_record,'registered_sources':sources,'trainer_s3_permissions_verified':True,'publication':publication,'historical_state':historical,'runs':runs,
       'inventory':inventory,'objects_quarantine':len(inventory),'objects_released':len(expected),
       'initial_execution_metrics':json.loads((workspace/'first_execution.json').read_text()) if (workspace/'first_execution.json').exists() else execution,'last_execution_metrics':execution,'monthly_sales':prepared['monthly_sales'],'totals':prepared['totals']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--restart',action='store_true');args=parser.parse_args()
    settings=Settings.project(ROOT);settings.assert_environment()
    contract=json.loads((ROOT/'contracts/bootstrap-v1.json').read_text())
    workspace=ROOT/'.local/bootstrap'/contract['batch_id']
    initial=collect(settings,workspace,contract)
    if args.restart:
        data_infra.compose('stop','postgres','minio')
        data_infra.compose('up','-d','--wait','--wait-timeout','120','postgres','minio')
        after=collect(settings,workspace,contract)
        def fingerprint(data):return canonical_hash({k:data[k] for k in ['counts_silver','monthly_sales','totals']}),[(o['object_key'],o['quarantine_version'],o['released_version']) for o in data['inventory']],data['historical_state']
        if fingerprint(initial)!=fingerprint(after):raise ValueError('Datos/versiones/corte cambiaron al reiniciar')
        initial=after
    prepared=json.loads((workspace/'prepared.json').read_text())
    subprocess.run([sys.executable,'-m','retailops_bootstrap.extract','--verify-only','--source',str(ROOT/'data/source/favorita'),'--workspace',str(workspace),'--contract',str(ROOT/'contracts/bootstrap-v1.json'),'--inventory',str(ROOT/'docs/DATA_INVENTORY.json'),'--ingested-at',prepared['ingested_at']],cwd=ROOT/'pipelines/ingestion',check=True)
    plan=json.loads((ROOT/'docs/DATA_BATCH_MANIFEST.json').read_text())
    if plan['release_performed'] or plan['historical_cutoff'] is not None or any(m['released'] for m in plan['incremental_batches']):raise ValueError('Se alteró el plan original')
    initial.update({'checked_at':datetime.now(ZoneInfo('America/Guayaquil')).isoformat(),'persistence_restart_verified':args.restart,
                    'source_hashes_verified':True,'planning_manifest_sha256':sha256(ROOT/'docs/DATA_BATCH_MANIFEST.json'),
                    'unreleased_incremental_plan_batches':len(plan['incremental_batches'])})
    (ROOT/'docs/BOOTSTRAP_EVIDENCE.json').write_text(json.dumps(initial,default=str,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:initial[k] for k in ['counts_silver','objects_quarantine','objects_released','persistence_restart_verified','source_hashes_verified']},indent=2))

if __name__=='__main__':main()
