# Hallazgos de EDA — F1-04A

## Alcance, preguntas y evidencia

Se ejecutaron completos `01_exploratory_data_analysis.ipynb` y `02_time_series_analysis.ipynb`, cinco celdas de código cada uno, usando exclusivamente vistas `training` con `retailops_trainer`. Ventana fija **2013-01-01 a 2014-12-31**, lote bootstrap. Las consultas validaron sesión read_only=on, ausencia de permiso sobre Silver/control, ausencia visible posterior al corte y **1,297,296** observaciones. La evidencia de ejecución/hashes/tiempos está en `docs/EDA_EXECUTION.json` (también localmente en `.local/eda/execution.json`); los notebooks entregados no contienen outputs persistidos.

Preguntas: distribución/ceros/decimales; diferencias entre tiendas/familias; calendario mensual y cobertura; extremos; tendencia, asociación semanal/mensual, dependencia temporal y posibles cambios de nivel. Todas las cifras siguientes se calcularon nuevamente desde training, no se copiaron del perfil global de 2015–2017.

## Distribución y calidad observada

| Medida del bootstrap | Resultado |
| --- | --- |
| Ventas registradas, suma exacta SQL | 349893260.221161100000000000 |
| Media por observación | 269.71 |
| P25 / mediana / P75 | 0 / 3 / 136 |
| P95 / P99 / máximo | 1421 / 4339 / 46271 |
| Ventas cero | 568,354 (43.81%) |
| Valores no enteros | 172,071 (13.26%) |
| Valores negativos | 0, comprobado en la consulta de resumen |
| Tiendas / familias observadas en hechos | 54 / 33 |
| Días observados / calendario | 728 / 730 |
| Cuadrícula de cada día observado | 1 782 claves, comprobada en notebook |
| Fechas sin observación | 2013-12-25, 2014-12-25 |

**Interpretación:** la media muy superior a la mediana y P99 reflejan una distribución asimétrica y con muchos ceros. Ceros reales y fechas ausentes son distintos: las Navidades quedan NaN, no cero. Los decimales son observaciones válidas; no se redondean a enteros. Los máximos no son automáticamente errores. Los gráficos de extremos agregan grupos tienda/familia ≥ P99 del bootstrap, sin exportar registros individuales ni eliminar observaciones.

Las cantidades mezclan unidades/peso según familia: no representan ingresos monetarios ni unidades físicas homogéneas al agregarlas. Se usan float64 para visualizaciones/correlaciones, pero el total de resumen se conserva como NUMERIC/Decimal leído de SQL. Ningún resultado se escribe en la base.

[Distribución](eda_figures/eda_distribution.png) · [Extremos agregados](eda_figures/eda_extremes.png)

## Diferencias por tienda y familia

La tienda **44** tiene el mayor volumen registrado agregado y representa **6.20%** del total. La familia **GROCERY I** representa **35.44%**. Se graficaron todas las 54 tiendas y 33 familias, no solo las de mayor volumen. La concentración sugiere reportar posteriormente métricas por segmento además de una cifra global; no prueba eficiencia ni tamaño económico de las tiendas.

Las series ilustrativas del notebook 02 son tiendas **1, 28, 54**, elegidas por identificador, y familias **GROCERY I, BEVERAGES, CLEANING**, elegidas por volumen del propio bootstrap. Son ejemplos, no una muestra representativa o selección validada de entrenamiento. No se añadieron ciudad, tipo, cluster o fechas de apertura.

[Tiendas](eda_figures/eda_stores.png) · [Familias](eda_figures/eda_families.png) · [Series seleccionadas](eda_figures/ts_segments.png)

## Tendencia y posibles cambios

| Año | Ventas registradas agregadas | Media por día observado | Proporción de ceros |
| --- | --- | --- | --- |
| 2013 | 140419013.92 | 385766.52 | 50.45% |
| 2014 | 209474246.30 | 575478.70 | 37.17% |

La media diaria de cantidades registradas es **49.18%** mayor en 2014. Ambos años tienen 364 días observados y la misma cuadrícula, mientras la proporción de ceros baja. Esto **no** demuestra crecimiento equivalente de demanda real ni permite atribuirlo a aperturas, promociones o cambios operativos. Hay niveles variables dentro de 2014 que requieren análisis por segmento en la fase posterior.

El mayor incremento entre medias mensuales por día observado ocurre en **2014-03 (+52.80%)** y la mayor caída en **2014-04 (-34.74%)**. Son candidatos descriptivos de revisión, no detecciones estadísticas de cambios de régimen. No se ajustó un detector ni se formuló una explicación causal.

Las curvas de 7/28 días son medias retrospectivas descriptivas con mínimos de 5/21 observaciones; no se han materializado como features. Las fechas de los puntos mensuales identifican el período, no la fecha en que el total mensual habría estado disponible para pronosticar.

[Tendencia](eda_figures/ts_trend.png) · [Totales y medias mensuales](eda_figures/eda_monthly.png)

