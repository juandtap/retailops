"""Operación local reproducible de F1-02; nunca ingiere ni libera datos."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker','compose','--project-directory',str(ROOT/'infra/docker'),'--env-file',str(ROOT/('.env' if (ROOT/'.env').is_file() else '.env.example')),'-f',str(ROOT/'infra/docker/compose.yaml')]
SECRET_DIR = ROOT/'.local/secrets'
PG_ROLES = ('admin','control','data','api','ingestor','releaser','trainer')
MINIO_ROLES = ('root','ingestor','releaser','trainer')


def run(args, *, input=None, capture=False, env=None):
    result=subprocess.run(args,cwd=ROOT,input=input,text=True,check=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,env=env)
    return result.stdout if capture else None


def compose(*args, **kwargs):
    return run([*COMPOSE,*args],**kwargs)


def initialize_secrets():
    SECRET_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(SECRET_DIR,0o700)
    entries={f'pg_{role}_password':secrets.token_urlsafe(36) for role in PG_ROLES}
    for role in MINIO_ROLES:
        entries[f'minio_{role}_user']='retailops-'+role+'-'+secrets.token_hex(4)
        entries[f'minio_{role}_password']=secrets.token_urlsafe(36)
    for name,value in entries.items():
        target=SECRET_DIR/name
        if target.exists():
            if target.is_symlink() or not target.is_file() or not target.read_text().strip():
                raise ValueError('Secreto existente inválido: '+name)
            if target.stat().st_mode & 0o077:
                raise ValueError('Secreto con permisos abiertos: '+name)
            continue
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(value+'\n')
    print('Secretos locales preparados (sin mostrar valores y sin sobrescribir existentes).')


def validate_configuration():
    for name in [*[f'pg_{r}_password' for r in PG_ROLES],*[f'minio_{r}_{suffix}' for r in MINIO_ROLES for suffix in ('user','password')]]:
        p=SECRET_DIR/name
        if not p.is_file() or p.is_symlink() or len(p.read_text().strip())<8 or p.stat().st_mode & 0o077:
            raise ValueError('Secreto faltante, débil o con permisos inválidos: '+name)
    for name,default in [('POSTGRES_PORT','5432'),('MINIO_PORT','9000')]:
        value=int(os.environ.get(name,default))
        if not 1<=value<=65535:raise ValueError(name+' fuera de rango')
    compose('config','--quiet')
    resolved=json.loads(compose('config','--format','json',capture=True))
    db=resolved['services']['postgres']['environment']['POSTGRES_DB']
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',db):raise ValueError('POSTGRES_DB debe ser un identificador simple en minúsculas')
    for service in ('postgres','minio'):
        for port in resolved['services'][service].get('ports',[]):
            if port.get('host_ip')!='127.0.0.1' or not 1<=int(port['published'])<=65535:
                raise ValueError('Puerto publicado inseguro o inválido: '+service)
    print('Configuración Compose y secretos validados.')


def psql(sql, role='admin', capture=True):
    user={'admin':'postgres','control':'retailops_control_migrator','data':'retailops_data_migrator'}.get(role,'retailops_'+role)
    # El shell dentro del contenedor lee un único secreto; nunca se interpola su valor en argv.
    command=f'export PGPASSWORD="$(cat /run/secrets/pg_{role}_password)"; exec psql -X -v ON_ERROR_STOP=1 -h postgres -U {user} -d "$POSTGRES_DB" -At'
    return compose('exec','-T','postgres','sh','-ec',command,input=sql,capture=capture)


def migrate():
    jar=ROOT/'apps/api/target/api-0.0.1-SNAPSHOT.jar'
    if not jar.is_file():raise ValueError('Compilar primero la API con ./mvnw verify')
    config=json.loads(compose('config','--format','json',capture=True))['services']['postgres']
    port=config['ports'][0]['published']
    database=config['environment']['POSTGRES_DB']
    environment={**os.environ,'RETAILOPS_SECRETS_DIR':str(SECRET_DIR),
                 'DB_JDBC_URL':f'jdbc:postgresql://127.0.0.1:{port}/{database}'}
    run(['java','-jar',str(jar),'--spring.profiles.active=storage','--spring.main.web-application-type=none'],env=environment)


def assert_empty():
    query="SELECT (SELECT COUNT(*) FROM control.batches)+(SELECT COUNT(*) FROM control.source_files)+(SELECT COUNT(*) FROM control.ingestion_runs)+(SELECT COUNT(*) FROM control.objects)"+''.join(f'+(SELECT COUNT(*) FROM silver.{t})' for t in ['sales','stores','families','holidays_events','oil_prices','store_transactions','observation_gaps'])+';'
    if psql(query).strip()!='0':raise ValueError('La comprobación F1-02 exige datos de negocio vacíos; no borrar datos existentes.')
    if psql('SELECT released_through IS NULL AND last_batch_id IS NULL FROM control.historical_state;').strip()!='t':
        raise ValueError('El corte ya no está vacío; no alterar un entorno con datos liberados.')


def verify():
    run([sys.executable,str(ROOT/'scripts/storage_contracts.py')])
    assert_empty()
    # Consultas mediante credenciales reales de entrenamiento y pruebas SQL aisladas con rollback.
    assert psql('SELECT COUNT(*) FROM training.sales;',role='trainer').strip()=='0'
    for denied_sql in ['SELECT COUNT(*) FROM silver.sales;', 'SET ROLE retailops_data_migrator;',
                       "UPDATE control.historical_state SET released_through='2099-12-31';",
                       'CREATE TEMP TABLE bypass_check(id integer);']:
        try:
            psql(denied_sql,role='trainer')
        except subprocess.CalledProcessError as exc:
            if 'permission denied' not in (exc.stderr or ''):raise
        else:raise AssertionError('Operación no autorizada del entrenador: '+denied_sql)
    psql((ROOT/'infra/docker/tests/access.sql').read_text())
    assert_empty()
    compose('run','--rm','minio-admin','check')
    for inventory in json.loads((ROOT/'docs/DATA_INVENTORY.json').read_text()):
        with (ROOT/'data/source/favorita'/inventory['file']).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=inventory['sha256']:
                raise ValueError('El checksum de SOURCE cambió: '+inventory['file'])
    print('Verificación correcta: migraciones, restricciones, aislamiento, tablas vacías, corte nulo y siete hashes originales.')


def persistence():
    assert_empty()
    # Marca administrativa persistente en comentario del esquema, sin ventas/lotes sintéticos persistidos.
    psql("COMMENT ON SCHEMA data_meta IS 'retailops-infrastructure-check-v1';")
    compose('run','--rm','minio-admin','check')
    before_pg=psql("SELECT oid, obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname='data_meta';").strip()
    before_object=json.loads(compose('run','--rm','minio-admin','fingerprint',capture=True))
    compose('stop','postgres','minio')
    compose('up','-d','--wait','--wait-timeout','120','postgres','minio')
    after_pg=psql("SELECT oid, obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname='data_meta';").strip()
    after_object=json.loads(compose('run','--rm','minio-admin','fingerprint',capture=True))
    assert before_pg==after_pg
    assert all(before_object[k]==after_object[k] for k in ('etag','versionID','size'))
    verify()
    print('Persistencia comprobada tras stop/up: esquema PostgreSQL y versión/contenido del marcador MinIO conservados.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init-secrets','config','build','up','migrate','configure-minio','verify','persistence','stop','down','status'])
    action=parser.parse_args().action
    if action=='init-secrets':initialize_secrets();return
    validate_configuration()
    if action=='config':return
    if action=='build':compose('build','minio')
    elif action=='up':compose('up','-d','--wait','--wait-timeout','120','postgres','minio')
    elif action=='migrate':migrate()
    elif action=='configure-minio':compose('run','--rm','minio-admin','configure')
    elif action=='verify':verify()
    elif action=='persistence':persistence()
    elif action=='stop':compose('stop','postgres','minio')
    elif action=='down':compose('down')  # Sin -v; no elimina volúmenes ni datos.
    elif action=='status':compose('ps')

if __name__=='__main__':
    main()
