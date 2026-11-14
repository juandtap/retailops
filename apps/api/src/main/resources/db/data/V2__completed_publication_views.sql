ALTER TABLE silver.observation_gaps ALTER COLUMN source_row_number DROP NOT NULL;
-- Publicación completa necesaria para las vistas, incluso si hay autorización SQL previa.
GRANT USAGE ON SCHEMA silver TO retailops_releaser;
GRANT SELECT ON ALL TABLES IN SCHEMA silver TO retailops_releaser;

CREATE OR REPLACE VIEW training.stores WITH (security_barrier=true) AS
SELECT d.store_nbr,d.city,d.state,d.store_type,d.cluster,d.known_from, d.batch_id
FROM silver.stores d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE OR REPLACE VIEW training.families WITH (security_barrier=true) AS
SELECT d.family,d.known_from, d.batch_id
FROM silver.families d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE OR REPLACE VIEW training.sales WITH (security_barrier=true) AS
SELECT d.date,d.store_nbr,d.family,d.sales, d.batch_id
FROM silver.sales d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through;

CREATE OR REPLACE VIEW training.holidays_events WITH (security_barrier=true) AS
SELECT d.event_id,d.date,d.event_type,d.locale,d.locale_name,d.description,d.transferred,d.known_from, d.batch_id
FROM silver.holidays_events d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE OR REPLACE VIEW training.oil_prices WITH (security_barrier=true) AS
SELECT d.date,d.dcoilwtico,d.known_from, d.batch_id
FROM silver.oil_prices d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through AND d.known_from IS NOT NULL AND d.known_from <= h.released_through AND d.availability_evidence IS NOT NULL;

CREATE OR REPLACE VIEW training.store_transactions WITH (security_barrier=true) AS
SELECT d.date,d.store_nbr,d.transactions, d.batch_id
FROM silver.store_transactions d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through;

CREATE OR REPLACE VIEW training.observation_gaps WITH (security_barrier=true) AS
SELECT d.date,d.entity,d.scope_key,d.reason, d.batch_id
FROM silver.observation_gaps d
JOIN control.batches b ON b.batch_id=d.batch_id
CROSS JOIN control.historical_state h
WHERE EXISTS (SELECT 1 FROM control.publications p WHERE p.batch_id=d.batch_id AND p.status='COMPLETE') AND b.state='RELEASED' AND h.released_through IS NOT NULL AND d.date <= h.released_through;
