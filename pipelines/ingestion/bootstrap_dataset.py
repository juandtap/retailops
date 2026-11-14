"""Operador del único bootstrap autorizado: no ofrece ingestas mensuales."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

from retailops_bootstrap.extract import canonical_hash, sha256
from retailops_bootstrap.pipeline import execute
from retailops_bootstrap.storage import Settings

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='Ejecuta o verifica idempotentemente el bootstrap autorizado')
    args=parser.parse_args()
    if not args.execute:parser.error('Se requiere --execute para esta operación de almacenamiento')
    settings=Settings.project(ROOT);settings.assert_environment()
    contract=json.loads((ROOT/'contracts/bootstrap-v1.json').read_text())
    workspace=ROOT/'.local/bootstrap'/contract['batch_id'];workspace.mkdir(parents=True,exist_ok=True)
    def prepare_callback(conn):
        # Extraer en un proceso separado. Loader/publicador solo reciben el workspace seleccionado.
        publication=conn.execute('SELECT ingested_at FROM control.publications WHERE batch_id=%s',(contract['batch_id'],)).fetchone()
        stamp=publication['ingested_at'].isoformat() if publication else datetime.now(timezone.utc).isoformat()
        prepared=workspace/'prepared.json'
        if prepared.exists():
            existing=json.loads(prepared.read_text())
            if existing['contract_sha256']!=canonical_hash(contract):raise ValueError('Contrato del workspace cambió')
            stamp=existing['ingested_at']
            # Verificar originales también en reejecución, mediante el extractor y sin volver a transformarlos.
        command=[sys.executable,'-m','retailops_bootstrap.extract','--source',str(ROOT/'data/source/favorita'),'--workspace',str(workspace),
                  '--contract',str(ROOT/'contracts/bootstrap-v1.json'),'--inventory',str(ROOT/'docs/DATA_INVENTORY.json'),'--ingested-at',stamp]
        if prepared.exists():command.append('--verify-only')
        subprocess.run(command,cwd=Path(__file__).parent,check=True)
    started=time.monotonic()
    result=execute(settings,workspace,contract,prepare_callback=prepare_callback)
    result['duration_seconds']=round(time.monotonic()-started,3)
    result['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result['extractor_peak_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if not (workspace/'first_execution.json').exists():
        (workspace/'first_execution.json').write_text(json.dumps(result,indent=2)+'\n')
    (workspace/'last_execution.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
