"""Credenciales solo desde secrets; backend MLflow separado del negocio."""
import os
from pathlib import Path
from urllib.parse import quote
from mlflow.cli import server
secret=lambda name:Path('/run/secrets',name).read_text().strip()
os.environ['AWS_ACCESS_KEY_ID']=secret('minio_mlflow_user')
os.environ['AWS_SECRET_ACCESS_KEY']=secret('minio_mlflow_password')
os.environ['AWS_DEFAULT_REGION']='us-east-1'
os.environ['MLFLOW_S3_ENDPOINT_URL']='http://minio:9000'
uri='postgresql+psycopg://retailops_mlflow:'+quote(secret('pg_mlflow_password'),safe='')+'@postgres:5432/retailops_mlflow'
server.main(args=['--backend-store-uri',uri,'--serve-artifacts','--artifacts-destination','s3://retailops-mlflow',
 '--host','0.0.0.0','--port','5000','--workers','1',
 '--allowed-hosts','127.0.0.1:*,localhost:*,mlflow:*'],prog_name='mlflow server')