## Calendario semanal y mensual

| Día | Media del total diario observado |
| --- | --- |
| Lunes | 468928.53 |
| Martes | 424364.84 |
| Miércoles | 437924.22 |
| Jueves | 381956.75 |
| Viernes | 427856.54 |
| Sábado | 591905.51 |
| Domingo | 631014.11 |

Sábado y domingo muestran medias agregadas mayores que los días laborables en este período. Los perfiles se graficaron también por año para mostrar que el nivel no es constante. Esa asociación no es un efecto causal ni una garantía de estacionalidad por cada tienda/familia.

Diciembre tiene una media por día observado elevada en ambos años. Se dispone de **solo dos ciclos anuales**; los demás meses presentan diferencias importantes entre años. No se concluye una estacionalidad anual estable. Comparar totales sin normalizar duración del mes o rellenar Navidades con cero distorsionaría el análisis.

[Perfil semanal](eda_figures/ts_weekly.png) · [Perfil mensual](eda_figures/ts_monthly.png)

## Correlación por retardo de calendario

Se usa Pearson por pares observados sobre un índice diario completo con NaN. Es una definición explícita para fechas ausentes; no se afirma equivalencia con todos los estimadores de ACF. No se comprimió el calendario, interpoló, completó con ceros o usó información posterior a 2014.

| Retardo (días) | Serie agregada | Diferencia de log(1+ventas) | Pares disponibles, serie diferenciada |
| --- | --- | --- | --- |
| 1 | 0.750 | -0.203 | 722 |
| 7 | 0.822 | 0.420 | 716 |
| 14 | 0.777 | 0.291 | 709 |
| 28 | 0.664 | 0.281 | 695 |
| 56 | 0.664 | 0.283 | 667 |

La correlación a siete días permanece positiva tras diferenciar log(1+ventas), aunque es menor que en la serie original. Esto motiva comparar un baseline semanal; no prueba estacionariedad, causalidad, significación estadística o precisión predictiva. La agregación puede ocultar intermitencia por segmento y los pares válidos cambian con el lag. No se calcularon bandas de confianza ni se realizaron pruebas múltiples de significación.

[Correlaciones por retardo](eda_figures/ts_autocorrelation.png)

## Restricciones de acceso y límites

- Las vistas de stores/families/holidays/oil devuelven cero filas por ausencia de known_from/evidencia. No se usaron sus tablas base, SOURCE o ficheros de otra fase para completar metadatos. No se analizan efectos de feriados, cotizaciones, promociones, ubicación o tipo de tienda.
- Las categorías tienda/familia provienen de hechos autorizados; no de vocabularios del futuro. La existencia de ceros no identifica aperturas o cierres.
- No hay precios, existencias, demanda insatisfecha ni tiempos de reposición; no se interpreta la cantidad registrada como demanda no censurada o beneficio.
- El rol no puede consultar el singleton de control. Se verifican identidad/permisos, población visible, fechas y ausencia futura; no se afirma haber leído el corte con privilegios elevados.
- El análisis es retrospectivo sobre 2013–2014 completo, no un backtest. Sus cuantiles, selección de segmentos y conclusiones no pueden reutilizarse sin recalcular en la ventana de entrenamiento de cada fold histórico.
- Se agregan datos en PostgreSQL y se imponen límites de tiempo/filas. Los percentiles ordenan observaciones en servidor; no se descarga la tabla de 1,3 millones al notebook.
- Los notebooks persistidos carecen de outputs y credenciales; solo se exportan gráficos agregados y este informe. Los resúmenes de ejecución locales no son un feature store ni sustituyen el origen autorizado.

## Hipótesis para F1-04B y baselines posibles — no implementados

1. Comparar un **naive de último valor observado** constante durante los siete días y un **naive semanal (lag 7)** por tienda/familia. Para los objetivos de los próximos siete días, comprobar que cada lag proviene de una fecha ya observada al emitir.
2. Considerar media/mediana retrospectiva de 28 días y una variante por día de semana, con estrategia explícita para lags ausentes (por ejemplo, mediana de observaciones previas autorizadas), nunca relleno cero automático o valores reales futuros.
3. Investigar ceros/intermitencia por segmento y reportar métricas segmentadas además de globales, evitando que familias de gran volumen oculten otras. La mezcla de unidades impide tratar todos los agregados como magnitudes comerciales homogéneas.
4. Evaluar log1p y métodos robustos como hipótesis; no recortar outliers por el P99 del EDA ni usar estadísticas globales para folds anteriores. No se entrenó ni seleccionó ninguna transformación/modelo aquí.
5. Diseñar backtests temporales de siete días dentro de 2013–2014, recalculando vocabularios, ventanas y estadísticas solo con pasado de cada emisión. Los resultados de 2015–2017 no se utilizan para elegir baselines.

F1-04B/GOLD, entrenamiento y MLflow permanecen pendientes de autorización. No se creó ninguna tabla, feature persistida, ingesta ni lote liberado.
