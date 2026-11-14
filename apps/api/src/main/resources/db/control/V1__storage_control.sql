-- Propietario: plano de control. No se registran lotes ni ejecuciones reales.
CREATE TABLE control.source_files (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    filename text NOT NULL CHECK (filename IN ('train.csv','stores.csv','holidays_events.csv','oil.csv','transactions.csv','test.csv','sample_submission.csv')),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    registered_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE control.batches (
    batch_id text PRIMARY KEY CHECK (length(batch_id) BETWEEN 1 AND 128),
    kind text NOT NULL CHECK (kind IN ('BOOTSTRAP','MONTHLY','AUXILIARY')),
    entity text NOT NULL,
    period_start date NOT NULL CHECK (isfinite(period_start)),
    period_end date NOT NULL CHECK (isfinite(period_end) AND period_end >= period_start),
    state text NOT NULL DEFAULT 'PLANNED' CHECK (state IN ('PLANNED','STAGED','VALIDATED','RELEASED','FAILED')),
    row_count bigint CHECK (row_count >= 0),
    released_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (kind, entity, period_start, period_end),
    CHECK ((state = 'RELEASED') = (released_at IS NOT NULL))
);
CREATE TABLE control.batch_sources (
    batch_id text REFERENCES control.batches(batch_id),
    source_sha256 text REFERENCES control.source_files(sha256),
    PRIMARY KEY (batch_id, source_sha256)
);
CREATE TABLE control.historical_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    released_through date CHECK (isfinite(released_through)),
    last_batch_id text REFERENCES control.batches(batch_id),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((released_through IS NULL) = (last_batch_id IS NULL))
);
-- Estado técnico inicial, sin histórico liberado.
INSERT INTO control.historical_state(singleton) VALUES (true);
CREATE TABLE control.objects (
    bucket text NOT NULL CHECK (bucket IN ('retailops-quarantine','retailops-released','retailops-artifacts')),
    object_key text NOT NULL CHECK (length(object_key) > 0),
    version_id text NOT NULL CHECK (length(version_id) > 0),
    batch_id text NOT NULL REFERENCES control.batches(batch_id),
    layer text NOT NULL CHECK (layer IN ('RAW','BRONZE','ARTIFACT')),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    registered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (bucket, object_key, version_id)
);
CREATE TABLE control.ingestion_runs (
    run_id uuid PRIMARY KEY,
    batch_id text NOT NULL REFERENCES control.batches(batch_id),
    status text NOT NULL CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')),
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    started_at timestamptz,
    finished_at timestamptz,
    airflow_run_id text UNIQUE,
    processed_rows bigint CHECK (processed_rows >= 0),
    error_code text,
    CHECK (status <> 'FAILED' OR error_code IS NOT NULL),
    CHECK (status NOT IN ('SUCCEEDED','FAILED') OR finished_at IS NOT NULL)
);
REVOKE ALL ON SCHEMA control FROM PUBLIC;
GRANT USAGE ON SCHEMA control TO retailops_data_migrator, retailops_api, retailops_ingestor, retailops_releaser;
GRANT SELECT, REFERENCES ON control.batches, control.batch_sources, control.source_files TO retailops_data_migrator;
GRANT SELECT ON control.historical_state TO retailops_data_migrator;
-- El guard de escritura necesita bloquear la fila de lote antes de INSERT.
GRANT UPDATE (batch_id) ON control.batches TO retailops_data_migrator;
GRANT SELECT ON ALL TABLES IN SCHEMA control TO retailops_api, retailops_releaser;
GRANT SELECT ON control.batches, control.source_files, control.batch_sources, control.objects TO retailops_ingestor;
GRANT INSERT (batch_id,kind,entity,period_start,period_end,row_count) ON control.batches TO retailops_ingestor;
GRANT INSERT ON control.source_files, control.batch_sources, control.objects TO retailops_ingestor;
GRANT UPDATE (state,released_at) ON control.batches TO retailops_releaser;
GRANT UPDATE (released_through,last_batch_id,updated_at) ON control.historical_state TO retailops_releaser;
-- No hay función de promoción todavía; se diseñará una operación transaccional en F1-03.
