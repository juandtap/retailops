"""Perfilado por bloques con índices temporales en disco y agregados acotados."""
from __future__ import annotations

import calendar
import csv
import hashlib
import math
import sqlite3
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from itertools import islice
from pathlib import Path

SCHEMAS = {
    "train.csv": {"id": "BIGINT", "date": "DATE", "store_nbr": "SMALLINT", "family": "TEXT", "sales": "NUMERIC", "onpromotion": "INTEGER"},
    "test.csv": {"id": "BIGINT", "date": "DATE", "store_nbr": "SMALLINT", "family": "TEXT", "onpromotion": "INTEGER"},
    "stores.csv": {"store_nbr": "SMALLINT", "city": "TEXT", "state": "TEXT", "type": "TEXT", "cluster": "SMALLINT"},
    "holidays_events.csv": {"date": "DATE", "type": "TEXT", "locale": "TEXT", "locale_name": "TEXT", "description": "TEXT", "transferred": "BOOLEAN"},
    "oil.csv": {"date": "DATE", "dcoilwtico": "NUMERIC"},
    "transactions.csv": {"date": "DATE", "store_nbr": "SMALLINT", "transactions": "INTEGER"},
    "sample_submission.csv": {"id": "BIGINT", "sales": "NUMERIC"},
}
KEYS = {"train.csv": ["date", "store_nbr", "family"], "test.csv": ["date", "store_nbr", "family"], "stores.csv": ["store_nbr"], "oil.csv": ["date"], "transactions.csv": ["date", "store_nbr"], "sample_submission.csv": ["id"]}
CATEGORICAL = {"store_nbr", "family", "city", "state", "type", "cluster", "locale", "locale_name", "description", "transferred"}


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table(filename: str) -> str:
    return quote(filename.removesuffix(".csv"))


@lru_cache(maxsize=16384)
def value_kind(value: str | None) -> str:
    if value is None or not value.strip():
        return "null"
    if value in {"True", "False", "true", "false"}:
        return "boolean"
    try:
        int(value)
        return "integer"
    except ValueError:
        pass
    try:
        number = float(value)
        return "decimal" if math.isfinite(number) else "non_finite"
    except ValueError:
        pass
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            date.fromisoformat(value)
            return "date"
        except ValueError:
            pass
    return "text"


def inferred_type(kinds: Counter) -> str:
    present = set(kinds) - {"null"}
    if not present:
        return "desconocido (solo nulos)"
    if present <= {"integer", "decimal"}:
        return "decimal" if "decimal" in present else "integer"
    if len(present) == 1:
        return next(iter(present))
    return "mixto: " + ", ".join(sorted(present))


class ColumnSummary:
    def __init__(self):
        self.kinds = Counter()
        self.count = self.zero = self.negative = self.fractional = 0
        self.minimum = self.maximum = None
        self.mean = self.m2 = 0.0

    def add(self, value):
        kind = value_kind(value)
        self.kinds[kind] += 1
        if kind not in {"integer", "decimal"}:
            return
        number = float(value)
        self.count += 1
        self.zero += number == 0
        self.negative += number < 0
        self.fractional += not number.is_integer()
        self.minimum = number if self.minimum is None else min(number, self.minimum)
        self.maximum = number if self.maximum is None else max(number, self.maximum)
        delta = number - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (number - self.mean)

    def numeric(self):
        if not self.count:
            return None
        return {"count": self.count, "min": self.minimum, "max": self.maximum, "mean": self.mean,
                "std_population": math.sqrt(max(0, self.m2 / self.count)), "zero": self.zero,
                "negative": self.negative, "fractional": self.fractional}


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def duplicate_excess(conn, name, columns):
    group = ",".join(map(quote, columns))
    return conn.execute(f"SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM {table(name)} GROUP BY {group} HAVING COUNT(*)>1)").fetchone()[0]


