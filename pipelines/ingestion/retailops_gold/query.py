"""SQL puro compartido por materializador y pruebas sintéticas; sin auxiliares."""
COLUMNS = '''feature_version,historical_cutoff,issue_date,target_date,horizon,store_nbr,family,
day_of_week,month,is_weekend,lag_7,lag_14,lag_28,lag_7_available,lag_14_available,
lag_28_available,rolling_mean_7,rolling_mean_28,rolling_std_28,history_count_28,missing_history_flag'''
# Los únicos datos externos a este SELECT son training.sales y parámetros cerrados.
QUERY = '''WITH source AS MATERIALIZED (
 SELECT date,store_nbr,family,sales FROM training.sales
 WHERE batch_id='bootstrap-2013-2014' AND date BETWEEN %(start)s::date-27 AND %(end)s
), pairs AS (
 SELECT store_nbr,family,min(date) first_date FROM training.sales WHERE batch_id='bootstrap-2013-2014' AND date<=%(end)s GROUP BY store_nbr,family
), calendar AS (
 SELECT d::date issue_date,p.store_nbr,p.family,s.sales
 FROM pairs p CROSS JOIN generate_series(%(start)s::date-27,%(end)s::date,interval '1 day') d
 LEFT JOIN source s ON s.date=d::date AND s.store_nbr=p.store_nbr AND s.family=p.family
 WHERE d::date>=p.first_date
), windows AS (
 SELECT *,avg(sales) OVER w7 mean7,avg(sales) OVER w28 mean28,
 stddev_samp(sales) OVER w28 std28,count(sales) OVER w28 count28
 FROM calendar
 WINDOW w7 AS (PARTITION BY store_nbr,family ORDER BY issue_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
 w28 AS (PARTITION BY store_nbr,family ORDER BY issue_date ROWS BETWEEN 27 PRECEDING AND CURRENT ROW)
)
SELECT 'sales-pit-v1'::text feature_version,DATE '2014-12-31' historical_cutoff,
 w.issue_date,w.issue_date+h.horizon target_date,h.horizon::smallint,w.store_nbr,w.family,
 extract(isodow FROM w.issue_date+h.horizon)::smallint day_of_week,
 extract(month FROM w.issue_date+h.horizon)::smallint AS "month",
 extract(isodow FROM w.issue_date+h.horizon)>=6 is_weekend,
 l7.sales lag_7,l14.sales lag_14,l28.sales lag_28,
 l7.sales IS NOT NULL lag_7_available,l14.sales IS NOT NULL lag_14_available,l28.sales IS NOT NULL lag_28_available,
 w.mean7 rolling_mean_7,w.mean28 rolling_mean_28,w.std28 rolling_std_28,
 w.count28::smallint history_count_28,w.count28<28 missing_history_flag
 FROM windows w CROSS JOIN generate_series(1,7) h(horizon)
 LEFT JOIN source l7 ON l7.date=w.issue_date+h.horizon-7 AND l7.date<=w.issue_date AND l7.store_nbr=w.store_nbr AND l7.family=w.family
 LEFT JOIN source l14 ON l14.date=w.issue_date+h.horizon-14 AND l14.date<=w.issue_date AND l14.store_nbr=w.store_nbr AND l14.family=w.family
 LEFT JOIN source l28 ON l28.date=w.issue_date+h.horizon-28 AND l28.date<=w.issue_date AND l28.store_nbr=w.store_nbr AND l28.family=w.family
 WHERE w.issue_date BETWEEN %(start)s AND %(end)s'''
LABEL_QUERY = '''SELECT DATE '2014-12-31',date,store_nbr,family,sales FROM training.sales
 WHERE batch_id='bootstrap-2013-2014' AND date BETWEEN %(start)s AND %(end)s AND date<=DATE '2014-12-31' '''
