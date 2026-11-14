-- Propietario: ingeniería de datos. Historial Flyway independiente en data_meta.
REVOKE ALL ON SCHEMA data_meta, silver, gold, training FROM PUBLIC;

-- Impide añadir observaciones a un lote después de su liberación.
CREATE FUNCTION data_meta.require_unreleased_batch() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $function$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM control.batches WHERE batch_id=NEW.batch_id AND state <> 'RELEASED' FOR SHARE) THEN
   RAISE EXCEPTION 'El lote no existe o ya fue liberado' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END
$function$;
REVOKE ALL ON FUNCTION data_meta.require_unreleased_batch() FROM PUBLIC;

CREATE TABLE silver.stores (
    store_nbr smallint PRIMARY KEY CHECK (store_nbr > 0),
    city text NOT NULL CHECK (city <> ''),
    state text NOT NULL CHECK (state <> ''),
    store_type text NOT NULL CHECK (store_type <> ''),
    cluster smallint NOT NULL CHECK (cluster > 0),
    known_from date CHECK (isfinite(known_from)),
    availability_evidence text,
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.stores WITH (security_barrier=true) AS
SELECT d.store_nbr,d.city,d.state,d.store_type,d.cluster,d.known_from, d.batch_id
FROM silver.stores d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE TABLE silver.families (
    family text PRIMARY KEY CHECK (family <> ''),
    known_from date CHECK (isfinite(known_from)),
    availability_evidence text,
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.families WITH (security_barrier=true) AS
SELECT d.family,d.known_from, d.batch_id
FROM silver.families d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE TABLE silver.sales (
    date date NOT NULL CHECK (isfinite(date)),
    store_nbr smallint NOT NULL REFERENCES silver.stores(store_nbr),
    family text NOT NULL REFERENCES silver.families(family),
    source_id bigint NOT NULL UNIQUE CHECK (source_id >= 0),
    sales numeric NOT NULL CHECK (sales >= 0 AND sales < 'Infinity'::numeric),
    onpromotion integer NOT NULL CHECK (onpromotion >= 0),
    PRIMARY KEY (date,store_nbr,family),
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.sales WITH (security_barrier=true) AS
SELECT d.date,d.store_nbr,d.family,d.sales, d.batch_id
FROM silver.sales d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through;

CREATE TABLE silver.holidays_events (
    event_id uuid PRIMARY KEY,
    date date NOT NULL CHECK (isfinite(date)),
    event_type text NOT NULL CHECK (event_type IN ('Holiday','Transfer','Additional','Bridge','Event','Work Day')),
    locale text NOT NULL CHECK (locale IN ('National','Regional','Local')),
    locale_name text NOT NULL CHECK (locale_name <> ''),
    description text NOT NULL,
    transferred boolean NOT NULL,
    known_from date CHECK (isfinite(known_from)),
    availability_evidence text,
    UNIQUE (date,event_type,locale,locale_name,description,transferred),
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.holidays_events WITH (security_barrier=true) AS
SELECT d.event_id,d.date,d.event_type,d.locale,d.locale_name,d.description,d.transferred,d.known_from, d.batch_id
FROM silver.holidays_events d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE TABLE silver.oil_prices (
    date date PRIMARY KEY CHECK (isfinite(date)),
    dcoilwtico numeric CHECK (dcoilwtico > 0 AND dcoilwtico < 'Infinity'::numeric),
    known_from date CHECK (isfinite(known_from)),
    availability_evidence text,
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.oil_prices WITH (security_barrier=true) AS
SELECT d.date,d.dcoilwtico,d.known_from, d.batch_id
FROM silver.oil_prices d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE TABLE silver.store_transactions (
    date date NOT NULL CHECK (isfinite(date)),
    store_nbr smallint NOT NULL REFERENCES silver.stores(store_nbr),
    transactions integer NOT NULL CHECK (transactions >= 0),
    PRIMARY KEY (date,store_nbr),
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.store_transactions WITH (security_barrier=true) AS
SELECT d.date,d.store_nbr,d.transactions, d.batch_id
FROM silver.store_transactions d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through;

CREATE TABLE silver.observation_gaps (
    date date NOT NULL CHECK (isfinite(date)),
    entity text NOT NULL CHECK (entity IN ('sales','oil','transactions')),
    scope_key text NOT NULL,
    reason text NOT NULL CHECK (reason IN ('NOT_IN_SOURCE','UNKNOWN','PARTIAL_PERIOD')),
    PRIMARY KEY (date,entity,scope_key),
    batch_id text NOT NULL,
    source_sha256 text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (batch_id,source_sha256) REFERENCES control.batch_sources(batch_id,source_sha256)
);

CREATE VIEW training.observation_gaps WITH (security_barrier=true) AS
SELECT d.date,d.entity,d.scope_key,d.reason, d.batch_id
FROM silver.observation_gaps d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through;


CREATE VIEW training.holiday_features WITH (security_barrier=true) AS
SELECT e.date,s.store_nbr,
       bool_or(NOT e.transferred AND e.event_type IN ('Holiday','Transfer','Additional','Bridge')) AS active_holiday,
       bool_or(e.event_type='Event') AS has_event,
       bool_or(e.event_type='Work Day') AS has_work_day,
       count(*) AS event_count
FROM training.holidays_events e
JOIN training.stores s ON e.locale='National'
   OR (e.locale='Regional' AND e.locale_name=s.state)
   OR (e.locale='Local' AND e.locale_name=s.city)
GROUP BY e.date,s.store_nbr;

GRANT USAGE ON SCHEMA silver TO retailops_ingestor;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA silver TO retailops_ingestor;
GRANT USAGE ON SCHEMA training TO retailops_trainer, retailops_api;
GRANT SELECT ON ALL TABLES IN SCHEMA training TO retailops_trainer, retailops_api;
-- onpromotion se conserva en Silver pero no se expone como feature sin evidencia de conocimiento.
-- No se concede USAGE de silver/control/data_meta/gold al entrenador ni CREATE/TEMP en la base.

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.stores FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.families FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.sales FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.holidays_events FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.oil_prices FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.store_transactions FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();

CREATE TRIGGER require_unreleased_batch BEFORE INSERT ON silver.observation_gaps FOR EACH ROW EXECUTE FUNCTION data_meta.require_unreleased_batch();
