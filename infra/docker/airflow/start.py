"""Configura secretos sin imprimirlos y ejecuta el componente solicitado."""
import os,sys
from pathlib import Path
from urllib.parse import quote
read=lambda name:Path('/run/secrets',name).read_text().strip()
os.environ['AIRFLOW__DATABASE__SQL_ALCHEMY_CONN']='postgresql+psycopg2://retailops_airflow:'+quote(read('pg_airflow_password'),safe='')+'@postgres:5432/retailops_airflow'
os.environ['AIRFLOW__CORE__FERNET_KEY']=read('airflow_fernet_key')
os.environ['AIRFLOW__API_AUTH__JWT_SECRET']=read('airflow_jwt_secret')
os.environ['AIRFLOW__API__SECRET_KEY']=read('airflow_jwt_secret')
# SimpleAuthManager abre el fichero con a+: copiar a runtime privado persistente, nunca abrir el secret RO.
users=Path('/opt/airflow/config/users.json')
if not users.exists():
    users.write_text(read('airflow_users'));users.chmod(0o600)
# El entrypoint oficial prepara NSS/usuario para el UID local y conserva señales.
os.execv('/entrypoint',['/entrypoint',*sys.argv[1:]])
