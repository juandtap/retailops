"""Verifica el contrato de diseño contra el perfil medido y el plan sin liberación."""
import json
import re
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def validate(contract, profile, manifest):
    if contract['contract_version']!=1:raise ValueError('Versión de contrato desconocida')
    if manifest.get('purpose')!='PLAN_ONLY' or manifest.get('release_performed') is not False or manifest.get('historical_cutoff') is not None:
        raise ValueError('El manifiesto ya no representa un plan sin liberación')
    batches=[manifest['bootstrap'],*manifest['incremental_batches']]
    previous=None
    identifiers=set()
    for batch in batches:
        if not batch or batch.get('released') is not False:raise ValueError('Lote ausente o liberado')
        start,end=date.fromisoformat(batch['period_start']),date.fromisoformat(batch['period_end'])
        if start>end or (previous is not None and start<=previous):raise ValueError('Períodos invertidos, solapados o desordenados')
        if previous is not None and (start-previous).days!=1:raise ValueError('Plan con intervalo no descrito')
        if batch['batch_id'] in identifiers:raise ValueError('Identificador de lote repetido')
        if type(batch['rows']) is not int or batch['rows']<0:raise ValueError('Recuento inválido')
        previous=end;identifiers.add(batch['batch_id'])
    for filename,schema in contract['source']['files'].items():
        file=profile['files'].get(filename)
        if not file or file['status']!='analizado':raise ValueError('Fuente faltante: '+filename)
        if not re.fullmatch('[0-9a-f]{64}',file['sha256']):raise ValueError('Checksum inválido')
        if list(file['columns'])!=[column['name'] for column in schema['columns']]:raise ValueError('Cabecera incompatible: '+filename)
        if file['malformed_rows'] or file['duplicate_rows_excess']:raise ValueError('Filas incompatibles: '+filename)
        for column in schema['columns']:
            measured=file['columns'][column['name']]
            if measured['invalid_for_recommended_type'] or (measured['nulls'] and not column['nullable']):raise ValueError('Tipo/nulabilidad incompatible: '+filename+'.'+column['name'])
    if manifest['source_sha256']!=profile['files']['train.csv']['sha256']:raise ValueError('Plan y fuente train incompatibles')
    if profile['files']['train.csv']['duplicate_keys_excess']:raise ValueError('Clave natural de ventas repetida')
    if sum(b['rows'] for b in batches)!=profile['files']['train.csv']['rows']:raise ValueError('Lotes no cubren el total de ventas')
    if (batches[0]['period_start'],batches[0]['period_end'])!=('2013-01-01','2014-12-31'):
        raise ValueError('Período de bootstrap incorrecto')
    measured={m['batch_id']:m for m in profile['sales_coverage']['months'] if m['batch_id']>='2015-01'}
    if [b['batch_id'] for b in manifest['incremental_batches']]!=list(measured):
        raise ValueError('Secuencia incremental incompatible con el perfil')
    for batch in manifest['incremental_batches']:
        expected=measured[batch['batch_id']]
        if any(batch[k]!=expected[k] for k in ('period_start','period_end','rows')):
            raise ValueError('Lote mensual incompatible con el perfil')


def main():
    contract=json.loads((ROOT/'contracts/data-storage-v1.json').read_text())
    profile=json.loads((ROOT/'docs/DATA_PROFILING.json').read_text())
    manifest=json.loads((ROOT/'docs/DATA_BATCH_MANIFEST.json').read_text())
    validate(contract,profile,manifest)
    print('Contrato v1 consistente con siete fuentes, esquema/nulos y plan; no libera ni transforma datos.')

if __name__=='__main__':main()
