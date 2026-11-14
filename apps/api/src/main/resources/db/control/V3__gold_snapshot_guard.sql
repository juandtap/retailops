-- Bloqueo mínimo del estado histórico, sin conceder UPDATE del corte al pipeline.
CREATE FUNCTION control.require_gold_snapshot() RETURNS date
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE cutoff date;
BEGIN
 SELECT h.released_through INTO cutoff FROM control.historical_state h
 JOIN control.batches b ON b.batch_id=h.last_batch_id
 JOIN control.publications p ON p.batch_id=b.batch_id
 WHERE b.batch_id='bootstrap-2013-2014' AND b.state='RELEASED' AND p.status='COMPLETE'
 AND h.released_through=DATE '2014-12-31' FOR SHARE OF h,b,p;
 IF cutoff IS NULL THEN RAISE EXCEPTION 'Estado histórico incompatible con GOLD v1'; END IF;
 RETURN cutoff;
END $$;
REVOKE ALL ON FUNCTION control.require_gold_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.require_gold_snapshot() TO retailops_ingestor;
