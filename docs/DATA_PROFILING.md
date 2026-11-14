# Perfilado y calidad de Corporación Favorita

Informe generado por `retailops_profiling` con Python 3.12. Las cifras proceden exclusivamente de los CSV locales. Los resultados son descriptivos de toda la fuente y **no son features, estadísticas de entrenamiento ni datos liberados**. No se avanzó el corte histórico.

## Reproducción y método

Desde la raíz del repositorio (con el Python 3.12 ya instalado por uv):

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv run --project pipelines/ingestion --locked python pipelines/ingestion/profile_dataset.py --source data/source/favorita --output docs
uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/tests -v
```

El proyecto usa solo la biblioteca estándar y su propio `pyproject.toml`/`uv.lock`. El lanzador permite importar el módulo al ejecutar el comando desde la raíz. Alternativamente, ejecutar `uv run --locked python -m retailops_profiling --source ../../data/source/favorita --output ../../docs` desde `pipelines/ingestion`.

Lectura CSV en bloques configurables (10 000 filas por defecto). SQLite de la biblioteca estándar se usa únicamente dentro de un directorio temporal, con caché de 16 MiB y ordenaciones temporales en disco; se elimina al terminar. No se crean tablas de aplicación ni capas Bronze/Silver. Los agregados de cobertura conservan como máximo las series y días observados, no todas las filas.

Nulos: celdas vacías o solo espacios; no se convierte automáticamente «NA» o «NaN» en ausencia. Se registran tipos no finitos y valores incompatibles por separado. Filas con longitud incorrecta se cuentan y se excluyen de cálculos de contenido, sin silenciarlas. Un archivo ausente figura explícitamente.

Duplicados: exceso de filas respecto a grupos distintos, tanto para filas completas como para claves naturales; no equivale a cantidad de grupos duplicados. La clave de ventas excluye `id`. Las cardinalidades excluyen nulos. La inferencia revisa todos los valores; los tipos recomendados son contratos propuestos y muestran incompatibilidades. Las estadísticas numéricas usan float64 y Welford (desviación poblacional); los percentiles son exactos sobre esos valores con interpolación lineal. No determinan precisión SQL ni modifican el CSV. Fechas con varios eventos son válidas en feriados.

SHA-256 antes/después de cada archivo y una segunda comprobación global al terminar protegen contra cambios durante la ejecución. Los resultados se escriben solo fuera de SOURCE. El informe/JSON no exportan registros originales.

## Resumen de archivos

| Archivo | Filas | Columnas | Celdas nulas | Filas duplicadas (exceso) | Claves duplicadas (exceso) | Filas malformadas |
| --- | --- | --- | --- | --- | --- | --- |
| stores.csv | 54 | 5 | 0 | 0 | 0 | 0 |
| holidays_events.csv | 350 | 6 | 0 | 0 | no se exige | 0 |
| oil.csv | 1218 | 2 | 43 | 0 | 0 | 0 |
| transactions.csv | 83488 | 3 | 0 | 0 | 0 | 0 |
| sample_submission.csv | 28512 | 2 | 0 | 0 | 0 | 0 |
| test.csv | 28512 | 5 | 0 | 0 | 0 | 0 |
| train.csv | 3000888 | 6 | 0 | 0 | 0 | 0 |

## stores.csv

SHA-256: `af503b2bce11d7906d249f81cc0598f10e2addcc9f6c59aa2d95c9f2652c296b`. Tamaño: 1387 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| store_nbr | integer | SMALLINT | 0 | 54 | 0 | — |
| city | text | TEXT | 0 | 22 | 0 | — |
| state | text | TEXT | 0 | 16 | 0 | — |
| type | text | TEXT | 0 | 5 | 0 | — |
| cluster | integer | SMALLINT | 0 | 17 | 0 | — |

| Variable | Mín. | Máx. | Media | Desv. poblacional | Ceros | Negativos | No enteros |
| --- | --- | --- | --- | --- | --- | --- | --- |
| store_nbr | 1 | 54 | 27.5 | 15.585784 | 0 | 0 | 0 |
| cluster | 1 | 17 | 8.481481 | 4.649734 | 0 | 0 | 0 |

Frecuencias categóricas principales (máximo diez por columna; el JSON conserva las mismas frecuencias):

| Variable | Valor : frecuencia |
| --- | --- |
| store_nbr | 1: 1; 10: 1; 11: 1; 12: 1; 13: 1; 14: 1; 15: 1; 16: 1; 17: 1; 18: 1 |
| city | Quito: 18; Guayaquil: 8; Cuenca: 3; Santo Domingo: 3; Ambato: 2; Latacunga: 2; Machala: 2; Manta: 2; Babahoyo: 1; Cayambe: 1 |
| state | Pichincha: 19; Guayas: 11; Azuay: 3; Manabi: 3; Santo Domingo de los Tsachilas: 3; Cotopaxi: 2; El Oro: 2; Los Rios: 2; Tungurahua: 2; Bolivar: 1 |
| type | D: 18; C: 15; A: 9; B: 8; E: 4 |
| cluster | 3: 7; 10: 6; 6: 6; 15: 5; 13: 4; 14: 4; 1: 3; 11: 3; 4: 3; 8: 3 |

Clave comprobada: `(store_nbr)`; filas con componentes nulos: 0. La comprobación usa los valores de la fuente sin normalizar identificadores.

## holidays_events.csv

SHA-256: `81a183d6c4d691b57f84a0fde6bbf734a5b3c36a74b97378bf33a592648e2999`. Tamaño: 22309 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| date | date | DATE | 0 | 312 | 0 | 2012-03-02 → 2017-12-26 |
| type | text | TEXT | 0 | 6 | 0 | — |
| locale | text | TEXT | 0 | 3 | 0 | — |
| locale_name | text | TEXT | 0 | 24 | 0 | — |
| description | text | TEXT | 0 | 103 | 0 | — |
| transferred | boolean | BOOLEAN | 0 | 2 | 0 | — |

Frecuencias categóricas principales (máximo diez por columna; el JSON conserva las mismas frecuencias):

| Variable | Valor : frecuencia |
| --- | --- |
| type | Holiday: 221; Event: 56; Additional: 51; Transfer: 12; Bridge: 5; Work Day: 5 |
| locale | National: 174; Local: 152; Regional: 24 |
| locale_name | Ecuador: 174; Quito: 13; Ambato: 12; Guaranda: 12; Latacunga: 12; Riobamba: 12; Guayaquil: 11; Cuenca: 7; Ibarra: 7; Cayambe: 6 |
| description | Carnaval: 10; Fundacion de Cuenca: 7; Fundacion de Ibarra: 7; Cantonizacion de Cayambe: 6; Cantonizacion de El Carmen: 6; Cantonizacion de Guaranda: 6; Cantonizacion de Latacunga: 6; Cantonizacion de Libertad: 6; Cantonizacion de Quevedo: 6; Cantonizacion de Riobamba: 6 |
| transferred | False: 338; True: 12 |

La fecha no es clave única: pueden coincidir feriados nacionales, regionales, locales y eventos. Los duplicados de fila completa se informan para revisión; no se eliminan automáticamente.

## oil.csv

SHA-256: `944b23b857580f9d804399346fd3ed69bffcb7facfd98c55fdb408b8d057cca7`. Tamaño: 20580 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| date | date | DATE | 0 | 1218 | 0 | 2013-01-01 → 2017-08-31 |
| dcoilwtico | decimal | NUMERIC | 43 | 998 | 0 | — |

| Variable | Mín. | Máx. | Media | Desv. poblacional | Ceros | Negativos | No enteros |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dcoilwtico | 26.19 | 110.62 | 67.714366 | 25.619567 | 0 | 0 | 1165 |

| Variable | P25 | P50 | P75 | P95 | P99 |
| --- | --- | --- | --- | --- | --- |
| dcoilwtico | 46.405 | 53.19 | 95.66 | 105.195 | 107.9578 |

Clave comprobada: `(date)`; filas con componentes nulos: 0. La comprobación usa los valores de la fuente sin normalizar identificadores.

## transactions.csv

SHA-256: `e116384a6981af74932832436aa2f6a43121f77ca81accc44e3a5160158ca03c`. Tamaño: 1552637 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| date | date | DATE | 0 | 1682 | 0 | 2013-01-01 → 2017-08-15 |
| store_nbr | integer | SMALLINT | 0 | 54 | 0 | — |
| transactions | integer | INTEGER | 0 | 4993 | 0 | — |

| Variable | Mín. | Máx. | Media | Desv. poblacional | Ceros | Negativos | No enteros |
| --- | --- | --- | --- | --- | --- | --- | --- |
| store_nbr | 1 | 54 | 26.939237 | 15.60811 | 0 | 0 | 0 |
| transactions | 5 | 8,359 | 1,694.602158 | 963.280874 | 0 | 0 | 0 |

| Variable | P25 | P50 | P75 | P95 | P99 |
| --- | --- | --- | --- | --- | --- |
| transactions | 1,046 | 1,393 | 2,079 | 3,712 | 4,862 |

Frecuencias categóricas principales (máximo diez por columna; el JSON conserva las mismas frecuencias):

| Variable | Valor : frecuencia |
| --- | --- |
| store_nbr | 26: 1678; 31: 1678; 33: 1678; 34: 1678; 37: 1678; 38: 1678; 39: 1678; 16: 1677; 2: 1677; 23: 1677 |

Clave comprobada: `(date, store_nbr)`; filas con componentes nulos: 0. La comprobación usa los valores de la fuente sin normalizar identificadores.

## sample_submission.csv

SHA-256: `17505ec561d9bc64a3c10c3eb00474becf162d9053cebf014a58a6c82ed530c4`. Tamaño: 342153 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| id | integer | BIGINT | 0 | 28512 | 0 | — |
| sales | decimal | NUMERIC | 0 | 1 | 0 | — |

| Variable | Mín. | Máx. | Media | Desv. poblacional | Ceros | Negativos | No enteros |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | 3,000,888 | 3,029,399 | 3,015,143.5 | 8,230.705433 | 0 | 0 | 0 |
| sales | 0 | 0 | 0 | 0 | 28512 | 0 | 0 |

| Variable | P25 | P50 | P75 | P95 | P99 |
| --- | --- | --- | --- | --- | --- |
| sales | 0 | 0 | 0 | 0 | 0 |

IDs repetidos (exceso): 0.

Clave comprobada: `(id)`; filas con componentes nulos: 0. La comprobación usa los valores de la fuente sin normalizar identificadores.

## test.csv

SHA-256: `087ec1ecec76dbba9ea2adb48b8b2fd527c7c59adb82b0dfb9f6f82739400d26`. Tamaño: 1022269 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| id | integer | BIGINT | 0 | 28512 | 0 | — |
| date | date | DATE | 0 | 16 | 0 | 2017-08-16 → 2017-08-31 |
| store_nbr | integer | SMALLINT | 0 | 54 | 0 | — |
| family | text | TEXT | 0 | 33 | 0 | — |
| onpromotion | integer | INTEGER | 0 | 212 | 0 | — |

| Variable | Mín. | Máx. | Media | Desv. poblacional | Ceros | Negativos | No enteros |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | 3,000,888 | 3,029,399 | 3,015,143.5 | 8,230.705433 | 0 | 0 | 0 |
| store_nbr | 1 | 54 | 27.5 | 15.585784 | 0 | 0 | 0 |
| onpromotion | 0 | 646 | 6.965383 | 20.683589 | 15943 | 0 | 0 |

| Variable | P25 | P50 | P75 | P95 | P99 |
| --- | --- | --- | --- | --- | --- |
| onpromotion | 0 | 0 | 6 | 35 | 82 |

Frecuencias categóricas principales (máximo diez por columna; el JSON conserva las mismas frecuencias):

| Variable | Valor : frecuencia |
| --- | --- |
| store_nbr | 1: 528; 10: 528; 11: 528; 12: 528; 13: 528; 14: 528; 15: 528; 16: 528; 17: 528; 18: 528 |
| family | AUTOMOTIVE: 864; BABY CARE: 864; BEAUTY: 864; BEVERAGES: 864; BOOKS: 864; BREAD/BAKERY: 864; CELEBRATION: 864; CLEANING: 864; DAIRY: 864; DELI: 864 |

IDs repetidos (exceso): 0.

Clave comprobada: `(date, store_nbr, family)`; filas con componentes nulos: 0. La comprobación usa los valores de la fuente sin normalizar identificadores.

## train.csv

SHA-256: `99a1b7f4241821df10fa71f23abdd71c634f71f901e3cab1400c0f0c583f862c`. Tamaño: 121800373 bytes. Cabecera contractual exacta: sí. Fuente sin cambios durante su lectura: sí.

| Columna | Tipo inferido | Tipo recomendado | Nulos | Cardinalidad | Incompatibles con tipo recomendado | Rango de fechas |
| --- | --- | --- | --- | --- | --- | --- |
| id | integer | BIGINT | 0 | 3000888 | 0 | — |
| date | date | DATE | 0 | 1684 | 0 | 2013-01-01 → 2017-08-15 |
| store_nbr | integer | SMALLINT | 0 | 54 | 0 | — |
| family | text | TEXT | 0 | 33 | 0 | — |
| sales | decimal | NUMERIC | 0 | 379610 | 0 | — |
| onpromotion | integer | INTEGER | 0 | 362 | 0 | — |

| Variable | Mín. | Máx. | Media | Desv. poblacional | Ceros | Negativos | No enteros |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | 0 | 3,000,887 | 1,500,443.5 | 866,281.747304 | 1 | 0 | 0 |
| store_nbr | 1 | 54 | 27.5 | 15.585784 | 0 | 0 | 0 |
| sales | 0 | 124,717 | 357.775749 | 1,101.997538 | 939130 | 0 | 462113 |
| onpromotion | 0 | 741 | 2.60277 | 12.21888 | 2389559 | 0 | 0 |

| Variable | P25 | P50 | P75 | P95 | P99 |
| --- | --- | --- | --- | --- | --- |
| sales | 0 | 11 | 195.84725 | 1,965 | 5,507 |
| onpromotion | 0 | 0 | 0 | 13 | 55 |

Frecuencias categóricas principales (máximo diez por columna; el JSON conserva las mismas frecuencias):

| Variable | Valor : frecuencia |
| --- | --- |
| store_nbr | 1: 55572; 10: 55572; 11: 55572; 12: 55572; 13: 55572; 14: 55572; 15: 55572; 16: 55572; 17: 55572; 18: 55572 |
| family | AUTOMOTIVE: 90936; BABY CARE: 90936; BEAUTY: 90936; BEVERAGES: 90936; BOOKS: 90936; BREAD/BAKERY: 90936; CELEBRATION: 90936; CLEANING: 90936; DAIRY: 90936; DELI: 90936 |

IDs repetidos (exceso): 0.

Clave comprobada: `(date, store_nbr, family)`; filas con componentes nulos: 0. La comprobación usa los valores de la fuente sin normalizar identificadores.

## Granularidad y cobertura de ventas

Train abarca **2013-01-01 → 2017-08-15**, 1684 fechas, 54 tiendas y 33 familias. Hay 1782 series observadas de 1782 combinaciones esperadas, con granularidad diaria por `(date, store_nbr, family)`.

Exceso de claves repetidas: 0; fechas con filas/claves distintas de la cuadrícula esperada (1782 al día): 0.

Fechas ausentes dentro del rango observado: 2013-12-25, 2014-12-25, 2015-12-25, 2016-12-25.

Ventas cero: 939130 (31.30 %); ventas negativas: 0; ventas no enteras: 462113. Promociones negativas: 0; promociones no enteras: 0. Primera fecha con promociones positivas: 2014-04-01.

Los ceros pueden representar falta de actividad, cierres o ausencia de ventas; no se pueden identificar aperturas ni demanda insatisfecha solo con estas observaciones. Una venta decimal es coherente con familias vendidas por peso, no un error por defecto. `onpromotion` se trata como conteo de productos promocionados de la familia/tienda, no como booleano ni porcentaje; los CSV por sí solos no certifican cuándo se conoció ese conteo.

### Cobertura por serie, tienda y familia

Se comprueba cada combinación observada. Firmas de cobertura por serie (el JSON `DATA_PROFILING.json` incluye las series individuales, además de agregados por tienda/familia):

| Series con esta firma | Filas por serie | Días por serie | Primera fecha | Última fecha | Días ausentes en calendario train |
| --- | --- | --- | --- | --- | --- |
| 1782 | 1684 | 1684 | 2013-01-01 | 2017-08-15 | 4 |

| Tienda | Filas | Días | Familias | Inicio | Fin |
| --- | --- | --- | --- | --- | --- |
| 1 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 2 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 3 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 4 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 5 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 6 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 7 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 8 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 9 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 10 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 11 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 12 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 13 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 14 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 15 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 16 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 17 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 18 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 19 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 20 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 21 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 22 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 23 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 24 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 25 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 26 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 27 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 28 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 29 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 30 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 31 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 32 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 33 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 34 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 35 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 36 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 37 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 38 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 39 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 40 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 41 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 42 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 43 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 44 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 45 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 46 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 47 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 48 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 49 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 50 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 51 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 52 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 53 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |
| 54 | 55572 | 1684 | 33 | 2013-01-01 | 2017-08-15 |

| Familia | Filas | Días | Tiendas | Inicio | Fin |
| --- | --- | --- | --- | --- | --- |
| AUTOMOTIVE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| BABY CARE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| BEAUTY | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| BEVERAGES | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| BOOKS | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| BREAD/BAKERY | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| CELEBRATION | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| CLEANING | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| DAIRY | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| DELI | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| EGGS | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| FROZEN FOODS | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| GROCERY I | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| GROCERY II | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| HARDWARE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| HOME AND KITCHEN I | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| HOME AND KITCHEN II | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| HOME APPLIANCES | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| HOME CARE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| LADIESWEAR | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| LAWN AND GARDEN | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| LINGERIE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| LIQUOR,WINE,BEER | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| MAGAZINES | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| MEATS | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| PERSONAL CARE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| PET SUPPLIES | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| PLAYERS AND ELECTRONICS | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| POULTRY | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| PREPARED FOODS | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| PRODUCE | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| SCHOOL AND OFFICE SUPPLIES | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |
| SEAFOOD | 90936 | 1684 | 54 | 2013-01-01 | 2017-08-15 |

### Promociones, ceros y transacciones por año

| Año | Filas | Filas con promoción positiva | Ventas cero | Filas con venta positiva sin transacción tienda/día |
| --- | --- | --- | --- | --- |
| 2013 | 648648 | 0 | 327273 | 68 |
| 2014 | 648648 | 64979 | 241081 | 49 |
| 2015 | 648648 | 135302 | 189816 | 0 |
| 2016 | 650430 | 227981 | 119922 | 3131 |
| 2017 | 404514 | 183067 | 61038 | 0 |

Una transición desde promociones siempre cero puede ser un cambio de disponibilidad/registro. No demuestra ausencia real de promociones antes de esa fecha. Documentar esta limitación antes de entrenar el bootstrap.

## Bootstrap y manifiesto mensual

`DATA_BATCH_MANIFEST.json` es un plan descriptivo: `purpose=PLAN_ONLY`, `release_performed=false`, `historical_cutoff=null` y todos los lotes `released=false`. No crea particiones, libera datos ni cambia estados de ejecución.

El manifiesto distingue `calendar_complete` de `observed_grid_complete` por mes. Completitud estricta respecto al calendario: todas las fechas del mes y todas las combinaciones tienda/familia, sin claves repetidas. Un mes con un feriado ausente se clasifica INCOMPLETE en este sentido aunque el CSV distribuido sea íntegro. No se inventan ventas ni se rechaza automáticamente un lote por esta etiqueta. La política de aceptación deberá decidirse en F1-03.

Lotes incrementales planificados: 32; completos respecto al calendario: 29; incompletos: 3.

| Lote | Desde | Hasta | Filas | Filas teóricas calendario | Completitud | Fechas ausentes |
| --- | --- | --- | --- | --- | --- | --- |
| bootstrap-2013-2014 | 2013-01-01 | 2014-12-31 | 1297296 | 1300860 | INCOMPLETE | 2013-12-25, 2014-12-25 |

Todos los meses observados (incluidos los del bootstrap):

| Mes | Filas | Días observados/calendario | Completitud | Fechas ausentes |
| --- | --- | --- | --- | --- |
| 2013-01 | 55242 | 31/31 | COMPLETE | ninguna |
| 2013-02 | 49896 | 28/28 | COMPLETE | ninguna |
| 2013-03 | 55242 | 31/31 | COMPLETE | ninguna |
| 2013-04 | 53460 | 30/30 | COMPLETE | ninguna |
| 2013-05 | 55242 | 31/31 | COMPLETE | ninguna |
| 2013-06 | 53460 | 30/30 | COMPLETE | ninguna |
| 2013-07 | 55242 | 31/31 | COMPLETE | ninguna |
| 2013-08 | 55242 | 31/31 | COMPLETE | ninguna |
| 2013-09 | 53460 | 30/30 | COMPLETE | ninguna |
| 2013-10 | 55242 | 31/31 | COMPLETE | ninguna |
| 2013-11 | 53460 | 30/30 | COMPLETE | ninguna |
| 2013-12 | 53460 | 30/31 | INCOMPLETE | 2013-12-25 |
| 2014-01 | 55242 | 31/31 | COMPLETE | ninguna |
| 2014-02 | 49896 | 28/28 | COMPLETE | ninguna |
| 2014-03 | 55242 | 31/31 | COMPLETE | ninguna |
| 2014-04 | 53460 | 30/30 | COMPLETE | ninguna |
| 2014-05 | 55242 | 31/31 | COMPLETE | ninguna |
| 2014-06 | 53460 | 30/30 | COMPLETE | ninguna |
| 2014-07 | 55242 | 31/31 | COMPLETE | ninguna |
| 2014-08 | 55242 | 31/31 | COMPLETE | ninguna |
| 2014-09 | 53460 | 30/30 | COMPLETE | ninguna |
| 2014-10 | 55242 | 31/31 | COMPLETE | ninguna |
| 2014-11 | 53460 | 30/30 | COMPLETE | ninguna |
| 2014-12 | 53460 | 30/31 | INCOMPLETE | 2014-12-25 |
| 2015-01 | 55242 | 31/31 | COMPLETE | ninguna |
| 2015-02 | 49896 | 28/28 | COMPLETE | ninguna |
| 2015-03 | 55242 | 31/31 | COMPLETE | ninguna |
| 2015-04 | 53460 | 30/30 | COMPLETE | ninguna |
| 2015-05 | 55242 | 31/31 | COMPLETE | ninguna |
| 2015-06 | 53460 | 30/30 | COMPLETE | ninguna |
| 2015-07 | 55242 | 31/31 | COMPLETE | ninguna |
| 2015-08 | 55242 | 31/31 | COMPLETE | ninguna |
| 2015-09 | 53460 | 30/30 | COMPLETE | ninguna |
| 2015-10 | 55242 | 31/31 | COMPLETE | ninguna |
| 2015-11 | 53460 | 30/30 | COMPLETE | ninguna |
| 2015-12 | 53460 | 30/31 | INCOMPLETE | 2015-12-25 |
| 2016-01 | 55242 | 31/31 | COMPLETE | ninguna |
| 2016-02 | 51678 | 29/29 | COMPLETE | ninguna |
| 2016-03 | 55242 | 31/31 | COMPLETE | ninguna |
| 2016-04 | 53460 | 30/30 | COMPLETE | ninguna |
| 2016-05 | 55242 | 31/31 | COMPLETE | ninguna |
| 2016-06 | 53460 | 30/30 | COMPLETE | ninguna |
| 2016-07 | 55242 | 31/31 | COMPLETE | ninguna |
| 2016-08 | 55242 | 31/31 | COMPLETE | ninguna |
| 2016-09 | 53460 | 30/30 | COMPLETE | ninguna |
| 2016-10 | 55242 | 31/31 | COMPLETE | ninguna |
| 2016-11 | 53460 | 30/30 | COMPLETE | ninguna |
| 2016-12 | 53460 | 30/31 | INCOMPLETE | 2016-12-25 |
| 2017-01 | 55242 | 31/31 | COMPLETE | ninguna |
| 2017-02 | 49896 | 28/28 | COMPLETE | ninguna |
| 2017-03 | 55242 | 31/31 | COMPLETE | ninguna |
| 2017-04 | 53460 | 30/30 | COMPLETE | ninguna |
| 2017-05 | 55242 | 31/31 | COMPLETE | ninguna |
| 2017-06 | 53460 | 30/30 | COMPLETE | ninguna |
| 2017-07 | 55242 | 31/31 | COMPLETE | ninguna |
| 2017-08 | 26730 | 15/31 | INCOMPLETE | 2017-08-16, 2017-08-17, 2017-08-18, 2017-08-19, 2017-08-20, 2017-08-21, 2017-08-22, 2017-08-23, 2017-08-24, 2017-08-25, 2017-08-26, 2017-08-27, 2017-08-28, 2017-08-29, 2017-08-30, 2017-08-31 |

## Integridad entre fuentes

| Comprobación | Resultado |
| --- | --- |
| train.csv.orphan_store_rows | 0 |
| test.csv.orphan_store_rows | 0 |
| transactions.csv.orphan_store_rows | 0 |
| test.unknown_families | 0 |
| train_test.overlapping_ids | 0 |
| train_test.overlapping_keys | 0 |
| test.ids_missing_submission | 0 |
| submission.ids_missing_test | 0 |
| transactions.rows_without_sales_key | 0 |
| train.store_days_missing_transactions | 7448 |
| train.positive_store_days_missing_transactions | 118 |
| train.zero_store_days_with_transactions | 0 |
| oil.train_days_without_row | 481 |
| oil.train_days_with_null | 40 |
| oil.train_days_without_observation | 521 |
| holidays.local_names_not_in_store_cities | 0 |
| holidays.regional_names_not_in_store_states | 0 |

Test: inicio 2017-08-16, fin 2017-08-31, 16 días. Su horizonte de competición no sustituye el objetivo de siete días de RetailOps. `sample_submission.sales` es una plantilla, no una observación ni una etiqueta válida para entrenar.

Fechas con más de un evento: 31; detalle de fechas/recuentos en JSON. Antes de un join con ventas, agregar indicadores por ámbito/tipo para evitar multiplicar ventas.

| Tipo de evento | Transferred | Filas |
| --- | --- | --- |
| Additional | False | 51 |
| Bridge | False | 5 |
| Event | False | 56 |
| Holiday | False | 209 |
| Holiday | True | 12 |
| Transfer | False | 12 |
| Work Day | False | 5 |

## Anomalías interpretadas y riesgo de fuga temporal

- **Calendario de ventas:** las fechas ausentes no se etiquetan automáticamente como corrupción. Conservar ausencia y una bandera; cualquier relleno debe justificarse y diferenciarse de un cero observado. El último mes termina en el máximo real de train, no en el fin nominal del mes.
- **Petróleo:** la ausencia de filas y las celdas nulas son problemas distintos. Días sin cotización pueden corresponder a calendario de mercado. No usar interpolación bidireccional ni backfill desde el futuro. Un forward-fill solo podrá partir de observaciones disponibles al corte; no garantiza que la cotización del mismo día estuviera publicada al emitir una predicción.
- **Transacciones:** granularidad tienda/día, no familia. La falta de una transacción no demuestra cero ventas ni cierre. Investigar faltantes con ventas positivas; no imponer una FK obligatoria desde cada venta a transacciones. En un horizonte futuro, las transacciones reales son desconocidas: excluirlas o usar lags observados seguros.
- **Feriados:** aplicar ámbito Local/Regional/National a ciudad/estado/país. `transferred=True` no equivale a día festivo activo en su fecha original; considerar Transfer, Bridge, Additional, Event y Work Day por separado. Los datos no incluyen fecha de anuncio, por lo que el calendario conocido históricamente requiere una hipótesis documentada. Coincidencias de eventos son relaciones uno-a-muchos legítimas.
- **Tiendas:** city/state/type/cluster son una fotografía sin vigencia temporal. No prueban fechas de apertura ni que una clasificación fuese conocida en 2013. Tratar esta disponibilidad como hipótesis, sin inferir aperturas a partir de ceros.
- **Promociones:** preservar el conteo; investigar el cambio de cobertura reportado por año. Las promociones futuras presentes en test no demuestran conocimiento al emitir predicciones históricas. En el baseline del bootstrap, excluirlas si no existe evidencia de disponibilidad; no fabricar historial promocional.
- **Ventas:** ceros, asimetría y colas altas no son automáticamente errores. Mantener decimales y revisar valores extremos por familia/tienda sin eliminarlos arbitrariamente. No usar el perfil global (incluidos cuantiles, categorías o imputaciones) como transformación ajustada con datos posteriores al corte.
- **Test/submission:** no incorporarlos al bootstrap ni a lotes de observaciones reales. No hay ventas reales en test; una plantilla de submission no sirve para evaluar el modelo.
- **Ventanas y lags:** al emitir siete días, toda variable debe estar disponible en esa emisión. Un lag de un día para objetivos posteriores puede requerir predicciones recursivas; validar también disponibilidad dentro del horizonte. Separar emisión histórica, fecha objetivo y timestamp real de ejecución.

## Recomendaciones Bronze, Silver y Gold

| Capa | Contrato propuesto | Controles y límites |
| --- | --- | --- |
| Bronze | Parquet posterior: date como fecha; id entero 64 bits; store_nbr/cluster enteros; sales y petróleo decimales con escala decidida tras inspección; onpromotion/transactions enteros; transferred booleano; texto UTF-8 | Conservar semántica y nulos, source_sha256, batch_id, source_file, row_number y timestamp real de ingesta. No se ha creado Parquet. |
| Silver | sales UNIQUE(date, store_nbr, family), ventas NUMERIC sin truncar; dimensión stores por store_nbr; transactions UNIQUE(date, store_nbr); oil por date nullable; feriados con identidad de evento/ámbito | FK tienda donde esté cubierta; no FK obligatoria de venta a transacción. CHECK no negativos justificado por los valores observados y contrato, no como regla universal de todos los datasets minoristas. Feriados no UNIQUE(date). Esquemas aún no creados. |
| Gold | Agregados por tienda/familia/día y features versionadas por corte | Lags/rolling desplazados y seguros al horizonte; calendario agregado sin fan-out; imputación solo hacia adelante con disponibilidad probada; no entrenar con estadísticas globales de este informe. |

## Límites de las conclusiones

Las relaciones y recomendaciones describen las fuentes disponibles. Igualdad textual de claves no valida por sí sola una futura normalización; los tipos recomendados deben aplicarse con controles de rango/precisión en la fase de esquema. No se conoce inventario, demanda perdida ni fecha de publicación de todas las variables. Los ceros y extremos no permiten concluir causalidad. No se libera ningún mes, incluso si figura COMPLETE.

Resultados verificables y cobertura completa: `DATA_PROFILING.json`; plan de bootstrap y lotes: `DATA_BATCH_MANIFEST.json`. Los hashes de Fase 0 siguen en `DATA_INVENTORY.json`.
