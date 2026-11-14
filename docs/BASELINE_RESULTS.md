# Resultados baseline — F1-05

Ejecutado completo `notebooks/03_baseline_backtesting.ipynb` sobre las vistas **training.gold_features y training.gold_labels**, con retailops_trainer y transacciones read-only. Snapshot sales-pit-v1, corte 2014-12-31. No se modificaron datos/materializaciones/migraciones ni se utilizaron SOURCE, Silver, auxiliares o estadísticas de 2015–2017.

## Métodos y protocolo

- **Seasonal Naïve:** lag_7 cuando lag_7_available=true; si falta, predicción ausente.
- **Rolling Mean 7:** rolling_mean_7 de GOLD, constante para los siete horizontes de cada emisión.
- **Rolling Mean 28:** rolling_mean_28 de GOLD, también constante durante el horizonte.

Las medias no modelan explícitamente el día de semana objetivo. No hay parámetros ajustados ni entrenamiento simulado; no se optimizaron umbrales/transformaciones con estos resultados. Las ventas del día de emisión se suponen disponibles al cierre, conforme a GOLD; faltan timestamps históricos de llegada.

Los folds son meses de **emisión**, no conjuntos de entrenamiento. Se puntúan todos sus objetivos disponibles hasta el corte, incluso cuando caen en el mes siguiente:

| Fold | Emisiones | Objetivos | Ejemplos | Sin etiqueta / posteriores al corte |
| --- | --- | --- | --- | --- |
| Julio | 2014-07-01..2014-07-31 | 2014-07-02..2014-08-07 | 386694 | 0 / 0 |
| Septiembre | 2014-09-01..2014-09-30 | 2014-09-02..2014-10-07 | 374220 | 0 / 0 |
| Noviembre | 2014-11-01..2014-11-30 | 2014-11-02..2014-12-07 | 374220 | 0 / 0 |

Total: **1 135 134 ejemplos comparables**. Cobertura individual de los tres baselines: **100 %**, tanto sobre todos los ejemplos como sobre los etiquetados, en cada fold. La intersección común coincide aquí con los conjuntos individuales; por tanto las métricas individuales y comparables son idénticas. Esto no garantiza cobertura en Navidad, inicios de serie u otros períodos. Los NULL se preservan y se contabilizan; las métricas excluyen etiquetas ausentes u objetivos posteriores al corte, sin crear ventas cero. En estos folds la exclusión fue cero.

La predicción consume exclusivamente cuatro columnas de features; la etiqueta se une para puntuar y nunca entra al predictor. Se lee por fold con cursor de servidor en bloques de 20 000 filas, sin cargar 9,1 millones de ejemplos. Solo se conservan sumas suficientes por grupo y un ejemplo prefijado, no predicciones masivas.

## Métricas globales

MAE = Σ|predicción−real|/n; WAPE = Σ|predicción−real|/Σreal; RMSLE = sqrt(media((log1p(predicción)−log1p(real))²)). WAPE se muestra en **porcentaje** en este informe y como fracción en las tablas del notebook. Si Σreal=0, WAPE es indefinido. Las predicciones no negativas se validan, sin clipping ni transformación. Cálculo float64; no se modifica NUMERIC almacenado. Las métricas globales se obtienen de las sumas de todos los ejemplos, no promediando métricas de folds/bloques.

| Baseline | n | MAE | WAPE (%) | RMSLE |
| --- | --- | --- | --- | --- |
| Seasonal Naïve | 1135134 | 71.7157 | 19.6473 | 0.7927 |
| Rolling Mean 7 | 1135134 | 96.3464 | 26.3951 | 0.6683 |
| Rolling Mean 28 | 1135134 | 105.8060 | 28.9867 | 0.7312 |

**Referencia principal por MAE/WAPE: Seasonal Naïve** (71,7157 / 19,6473 %). **Mejor RMSLE global: Rolling Mean 7** (0,6683). No hay un ganador universal: las métricas ponderan los errores de distinta manera. No se justifica un ensemble o regla por segmento sin una evaluación posterior independiente.

[Comparación global](baseline_figures/global.png)

## Resultados por fold