def exact_quantiles(conn, name, column, count, filter_numeric=False):
    """Percentiles lineales exactos, índice temporal en disco para no ordenar en RAM."""
    if not count:
        return {}
    conn.execute('DROP TABLE IF EXISTS numeric_order')
    predicate = f"kind({quote(column)}) IN ('integer','decimal')" if filter_numeric else f"{quote(column)} IS NOT NULL"
    conn.execute(f'CREATE TABLE numeric_order AS SELECT CAST({quote(column)} AS REAL) value FROM {table(name)} WHERE {predicate}')
    conn.execute('CREATE INDEX numeric_value ON numeric_order(value)')
    result = {}
    for q in (0.25, 0.5, 0.75, 0.95, 0.99):
        position = (count - 1) * q
        low = math.floor(position)
        values = [row[0] for row in conn.execute('SELECT value FROM numeric_order ORDER BY value LIMIT 2 OFFSET ?', (low,))]
        result[str(q)] = values[0] if len(values) == 1 else values[0] + (values[1] - values[0]) * (position - low)
    conn.execute('DROP TABLE numeric_order')
    return result


def profile_file(conn, path: Path, batch_size=10000):
    if batch_size <= 0:
        raise ValueError("El tamaño de bloque debe ser positivo")
    before = checksum(path)
    summaries = {}
    rows = malformed = 0
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        columns = next(reader, [])
        if not columns or len(set(columns)) != len(columns) or any(not c for c in columns):
            raise ValueError(f"Cabecera ausente o ambigua: {path.name}")
        summaries = {column: ColumnSummary() for column in columns}
        conn.execute(f'CREATE TABLE {table(path.name)} ({",".join(quote(c)+" TEXT" for c in columns)})')
        statement = f'INSERT INTO {table(path.name)} VALUES ({",".join("?" for _ in columns)})'
        while batch := list(islice(reader, batch_size)):
            valid = []
            for row in batch:
                rows += 1
                if len(row) != len(columns):
                    malformed += 1
                    continue
                normalized = [None if not v.strip() else v for v in row]
                for column, value in zip(columns, normalized):
                    summaries[column].add(value)
                valid.append(normalized)
            conn.executemany(statement, valid)
            conn.commit()
    after = checksum(path)
    if before != after:
        raise RuntimeError(f"La fuente cambió durante el perfilado: {path.name}")
    result = {"status": "analizado", "sha256": before, "source_unchanged": True, "bytes": path.stat().st_size,
              "rows": rows, "valid_rows": rows - malformed, "malformed_rows": malformed,
              "column_count": len(columns), "schema_matches": columns == list(SCHEMAS[path.name]), "columns": {}}
    for column, summary in summaries.items():
        quoted = quote(column)
        cardinality = conn.execute(f'SELECT COUNT(DISTINCT {quoted}) FROM {table(path.name)}').fetchone()[0]
        recommendation = SCHEMAS[path.name].get(column, "TEXT (revisar)")
        allowed = {"integer", "decimal"} if recommendation == "NUMERIC" else {"integer"} if recommendation in {"BIGINT", "SMALLINT", "INTEGER"} else {"date"} if recommendation == "DATE" else {"boolean"} if recommendation == "BOOLEAN" else None
        profile = {"inferred_type": inferred_type(summary.kinds), "recommended_type": recommendation,
                   "nulls": summary.kinds['null'], "cardinality": cardinality,
                   "kind_counts": dict(sorted(summary.kinds.items())),
                   "invalid_for_recommended_type": sum(n for k,n in summary.kinds.items() if k != "null" and allowed is not None and k not in allowed)}
        if column in CATEGORICAL:
            profile['top_values'] = conn.execute(f'SELECT {quoted}, COUNT(*) n FROM {table(path.name)} WHERE {quoted} IS NOT NULL GROUP BY {quoted} ORDER BY n DESC, {quoted} LIMIT 10').fetchall()
        if recommendation == "DATE":
            profile['date_range'] = conn.execute(f"SELECT MIN({quoted}), MAX({quoted}) FROM {table(path.name)} WHERE kind({quoted})='date'").fetchone()
        if numeric := summary.numeric():
            # Cuantiles relevantes para demanda, promociones, petróleo y transacciones.
            if column in {"sales", "onpromotion", "transactions", "dcoilwtico"}:
                numeric['quantiles'] = exact_quantiles(conn, path.name, column, numeric['count'], sum(n for k,n in summary.kinds.items() if k not in {'null','integer','decimal'}) > 0)
            profile['numeric'] = numeric
        result['columns'][column] = profile
    result['duplicate_rows_excess'] = duplicate_excess(conn, path.name, columns)
    if 'id' in summaries:
        result['duplicate_ids_excess'] = rows - malformed - summaries['id'].kinds['null'] - result['columns']['id']['cardinality']
    if key := KEYS.get(path.name):
        if set(key) <= set(columns):
            result['natural_key'] = key
            result['duplicate_keys_excess'] = duplicate_excess(conn, path.name, key)
            result['null_key_rows'] = conn.execute(f'SELECT COUNT(*) FROM {table(path.name)} WHERE '+ ' OR '.join(quote(c)+' IS NULL' for c in key)).fetchone()[0]
            conn.execute(f'CREATE INDEX {quote(path.stem+"_natural_key")} ON {table(path.name)} ({",".join(map(quote,key))})')
    return result


