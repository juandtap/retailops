"""Informe en español a partir de resultados medidos; sin ejemplos de filas originales."""
from __future__ import annotations

import json
from collections import Counter


def cell(value):
    if value is None:
        return '—'
    if isinstance(value,bool):
        return 'sí' if value else 'no'
    if isinstance(value,float):
        return f'{value:,.6f}'.rstrip('0').rstrip('.')
    return str(value).replace('|','\\|').replace('\n',' ')


def markdown_table(headers, rows):
    return ['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |',
            *['| '+' | '.join(map(cell,row))+' |' for row in rows], '']


def render_report(result, manifest):
    files=result['files']; coverage=result['sales_coverage']; relations=result['relationships']
    lines=['# Perfilado y calidad de Corporación Favorita','',
           'Informe generado por `retailops_profiling` con Python 3.12. Las cifras proceden exclusivamente de los CSV locales. Los resultados son descriptivos de toda la fuente y **no son features, estadísticas de entrenamiento ni datos liberados**. No se avanzó el corte histórico.','',
           '## Reproducción y método','',
           'Desde la raíz del repositorio (con el Python 3.12 ya instalado por uv):','',
           '```bash',
           'export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"',
           'uv run --project pipelines/ingestion --locked python pipelines/ingestion/profile_dataset.py --source data/source/favorita --output docs',
           'uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/tests -v',
           '```','',
           'El proyecto usa solo la biblioteca estándar y su propio `pyproject.toml`/`uv.lock`. El lanzador permite importar el módulo al ejecutar el comando desde la raíz. Alternativamente, ejecutar `uv run --locked python -m retailops_profiling --source ../../data/source/favorita --output ../../docs` desde `pipelines/ingestion`.','',
           'Lectura CSV en bloques configurables (10 000 filas por defecto). SQLite de la biblioteca estándar se usa únicamente dentro de un directorio temporal, con caché de 16 MiB y ordenaciones temporales en disco; se elimina al terminar. No se crean tablas de aplicación ni capas Bronze/Silver. Los agregados de cobertura conservan como máximo las series y días observados, no todas las filas.','',
           'Nulos: celdas vacías o solo espacios; no se convierte automáticamente «NA» o «NaN» en ausencia. Se registran tipos no finitos y valores incompatibles por separado. Filas con longitud incorrecta se cuentan y se excluyen de cálculos de contenido, sin silenciarlas. Un archivo ausente figura explícitamente.','',
           'Duplicados: exceso de filas respecto a grupos distintos, tanto para filas completas como para claves naturales; no equivale a cantidad de grupos duplicados. La clave de ventas excluye `id`. Las cardinalidades excluyen nulos. La inferencia revisa todos los valores; los tipos recomendados son contratos propuestos y muestran incompatibilidades. Las estadísticas numéricas usan float64 y Welford (desviación poblacional); los percentiles son exactos sobre esos valores con interpolación lineal. No determinan precisión SQL ni modifican el CSV. Fechas con varios eventos son válidas en feriados.','',
           'SHA-256 antes/después de cada archivo y una segunda comprobación global al terminar protegen contra cambios durante la ejecución. Los resultados se escriben solo fuera de SOURCE. El informe/JSON no exportan registros originales.','',
           '## Resumen de archivos','']
    rows=[]
    for name,p in files.items():
        if p['status']=='faltante':
            rows.append([name,'FALTANTE','—','—','—','—','—']);continue
        rows.append([name,p['rows'],p['column_count'],sum(c['nulls'] for c in p['columns'].values()),p['duplicate_rows_excess'],p.get('duplicate_keys_excess','no se exige'),p['malformed_rows']])
    lines+=markdown_table(['Archivo','Filas','Columnas','Celdas nulas','Filas duplicadas (exceso)','Claves duplicadas (exceso)','Filas malformadas'],rows)
    for name,p in files.items():
        lines+=['## '+name,'']
        if p['status']=='faltante':
            lines+=['Archivo faltante; sin inferencia ni relaciones certificadas.',''];continue
        lines += [f"SHA-256: `{p['sha256']}`. Tamaño: {p['bytes']} bytes. Cabecera contractual exacta: {cell(p['schema_matches'])}. Fuente sin cambios durante su lectura: {cell(p['source_unchanged'])}.",'']
        lines+=markdown_table(['Columna','Tipo inferido','Tipo recomendado','Nulos','Cardinalidad','Incompatibles con tipo recomendado','Rango de fechas'],[
            [c,v['inferred_type'],v['recommended_type'],v['nulls'],v['cardinality'],v['invalid_for_recommended_type'],' → '.join(str(x) for x in v.get('date_range',[])) or '—'] for c,v in p['columns'].items()])
        numeric=[(c,v['numeric']) for c,v in p['columns'].items() if 'numeric' in v]
        if numeric:
            lines+=markdown_table(['Variable','Mín.','Máx.','Media','Desv. poblacional','Ceros','Negativos','No enteros'],[[c,n['min'],n['max'],n['mean'],n['std_population'],n['zero'],n['negative'],n['fractional']] for c,n in numeric])
            quantiles=[(c,n) for c,n in numeric if 'quantiles' in n]
            if quantiles:
                lines+=markdown_table(['Variable','P25','P50','P75','P95','P99'],[[c,*[n['quantiles'].get(str(q)) for q in (.25,.5,.75,.95,.99)]] for c,n in quantiles])
        cats=[(c,v) for c,v in p['columns'].items() if 'top_values' in v]
        if cats:
            lines+=['Frecuencias categóricas principales (máximo diez por columna; el JSON conserva las mismas frecuencias):','']
            lines+=markdown_table(['Variable','Valor : frecuencia'],[[c,'; '.join(f'{x}: {n}' for x,n in v['top_values'])] for c,v in cats])
        if 'duplicate_ids_excess' in p:
            lines += [f"IDs repetidos (exceso): {p['duplicate_ids_excess']}.",'']
        if 'natural_key' in p:
            lines += [f"Clave comprobada: `({', '.join(p['natural_key'])})`; filas con componentes nulos: {p['null_key_rows']}. La comprobación usa los valores de la fuente sin normalizar identificadores.",'']
        if name=='holidays_events.csv':
            lines+=['La fecha no es clave única: pueden coincidir feriados nacionales, regionales, locales y eventos. Los duplicados de fila completa se informan para revisión; no se eliminan automáticamente.','']
    lines+=['## Granularidad y cobertura de ventas','']
    if 'first_date' in coverage:
        train=files['train.csv']; sales=train['columns']['sales'].get('numeric'); promo=train['columns']['onpromotion'].get('numeric')
        lines += [f"Train abarca **{coverage['first_date']} → {coverage['last_date']}**, {coverage['observed_days']} fechas, {coverage['stores']} tiendas y {coverage['families']} familias. Hay {coverage['observed_series']} series observadas de {coverage['expected_series']} combinaciones esperadas, con granularidad diaria por `(date, store_nbr, family)`.",'',
                  f"Exceso de claves repetidas: {train.get('duplicate_keys_excess')}; fechas con filas/claves distintas de la cuadrícula esperada ({coverage['expected_series']} al día): {len(coverage['days_with_unexpected_granularity'])}.",'',
                  'Fechas ausentes dentro del rango observado: '+(', '.join(coverage['missing_dates']) or 'ninguna')+'.','',
                  (f"Ventas cero: {sales['zero']} ({100*sales['zero']/sales['count']:.2f} %); ventas negativas: {sales['negative']}; ventas no enteras: {sales['fractional']}. Promociones negativas: {promo['negative']}; promociones no enteras: {promo['fractional']}. Primera fecha con promociones positivas: {coverage['first_positive_promotion_date']}." if sales and promo else 'No hay suficientes valores numéricos válidos para resumir ventas/promociones; revisar incompatibilidades en las tablas.'),'',
                  'Los ceros pueden representar falta de actividad, cierres o ausencia de ventas; no se pueden identificar aperturas ni demanda insatisfecha solo con estas observaciones. Una venta decimal es coherente con familias vendidas por peso, no un error por defecto. `onpromotion` se trata como conteo de productos promocionados de la familia/tienda, no como booleano ni porcentaje; los CSV por sí solos no certifican cuándo se conoció ese conteo.','']
        series=coverage['series']
        signatures=Counter((s['rows'],s['observed_days'],s['first_date'],s['last_date'],s['missing_days_in_train_calendar']) for s in series)
        lines+=['### Cobertura por serie, tienda y familia','',
                'Se comprueba cada combinación observada. Firmas de cobertura por serie (el JSON `DATA_PROFILING.json` incluye las series individuales, además de agregados por tienda/familia):','']
        lines+=markdown_table(['Series con esta firma','Filas por serie','Días por serie','Primera fecha','Última fecha','Días ausentes en calendario train'],[[n,*sig] for sig,n in sorted(signatures.items())])
        lines+=markdown_table(['Tienda','Filas','Días','Familias','Inicio','Fin'],[[r[k] for k in ['store_nbr','rows','observed_days','families','first_date','last_date']] for r in coverage['by_store']])
        lines+=markdown_table(['Familia','Filas','Días','Tiendas','Inicio','Fin'],[[r[k] for k in ['family','rows','observed_days','stores','first_date','last_date']] for r in coverage['by_family']])
        lines+=['### Promociones, ceros y transacciones por año','']
        lines+=markdown_table(['Año','Filas','Filas con promoción positiva','Ventas cero','Filas con venta positiva sin transacción tienda/día'],[[r[k] for k in ['year','rows','promoted_rows','sales_zero_rows','positive_sales_missing_transactions']] for r in coverage['by_year']])
        lines+=['Una transición desde promociones siempre cero puede ser un cambio de disponibilidad/registro. No demuestra ausencia real de promociones antes de esa fecha. Documentar esta limitación antes de entrenar el bootstrap.','']
    else:
        lines += ['No se certifica cobertura: '+coverage.get('status','sin datos')+'.','']
    lines+=['## Bootstrap y manifiesto mensual','',
            '`DATA_BATCH_MANIFEST.json` es un plan descriptivo: `purpose=PLAN_ONLY`, `release_performed=false`, `historical_cutoff=null` y todos los lotes `released=false`. No crea particiones, libera datos ni cambia estados de ejecución.','',
            'El manifiesto distingue `calendar_complete` de `observed_grid_complete` por mes. Completitud estricta respecto al calendario: todas las fechas del mes y todas las combinaciones tienda/familia, sin claves repetidas. Un mes con un feriado ausente se clasifica INCOMPLETE en este sentido aunque el CSV distribuido sea íntegro. No se inventan ventas ni se rechaza automáticamente un lote por esta etiqueta. La política de aceptación deberá decidirse en F1-03.','']
    lines += [f"Lotes incrementales planificados: {len(manifest['incremental_batches'])}; completos respecto al calendario: {sum(m['completeness']=='COMPLETE' for m in manifest['incremental_batches'])}; incompletos: {sum(m['completeness']=='INCOMPLETE' for m in manifest['incremental_batches'])}.",'']
    if bootstrap:=manifest['bootstrap']:
        lines+=markdown_table(['Lote','Desde','Hasta','Filas','Filas teóricas calendario','Completitud','Fechas ausentes'],[[bootstrap[k] for k in ['batch_id','period_start','period_end','rows','expected_rows_calendar','completeness']]+[', '.join(bootstrap['missing_dates']) or 'ninguna']])
    if 'months' in coverage:
        lines+=['Todos los meses observados (incluidos los del bootstrap):','']
        lines+=markdown_table(['Mes','Filas','Días observados/calendario','Completitud','Fechas ausentes'],[[m['batch_id'],m['rows'],f"{m['observed_days']}/{m['calendar_days']}",m['completeness'],', '.join(m['missing_dates']) or 'ninguna'] for m in coverage['months']])
    lines+=['## Integridad entre fuentes','']
    scalar=[(k,v) for k,v in relations.items() if not isinstance(v,(list,tuple))]
    lines+=markdown_table(['Comprobación','Resultado'],scalar)
    if 'test.date_range' in relations:
        lines += [f"Test: inicio {relations['test.date_range'][0]}, fin {relations['test.date_range'][1]}, {relations['test.date_range'][2]} días. Su horizonte de competición no sustituye el objetivo de siete días de RetailOps. `sample_submission.sales` es una plantilla, no una observación ni una etiqueta válida para entrenar.",'']
    if 'holidays.multi_event_dates' in relations:
        lines += [f"Fechas con más de un evento: {len(relations['holidays.multi_event_dates'])}; detalle de fechas/recuentos en JSON. Antes de un join con ventas, agregar indicadores por ámbito/tipo para evitar multiplicar ventas.",'']
        lines+=markdown_table(['Tipo de evento','Transferred','Filas'],relations['holidays.type_transferred'])
    lines+=['## Anomalías interpretadas y riesgo de fuga temporal','',
            '- **Calendario de ventas:** las fechas ausentes no se etiquetan automáticamente como corrupción. Conservar ausencia y una bandera; cualquier relleno debe justificarse y diferenciarse de un cero observado. El último mes termina en el máximo real de train, no en el fin nominal del mes.',
            '- **Petróleo:** la ausencia de filas y las celdas nulas son problemas distintos. Días sin cotización pueden corresponder a calendario de mercado. No usar interpolación bidireccional ni backfill desde el futuro. Un forward-fill solo podrá partir de observaciones disponibles al corte; no garantiza que la cotización del mismo día estuviera publicada al emitir una predicción.',
            '- **Transacciones:** granularidad tienda/día, no familia. La falta de una transacción no demuestra cero ventas ni cierre. Investigar faltantes con ventas positivas; no imponer una FK obligatoria desde cada venta a transacciones. En un horizonte futuro, las transacciones reales son desconocidas: excluirlas o usar lags observados seguros.',
            '- **Feriados:** aplicar ámbito Local/Regional/National a ciudad/estado/país. `transferred=True` no equivale a día festivo activo en su fecha original; considerar Transfer, Bridge, Additional, Event y Work Day por separado. Los datos no incluyen fecha de anuncio, por lo que el calendario conocido históricamente requiere una hipótesis documentada. Coincidencias de eventos son relaciones uno-a-muchos legítimas.',
            '- **Tiendas:** city/state/type/cluster son una fotografía sin vigencia temporal. No prueban fechas de apertura ni que una clasificación fuese conocida en 2013. Tratar esta disponibilidad como hipótesis, sin inferir aperturas a partir de ceros.',
            '- **Promociones:** preservar el conteo; investigar el cambio de cobertura reportado por año. Las promociones futuras presentes en test no demuestran conocimiento al emitir predicciones históricas. En el baseline del bootstrap, excluirlas si no existe evidencia de disponibilidad; no fabricar historial promocional.',
            '- **Ventas:** ceros, asimetría y colas altas no son automáticamente errores. Mantener decimales y revisar valores extremos por familia/tienda sin eliminarlos arbitrariamente. No usar el perfil global (incluidos cuantiles, categorías o imputaciones) como transformación ajustada con datos posteriores al corte.',
            '- **Test/submission:** no incorporarlos al bootstrap ni a lotes de observaciones reales. No hay ventas reales en test; una plantilla de submission no sirve para evaluar el modelo.',
            '- **Ventanas y lags:** al emitir siete días, toda variable debe estar disponible en esa emisión. Un lag de un día para objetivos posteriores puede requerir predicciones recursivas; validar también disponibilidad dentro del horizonte. Separar emisión histórica, fecha objetivo y timestamp real de ejecución.','',
            '## Recomendaciones Bronze, Silver y Gold','']
    lines+=markdown_table(['Capa','Contrato propuesto','Controles y límites'],[
        ['Bronze','Parquet posterior: date como fecha; id entero 64 bits; store_nbr/cluster enteros; sales y petróleo decimales con escala decidida tras inspección; onpromotion/transactions enteros; transferred booleano; texto UTF-8','Conservar semántica y nulos, source_sha256, batch_id, source_file, row_number y timestamp real de ingesta. No se ha creado Parquet.'],
        ['Silver','sales UNIQUE(date, store_nbr, family), ventas NUMERIC sin truncar; dimensión stores por store_nbr; transactions UNIQUE(date, store_nbr); oil por date nullable; feriados con identidad de evento/ámbito','FK tienda donde esté cubierta; no FK obligatoria de venta a transacción. CHECK no negativos justificado por los valores observados y contrato, no como regla universal de todos los datasets minoristas. Feriados no UNIQUE(date). Esquemas aún no creados.'],
        ['Gold','Agregados por tienda/familia/día y features versionadas por corte','Lags/rolling desplazados y seguros al horizonte; calendario agregado sin fan-out; imputación solo hacia adelante con disponibilidad probada; no entrenar con estadísticas globales de este informe.']])
    lines+=['## Límites de las conclusiones','',
            'Las relaciones y recomendaciones describen las fuentes disponibles. Igualdad textual de claves no valida por sí sola una futura normalización; los tipos recomendados deben aplicarse con controles de rango/precisión en la fase de esquema. No se conoce inventario, demanda perdida ni fecha de publicación de todas las variables. Los ceros y extremos no permiten concluir causalidad. No se libera ningún mes, incluso si figura COMPLETE.','',
            'Resultados verificables y cobertura completa: `DATA_PROFILING.json`; plan de bootstrap y lotes: `DATA_BATCH_MANIFEST.json`. Los hashes de Fase 0 siguen en `DATA_INVENTORY.json`.']
    return '\n'.join(lines)+'\n'
