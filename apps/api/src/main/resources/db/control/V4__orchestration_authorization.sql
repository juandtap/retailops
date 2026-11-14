CREATE TABLE control.monthly_authorizations (
 batch_id text PRIMARY KEY CHECK(batch_id ~ '^20(15|16|17)-(0[1-9]|1[0-2])$'),
 authorization_id uuid NOT NULL UNIQUE,
 previous_cutoff date NOT NULL, period_end date NOT NULL,
 expected_rows bigint NOT NULL CHECK(expected_rows>0),
 authorized_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 gold_complete boolean NOT NULL DEFAULT false
);
GRANT SELECT ON control.monthly_authorizations TO retailops_ingestor,retailops_releaser,retailops_data_migrator;
GRANT UPDATE(gold_complete) ON control.monthly_authorizations TO retailops_data_migrator;
CREATE FUNCTION control.authorize_month(batch text, identifier uuid, cutoff date, ending date, rows_expected bigint) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE active date;
BEGIN
 SELECT released_through INTO active FROM control.historical_state WHERE singleton FOR UPDATE;
 IF active IS DISTINCT FROM cutoff OR batch<>to_char(active+1,'YYYY-MM') OR batch<'2015-01' OR batch>'2017-08'
 OR ending<active+1 OR ending> (date_trunc('month',active+1)+interval '1 month-1 day')::date THEN
 RAISE EXCEPTION 'Mes fuera de secuencia/corte autorizado'; END IF;
 IF EXISTS(SELECT 1 FROM control.monthly_authorizations WHERE NOT gold_complete AND batch_id<>batch) THEN
 RAISE EXCEPTION 'Completar GOLD anterior antes de otra autorización'; END IF;
 IF EXISTS(SELECT 1 FROM control.monthly_authorizations WHERE batch_id=batch) THEN
 RETURN (SELECT authorization_id FROM control.monthly_authorizations WHERE batch_id=batch);
 END IF;
 INSERT INTO control.monthly_authorizations(batch_id,authorization_id,previous_cutoff,period_end,expected_rows)
 VALUES(batch,identifier,cutoff,ending,rows_expected);
 RETURN identifier;
END $$;
REVOKE ALL ON FUNCTION control.authorize_month(text,uuid,date,date,bigint) FROM PUBLIC;
-- La API operadora NO se monta en los contenedores de Airflow.
GRANT EXECUTE ON FUNCTION control.authorize_month(text,uuid,date,date,bigint) TO retailops_api;
CREATE FUNCTION control.guard_monthly_authorization() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.kind='MONTHLY' AND NOT EXISTS(
 SELECT 1 FROM control.monthly_authorizations a CROSS JOIN control.historical_state h
 WHERE a.batch_id=NEW.batch_id AND (a.previous_cutoff=h.released_through OR (NEW.batch_id=h.last_batch_id AND a.period_end=h.released_through))
 AND NEW.period_start=a.previous_cutoff+1 AND NEW.period_end=a.period_end AND NEW.row_count=a.expected_rows) THEN
 RAISE EXCEPTION 'No existe autorización mensual explícita compatible'; END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION control.guard_monthly_authorization() FROM PUBLIC;
CREATE TRIGGER require_monthly_authorization BEFORE INSERT ON control.batches FOR EACH ROW EXECUTE FUNCTION control.guard_monthly_authorization();
CREATE FUNCTION control.require_released_snapshot(cutoff date) RETURNS date
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE active date;
BEGIN
 SELECT h.released_through INTO active FROM control.historical_state h JOIN control.batches b ON b.batch_id=h.last_batch_id
 JOIN control.publications p USING(batch_id) WHERE h.released_through=cutoff AND b.state='RELEASED' AND p.status='COMPLETE' FOR SHARE OF h,b,p;
 IF active IS NULL THEN RAISE EXCEPTION 'Snapshot no publicado completamente'; END IF;
 RETURN active;
END $$;
REVOKE ALL ON FUNCTION control.require_released_snapshot(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.require_released_snapshot(date) TO retailops_ingestor;
CREATE TABLE control.orchestration_runs (
 logical_id text PRIMARY KEY, snapshot date NOT NULL, status text NOT NULL CHECK(status IN('RUNNING','SUCCEEDED','FAILED')),
 result jsonb, error_code text, updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
GRANT SELECT,INSERT,UPDATE ON control.orchestration_runs TO retailops_ingestor;
