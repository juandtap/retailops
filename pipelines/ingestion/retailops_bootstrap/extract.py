"""Único módulo que abre SOURCE. Preserva bytes RAW y ordinales originales."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pyarrow as pa
import pyarrow.parquet as pq

from retailops_profiling.core import SCHEMAS

FILES={'stores':'stores.csv','sales':'train.csv','holidays_events':'holidays_events.csv',
       'oil_prices':'oil.csv','store_transactions':'transactions.csv'}
FIELDS={
 'stores':[('store_nbr',pa.int16()),('city',pa.string()),('state',pa.string()),('store_type',pa.string()),('cluster',pa.int16()),('known_from',pa.date32()),('availability_evidence',pa.string())],
 'families':[('family',pa.string()),('known_from',pa.date32()),('availability_evidence',pa.string())],
 'sales':[('date',pa.date32()),('store_nbr',pa.int16()),('family',pa.string()),('source_id',pa.int64()),('sales',pa.decimal128(38,18)),('onpromotion',pa.int32())],
 'holidays_events':[('event_id',pa.string()),('date',pa.date32()),('event_type',pa.string()),('locale',pa.string()),('locale_name',pa.string()),('description',pa.string()),('transferred',pa.bool_()),('known_from',pa.date32()),('availability_evidence',pa.string())],
 'oil_prices':[('date',pa.date32()),('dcoilwtico',pa.decimal128(38,18)),('known_from',pa.date32()),('availability_evidence',pa.string())],
 'store_transactions':[('date',pa.date32()),('store_nbr',pa.int16()),('transactions',pa.int32())],
 'observation_gaps':[('date',pa.date32()),('entity',pa.string()),('scope_key',pa.string()),('reason',pa.string())]}
TRACE=[('batch_id',pa.string()),('source_sha256',pa.string()),('source_row_number',pa.int64()),('ingested_at',pa.timestamp('us',tz='UTC'))]

class ConflictError(RuntimeError):
    """Conflicto que nunca se resuelve sobrescribiendo datos."""


def sha256(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_sources(source,inventory):
    for entry in inventory:
        if sha256(Path(source)/entry['file'])!=entry['sha256']:
            raise ValueError('SHA-256 de SOURCE incorrecto: '+entry['file'])


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def schema(entity):
    nullable={'known_from','availability_evidence','dcoilwtico'}
    if entity=='observation_gaps':nullable.add('source_row_number')
    return pa.schema([pa.field(name,kind,nullable=name in nullable) for name,kind in FIELDS[entity]+TRACE+[('source_file',pa.string()),('contract_version',pa.int16())]],metadata={b'retailops.contract':b'bootstrap-v1'})


class CapturedLines:
    def __init__(self,stream):self.stream=stream;self.lines=[]
    def __iter__(self):return self
    def __next__(self):
        line=next(self.stream);self.lines.append(line);return line
    def take(self):
        value=''.join(self.lines).encode('utf-8');self.lines.clear();return value


def source_records(path):
    with path.open(encoding='utf-8',newline='') as stream:
        captured=CapturedLines(stream);reader=csv.reader(captured,strict=True)
        header=next(reader);header_bytes=captured.take()
        if header!=list(SCHEMAS[path.name]):raise ValueError('Cabecera incompatible: '+path.name)
        for ordinal,values in enumerate(reader,1):
            raw=captured.take()
            if len(values)!=len(header):raise ValueError('Fila malformada: '+path.name)
            yield ordinal,dict(zip(header,values)),raw,header_bytes


def decimal_value(value,nullable=False):
    if value=='' and nullable:return None
    number=Decimal(value)
    if not number.is_finite() or number<0:raise ValueError('Número negativo o no finito')
    if -number.as_tuple().exponent>18:raise ValueError('Escala decimal excede contrato; no truncar')
    return number


def convert(entity,row,ordinal,source_hash):
    if entity=='sales':return {'date':date.fromisoformat(row['date']),'store_nbr':int(row['store_nbr']),'family':row['family'],'source_id':int(row['id']),'sales':decimal_value(row['sales']),'onpromotion':int(row['onpromotion'])}
    if entity=='stores':return {'store_nbr':int(row['store_nbr']),'city':row['city'],'state':row['state'],'store_type':row['type'],'cluster':int(row['cluster']),'known_from':None,'availability_evidence':None}
    if entity=='store_transactions':return {'date':date.fromisoformat(row['date']),'store_nbr':int(row['store_nbr']),'transactions':int(row['transactions'])}
    if entity=='oil_prices':return {'date':date.fromisoformat(row['date']),'dcoilwtico':decimal_value(row['dcoilwtico'],True),'known_from':None,'availability_evidence':None}
    if entity=='holidays_events':
        if row['transferred'] not in ('True','False'):raise ValueError('Booleano inválido')
        return {'event_id':str(uuid5(NAMESPACE_URL,f'{source_hash}:{ordinal}')),'date':date.fromisoformat(row['date']),'event_type':row['type'],'locale':row['locale'],'locale_name':row['locale_name'],'description':row['description'],'transferred':row['transferred']=='True','known_from':None,'availability_evidence':None}
    raise ValueError(entity)


def validate_coverage(contract,daily,series,stores,families):
    start,end=map(date.fromisoformat,(contract['period_start'],contract['period_end']))
    days={(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)}
    if set(daily)-days:raise ValueError('Observaciones fuera del período')
    if days-set(daily)!=set(contract['accepted_missing_dates']):raise ValueError('Ausencias no aceptadas por contrato')
    if sum(daily.values())!=contract['expected_sales']:raise ValueError('Conteo de ventas incorrecto')
    if len(stores)!=contract['expected_stores'] or len(families)!=contract['expected_families']:raise ValueError('Dimensiones de ventas incorrectas')
    expected=len(stores)*len(families)
    if any(n!=expected for n in daily.values()) or any(n!=len(daily) for n in series.values()) or len(series)!=expected:
        raise ValueError('Cuadrícula incompleta; se requieren también claves únicas en Silver')


def prepare(source,workspace,contract,inventory,ingested_at):
    source,workspace=Path(source).resolve(),Path(workspace).resolve()
    if workspace==source or source in workspace.parents:raise ValueError('Workspace dentro de SOURCE')
    source_hashes={entry['file']:entry for entry in inventory}
    for filename,entry in source_hashes.items():
        if sha256(source/filename)!=entry['sha256']:raise ValueError('SHA-256 de SOURCE incorrecto: '+filename)
    workspace.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(workspace,0o700)
    # Archivos incompletos de un proceso anterior no se usan como evidencia.
    staging=workspace/('attempt-'+os.urandom(6).hex());staging.mkdir(mode=0o700)
    stamp=datetime.fromisoformat(ingested_at).astimezone(timezone.utc)
    start,end=map(date.fromisoformat,(contract['period_start'],contract['period_end']))
    pending=0
    totals={'sales_sum':Decimal(0),'onpromotion_sum':0,'sales_zero':0,'sales_fractional':0}
    handles={};writers={};buffers={};counts=Counter();part_counts=Counter();daily=Counter();series=Counter();stores=set();families={}
    def add(entity,partition,row,ordinal,source_hash,raw=None,header=None):
        nonlocal pending
        key=(entity,partition);counts[entity]+=1;part_counts[key]+=1
        if key not in writers:
            folder=staging/entity/partition;folder.mkdir(parents=True)
            writers[key]=pq.ParquetWriter(folder/'bronze.parquet',schema(entity),compression='snappy',version='2.6')
            buffers[key]=[]
            if raw is not None:
                handles[key]=(folder/'raw.csv').open('wb');handles[key].write(header)
        if raw is not None:handles[key].write(raw)
        row={**row,'batch_id':contract['batch_id'],'source_sha256':source_hash,'source_row_number':ordinal,'ingested_at':stamp,'source_file':FILES.get(entity,'train.csv'),'contract_version':1}
        buffers[key].append(row)
        pending+=1
        if pending>=contract['row_group_size']:
            for current,buffer in buffers.items():
                if buffer: writers[current].write_table(pa.Table.from_pylist(buffer,schema=schema(current[0])));buffer.clear()
            pending=0
    try:
        for entity,filename in FILES.items():
            original_hash=source_hashes[filename]['sha256']
            for ordinal,row,raw,header in source_records(source/filename):
                if entity!='stores':
                    observed=date.fromisoformat(row['date'])
                    if not start<=observed<=end:continue
                    partition=f'year={observed.year}/month={observed.month:02}'
                else:partition='snapshot=undated'
                typed=convert(entity,row,ordinal,original_hash)
                if entity=='sales':
                    if typed['onpromotion']<0:raise ValueError('Promoción negativa')
                    with localcontext() as ctx:
                        ctx.prec=50;totals['sales_sum']+=typed['sales']
                    totals['onpromotion_sum']+=typed['onpromotion']
                    totals['sales_zero']+=typed['sales']==0
                    totals['sales_fractional']+=typed['sales']!=typed['sales'].to_integral_value()
                    day=typed['date'].isoformat();daily[day]+=1;stores.add(typed['store_nbr']);series[(typed['store_nbr'],typed['family'])]+=1
                    families.setdefault(typed['family'],ordinal)
                add(entity,partition,typed,ordinal,original_hash,raw,header)
        validate_coverage(contract,daily,series,stores,families)
        if counts['stores']!=contract['expected_stores']:raise ValueError('Número de tiendas auxiliares incorrecto')
        train_hash=source_hashes['train.csv']['sha256']
        for family,ordinal in sorted(families.items()):
            add('families','snapshot=observed-identifiers',{'family':family,'known_from':None,'availability_evidence':None},ordinal,train_hash)
        for missing in contract['accepted_missing_dates']:
            d=date.fromisoformat(missing)
            add('observation_gaps',f'year={d.year}/month={d.month:02}',{'date':d,'entity':'sales','scope_key':'ALL_STORES_ALL_FAMILIES','reason':'NOT_IN_SOURCE'},None,train_hash)
    finally:
        for key,writer in writers.items():
            if buffers[key]:writer.write_table(pa.Table.from_pylist(buffers[key],schema=schema(key[0])))
            writer.close()
        for stream in handles.values():stream.close()
    objects=[]
    for entity,partition in sorted(writers):
        folder=staging/entity/partition
        for layer,filename in [('RAW','raw.csv'),('BRONZE','bronze.parquet')]:
            path=folder/filename
            if not path.exists():continue # Dimensiones derivadas y huecos: solo BRONZE, no se inventa RAW.
            digest=sha256(path);suffix='csv' if layer=='RAW' else 'parquet'
            key=f'{layer.lower()}/{entity}/{partition}/batch={contract["batch_id"]}/{digest}.{suffix}'
            original=FILES.get(entity,'train.csv')
            objects.append({'object_key':key,'entity':entity,'layer':layer,'sha256':digest,'source_sha256':source_hashes[original]['sha256'],
                            'size_bytes':path.stat().st_size,'row_count':part_counts[(entity,partition)],
                            'publishable':entity in contract['s3_publishable_entities'],'local_path':str(path.relative_to(workspace))})
    for filename,entry in source_hashes.items():
        if sha256(source/filename)!=entry['sha256']:raise ValueError('SOURCE cambió durante extracción')
    result={'batch_id':contract['batch_id'],'contract_sha256':canonical_hash(contract),'ingested_at':ingested_at,
            'counts':dict(sorted(counts.items())),'totals':{k:str(v) if isinstance(v,Decimal) else v for k,v in totals.items()},'monthly_sales':{key:sum(n for d,n in daily.items() if d.startswith(key)) for key in sorted({d[:7] for d in daily})},
            'sources':[source_hashes[n] for n in FILES.values()], 'objects':objects}
    result['inventory_sha256']=canonical_hash([{k:v for k,v in obj.items() if k!='local_path'} for obj in objects])
    # El manifiesto del workspace se publica atómicamente tras toda validación.
    target=workspace/'prepared.json';tmp=workspace/('prepared-'+os.urandom(6).hex()+'.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');tmp.replace(target)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('source','workspace','contract','inventory','ingested-at'):parser.add_argument('--'+arg,required=True)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    if args.verify_only:
        verify_sources(args.source,json.loads(Path(args.inventory).read_text()))
        print('Siete hashes de SOURCE verificados; sin extracción repetida.')
        return
    result=prepare(args.source,args.workspace,json.loads(Path(args.contract).read_text()),json.loads(Path(args.inventory).read_text()),args.ingested_at)
    print(json.dumps({'batch_id':result['batch_id'],'counts':result['counts'],'objects':len(result['objects'])}))

if __name__=='__main__':main()