def day_range(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def month_status(start: date, dates: set[str], row_count: int, expected_series: int, distinct_keys: int):
    end = date(start.year, start.month, calendar.monthrange(start.year,start.month)[1])
    missing = [day.isoformat() for day in day_range(start,end) if day.isoformat() not in dates]
    expected = end.day * expected_series
    complete = not missing and row_count == distinct_keys == expected
    observed_grid_complete = row_count == distinct_keys == len(dates) * expected_series
    return {"calendar_complete": not missing, "observed_grid_complete": observed_grid_complete,
            "duplicate_key_rows": row_count - distinct_keys,
            "missing_expected_rows": max(0, expected - distinct_keys),
            "period_start": start.isoformat(), "period_end": end.isoformat(),
            "observed_start": min(dates) if dates else None, "observed_end": max(dates) if dates else None,
            "rows": row_count, "distinct_keys": distinct_keys, "expected_rows_calendar": expected,
            "observed_days": len(dates), "calendar_days": end.day, "missing_dates": missing,
            "completeness": "COMPLETE" if complete else "INCOMPLETE", "released": False}


def sales_coverage(conn, include_transactions=False):
    stores = [r[0] for r in conn.execute('SELECT DISTINCT store_nbr FROM train ORDER BY CAST(store_nbr AS INTEGER)')]
    families = [r[0] for r in conn.execute('SELECT DISTINCT family FROM train ORDER BY family')]
    expected_series = len(stores) * len(families)
    daily = {r[0]: {'rows':r[1], 'keys':r[2]} for r in conn.execute("SELECT date,SUM(n),COUNT(*) FROM (SELECT date,store_nbr,family,COUNT(*) n FROM train WHERE kind(date)='date' GROUP BY date,store_nbr,family) GROUP BY date ORDER BY date")}
    if not daily:
        return {"status": "sin fechas válidas"}, {"bootstrap": None, "incremental_batches": []}
    first, last = date.fromisoformat(min(daily)), date.fromisoformat(max(daily))
    missing = [d.isoformat() for d in day_range(first,last) if d.isoformat() not in daily]
    current = first.replace(day=1)
    months = []
    while current <= last:
        prefix = current.strftime('%Y-%m')
        days = {d for d in daily if d.startswith(prefix)}
        month = month_status(current, days, sum(daily[d]['rows'] for d in days), expected_series, sum(daily[d]['keys'] for d in days))
        months.append({"batch_id": prefix, **month})
        current = (current.replace(day=28)+timedelta(days=4)).replace(day=1)
    series = [{"store_nbr":int(s), "family":f, "rows":n, "observed_days":days, "first_date":a, "last_date":b,
               "missing_days_in_train_calendar": (last-first).days+1-days}
              for s,f,n,days,a,b in conn.execute('SELECT store_nbr,family,COUNT(*),COUNT(DISTINCT date),MIN(date),MAX(date) FROM train GROUP BY store_nbr,family ORDER BY CAST(store_nbr AS INTEGER),family')]
    store_coverage = [dict(zip(['store_nbr','rows','observed_days','families','first_date','last_date'],r)) for r in conn.execute('SELECT CAST(store_nbr AS INTEGER),COUNT(*),COUNT(DISTINCT date),COUNT(DISTINCT family),MIN(date),MAX(date) FROM train GROUP BY store_nbr ORDER BY CAST(store_nbr AS INTEGER)')]
    family_coverage = [dict(zip(['family','rows','observed_days','stores','first_date','last_date'],r)) for r in conn.execute('SELECT family,COUNT(*),COUNT(DISTINCT date),COUNT(DISTINCT store_nbr),MIN(date),MAX(date) FROM train GROUP BY family ORDER BY family')]
    bootstrap_months = [m for m in months if '2013-01' <= m['batch_id'] <= '2014-12']
    bootstrap_rows = conn.execute("SELECT COUNT(*) FROM train WHERE date BETWEEN '2013-01-01' AND '2014-12-31'").fetchone()[0]
    bootstrap_missing = [d.isoformat() for d in day_range(date(2013,1,1),date(2014,12,31)) if d.isoformat() not in daily]
    bootstrap = {"batch_id":"bootstrap-2013-2014", "period_start":"2013-01-01", "period_end":"2014-12-31", "rows":bootstrap_rows,
                 "expected_rows_calendar":730*expected_series, "missing_dates":bootstrap_missing,
                 "completeness":"COMPLETE" if len(bootstrap_months)==24 and all(m['completeness']=='COMPLETE' for m in bootstrap_months) else "INCOMPLETE", "released":False}
    promotion_start = conn.execute('SELECT MIN(date) FROM train WHERE CAST(onpromotion AS REAL)>0').fetchone()[0]
    yearly = [dict(zip(['year','rows','promoted_rows','sales_zero_rows','positive_sales_missing_transactions'],r)) for r in conn.execute("SELECT substr(t.date,1,4),COUNT(*),SUM(CAST(t.onpromotion AS REAL)>0),SUM(kind(t.sales) IN ('integer','decimal') AND CAST(t.sales AS REAL)=0),SUM(CAST(t.sales AS REAL)>0 AND NOT EXISTS(SELECT 1 FROM transactions x WHERE x.date=t.date AND x.store_nbr=t.store_nbr)) FROM train t GROUP BY substr(t.date,1,4)")] if include_transactions else []
    coverage = {"first_date":first.isoformat(), "last_date":last.isoformat(), "stores":len(stores), "families":len(families),
                "expected_series":expected_series, "observed_series":len(series), "observed_days":len(daily), "missing_dates":missing,
                "days_with_unexpected_granularity":{d:v for d,v in daily.items() if v['rows']!=expected_series or v['keys']!=expected_series},
                "months":months, "series":series, "by_store":store_coverage, "by_family":family_coverage,
                "first_positive_promotion_date":promotion_start, "by_year":yearly}
    return coverage, {"bootstrap":bootstrap, "incremental_batches":[m for m in months if m['batch_id']>='2015-01']}


def relationships(conn, profiles):
    def available(*names):
        return all(profiles[n].get('schema_matches') and profiles[n].get('malformed_rows')==0 for n in names)
    results = {}
    def scalar(key, sql):
        results[key] = conn.execute(sql).fetchone()[0]
    for name in ('train.csv','test.csv','transactions.csv'):
        if available(name,'stores.csv'):
            scalar(name+'.orphan_store_rows', f'SELECT COUNT(*) FROM {table(name)} x WHERE NOT EXISTS (SELECT 1 FROM stores s WHERE s.store_nbr=x.store_nbr)')
    if available('train.csv','test.csv'):
        scalar('test.unknown_families', 'SELECT COUNT(DISTINCT family) FROM test WHERE family NOT IN (SELECT DISTINCT family FROM train)')
        scalar('train_test.overlapping_ids','SELECT COUNT(*) FROM test e WHERE EXISTS(SELECT 1 FROM train t WHERE t.id=e.id)')
        scalar('train_test.overlapping_keys','SELECT COUNT(*) FROM test e WHERE EXISTS(SELECT 1 FROM train t WHERE t.date=e.date AND t.store_nbr=e.store_nbr AND t.family=e.family)')
        results['test.date_range'] = conn.execute('SELECT MIN(date),MAX(date),COUNT(DISTINCT date) FROM test').fetchone()
    if available('test.csv','sample_submission.csv'):
        scalar('test.ids_missing_submission','SELECT COUNT(*) FROM test t WHERE NOT EXISTS(SELECT 1 FROM sample_submission s WHERE s.id=t.id)')
        scalar('submission.ids_missing_test','SELECT COUNT(*) FROM sample_submission s WHERE NOT EXISTS(SELECT 1 FROM test t WHERE t.id=s.id)')
    if available('train.csv','transactions.csv'):
        conn.execute('CREATE TABLE store_days AS SELECT date,store_nbr,SUM(CAST(sales AS REAL)) sales FROM train GROUP BY date,store_nbr')
        conn.execute('CREATE INDEX store_day_key ON store_days(date,store_nbr)')
        scalar('transactions.rows_without_sales_key','SELECT COUNT(*) FROM transactions t WHERE NOT EXISTS(SELECT 1 FROM store_days s WHERE s.date=t.date AND s.store_nbr=t.store_nbr)')
        scalar('train.store_days_missing_transactions','SELECT COUNT(*) FROM store_days s WHERE NOT EXISTS(SELECT 1 FROM transactions t WHERE s.date=t.date AND s.store_nbr=t.store_nbr)')
        scalar('train.positive_store_days_missing_transactions','SELECT COUNT(*) FROM store_days s WHERE sales>0 AND NOT EXISTS(SELECT 1 FROM transactions t WHERE s.date=t.date AND s.store_nbr=t.store_nbr)')
        scalar('train.zero_store_days_with_transactions','SELECT COUNT(*) FROM store_days s WHERE sales=0 AND EXISTS(SELECT 1 FROM transactions t WHERE s.date=t.date AND s.store_nbr=t.store_nbr)')
    if available('train.csv','oil.csv'):
        days = [r[0] for r in conn.execute('SELECT DISTINCT date FROM train ORDER BY date')]
        oil = dict(conn.execute('SELECT date,dcoilwtico FROM oil'))
        results['oil.train_days_without_row'] = sum(d not in oil for d in days)
        results['oil.train_days_with_null'] = sum(d in oil and oil[d] is None for d in days)
        results['oil.train_days_without_observation'] = sum(oil.get(d) is None for d in days)
    if available('holidays_events.csv','stores.csv'):
        scalar('holidays.local_names_not_in_store_cities', "SELECT COUNT(*) FROM holidays_events WHERE locale='Local' AND locale_name NOT IN (SELECT city FROM stores)")
        scalar('holidays.regional_names_not_in_store_states', "SELECT COUNT(*) FROM holidays_events WHERE locale='Regional' AND locale_name NOT IN (SELECT state FROM stores)")
        results['holidays.multi_event_dates'] = conn.execute('SELECT date,COUNT(*) n FROM holidays_events GROUP BY date HAVING n>1 ORDER BY date').fetchall()
        results['holidays.type_transferred'] = conn.execute('SELECT type,transferred,COUNT(*) FROM holidays_events GROUP BY type,transferred ORDER BY type,transferred').fetchall()
    return results


def analyze(source: Path, conn: sqlite3.Connection, batch_size=10000, progress=None):
    conn.execute('PRAGMA cache_size=-16384')
    conn.execute('PRAGMA temp_store=FILE')
    conn.create_function('kind',1,value_kind,deterministic=True)
    profiles = {}
    # Dimensiones pequeñas primero; el orden es determinista.
    for name in ('stores.csv','holidays_events.csv','oil.csv','transactions.csv','sample_submission.csv','test.csv','train.csv'):
        if progress:
            progress(f'Analizando {name}…')
        path = source/name
        profiles[name] = profile_file(conn,path,batch_size) if path.is_file() else {'status':'faltante'}
    # Los índices ID permiten comprobar relaciones sin cruces cuadráticos.
    for name in ('train.csv','test.csv','sample_submission.csv'):
        if 'id' in profiles[name].get('columns',{}):
            conn.execute(f'CREATE INDEX {quote(Path(name).stem+"_id")} ON {table(name)}(id)')
    if progress:
        progress('Comprobando relaciones, cobertura y lotes…')
    relations = relationships(conn, profiles)
    coverage, manifest = ({'status':'train ausente o esquema incompatible'}, {'bootstrap':None,'incremental_batches':[]})
    train = profiles['train.csv']
    key_compatible = train.get('schema_matches') and not train.get('malformed_rows') and not train.get('null_key_rows') and all(
        train['columns'][c]['invalid_for_recommended_type'] == 0 for c in ('date','store_nbr'))
    if key_compatible:
        coverage, manifest = sales_coverage(conn, profiles['transactions.csv'].get('schema_matches',False) and not profiles['transactions.csv'].get('malformed_rows',0))
    elif train.get('schema_matches'):
        coverage = {'status':'claves nulas, tipos de clave incompatibles o filas malformadas; no se certifica cobertura'}
    return {'format_version':1,'files':profiles,'relationships':relations,'sales_coverage':coverage}, {
        'format_version':1, 'purpose':'PLAN_ONLY', 'historical_cutoff':None,
        'release_performed':False,'source_sha256':profiles['train.csv'].get('sha256'), **manifest}