| Fold | Baseline | MAE | WAPE (%) | RMSLE |
| --- | --- | --- | --- | --- |
| 2014-07 | Seasonal Naïve | 76.9302 | 22.7199 | 0.9855 |
| 2014-07 | Rolling Mean 7 | 91.6788 | 27.0756 | 0.8375 |
| 2014-07 | Rolling Mean 28 | 108.0817 | 31.9199 | 0.9104 |
| 2014-09 | Seasonal Naïve | 68.8454 | 18.2711 | 0.7980 |
| 2014-09 | Rolling Mean 7 | 99.8371 | 26.4962 | 0.5957 |
| 2014-09 | Rolling Mean 28 | 115.2628 | 30.5900 | 0.7055 |
| 2014-11 | Seasonal Naïve | 69.1978 | 18.1847 | 0.5154 |
| 2014-11 | Rolling Mean 7 | 97.6790 | 25.6694 | 0.5246 |
| 2014-11 | Rolling Mean 28 | 93.9976 | 24.7019 | 0.5171 |

El semanal obtiene menor MAE/WAPE en los tres folds. Rolling Mean 7 obtiene menor RMSLE en julio/septiembre; el semanal, en noviembre. Estos cambios son descriptivos, no pruebas de causalidad ni de cambio de régimen.

## Comparación por horizonte

Cada horizonte tiene 162 162 observaciones en la comparación común:

| Horizonte | MAE semanal | MAE media 7 | MAE media 28 | WAPE semanal (%) |
| --- | --- | --- | --- | --- |
| 1 | 77.0296 | 91.8614 | 104.0683 | 20.9311 |
| 2 | 75.2234 | 93.7073 | 104.4958 | 20.5016 |
| 3 | 72.7062 | 94.6872 | 104.1778 | 19.9049 |
| 4 | 72.0533 | 97.9049 | 106.7129 | 19.6823 |
| 5 | 70.5866 | 99.5835 | 108.1725 | 19.3145 |
| 6 | 68.2521 | 97.8206 | 106.1572 | 18.8285 |
| 7 | 66.1588 | 98.8602 | 106.8575 | 18.3327 |

Seasonal Naïve conserva menor MAE/WAPE en los siete horizontes. Su error decreciente aquí no demuestra que los horizontes largos sean intrínsecamente más fáciles: las fechas objetivo y su composición varían con el horizonte. El notebook y el resumen local contienen también RMSLE y WAPE de todos los métodos para cada horizonte.

[Errores por horizonte](baseline_figures/horizon.png)

## Familias y tiendas

Se calcularon MAE/WAPE/RMSLE para **todas las 33 familias y 54 tiendas**, sobre la intersección común. El notebook muestra los desgloses completos. Las tablas siguientes resumen los tres MAE menores y mayores **del semanal**, manteniendo los otros métodos en esas mismas claves; no se eligen modelos por segmento.

| Familia | MAE semanal | MAE media 7 | MAE media 28 | WAPE semanal (%) |
| --- | --- | --- | --- | --- |
| BOOKS | 0.0000 | 0.0000 | 0.0000 | Indefinido |
| BABY CARE | 0.0879 | 0.0761 | 0.0743 | 136.3841 |
| HOME APPLIANCES | 0.4378 | 0.3910 | 0.4209 | 121.0141 |
| PRODUCE | 417.4015 | 603.1339 | 865.3014 | 21.6455 |
| BEVERAGES | 514.2040 | 688.7661 | 762.1290 | 20.0406 |
| GROCERY I | 576.4159 | 778.1178 | 749.4526 | 17.2447 |

| Tienda | MAE semanal | MAE media 7 | MAE media 28 | WAPE semanal (%) |
| --- | --- | --- | --- | --- |
| 20 | 0.0000 | 0.0000 | 0.0000 | Indefinido |
| 21 | 0.0000 | 0.0000 | 0.0000 | Indefinido |
| 22 | 0.0000 | 0.0000 | 0.0000 | Indefinido |
| 47 | 194.9798 | 280.6341 | 301.9376 | 19.8873 |
| 45 | 195.5851 | 313.6467 | 339.7953 | 18.3067 |
| 44 | 218.8247 | 368.2226 | 414.7927 | 16.6223 |

