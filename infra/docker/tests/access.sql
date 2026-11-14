-- Fixtures de prueba sintéticas, siempre revertidas. No registra ingestas persistentes.
BEGIN;
INSERT INTO control.source_files VALUES (repeat('a',64),'train.csv',1,clock_timestamp());
INSERT INTO control.batches(batch_id,kind,entity,period_start,period_end,state,released_at) VALUES
 ('_test_released','BOOTSTRAP','_checks','2014-01-01','2014-12-31','VALIDATED',NULL),
 ('_test_unreleased','MONTHLY','_checks','2015-01-01','2015-01-31','STAGED',NULL),
 ('_test_wrong_future','MONTHLY','_checks','2015-02-01','2015-02-28','VALIDATED',NULL);
INSERT INTO control.batch_sources SELECT batch_id,repeat('a',64) FROM control.batches WHERE entity='_checks';
UPDATE control.historical_state SET released_through='2014-12-31',last_batch_id='_test_released';
INSERT INTO silver.stores VALUES (1,'Quito','Pichincha','D',1,'2013-01-01','fixture de prueba, no dato real','_test_released',repeat('a',64),1,clock_timestamp());
INSERT INTO silver.families VALUES ('_TEST','2013-01-01','fixture de prueba, no dato real','_test_released',repeat('a',64),1,clock_timestamp());
INSERT INTO silver.sales VALUES
 ('2014-12-30',1,'_TEST',1,1.125,2,'_test_released',repeat('a',64),1,clock_timestamp()),
 ('2014-12-31',1,'_TEST',2,2.5,0,'_test_unreleased',repeat('a',64),2,clock_timestamp()),
 ('2015-02-01',1,'_TEST',3,3.75,0,'_test_wrong_future',repeat('a',64),3,clock_timestamp());
INSERT INTO silver.oil_prices VALUES ('2014-12-30',NULL,NULL,NULL,'_test_released',repeat('a',64),1,clock_timestamp());
INSERT INTO silver.oil_prices VALUES ('2014-12-29',45,'2015-01-01','fixture','_test_released',repeat('a',64),2,clock_timestamp());
INSERT INTO silver.holidays_events VALUES
 ('00000000-0000-0000-0000-000000000001','2015-01-01','Holiday','National','Ecuador','_check',false,'2014-01-01','fixture','_test_released',repeat('a',64),1,clock_timestamp()),
 ('00000000-0000-0000-0000-000000000002','2015-01-01','Additional','Local','Quito','_check',false,'2014-01-01','fixture','_test_released',repeat('a',64),2,clock_timestamp()),
 ('00000000-0000-0000-0000-000000000003','2015-01-01','Event','Local','Cuenca','_check',false,'2014-01-01','fixture','_test_released',repeat('a',64),3,clock_timestamp()),
 ('00000000-0000-0000-0000-000000000004','2015-01-02','Event','National','Ecuador','_check',false,NULL,NULL,'_test_released',repeat('a',64),4,clock_timestamp()),
 ('00000000-0000-0000-0000-000000000005','2014-12-26','Holiday','National','Ecuador','_check',true,'2014-01-01','fixture','_test_released',repeat('a',64),5,clock_timestamp());
