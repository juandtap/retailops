"""Provisiona solo identidad/base/bucket MLflow; no transforma ni altera negocio."""
import os
from pathlib import Path
import secrets
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from data_infra import compose

def prepare():
    folder=ROOT/'.local/secrets'
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    for name in ('pg_mlflow_password','minio_mlflow_user','minio_mlflow_password'):
        path=folder/name
        if not path.exists():
            value=('retailops-mlflow-'+secrets.token_hex(5)) if name.endswith('_user') else secrets.token_urlsafe(36)
            with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:stream.write(value+'\n')
        if path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('Secreto inseguro')
    print('Secretos MLflow preparados sin reemplazar existentes.')

def provision():
    import psycopg
    from psycopg import sql
    def secret(name):
        p=ROOT/'.local/secrets'/name
        if p.is_symlink() or p.stat().st_mode&0o077:raise ValueError('Secreto inseguro')
        return p.read_text().strip()
    with psycopg.connect(host='127.0.0.1',port=int(os.environ.get('POSTGRES_PORT','5432')),dbname='postgres',user='postgres',password=secret('pg_admin_password'),autocommit=True) as conn:
        exists=conn.execute("SELECT 1 FROM pg_roles WHERE rolname='retailops_mlflow'").fetchone()
        if not exists:conn.execute(sql.SQL('CREATE ROLE retailops_mlflow LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(sql.Literal(secret('pg_mlflow_password'))))
        flags=conn.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='retailops_mlflow'").fetchone()
        if any(flags):raise ValueError('Rol MLflow con privilegios inesperados')
        owner=conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='retailops_mlflow'").fetchone()
        if owner and owner[0]!='retailops_mlflow':raise ValueError('Base MLflow con propietario ajeno')
        if not owner:conn.execute('CREATE DATABASE retailops_mlflow OWNER retailops_mlflow')
        conn.execute('REVOKE ALL ON DATABASE retailops_mlflow FROM PUBLIC')
        conn.execute('GRANT CONNECT ON DATABASE retailops_mlflow TO retailops_mlflow')
    compose('run','--rm','mlops-admin')
    print('Base y bucket MLflow separados preparados; negocio sin cambios.')

if __name__=='__main__':
    if sys.argv[1:] == ['prepare']:prepare()
    elif sys.argv[1:] == ['provision']:provision()
    else:raise SystemExit('Usar prepare o provision')
