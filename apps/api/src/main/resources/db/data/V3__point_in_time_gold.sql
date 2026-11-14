-- GOLD pertenece al migrador de datos. El ingestor transforma; trainer solo lee vistas.
CREATE TABLE gold.features (
 feature_version text NOT NULL CHECK(feature_version='sales-pit-v1'),
 historical_cutoff date NOT NULL CHECK(historical_cutoff=DATE '2014-12-31'),
 issue_date date NOT NULL CHECK(issue_date BETWEEN DATE '2013-01-01' AND DATE '2014-12-31'),
 target_date date NOT NULL,
 horizon smallint NOT NULL CHECK(horizon BETWEEN 1 AND 7),
 store_nbr smallint NOT NULL CHECK(store_nbr>0), family text NOT NULL CHECK(family<>''),
 day_of_week smallint NOT NULL CHECK(day_of_week BETWEEN 1 AND 7),
 month smallint NOT NULL CHECK(month BETWEEN 1 AND 12), is_weekend boolean NOT NULL,
 lag_7 numeric, lag_14 numeric, lag_28 numeric,
 lag_7_available boolean NOT NULL, lag_14_available boolean NOT NULL, lag_28_available boolean NOT NULL,
 rolling_mean_7 numeric, rolling_mean_28 numeric, rolling_std_28 numeric,
 history_count_28 smallint NOT NULL CHECK(history_count_28 BETWEEN 0 AND 28),
 missing_history_flag boolean NOT NULL,
 PRIMARY KEY(feature_version,historical_cutoff,issue_date,store_nbr,family,horizon),
 CHECK(target_date=issue_date+horizon),
 CHECK(lag_7_available=(lag_7 IS NOT NULL)),
 CHECK(lag_14_available=(lag_14 IS NOT NULL)),
 CHECK(lag_28_available=(lag_28 IS NOT NULL)),
 CHECK(missing_history_flag=(history_count_28<28)),
 CHECK((rolling_std_28 IS NOT NULL)=(history_count_28>=2))
);
CREATE TABLE gold.labels (
 historical_cutoff date NOT NULL CHECK(historical_cutoff=DATE '2014-12-31'),
 target_date date NOT NULL CHECK(target_date BETWEEN DATE '2013-01-01' AND historical_cutoff),
 store_nbr smallint NOT NULL, family text NOT NULL, sales numeric NOT NULL CHECK(sales>=0 AND sales<'Infinity'::numeric),
 PRIMARY KEY(historical_cutoff,target_date,store_nbr,family)
);
CREATE TABLE gold.materializations (
 feature_version text NOT NULL, historical_cutoff date NOT NULL,
 issue_start date NOT NULL, issue_end date NOT NULL CHECK(issue_end>=issue_start),
 code_sha256 text NOT NULL CHECK(code_sha256 ~ '^[0-9a-f]{64}$'),
 feature_rows bigint NOT NULL CHECK(feature_rows>=0), label_rows bigint NOT NULL CHECK(label_rows>=0),
 completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(feature_version,historical_cutoff,issue_start)
);
CREATE VIEW training.gold_features WITH(security_barrier=true) AS
 SELECT f.* FROM gold.features f CROSS JOIN control.historical_state h
 WHERE f.historical_cutoff<=h.released_through
 AND EXISTS(SELECT 1 FROM control.batches b JOIN control.publications p USING(batch_id)
 WHERE b.batch_id='bootstrap-2013-2014' AND b.state='RELEASED' AND p.status='COMPLETE');
CREATE VIEW training.gold_labels WITH(security_barrier=true) AS
 SELECT l.* FROM gold.labels l CROSS JOIN control.historical_state h
 WHERE l.target_date<=h.released_through AND l.historical_cutoff<=h.released_through
 AND EXISTS(SELECT 1 FROM control.batches b JOIN control.publications p USING(batch_id)
 WHERE b.batch_id='bootstrap-2013-2014' AND b.state='RELEASED' AND p.status='COMPLETE');
GRANT USAGE ON SCHEMA gold,training TO retailops_ingestor;
GRANT SELECT ON training.sales TO retailops_ingestor;
GRANT SELECT,INSERT ON gold.features,gold.labels,gold.materializations TO retailops_ingestor;
GRANT SELECT ON training.gold_features,training.gold_labels TO retailops_trainer;