Las familias de mayor MAE semanal son **GROCERY I, BEVERAGES y PRODUCE**; las de menor MAE son **BOOKS, BABY CARE y HOME APPLIANCES**. En BOOKS, todos los reales y las predicciones evaluadas son cero: MAE/RMSLE=0 y WAPE indefinido para los tres baselines. No se presenta ese caso como precisión comercial generalizable. BABY CARE/HOME APPLIANCES tienen errores absolutos pequeños y WAPE superior al 100 %: escalas pequeñas no implican buen error relativo. Las cantidades mezclan unidades/peso entre familias y no son ingresos; el volumen afecta el ranking por MAE.

[Todas las familias](baseline_figures/families.png) · [Ejemplo real frente a predicciones](baseline_figures/example.png)

El ejemplo fue fijado antes de evaluar: tienda 1, GROCERY I, emisión 2014-07-15 y objetivos 16..22 de julio. Las medias son constantes y el semanal conserva variación por día; un ejemplo no representa el rendimiento global.

## Ejecución reproducible y pruebas mínimas

Desde la raíz, con los secretos y volúmenes existentes:

```bash
export UV_CACHE_DIR=/tmp/retailops-uv-cache
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
docker compose --env-file .env.example -f infra/docker/compose.yaml up -d --wait --wait-timeout 120 postgres
uv run --project notebooks --locked python -m unittest discover -s notebooks/tests -p test_baselines.py -v
uv run --project notebooks --locked python notebooks/run_notebooks.py --only 03_baseline_backtesting.ipynb
# Si PostgreSQL estaba detenido antes de comenzar:
docker compose --env-file .env.example -f infra/docker/compose.yaml stop postgres
```

Mismo proyecto uv/Python 3.12.16 y kernel local, sin dependencias nuevas ni instalaciones globales. Variables EDA_PG_HOST/PORT/DATABASE y archivo pg_trainer_password según notebooks/README. Para JupyterLab interactivo: `uv run --project notebooks --locked python notebooks/lab.py`.

**Tres pruebas unitarias aprobadas**: métricas con resultado conocido y denominador cero; predicciones ausentes/ceros y etiquetas extremas que no cambian las predicciones; límites temporales de folds y coherencia emisión/objetivo/horizonte. No se repitieron suites de Java, GOLD, bootstrap ni infraestructura. La verificación funcional principal fue el notebook completo, con consultas reales de solo lectura y cuatro gráficos; comparación global y ejemplo revisados visualmente.

Notebook: **7 celdas de código ejecutadas sin errores**, 9.153 s en total; consultas/evaluación 7.378 s. SHA-256: `617fffcefab28e7a54add6e6e27a05b5dafeb2d5d340bf9f607f07fe60063821`. Notebook canónico con outputs=[] y execution_count=null, sin credenciales. Resultados completos por grupo en `.local/baselines/results.json`; evidencia de ejecución/hashes del módulo/lock en `.local/baselines/execution.json`, ambos locales ignorados. Se generaron cuatro PNG en docs/baseline_figures.

## Limitaciones y siguiente experimento

Solo tres meses de emisión de 2014; no se evalúan todos los años ni un holdout futuro. Emisiones diarias solapadas reutilizan etiquetas: n no representa muestras independientes y no se calculan intervalos de confianza. Los resultados no demuestran causalidad ni estabilidad fuera de estos folds. Los auxiliares no certificados siguen fuera del análisis. Navidad y series de poco historial tienen ausencias reales y no están representadas por la cobertura del 100 % observada aquí.

Siguiente experimento propuesto: un modelo supervisado global por tienda/familia con las mismas features point-in-time, manteniendo estos baselines fijos y **reservando antes del ajuste un período temporal posterior no usado aquí**. Definir los cortes internos y disponibilidad de etiquetas de cada entrenamiento antes de seleccionar hiperparámetros; reportar MAE/WAPE y RMSLE con coberturas comparables. No reutilizar estos folds como holdout independiente después de tomar decisiones con ellos. No se implementa ni entrena ese modelo en esta tarea.

F1-05 se ajustó al alcance autorizado: el roadmap anterior incluía MLflow, ahora queda expresamente diferido. No se inicializó Git, no se instaló MLflow/Airflow, no se liberaron meses y no se modificó GOLD. PostgreSQL estaba detenido inicialmente y se detuvo al cerrar conservando sus datos; MinIO permaneció detenido.