UPDATE control.batches SET state='RELEASED',released_at=clock_timestamp() WHERE batch_id IN ('_test_released','_test_wrong_future');
INSERT INTO control.publications(batch_id,status,contract_sha256,inventory_sha256,object_count,silver_loaded,ingested_at,authorized_at,completed_at) SELECT batch_id,'COMPLETE',repeat('a',64),repeat('a',64),1,true,clock_timestamp(),clock_timestamp(),clock_timestamp() FROM control.batches WHERE batch_id IN ('_test_released','_test_wrong_future');
SET LOCAL ROLE retailops_trainer;
DO $checks$
BEGIN
 IF (SELECT COUNT(*) FROM training.sales) <> 1 THEN RAISE EXCEPTION 'Fuga: lote no liberado o fecha futura visible'; END IF;
 IF (SELECT sales FROM training.sales) <> 1.125 THEN RAISE EXCEPTION 'Venta decimal truncada'; END IF;
 IF (SELECT COUNT(*) FROM training.oil_prices) <> 0 THEN RAISE EXCEPTION 'Disponibilidad desconocida expuesta'; END IF;
 IF (SELECT count(*) FROM training.holiday_features WHERE date='2015-01-01') <> 1 THEN RAISE EXCEPTION 'Fan-out de feriados'; END IF;
 IF (SELECT event_count FROM training.holiday_features WHERE date='2015-01-01') <> 2 THEN RAISE EXCEPTION 'Ámbito de feriados incorrecto'; END IF;
 IF (SELECT active_holiday FROM training.holiday_features WHERE date='2014-12-26') IS NOT FALSE THEN RAISE EXCEPTION 'Feriado transferido activado en fecha original'; END IF;
 IF (SELECT count(*) FROM training.holidays_events WHERE date='2015-01-02') <> 0 THEN RAISE EXCEPTION 'Calendario sin evidencia visible'; END IF;
 PERFORM set_config('retailops.cutoff','2099-12-31',true);
 IF (SELECT count(*) FROM training.sales) <> 1 THEN RAISE EXCEPTION 'Filtro manipulable por entrenador'; END IF;
 BEGIN PERFORM * FROM silver.sales; RAISE EXCEPTION 'Acceso directo a Silver'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN UPDATE control.historical_state SET released_through='2099-12-31'; RAISE EXCEPTION 'Modificación de corte autorizada'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END
$checks$;
RESET ROLE;
SET LOCAL ROLE retailops_ingestor;
DO $checks$
BEGIN
 BEGIN INSERT INTO silver.sales VALUES ('2014-12-29',1,'_TEST',9,1,0,'_test_released',repeat('a',64),9,clock_timestamp()); RAISE EXCEPTION 'Lote liberado mutable'; EXCEPTION WHEN check_violation THEN NULL; END;
 BEGIN UPDATE control.batches SET state='RELEASED',released_at=clock_timestamp() WHERE batch_id='_test_unreleased'; RAISE EXCEPTION 'Ingestor liberó lote'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN INSERT INTO control.batches(batch_id,kind,entity,period_start,period_end,state,released_at) VALUES ('_test_insert','MONTHLY','_checks','2015-03-01','2015-03-31','RELEASED',clock_timestamp()); RAISE EXCEPTION 'Ingestor insertó lote liberado'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END
$checks$;
RESET ROLE;
DO $checks$
BEGIN
 BEGIN INSERT INTO silver.sales VALUES ('2014-12-31',1,'_TEST',4,1,0,'_test_unreleased',repeat('a',64),4,clock_timestamp()); RAISE EXCEPTION 'Clave natural repetida aceptada'; EXCEPTION WHEN unique_violation THEN NULL; END;
 BEGIN INSERT INTO silver.sales VALUES ('2014-12-29',1,'_TEST',4,-1,0,'_test_unreleased',repeat('a',64),4,clock_timestamp()); RAISE EXCEPTION 'Venta negativa aceptada'; EXCEPTION WHEN check_violation THEN NULL; END;
 BEGIN INSERT INTO silver.sales VALUES ('2014-12-29',1,'_TEST',4,1,-1,'_test_unreleased',repeat('a',64),4,clock_timestamp()); RAISE EXCEPTION 'Promoción negativa aceptada'; EXCEPTION WHEN check_violation THEN NULL; END;
 IF (SELECT dcoilwtico IS NULL FROM silver.oil_prices WHERE date='2014-12-30') IS NOT TRUE THEN RAISE EXCEPTION 'Nulo convertido en cero'; END IF;
END
$checks$;
ROLLBACK;
