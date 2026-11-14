"""Conexión restringida y consultas acotadas; solo abre el archivo de contraseña trainer."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import os
import math
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row
from .queries import QUERIES

ROOT=Path(__file__).resolve().parents[2]
START=date(2013,1,1)
CUTOFF=date(2014,12,31)
BATCH='bootstrap-2013-2014'
MAX_ROWS=5000

@dataclass(frozen=True)
class Config:
    host: str='127.0.0.1'
    port: int=5432
    database: str='retailops'
    password_file: Path=ROOT/'.local/secrets/pg_trainer_password'

    @classmethod
    def environment(cls):
        return cls(host=os.environ.get('EDA_PG_HOST','127.0.0.1'),port=int(os.environ.get('EDA_PG_PORT','5432')),
                   database=os.environ.get('EDA_PG_DATABASE','retailops'),
                   password_file=Path(os.environ.get('EDA_PASSWORD_FILE',str(ROOT/'.local/secrets/pg_trainer_password'))))

    def validate(self):
        if self.host not in ('127.0.0.1','localhost','postgres') or not 1<=self.port<=65535:
            raise ValueError('Solo se admite PostgreSQL local o DNS interno postgres y puerto válido')
        # No aceptar por configuración otro archivo de credenciales del proyecto.
        path=self.password_file.resolve()
        if path.name!='pg_trainer_password' or self.password_file.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError('Se requiere el archivo restringido de credenciales trainer (0600)')

@contextmanager
def connection(config=None):
    config=config or Config.environment();config.validate()
    password=config.password_file.read_text().strip()
    if not password:raise ValueError('La credencial trainer está vacía')
    try:
        conn=psycopg.connect(host=config.host,port=config.port,dbname=config.database,user='retailops_trainer',
          password=password,row_factory=dict_row,connect_timeout=5,application_name='retailops-eda',
          options='-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000 -c idle_in_transaction_session_timeout=30000 -c search_path=pg_catalog,training')
    except psycopg.Error:
        raise RuntimeError('No se pudo conectar como trainer. Revisar servicio y configuración local sin mostrar secretos.') from None
    try:
        yield conn
    finally:
        conn.rollback();conn.close()


def query(name,*,config=None,**parameters):
    if name not in QUERIES:raise ValueError('Consulta no autorizada')
    if set(parameters)-{'threshold','stores','families'}:raise ValueError('No se puede cambiar período, lote ni SQL')
    if name=='store_daily' and (not parameters.get('stores') or len(parameters['stores'])>3):raise ValueError('Máximo tres tiendas por consulta temporal')
    if name=='family_daily' and (not parameters.get('families') or len(parameters['families'])>3):raise ValueError('Máximo tres familias por consulta temporal')
    if name=='extremes' and (not isinstance(parameters.get('threshold'),(int,float,Decimal)) or not math.isfinite(float(parameters['threshold'])) or parameters['threshold']<0):raise ValueError('Umbral extremo inválido')
    params={'start':START,'end':CUTOFF,'batch':BATCH,**parameters}
    with connection(config) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM ('+QUERIES[name]+') AS eda_result LIMIT '+str(MAX_ROWS+1),params)
                rows=cursor.fetchmany(MAX_ROWS+1)
                if len(rows)>MAX_ROWS:raise ValueError('La consulta excede el máximo de filas permitido')
                frame=pd.DataFrame(rows,columns=[column.name for column in cursor.description])
        except psycopg.Error as exc:
            raise RuntimeError(f'Consulta {name} rechazada (SQLSTATE {exc.sqlstate}); revisar límites y contrato sin elevar privilegios.') from None
    for column in frame.columns:
        if column in ('date','month','first_date','last_date'):frame[column]=pd.to_datetime(frame[column])
    return frame


def validate_bootstrap():
    session=query('session').iloc[0]
    if session['role']!='retailops_trainer' or session['read_only']!='on' or session['silver_access'] or session['control_access']:
        raise ValueError('La conexión no cumple el contrato de acceso restringido')
    overview=query('overview').iloc[0]
    if int(overview['records'])!=1297296 or overview['first_date'].date()!=START or overview['last_date'].date()!=CUTOFF:
        raise ValueError('El bootstrap visible no coincide con el período autorizado')
    if bool(query('future_visible').iloc[0]['future_visible']):raise ValueError('Hay fechas posteriores visibles: detener el EDA')
    return overview
