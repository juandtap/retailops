"""Identidad Airflow viewer para consultas del backend, preservando usuarios existentes."""
import json,os,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'.local/secrets'
source=folder/'airflow_users.json';runtime=ROOT/'.local/airflow/auth/users.json';reader=folder/'airflow_reader.json'
users=json.loads(source.read_text())
if reader.exists():
    value=json.loads(reader.read_text())
    if value['username']!='retailops_viewer':raise ValueError('Identidad lectora incompatible')
else:value={'username':'retailops_viewer','password':users.get('retailops_viewer') or secrets.token_urlsafe(30)}
if 'retailops_viewer' in users and users['retailops_viewer']!=value['password']:raise ValueError('Credencial lectora conflictiva')
users['retailops_viewer']=value['password']
for path in (source,runtime):
    existing=json.loads(path.read_text()) if path.exists() else {}
    if any(k!='retailops_viewer' and users.get(k)!=v for k,v in existing.items()):raise ValueError('No reemplazar credenciales existentes')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    path.write_text(json.dumps(users)+'\n');os.chmod(path,0o600)
reader.write_text(json.dumps(value)+'\n');os.chmod(reader,0o600)
print('Identidad Airflow viewer preparada; contraseñas existentes preservadas, sin mostrar valores.')
