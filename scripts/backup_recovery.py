"""Backup F5.4 privado y restauración exclusivamente en recursos nuevos y aislados."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import ipaddress
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from infra.backup.core import FORMAT,check_files,crypt,digest,file_inventory,mac,outside_repo,private_dir,safe_extract,verify_envelope,write_json

PG='retailops-data-postgres-1';MINIO='retailops-data-minio-1'
PYTHON_IMAGE='python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df'
DATABASES=['retailops','retailops_mlflow','retailops_airflow']


def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def run(args,**kw):return subprocess.run(args,check=True,stderr=subprocess.PIPE,**kw)
def output(args):return run(args,stdout=subprocess.PIPE).stdout.decode()
def inspect(name,kind='container'):return json.loads(output(['docker',kind,'inspect',name]))[0]
def secret(name):return (ROOT/'.local/secrets'/name).read_text().strip()
def pg_args(container,args,password_file,user='postgres'):
    return ['docker','exec','-i',container,'sh','-c','export PGPASSWORD="$(cat "$1")"; shift; exec "$@"','sh',password_file,*args]


def source_config():
    return {'host':'127.0.0.1','port':5432,'user':'postgres','password':secret('pg_admin_password')}


def fingerprint(config,mapping=None):
    import psycopg
    from psycopg import sql
    mapping=mapping or {name:name for name in DATABASES};result={}
    for logical,dbname in mapping.items():
        tables={}
        with psycopg.connect(**config,dbname=dbname,options='-c default_transaction_read_only=on -c statement_timeout=600000') as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            rows=conn.execute("SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' ORDER BY 1,2").fetchall()
            for schema,name,owner in rows:
                relation=sql.Identifier(schema,name)
                pk=conn.execute("SELECT a.attname FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum WHERE i.indrelid=%s::regclass AND i.indisprimary ORDER BY k.ord",(f'"{schema}"."{name}"',)).fetchall()
                ordering=sql.SQL(',').join(sql.Identifier(p[0]) for p in pk) if pk else sql.SQL('t::text COLLATE "C"')
                count=conn.execute(sql.SQL('SELECT count(*) FROM {}').format(relation)).fetchone()[0]
                h=hashlib.sha256()
                with conn.cursor().copy(sql.SQL('COPY (SELECT t.* FROM {} t ORDER BY {}) TO STDOUT (FORMAT BINARY)').format(relation,ordering)) as copy:
                    for block in copy:h.update(block)
                constraints=conn.execute("SELECT conname,contype,convalidated,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s::regclass ORDER BY conname",(f'"{schema}"."{name}"',)).fetchall()
                if any(not c[2] for c in constraints):raise ValueError('Constraint no validada: no aceptar recuperación completa')
                tables[f'{schema}.{name}']={'rows':count,'owner':owner,'binary_copy_sha256':h.hexdigest(),'constraints':constraints}
                print(f'Inventario {logical}.{schema}.{name}: {count} filas',flush=True)
            sequences=[]
            for schema,name in conn.execute("SELECT schemaname,sequencename FROM pg_sequences WHERE schemaname NOT LIKE 'pg_%' ORDER BY 1,2"):
                value=conn.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(schema,name))).fetchone()
                sequences.append([schema,name,*value])
            result[logical]={'tables':tables,'sequences':sequences}
            if logical=='retailops':
                result[logical]['state']={
                    'cutoff':conn.execute('SELECT released_through FROM control.historical_state').fetchone()[0].isoformat(),
                    'sales':list(conn.execute('SELECT count(*),min(date)::text,max(date)::text,sum(sales)::text FROM training.sales').fetchone()),
                    'features':conn.execute('SELECT count(*) FROM training.gold_features').fetchone()[0],
                    'authorizations':conn.execute('SELECT count(*) FROM control.monthly_authorizations').fetchone()[0]}
                assert result[logical]['state']['cutoff']=='2014-12-31'
                assert result[logical]['state']['sales'][0]==1297296 and result[logical]['state']['features']==9106020
                assert result[logical]['state']['authorizations']==0
    return result


def compare_databases(actual,expected,config,mapping):
    """Compara bytes de datos; CHECK mediante parser PostgreSQL, no texto de catálogo."""
    import psycopg
    from psycopg import sql
    actual=json.loads(json.dumps(actual));differences=[]
    if set(actual)!=set(expected):raise ValueError('Inventario de bases distinto')
    for database,reference in expected.items():
        observed=actual[database]
        if set(observed['tables'])!=set(reference['tables']):raise ValueError('Inventario de tablas distinto')
        for key in reference:
            if key!='tables' and observed[key]!=reference[key]:raise ValueError('Estado/secuencias/agregados diferentes')
        with psycopg.connect(**config,dbname=mapping[database]) as conn:
            for relation,original in reference['tables'].items():
                restored=observed['tables'][relation]
                if any(restored[k]!=v for k,v in original.items() if k!='constraints'):raise ValueError('Recuento, propietario o hash completo distinto')
                expected_constraints=original['constraints'];actual_constraints=restored['constraints']
                normal=lambda values:sorted((c[1],c[2],c[3]) for c in values if c[1]=='n')
                if normal(expected_constraints)!=normal(actual_constraints):raise ValueError('NOT NULL no preservado')
                if [c for c in expected_constraints if c[1]=='n']!=[c for c in actual_constraints if c[1]=='n']:
                    differences.append({'database':database,'table':relation,'kind':'postgres_generated_not_null_names','equivalent':True})
                other_expected={c[0]:c for c in expected_constraints if c[1]!='n'}
                other_actual={c[0]:c for c in actual_constraints if c[1]!='n'}
                if set(other_expected)!=set(other_actual):raise ValueError('Constraints faltantes/adicionales')
                checks=[c for c in other_expected.values() if c[1]=='c' and c!=other_actual[c[0]]]
                temp='restore_check_'+uuid.uuid4().hex[:12]
                if checks:
                    schema,table=relation.split('.',1)
                    conn.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE {}) ON COMMIT DROP').format(sql.Identifier(temp),sql.Identifier(schema,table)))
                for name,constraint in other_expected.items():
                    if constraint==other_actual[name]:continue
                    if constraint[1]!='c' or constraint[1:3]!=other_actual[name][1:3]:raise ValueError('PK/FK/unique o validación distintas')
                    conn.execute(sql.SQL('ALTER TABLE {} ADD CONSTRAINT {} {} NOT VALID').format(sql.Identifier(temp),sql.Identifier(name),sql.SQL(constraint[3])))
                    canonical=conn.execute('SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s::regclass AND conname=%s',(temp,name)).fetchone()[0]
                    if canonical.removesuffix(' NOT VALID')!=other_actual[name][3]:raise ValueError('CHECK semánticamente diferente')
                    differences.append({'database':database,'table':relation,'constraint':name,'kind':'postgres_check_reparse','equivalent':True})
    return differences


def s3(endpoint,user,password):
    import boto3
    from botocore.config import Config
    return boto3.client('s3',endpoint_url=endpoint,aws_access_key_id=user,aws_secret_access_key=password,config=Config(signature_version='s3v4',retries={'max_attempts':2}))


def objects(client):
    inventory=[]
    for bucket in sorted(b['Name'] for b in client.list_buckets()['Buckets']):
        versioning=client.get_bucket_versioning(Bucket=bucket).get('Status','Disabled')
        for page in client.get_paginator('list_object_versions').paginate(Bucket=bucket):
            for item in page.get('Versions',[]):
                obj=client.get_object(Bucket=bucket,Key=item['Key'],VersionId=item['VersionId']);h=hashlib.sha256()
                with obj['Body'] as stream:
                    for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
                inventory.append({'bucket':bucket,'key':item['Key'],'version_id':item['VersionId'],'latest':item['IsLatest'],'bytes':item['Size'],'etag':item['ETag'],'sha256':h.hexdigest(),'versioning':versioning})
            for item in page.get('DeleteMarkers',[]):inventory.append({'bucket':bucket,'key':item['Key'],'version_id':item['VersionId'],'latest':item['IsLatest'],'delete_marker':True,'versioning':versioning})
        inventory.append({'bucket':bucket,'bucket_marker':True,'versioning':versioning})
    return sorted(inventory,key=lambda i:(i['bucket'],i.get('key',''),i.get('version_id','')))


def verify_references(config,mapping,inventory):
    import psycopg
    available={(i['bucket'],i.get('key'),i.get('version_id')):i for i in inventory if not i.get('delete_marker') and not i.get('bucket_marker')}
    with psycopg.connect(**config,dbname=mapping['retailops'],options='-c default_transaction_read_only=on') as conn:
        refs=conn.execute('SELECT bucket,object_key,version_id,sha256,size_bytes FROM control.objects').fetchall()
        for bucket,key,version,sha,size in refs:
            obj=available.get((bucket,key,version))
            if not obj or obj['sha256']!=sha or obj['bytes']!=size:raise ValueError('Referencia SQL/VersionId/SHA no recuperada; no modificar referencias')
        publications=conn.execute('SELECT object_key,quarantine_version,released_version,sha256,size_bytes FROM control.publication_objects').fetchall()
        checked=len(refs)
        for key,quarantine,released,sha,size in publications:
            for bucket,version in [('retailops-quarantine',quarantine),('retailops-released',released)]:
                if version is None:continue
                obj=available.get((bucket,key,version))
                if not obj or obj['sha256']!=sha or obj['bytes']!=size:raise ValueError('VersionId de publicación no recuperado; detener sin reescribir')
                checked+=1
    return checked


def quiescent(allow_minio=True):
    nodes=json.loads(output([str(ROOT/'.local/f4/tools/kubectl'),'--context','default','--kubeconfig',str(ROOT/'.local/f4/kubeconfig'),'get','deployments','-A','-o','json']))
    assert all(i['spec'].get('replicas',1)==0 for i in nodes['items'] if i['metadata']['namespace'] in ['retailops','retailops-observability']),'Workloads deben estar a cero'
    names=output(['docker','ps','--filter','label=com.docker.compose.project=retailops-data','--format','{{.Names}}']).splitlines()
    assert set(names)<=({PG,MINIO} if allow_minio else {PG}),'Detener todos los escritores Compose antes del backup'
    import psycopg
    with psycopg.connect(**source_config(),dbname='postgres') as conn:
        others=conn.execute("SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid() AND usename<>'postgres'").fetchone()[0]
        assert others==0,'Hay clientes de trabajo conectados'


def volume_export(container,path):
    # Docker cp admite contenedor detenido: no monta origen en un contenedor nuevo.
    assert container==MINIO and not inspect(container)['State']['Running']
    with Path(path).open('xb') as stream:
        run(['docker','cp',container+':/data','-'],stdout=stream)
    Path(path).chmod(0o600)


def backup(args):
    started=time.monotonic();os.umask(0o077)
    dest=private_dir(outside_repo(args.destination));keys=private_dir(outside_repo(args.keys))
    identity=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12]
    base=private_dir(dest/('backup-'+identity),new=True);stage=private_dir(base/'staging',new=True)
    keyfile=keys/(identity+'.key');key=secrets.token_bytes(64)
    with keyfile.open('xb') as stream:stream.write(key)
    keyfile.chmod(0o600)
    start_utc=now();quiescent()
    print('Quiescencia comprobada; no se admite escritura concurrente operadora durante el backup',flush=True)
    original=source_config();finger=fingerprint(original)
    client=s3('http://127.0.0.1:9000',secret('minio_root_user'),secret('minio_root_password'));inventory=objects(client)
    reference_count=verify_references(original,{n:n for n in DATABASES},inventory)
    pgdir=private_dir(stage/'postgres')
    for database in DATABASES:
        with (pgdir/(database+'.dump')).open('xb') as stream:
            run(pg_args(PG,['pg_dump','-U','postgres','-Fc','--create',database],'/run/secrets/pg_admin_password'),stdout=stream)
    roles=output(pg_args(PG,['pg_dumpall','-U','postgres','--roles-only','--no-role-passwords'],'/run/secrets/pg_admin_password'))
    assert 'PASSWORD ' not in roles
    (pgdir/'roles.sql').write_text(roles)
    # No snapshot distribuido: sin escritores; verificar igualdad antes/después.
    assert fingerprint(original)==finger,'Datos cambiaron durante dump; backup incompleto'
    assert objects(client)==inventory,'Objetos cambiaron durante dump; backup incompleto'
    run(['docker','stop',MINIO],stdout=subprocess.DEVNULL);quiescent(allow_minio=False)
    source=inspect(MINIO);volume=next(m['Name'] for m in source['Mounts'] if m['Destination']=='/data' and m['Type']=='volume')
    assert not source['State']['Running']
    volume_export(MINIO,stage/'minio-cold.tar')
    assert not inspect(MINIO)['State']['Running']
    with (stage/'airflow-logs.tar').open('xb') as stream:
        run(['docker','cp','retailops-data-airflow-api-1:/opt/airflow/logs','-'],stdout=stream)
    links=[]
    with tarfile.open(stage/'airflow-logs.tar') as source_logs, tarfile.open(stage/'airflow-log-files.tar','w') as log_files:
        for member in source_logs:
            if member.issym():links.append({'path':member.name,'target':member.linkname});continue
            if not(member.isfile() or member.isdir()):raise ValueError('Entrada inesperada en logs Airflow')
            log_files.addfile(member,source_logs.extractfile(member) if member.isfile() else None)
    write_json(stage/'airflow-log-links.json',links)
    # Credenciales de recuperación solo dentro del payload cifrado; no se habilitan en clones.
    secret_dir=private_dir(stage/'recovery-secrets')
    for path in (ROOT/'.local/secrets').iterdir():
        if path.is_file() and not path.is_symlink():shutil.copyfile(path,secret_dir/path.name);(secret_dir/path.name).chmod(0o600)
    config=private_dir(stage/'configuration')
    for relative in ['.local/f52/values-app.yaml','.local/f51/grafana-admin-user','.local/f51/grafana-admin-password']:
        source_file=ROOT/relative
        if source_file.exists():shutil.copyfile(source_file,config/source_file.name)
    with tarfile.open(stage/'source.tar','w') as tar:
        for name in sorted(set(output(['git','ls-files','--cached','--others','--exclude-standard']).splitlines())):
            path=ROOT/name
            if path.is_symlink():raise ValueError('Revisar symlink de fuente antes de respaldar')
            if path.is_file():tar.add(path,arcname=name,recursive=False)
    kube=[]
    for namespace in ['retailops','retailops-observability']:
        kube.append(json.loads(output([str(ROOT/'.local/f4/tools/kubectl'),'--context','default','--kubeconfig',str(ROOT/'.local/f4/kubeconfig'),'get','deployments,services,configmaps,networkpolicies,pvc','-n',namespace,'-o','json'])))
    write_json(config/'kubernetes.json',kube)
    images={name:inspect(container)['Image'] for name,container in [('postgres',PG),('minio',MINIO)]}
    images['mlflow']=inspect('retailops-mlflow:local-v1','image')['Id']
    with (stage/'images.tar').open('xb') as stream:run(['docker','save',*sorted(set(images.values()))],stdout=stream)
    write_json(stage/'inventory.json',{'databases':finger,'objects':inventory,'sql_version_references':reference_count,'images':images,'source_pg_version':output(['docker','exec',PG,'postgres','--version']).strip(),'openssl_version':output(['openssl','version']).strip(),'docker_version':output(['docker','version','--format','{{.Server.Version}}']).strip(),'source_commit':output(['git','rev-parse','HEAD']).strip(),'quiescence_started_utc':start_utc,'minio_consistency':'cold-volume; no writers; original VersionId required'})
    write_json(stage/'manifest.json',{'format':FORMAT,'created_utc':now(),'files':file_inventory(stage)})
    check_files(stage,json.loads((stage/'manifest.json').read_text()))
    archive=base/'payload.tar'
    with tarfile.open(archive,'w') as tar:
        for path in sorted(stage.rglob('*')):
            if path.is_file():tar.add(path,arcname=str(path.relative_to(stage)),recursive=False)
    crypt(archive,base/'payload.enc',key)
    envelope={'format':FORMAT,'status':'complete','id':identity,'started_utc':start_utc,'completed_utc':now(),'backup_seconds':time.monotonic()-started,'cipher':'AES-256-CBC/PBKDF2-SHA256-200000 + encrypt-then-HMAC-SHA256','bytes':(base/'payload.enc').stat().st_size,'sha256':digest(base/'payload.enc'),'hmac_sha256':mac(base/'payload.enc',key),'key_file':keyfile.name}
    envelope['backup_seconds']=time.monotonic()-started;envelope['completed_utc']=now()
    write_json(base/'manifest.json',envelope);verify_envelope(base,keyfile)
    # Solo temporales creados por este comando dentro del backup nuevo; nunca volúmenes.
    shutil.rmtree(stage);archive.unlink()
    print(json.dumps({'backup':str(base),'key':str(keyfile),'seconds':envelope['backup_seconds']},indent=2),flush=True)


def unpack(args,workspace):
    envelope,key=verify_envelope(args.backup,args.key)
    archive=workspace/'payload.tar';crypt(Path(args.backup)/'payload.enc',archive,key,decrypt=True)
    payload=private_dir(workspace/'payload',new=True);safe_extract(archive,payload)
    manifest=json.loads((payload/'manifest.json').read_text());check_files(payload,manifest)
    return envelope,payload


def verify(args):
    started=time.monotonic();workspace=private_dir(outside_repo(args.workspace),new=True)
    envelope,payload=unpack(args,workspace)
    write_json(workspace/'verification.json',{'valid':True,'id':envelope['id'],'files':len(json.loads((payload/'manifest.json').read_text())['files']),'verify_seconds':time.monotonic()-started,'verified_utc':now()})
    print('Cifrado/MAC, manifiesto y todos los archivos SHA-256 válidos',flush=True)


def address(container):
    networks=inspect(container)['NetworkSettings']['Networks']
    assert len(networks)==1 and next(iter(networks)).startswith('retailops-restore-')
    return next(iter(networks.values()))['IPAddress']


def wait(check,description,timeout=120,container=None):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if container and inspect(container)['State']['Status'] in ['exited','dead']:raise RuntimeError('Contenedor aislado falló: '+description)
        try:
            value=check()
            if value:return value
        except Exception:pass
        time.sleep(1)
    raise RuntimeError('Timeout: '+description)


def restore(args):
    import psycopg
    from psycopg import sql
    started=time.monotonic();workspace=private_dir(outside_repo(args.workspace),new=True)
    envelope,payload=unpack(args,workspace);inventory=json.loads((payload/'inventory.json').read_text())
    identity=uuid.uuid4().hex[:12];prefix='retailops-restore-'+identity
    names={k:prefix+'-'+k for k in ['postgres','minio','mlflow','network','pgdata','objects']}
    state={'id':identity,'prefix':prefix,'resources':names,'workspace':str(workspace),'backup_id':envelope['id'],'started_utc':now(),'status':'preparing'}
    write_json(workspace/'restore-state.json',state)
    for image in inventory['images'].values():inspect(image,'image') # no carga automática que cambie tags
    for kind,name in [('container',names[k]) for k in ['postgres','minio','mlflow']]+[('volume',names[k]) for k in ['pgdata','objects']]+[('network',names['network'])]:
        result=subprocess.run(['docker',kind,'inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode==0:raise ValueError('Conflicto de recursos; no sobrescribir')
    if (payload/'airflow-log-files.tar').exists():safe_extract(payload/'airflow-log-files.tar',private_dir(workspace/'airflow-logs'))
    runtime=private_dir(workspace/'runtime');secrets_dir=private_dir(runtime/'secrets');admin='restore_admin_'+identity
    creds={name:secrets.token_urlsafe(36) for name in ['admin','minio_root_user','minio_root_password','pg_mlflow_password']}
    for name,value in creds.items():(secrets_dir/name).write_text(value);(secrets_dir/name).chmod(0o600)
    label=['--label','retailops.restore.id='+identity]
    run(['docker','network','create','--internal',*label,names['network']],stdout=subprocess.DEVNULL)
    for name in ['pgdata','objects']:run(['docker','volume','create',*label,names[name]],stdout=subprocess.DEVNULL)
    common=['docker','run','-d',*label,'--network',names['network'],'--security-opt','no-new-privileges','--pids-limit','256']
    run(common+['--name',names['postgres'],'--memory','2g','--cpus','2','-v',names['pgdata']+':/var/lib/postgresql','-v',str(secrets_dir)+':/run/secrets:ro','-e','POSTGRES_USER='+admin,'-e','POSTGRES_PASSWORD_FILE=/run/secrets/admin','-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256',inventory['images']['postgres']],stdout=subprocess.DEVNULL)
    config={'host':address(names['postgres']),'port':5432,'user':admin,'password':creds['admin']}
    def ready():
        with psycopg.connect(**config,dbname='postgres',connect_timeout=2) as conn:return conn.execute('SELECT 1').fetchone()[0]==1
    wait(ready,'PostgreSQL aislado',container=names['postgres'])
    psql=['psql','-U',admin,'-d','postgres','-v','ON_ERROR_STOP=1']
    with (payload/'postgres/roles.sql').open('rb') as stream:run(pg_args(names['postgres'],psql,'/run/secrets/admin'),stdin=stream,stdout=subprocess.DEVNULL)
    mapping={}
    for database in DATABASES:
        print('Restaurando base aislada:',database,flush=True)
        with (payload/'postgres'/(database+'.dump')).open('rb') as stream:
            run(pg_args(names['postgres'],['pg_restore','-U',admin,'--exit-on-error','--create','--dbname','postgres'],'/run/secrets/admin'),stdin=stream,stdout=subprocess.DEVNULL)
        renamed='restore_'+identity+'_'+database
        with psycopg.connect(**config,dbname='postgres',autocommit=True) as conn:conn.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(database),sql.Identifier(renamed)))
        mapping[database]=renamed
    # Todos los logins recuperados reciben contraseñas nuevas; nunca originales.
    with psycopg.connect(**config,dbname='postgres',autocommit=True) as conn:
        for (role,) in conn.execute('SELECT rolname FROM pg_roles WHERE rolcanlogin AND rolname<>%s',(admin,)).fetchall():
            value=creds['pg_mlflow_password'] if role=='retailops_mlflow' else secrets.token_urlsafe(36)
            conn.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role),sql.Literal(value)))
    try:
        psycopg.connect(host=config['host'],port=config['port'],user='retailops_api',password=(payload/'recovery-secrets/pg_api_password').read_text().strip(),dbname=mapping['retailops'],connect_timeout=3).close()
    except psycopg.OperationalError as error:
        assert 'password authentication failed' in str(error)
    else:raise ValueError('Credencial SQL original aceptada en clone; detener')
    # El helper de restauración solo monta el NUEVO volumen, nunca el autoritativo.
    restore_code="import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|');\nfor m in t:\n assert m.name=='data' or m.name.startswith('data/'); assert '..' not in m.name.split('/'); assert m.isfile() or m.isdir(); t.extract(m,path='/out',set_attrs=False,filter='data')"
    with (payload/'minio-cold.tar').open('rb') as stream:
        run(['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','-v',names['objects']+':/out/data',PYTHON_IMAGE,'python','-c',restore_code],stdin=stream,stdout=subprocess.DEVNULL)
    mcdir=private_dir(runtime/'mc')
    write_json(mcdir/'config.json',{'version':'10','aliases':{'restore':{'url':'http://127.0.0.1:9000','accessKey':creds['minio_root_user'],'secretKey':creds['minio_root_password'],'api':'S3v4','path':'auto'}}})
    run(common+['--name',names['minio'],'--user','0:0','--memory','1g','--cpus','1','-v',names['objects']+':/data','-v',str(secrets_dir)+':/run/secrets:ro','-v',str(mcdir)+':/mc','-e','MINIO_ROOT_USER_FILE=/run/secrets/minio_root_user','-e','MINIO_ROOT_PASSWORD_FILE=/run/secrets/minio_root_password','-e','MINIO_BROWSER=off',inventory['images']['minio'],'server','/data','--address',':9000'],stdout=subprocess.DEVNULL)
    endpoint='http://'+address(names['minio'])+':9000';client=s3(endpoint,creds['minio_root_user'],creds['minio_root_password'])
    wait(lambda:client.list_buckets(),'MinIO aislado; detener si no conserva versiones',container=names['minio'])
    mc=['docker','exec','--user',str(os.getuid())+':'+str(os.getgid()),names['minio'],'mc','--config-dir','/mc','--json','admin','user']
    users=[json.loads(line) for line in output(mc+['list','restore']).splitlines() if line.strip()]
    for user in users:run(mc+['disable','restore',user['accessKey']],stdout=subprocess.DEVNULL)
    source_root=(payload/'recovery-secrets/minio_root_user').read_text().strip();source_password=(payload/'recovery-secrets/minio_root_password').read_text().strip()
    from botocore.exceptions import ClientError
    try:s3(endpoint,source_root,source_password).list_buckets()
    except ClientError as error:
        assert error.response['Error']['Code'] in ['InvalidAccessKeyId','SignatureDoesNotMatch','AccessDenied']
    else:raise ValueError('Credenciales originales siguen habilitadas en clone; detener')
    client.list_buckets() # Contraprueba positiva: el rechazo anterior no fue caída de red.
    restore_seconds=time.monotonic()-started;validation_started=time.monotonic()
    actual=fingerprint(config,mapping)
    # JSON normaliza tuplas de psycopg antes de comparar con el manifiesto.
    write_json(workspace/'validation-databases.json',actual)
    constraint_differences=compare_databases(actual,inventory['databases'],config,mapping)
    restored_objects=objects(client)
    assert restored_objects==inventory['objects'],'VersionId/hash/inventario distinto: no modificar referencias'
    references=verify_references(config,mapping,restored_objects)
    print('Datos/objetos/versiones recuperados; todas las referencias SQL conservadas',flush=True)
    # MLflow solo en la red aislada; no se permite acceso al PG/MinIO originales.
    subnet=inspect(names['network'],'network')['IPAM']['Config'][0]['Subnet']
    mlflow_ip=str(ipaddress.ip_network(subnet).network_address+10)
    launch=runtime/'launch_tracking.py'
    launch.write_text("""import os
