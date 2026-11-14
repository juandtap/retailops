-- Estado de autorización distinto de terminación. V1 permanece intacta.
CREATE TABLE control.publications (
    batch_id text PRIMARY KEY REFERENCES control.batches(batch_id),
    status text NOT NULL DEFAULT 'STAGING' CHECK (status IN ('STAGING','AUTHORIZED','COMPLETE')),
    contract_sha256 text NOT NULL CHECK (contract_sha256 ~ '^[0-9a-f]{64}$'),
    inventory_sha256 text CHECK (inventory_sha256 ~ '^[0-9a-f]{64}$'),
    expected_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    object_count integer CHECK (object_count > 0),
    silver_loaded boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    ingested_at timestamptz NOT NULL,
    authorized_at timestamptz,
    completed_at timestamptz,
    CHECK (status='STAGING' OR (silver_loaded AND inventory_sha256 IS NOT NULL AND object_count IS NOT NULL AND authorized_at IS NOT NULL)),
    CHECK ((status='COMPLETE') = (completed_at IS NOT NULL))
);
CREATE UNIQUE INDEX one_incomplete_publication ON control.publications ((true)) WHERE status <> 'COMPLETE';
CREATE TABLE control.publication_objects (
    batch_id text NOT NULL REFERENCES control.publications(batch_id),
    object_key text NOT NULL CHECK (object_key <> ''),
    entity text NOT NULL,
    layer text NOT NULL CHECK (layer IN ('RAW','BRONZE')),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    source_sha256 text NOT NULL REFERENCES control.source_files(sha256),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    row_count bigint NOT NULL CHECK (row_count > 0),
    publishable boolean NOT NULL,
    quarantine_version text,
    released_version text,
    published_at timestamptz,
    PRIMARY KEY (batch_id,object_key),
    CHECK (publishable OR (released_version IS NULL AND published_at IS NULL)),
    CHECK ((released_version IS NULL) = (published_at IS NULL))
);
GRANT SELECT, REFERENCES ON control.publications TO retailops_data_migrator;
GRANT SELECT ON control.publications,control.publication_objects TO retailops_ingestor,retailops_releaser,retailops_api;
GRANT INSERT (batch_id,contract_sha256,ingested_at) ON control.publications TO retailops_ingestor;
GRANT UPDATE (inventory_sha256,expected_counts,object_count,silver_loaded) ON control.publications TO retailops_ingestor;
GRANT INSERT ON control.publication_objects TO retailops_ingestor;
GRANT UPDATE (quarantine_version) ON control.publication_objects TO retailops_ingestor;
GRANT UPDATE (status,authorized_at,completed_at) ON control.publications TO retailops_releaser;
GRANT UPDATE (released_version,published_at) ON control.publication_objects TO retailops_releaser;
GRANT INSERT ON control.objects TO retailops_releaser;
GRANT INSERT ON control.ingestion_runs TO retailops_ingestor;
GRANT SELECT ON control.ingestion_runs,control.historical_state TO retailops_ingestor;
GRANT UPDATE (status,started_at,finished_at,processed_rows,error_code) ON control.ingestion_runs TO retailops_ingestor;

CREATE FUNCTION control.guard_next_batch() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM control.publications WHERE status <> 'COMPLETE' AND batch_id <> NEW.batch_id) THEN
   RAISE EXCEPTION 'Hay una publicación incompatible pendiente' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION control.guard_next_batch() FROM PUBLIC;
CREATE TRIGGER guard_next_batch BEFORE INSERT ON control.batches FOR EACH ROW EXECUTE FUNCTION control.guard_next_batch();
CREATE FUNCTION control.guard_run_success() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.status='SUCCEEDED' AND NOT EXISTS(SELECT 1 FROM control.publications p JOIN control.historical_state h ON h.last_batch_id=p.batch_id WHERE p.batch_id=NEW.batch_id AND p.status='COMPLETE') THEN
   RAISE EXCEPTION 'Publicación no completada: no puede registrarse éxito' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION control.guard_run_success() FROM PUBLIC;
CREATE TRIGGER guard_run_success BEFORE INSERT OR UPDATE ON control.ingestion_runs FOR EACH ROW EXECUTE FUNCTION control.guard_run_success();

CREATE FUNCTION control.guard_publication_state() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF OLD.status <> 'STAGING' AND (NEW.inventory_sha256,NEW.expected_counts,NEW.object_count,NEW.silver_loaded) IS DISTINCT FROM (OLD.inventory_sha256,OLD.expected_counts,OLD.object_count,OLD.silver_loaded) THEN
   RAISE EXCEPTION 'Inventario autorizado inmutable' USING ERRCODE='23514';
 END IF;
 IF NEW.status IS DISTINCT FROM OLD.status THEN
   IF NOT ((OLD.status='STAGING' AND NEW.status='AUTHORIZED') OR (OLD.status='AUTHORIZED' AND NEW.status='COMPLETE')) THEN
     RAISE EXCEPTION 'Transición de publicación inválida' USING ERRCODE='23514';
   END IF;
   IF NEW.object_count IS DISTINCT FROM (SELECT count(*)::integer FROM control.publication_objects WHERE batch_id=NEW.batch_id)
      OR EXISTS(SELECT 1 FROM control.publication_objects WHERE batch_id=NEW.batch_id AND quarantine_version IS NULL) THEN
     RAISE EXCEPTION 'Inventario de cuarentena incompleto' USING ERRCODE='23514';
   END IF;
   IF NEW.status='COMPLETE' AND EXISTS(SELECT 1 FROM control.publication_objects WHERE batch_id=NEW.batch_id AND publishable AND released_version IS NULL) THEN
     RAISE EXCEPTION 'Publicación S3 incompleta' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION control.guard_publication_state() FROM PUBLIC;
CREATE TRIGGER guard_publication_state BEFORE UPDATE ON control.publications FOR EACH ROW EXECUTE FUNCTION control.guard_publication_state();
CREATE FUNCTION control.guard_inventory() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE phase text;
BEGIN
 SELECT status INTO phase FROM control.publications WHERE batch_id=NEW.batch_id FOR SHARE;
 IF TG_OP='INSERT' AND phase <> 'STAGING' THEN RAISE EXCEPTION 'Inventario cerrado' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' THEN
   IF NEW.quarantine_version IS DISTINCT FROM OLD.quarantine_version AND phase <> 'STAGING' THEN
     RAISE EXCEPTION 'Versión de cuarentena autorizada inmutable' USING ERRCODE='23514';
   END IF;
   IF NEW.released_version IS DISTINCT FROM OLD.released_version AND (phase <> 'AUTHORIZED' OR NOT NEW.publishable OR OLD.released_version IS NOT NULL) THEN
     RAISE EXCEPTION 'Publicación sin autorización o versión conflictiva' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION control.guard_inventory() FROM PUBLIC;
CREATE TRIGGER guard_inventory BEFORE INSERT OR UPDATE ON control.publication_objects FOR EACH ROW EXECUTE FUNCTION control.guard_inventory();
