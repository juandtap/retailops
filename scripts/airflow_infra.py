"""Provisiona únicamente metadatos Airflow, sin liberar datos ni entrenar."""
from pathlib import Path
import os,secrets,sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from data_infra import compose

def prepare():
    from cryptography.fernet import Fernet
    values={'pg_airflow_password':secrets.token_urlsafe(36),'airflow_fernet_key':Fernet.generate_key().decode(),
      'airflow_jwt_secret':secrets.token_urlsafe(48),'airflow_users.json':json.dumps({'admin':secrets.token_urlsafe(24)})}
    folder=ROOT/'.local/secrets'
    for name,value in values.items():
        p=folder/name
        if not p.exists():
            with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(value+'\n')
        if p.is_symlink() or p.stat().st_mode&0o077:raise ValueError('Secreto inseguro')
    for name in ('monthly','ml','auth'):
        path=ROOT/'.local/airflow'/name;path.mkdir(parents=True,exist_ok=True,mode=0o700)
    print('Secretos y runtime Airflow preparados, sin reemplazar existentes.')

def provision():
    import psycopg
    from psycopg import sql
    read=lambda n:(ROOT/'.local/secrets'/n).read_text().strip()
    with psycopg.connect(host='127.0.0.1',port=int(os.environ.get('POSTGRES_PORT','5432')),dbname='postgres',user='postgres',password=read('pg_admin_password'),autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='retailops_airflow'").fetchone():
            c.execute(sql.SQL('CREATE ROLE retailops_airflow LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(sql.Literal(read('pg_airflow_password'))))
        owner=c.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='retailops_airflow'").fetchone()
        if owner and owner[0]!='retailops_airflow':raise ValueError('Propietario incompatible')
        if not owner:c.execute('CREATE DATABASE retailops_airflow OWNER retailops_airflow')
        c.execute('REVOKE ALL ON DATABASE retailops_airflow FROM PUBLIC')
        c.execute('GRANT CONNECT ON DATABASE retailops_airflow TO retailops_airflow')
    compose('run','--rm','airflow-api','db','migrate')
    compose('run','--rm','airflow-api','pools','set','retailops_serial','1','Serializa operaciones RetailOps')

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['provision']:provision()
    else:raise SystemExit('Usar prepare o provision')
