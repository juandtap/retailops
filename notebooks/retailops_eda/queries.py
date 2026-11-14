"""Consultas cerradas: solo agregados del bootstrap y sin SQL arbitrario del notebook."""
BASE="""FROM training.sales WHERE date BETWEEN %(start)s AND %(end)s AND batch_id=%(batch)s"""
DAILY=f"""SELECT date, sum(sales)::double precision total_sales, count(*) records,
 count(*) FILTER(WHERE sales=0) zero_sales, count(*) FILTER(WHERE sales<>trunc(sales)) decimal_sales {BASE} GROUP BY date"""
QUERIES={
 'overview':f"""SELECT count(*) records,min(date) first_date,max(date) last_date,
 count(DISTINCT store_nbr) stores,count(DISTINCT family) families,
 sum(sales) total_sales,min(sales) minimum,max(sales) maximum,avg(sales) mean_sales,
 count(*) FILTER(WHERE sales=0) zero_sales,count(*) FILTER(WHERE sales<>trunc(sales)) decimal_sales,
 count(*) FILTER(WHERE sales<0) negative_sales,
 percentile_cont(0.25) WITHIN GROUP(ORDER BY sales::double precision) p25,
 percentile_cont(0.5) WITHIN GROUP(ORDER BY sales::double precision) p50,
 percentile_cont(0.75) WITHIN GROUP(ORDER BY sales::double precision) p75,
 percentile_cont(0.95) WITHIN GROUP(ORDER BY sales::double precision) p95,
 percentile_cont(0.99) WITHIN GROUP(ORDER BY sales::double precision) p99 {BASE}""",
 'distribution':f"""SELECT CASE WHEN sales=0 THEN 0 WHEN sales<1 THEN 1 WHEN sales<10 THEN 2
 WHEN sales<100 THEN 3 WHEN sales<1000 THEN 4 WHEN sales<10000 THEN 5 ELSE 6 END bucket,
 count(*) records {BASE} GROUP BY 1 ORDER BY 1""",
 'by_store':f"""SELECT store_nbr,count(*) records,sum(sales)::double precision total_sales,
 avg(sales)::double precision mean_sales,count(*) FILTER(WHERE sales=0) zero_sales,
 count(*) FILTER(WHERE sales<>trunc(sales)) decimal_sales {BASE} GROUP BY store_nbr ORDER BY store_nbr""",
 'by_family':f"""SELECT family,count(*) records,sum(sales)::double precision total_sales,
 avg(sales)::double precision mean_sales,count(*) FILTER(WHERE sales=0) zero_sales,
 count(*) FILTER(WHERE sales<>trunc(sales)) decimal_sales,max(sales)::double precision maximum
 {BASE} GROUP BY family ORDER BY total_sales DESC,family""",
 'daily':DAILY+' ORDER BY date',
 'monthly':f"""SELECT date_trunc('month',date)::date AS "month",sum(sales)::double precision total_sales,
 count(*) records,count(DISTINCT date) observed_days {BASE} GROUP BY 1 ORDER BY 1""",
 'extremes':f"""SELECT store_nbr,family,count(*) records,max(sales)::double precision maximum,
 avg(sales)::double precision mean_sales {BASE} AND sales >= %(threshold)s
 GROUP BY store_nbr,family ORDER BY maximum DESC,store_nbr,family LIMIT 20""",
 'store_daily':f"""SELECT date,store_nbr,sum(sales)::double precision total_sales {BASE}
 AND store_nbr=ANY(%(stores)s) GROUP BY date,store_nbr ORDER BY date,store_nbr""",
 'family_daily':f"""SELECT date,family,sum(sales)::double precision total_sales {BASE}
 AND family=ANY(%(families)s) GROUP BY date,family ORDER BY date,family""",
 'gaps':"""SELECT date,entity,reason FROM training.observation_gaps WHERE date BETWEEN %(start)s AND %(end)s
 AND batch_id=%(batch)s AND entity='sales' ORDER BY date""",
 'availability':"""SELECT 'stores' entity,count(*) records FROM training.stores WHERE known_from BETWEEN %(start)s AND %(end)s AND batch_id=%(batch)s
 UNION ALL SELECT 'families',count(*) FROM training.families WHERE known_from BETWEEN %(start)s AND %(end)s AND batch_id=%(batch)s
 UNION ALL SELECT 'holidays_events',count(*) FROM training.holidays_events WHERE date BETWEEN %(start)s AND %(end)s AND batch_id=%(batch)s
 UNION ALL SELECT 'oil_prices',count(*) FROM training.oil_prices WHERE date BETWEEN %(start)s AND %(end)s AND batch_id=%(batch)s""",
 # Es una comprobación de ausencia, no devuelve observaciones/estadísticas futuras.
 'future_visible':"SELECT EXISTS(SELECT 1 FROM training.sales WHERE date>%(end)s) future_visible",
 'session':"""SELECT current_user role,current_setting('transaction_read_only') read_only,
 current_setting('statement_timeout') statement_timeout,
 has_schema_privilege(current_user,'silver','USAGE') silver_access,
 has_schema_privilege(current_user,'control','USAGE') control_access"""
}