from pathlib import Path
from urllib.parse import quote
from mlflow.cli import server
s=lambda n:Path('/run/secrets',n).read_text().strip()
os.environ['AWS_ACCESS_KEY_ID']=s('minio_root_user');os.environ['AWS_SECRET_ACCESS_KEY']=s('minio_root_password');os.environ['AWS_DEFAULT_REGION']='us-east-1'
os.environ['MLFLOW_S3_ENDPOINT_URL']='http://"""+names['minio']+""":9000'
uri='postgresql+psycopg://retailops_mlflow:'+quote(s('pg_mlflow_password'),safe='')+'@"""+names['postgres']+':5432/'+mapping['retailops_mlflow']+"""'
server.main(args=['--backend-store-uri',uri,'--serve-artifacts','--artifacts-destination','s3://retailops-mlflow','--host','0.0.0.0','--port','5000','--workers','1','--allowed-hosts','127.0.0.1:*,localhost:*,"""+mlflow_ip+""":*'])
""")
    run(common+['--name',names['mlflow'],'--ip',mlflow_ip,'--memory','2g','--memory-swap','3g','--cpus','2','-v',str(secrets_dir)+':/run/secrets:ro','-v',str(launch)+':/restore/launch_tracking.py:ro','--entrypoint','python',inventory['images']['mlflow'],'/restore/launch_tracking.py'],stdout=subprocess.DEVNULL)
    tracking='http://'+mlflow_ip+':5000'
    import urllib.request
    wait(lambda:urllib.request.urlopen(tracking+'/health',timeout=3).status==200,'MLflow aislado',timeout=180,container=names['mlflow'])
    import mlflow
    from mlflow.tracking import MlflowClient
    mlflow.set_tracking_uri(tracking);client_ml=MlflowClient(tracking_uri=tracking)
    versions=client_ml.search_model_versions("name='retailops-sales-global'")
    assert len(versions)==1 and versions[0].version=='1'
    private_dir(runtime/'model-check')
    model=mlflow.sklearn.load_model('models:/retailops-sales-global/1',dst_path=str(runtime/'model-check'))
    assert model is not None
    info=mlflow.models.get_model_info('models:/retailops-sales-global/1')
    with tarfile.open(payload/'source.tar') as source_tar:
        contract=source_tar.extractfile('contracts/gold-features-v1.json').read()
    assert info.metadata['contract_sha256']==hashlib.sha256(contract).hexdigest()
    assert info.metadata['historical_cutoff']=='2014-12-31' and info.metadata['feature_version']=='sales-pit-v1'
    assert versions[0].tags.get('purpose')=='candidate_local_preview'
    compare_databases(fingerprint(config,mapping),inventory['databases'],config,mapping)
    validation_seconds=time.monotonic()-validation_started
    report={'status':'validated','backup_id':envelope['id'],'backup_point_utc':inventory['quiescence_started_utc'],'restored_utc':now(),'restore_seconds':restore_seconds,'validation_seconds':validation_seconds,'total_seconds':time.monotonic()-started,'source_age_seconds':time.time()-datetime.fromisoformat(inventory['quiescence_started_utc'].replace('Z','+00:00')).timestamp(),'table_hashes':'full ordered binary COPY per table','constraint_representation_differences':constraint_differences,'object_hashes':'full SHA-256 all versions','sql_version_references':references,'objects':len([i for i in restored_objects if 'sha256' in i]),'model_version':'1','model_run_id':versions[0].run_id,'model_artifact_load':True,'source_iam_accounts_disabled_in_clone':len(users),'original_root_credentials_rejected':True,'original_pg_api_password_rejected':True,'rto_scope':'Datos PostgreSQL/MinIO + metadata y carga de artefacto MLflow; no RTO integral apps/K3s/Airflow UI','resources':names,'databases':mapping}
    write_json(workspace/'restore-report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


def stop(args):
    state=json.loads((Path(args.workspace)/'restore-state.json').read_text());identity=state['id'];prefix='retailops-restore-'+identity
    if not(len(identity)==12 and all(c in '0123456789abcdef' for c in identity)):raise ValueError('Identidad de restore inválida')
    for component in ['mlflow','minio','postgres']:
        name=state['resources'][component]
        if name!=prefix+'-'+component:raise ValueError('Recurso fuera del restore: no tocar')
        result=subprocess.run(['docker','container','inspect',name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        if result.returncode:continue
        data=json.loads(result.stdout)[0]
        if data['Config']['Labels'].get('retailops.restore.id')!=identity:raise ValueError('Propietario de recurso distinto: no tocar')
        if data['State']['Running']:run(['docker','stop',name],stdout=subprocess.DEVNULL)
    print('Solo contenedores aislados detenidos; volúmenes/red/backup conservados')


def main():
    if not __debug__:raise RuntimeError('No ejecutar backup/restore con Python -O; requiere comprobaciones activas')
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('backup');p.add_argument('--destination',required=True);p.add_argument('--keys',required=True)
    for name in ['verify','restore']:
        p=sub.add_parser(name);p.add_argument('--backup',required=True);p.add_argument('--key',required=True);p.add_argument('--workspace',required=True)
    p=sub.add_parser('stop');p.add_argument('--workspace',required=True)
    args=parser.parse_args()
    (ROOT/'.local').mkdir(exist_ok=True)
    with (ROOT/'.local/f54-operation.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        globals()[args.command](args)


if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as error:
        # stderr podría contener SQL/credenciales; no imprimir comando ni contenido.
        print('Falló una herramienta; conservar estado privado e inspeccionar localmente. Código:',error.returncode,file=sys.stderr);sys.exit(1)
