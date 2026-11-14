-- Append-only; las tablas/vistas v1 y sus nueve millones de filas permanecen intactas.
CREATE TABLE gold.incremental_features (LIKE gold.features INCLUDING DEFAULTS);
ALTER TABLE gold.incremental_features ADD PRIMARY KEY(feature_version,issue_date,store_nbr,family,horizon),
 ADD CHECK(feature_version='sales-pit-v2'), ADD CHECK(issue_date>=DATE '2015-01-01' AND issue_date<=historical_cutoff),
 ADD CHECK(horizon BETWEEN 1 AND 7 AND target_date=issue_date+horizon),
 ADD CHECK(history_count_28 BETWEEN 0 AND 28 AND missing_history_flag=(history_count_28<28)),
 ADD CHECK(lag_7_available=(lag_7 IS NOT NULL) AND lag_14_available=(lag_14 IS NOT NULL) AND lag_28_available=(lag_28 IS NOT NULL));
CREATE TABLE gold.incremental_labels (LIKE gold.labels INCLUDING DEFAULTS);
ALTER TABLE gold.incremental_labels ADD PRIMARY KEY(target_date,store_nbr,family),
 ADD CHECK(target_date>=DATE '2015-01-01' AND target_date<=historical_cutoff),
 ADD CHECK(sales>=0 AND sales<'Infinity'::numeric);
CREATE TABLE gold.incremental_materializations (
 issue_start date PRIMARY KEY, issue_end date NOT NULL, historical_cutoff date NOT NULL,
 code_sha256 text NOT NULL, feature_rows bigint NOT NULL, label_rows bigint NOT NULL,
 completed_at timestamptz NOT NULL DEFAULT clock_timestamp(), CHECK(issue_start<=issue_end AND issue_end=historical_cutoff)
);
CREATE VIEW training.gold_features_v2 WITH(security_barrier=true) AS
 SELECT 'sales-pit-v2'::text feature_version,f.historical_cutoff,f.issue_date,f.target_date,f.horizon,f.store_nbr,f.family,
 f.day_of_week,f.month,f.is_weekend,f.lag_7,f.lag_14,f.lag_28,f.lag_7_available,f.lag_14_available,f.lag_28_available,
 f.rolling_mean_7,f.rolling_mean_28,f.rolling_std_28,f.history_count_28,f.missing_history_flag FROM training.gold_features f
 UNION ALL SELECT f.* FROM gold.incremental_features f CROSS JOIN control.historical_state h
 WHERE f.historical_cutoff<=h.released_through AND EXISTS(SELECT 1 FROM gold.incremental_materializations m WHERE m.historical_cutoff=f.historical_cutoff);
CREATE VIEW training.gold_labels_v2 WITH(security_barrier=true) AS
 SELECT * FROM training.gold_labels UNION ALL
 SELECT l.* FROM gold.incremental_labels l CROSS JOIN control.historical_state h
 WHERE l.target_date<=h.released_through AND l.historical_cutoff<=h.released_through
 AND EXISTS(SELECT 1 FROM gold.incremental_materializations m WHERE m.historical_cutoff=l.historical_cutoff);
GRANT SELECT ON training.gold_features_v2,training.gold_labels_v2 TO retailops_trainer;
GRANT SELECT,INSERT ON gold.incremental_features,gold.incremental_labels,gold.incremental_materializations TO retailops_ingestor;
CREATE FUNCTION gold.confirm_incremental(ending date) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM gold.incremental_materializations WHERE historical_cutoff=ending) THEN
 RAISE EXCEPTION 'Materialización incremental pendiente'; END IF;
 UPDATE control.monthly_authorizations SET gold_complete=true WHERE period_end=ending;
END $$;
REVOKE ALL ON FUNCTION gold.confirm_incremental(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gold.confirm_incremental(date) TO retailops_ingestor;
