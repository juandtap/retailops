"""Clientes de trabajo sin credenciales administrativas y verificación de bytes S3."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error
import psycopg
from psycopg.rows import dict_row

from .extract import ConflictError

QUARANTINE='retailops-quarantine'
RELEASED='retailops-released'

@dataclass
class Settings:
    root: Path
    database: str
    pg_port: int
    minio_endpoint: str
    secure: bool=False

    @classmethod
    def project(cls,root,database=None):
        root=Path(root).resolve()
        envfile=root/('.env' if (root/'.env').exists() else '.env.example')
        command=['docker','compose','--env-file',str(envfile),'-f',str(root/'infra/docker/compose.yaml'),'config','--format','json']
        config=json.loads(subprocess.check_output(command,text=True,cwd=root))
        if config['name']!='retailops-data':raise ValueError('No corresponde al proyecto RetailOps')
        pg=config['services']['postgres'];s3=config['services']['minio']
        for service in (pg,s3):
            if service['ports'][0]['host_ip']!='127.0.0.1':raise ValueError('Solo endpoints locales autorizados')
        return cls(root,database or pg['environment']['POSTGRES_DB'],int(pg['ports'][0]['published']),f"127.0.0.1:{s3['ports'][0]['published']}")

    def secret(self,name):
        path=self.root/'.local/secrets'/name
        if path.is_symlink() or path.stat().st_mode & 0o077:raise ValueError('Permisos de secreto inválidos')
        value=path.read_text().strip()
        if not value:raise ValueError('Secreto vacío')
        return value

    def db(self,role):
        if role not in ('ingestor','releaser','trainer'):raise ValueError('Rol de trabajo no permitido')
        return psycopg.connect(host=os.environ.get('RETAILOPS_PG_HOST','127.0.0.1'),port=self.pg_port,dbname=self.database,user='retailops_'+role,
             password=self.secret('pg_'+role+'_password'),autocommit=True,row_factory=dict_row)

    def s3(self,role):
        if role not in ('ingestor','releaser','trainer'):raise ValueError('Rol S3 de trabajo no permitido')
        return Minio(self.minio_endpoint,access_key=self.secret('minio_'+role+'_user'),secret_key=self.secret('minio_'+role+'_password'),secure=self.secure)

    def assert_environment(self):
        for service in ('postgres','minio'):
            name=f'retailops-data-{service}-1'
            container=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
            labels=container['Config']['Labels']
            if labels.get('com.docker.compose.project')!='retailops-data' or labels.get('com.docker.compose.service')!=service:
                raise ValueError('Contenedor ajeno al proyecto')
            if container['State'].get('Health',{}).get('Status')!='healthy':raise ValueError('Servicio no saludable: '+service)
        with self.db('ingestor') as conn:
            conn.execute('SELECT ingested_at FROM control.publications LIMIT 0')
        for bucket in (QUARANTINE,RELEASED):
            if not self.s3('releaser').bucket_exists(bucket):raise ValueError('Bucket faltante')


def stat_optional(client,bucket,key):
    try:return client.stat_object(bucket,key)
    except S3Error as exc:
        if exc.code in ('NoSuchKey','NoSuchObject'):return None
        raise


def verify_object(client,bucket,key,digest,size,version=None):
    info=client.stat_object(bucket,key,version_id=version)
    if info.size!=size:raise ConflictError('Tamaño S3 conflictivo: '+key)
    response=client.get_object(bucket,key,version_id=version)
    hasher=hashlib.sha256()
    try:
        for chunk in response.stream(1024*1024):hasher.update(chunk)
    finally:response.close();response.release_conn()
    if hasher.hexdigest()!=digest:raise ConflictError('Contenido S3 conflictivo: '+key)
    if not info.version_id or info.version_id=='null':raise ConflictError('Objeto sin versión: '+key)
    return info.version_id


def upload_immutable(client,bucket,key,path,digest,size):
    existing=stat_optional(client,bucket,key)
    if existing is None:
        client.fput_object(bucket,key,str(path),metadata={'sha256':digest})
    return verify_object(client,bucket,key,digest,size)


def copy_immutable(client,item):
    key=item['object_key']
    verify_object(client,QUARANTINE,key,item['sha256'],item['size_bytes'],item['quarantine_version'])
    existing=stat_optional(client,RELEASED,key)
    if existing is None:
        client.copy_object(RELEASED,key,CopySource(QUARANTINE,key,version_id=item['quarantine_version']))
    return verify_object(client,RELEASED,key,item['sha256'],item['size_bytes'])
