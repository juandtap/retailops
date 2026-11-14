# GOLD point-in-time — F1-04B

## Contrato y semántica

Versión `sales-pit-v1`, snapshot `bootstrap-2013-2014/RELEASED/COMPLETE`, corte fijo **2014-12-31**. Fuente exclusiva de transformación: `training.sales`, sin SOURCE, estadísticas del perfil global, promociones, transacciones ni auxiliares. Contrato legible por máquina: [gold-features-v1.json](../contracts/gold-features-v1.json).

Cada emisión representa el **cierre del día**: se supone que las ventas observadas de ese día estaban disponibles entonces. La fuente no aporta tiempos históricos de llegada/corrección; esta simulación no prueba disponibilidad intradiaria real. `ingested_at` actual no se interpreta como disponibilidad histórica. No se permite incorporar revisiones retrospectivas silenciosas.

| Columna | Semántica |
| --- | --- |
| issue_date | Día al cierre del cual se observa la historia |
| target_date / horizon | issue_date + 1..7 días de calendario |
| store_nbr / family | Clave natural; combinación descubierta solo si fue observada antes o en issue_date |
| feature_version / historical_cutoff | Versión inmutable y estado autorizado usado, incluidos en la clave |
| day_of_week / month / is_weekend | Calendario del objetivo, ISO lunes=1/domingo=7; fin de semana sábado/domingo |
| lag_7 / lag_14 / lag_28 | Venta en target_date menos lag días, solo si existe y esa fecha ≤ issue_date |
| lag_*_available | Booleano independiente por lag; cero observado cuenta como disponible |
| rolling_mean_7 | Media de observaciones en [issue_date−6, issue_date] |
| rolling_mean_28 | Media de observaciones en [issue_date−27, issue_date] |
| rolling_std_28 | Desviación muestral, ddof=1, de la misma ventana de 28 días; NULL si hay menos de dos observaciones |
| history_count_28 | Número de observaciones, 0..28, sin comprimir fechas ausentes |
| missing_history_flag | history_count_28 < 28, incluido el borde izquierdo del histórico |

Las medias de una ventana vacía son NULL. Ventanas cortas usan solo las observaciones presentes, sin exigir siete/28 observaciones y sin inventar anteriores al inicio de la serie. Se conserva NUMERIC, incluidas ventas decimales; medias/desviaciones usan la precisión NUMERIC de PostgreSQL, sin conversión a float. El calendario denso es transitorio dentro del SELECT, no crea ventas. Una emisión el 25 de diciembre es válida aunque no haya venta de ese día; su historia conserva la ausencia.

Para horizontes 1..7, target_date−7 ≤ issue_date por construcción. El SQL comprueba además esta condición para cada lag. Ningún horizonte utiliza ventas reales de los primeros seis días pronosticados; las ventanas son iguales para los siete objetivos de una misma emisión.

## Tablas, vistas y etiquetas

- `gold.features`: materialización por emisión/tienda/familia/horizonte. PK `(feature_version, historical_cutoff, issue_date, store_nbr, family, horizon)`; checks de horizonte/fechas y coherencia de indicadores/NULL.
- `gold.labels`: venta real por `(historical_cutoff, target_date, store_nbr, family)`, separada de las entradas. CHECK impide fechas posteriores al corte. Los días sin venta fuente no tienen etiqueta; el consumidor debe conservar ausencia con LEFT JOIN, nunca COALESCE a cero.
- `gold.materializations`: 24 bloques mensuales con fechas, versión, SHA-256 del código, recuentos y timestamp real de terminación.
- `training.gold_features` / `training.gold_labels`: únicas superficies nuevas para trainer, de solo lectura; barreras de seguridad condicionadas al corte activo y bootstrap RELEASED/COMPLETE. Las features pueden tener objetivos futuros porque no contienen observaciones de esos objetivos; sus emisiones y su snapshot permanecen autorizados.

No se incluye una etiqueta entre las columnas de features. `MODEL_INPUTS` define la lista explícita de entradas para consumidores futuros; las claves/metadatos se transportan aparte. `BASELINE_INPUTS` declara compatibilidad con lag semanal y media retrospectiva, sin implementar/evaluar modelos. Para backtesting se unen etiquetas por fecha objetivo/tienda/familia/snapshot después de calcular features, y se limita el entrenamiento de cada fold a etiquetas ya observadas en su fecha de ajuste. Los ejemplos solapados requieren particiones temporales, nunca split aleatorio.

## Permisos y migraciones

Control V3 añade `control.require_gold_snapshot()`: SECURITY DEFINER con search_path fijo, sin SQL dinámico, valida estado fijo y toma FOR SHARE sobre estado/lote/publicación durante cada transacción. Solo ingestor puede invocarla; no recibe UPDATE del corte. Datos V3 crea GOLD y vistas. No se editaron V1/V2. El único runner sigue siendo Spring Boot/Flyway, control antes que datos, con historiales separados y propietarios migradores existentes.

`retailops_ingestor` es el rol de pipeline autorizado, separado de `retailops_trainer`: recibe SELECT sobre training.sales y SELECT/INSERT en las tres tablas GOLD; sin UPDATE/DELETE/DDL en GOLD. Ya era una identidad de ingesta confiable con permisos Silver, pero este módulo no los usa. No se introduce otra tecnología ni se entregan secretos migradores al materializador. El trainer conserva solo SELECT en training, sin acceso directo a gold/silver/control, TEMP, escritura o escalada. Tampoco se permite acceder a la función de control.

El pipeline es una autoridad de transformación confiable: sus permisos INSERT no impiden que un programa malicioso con ese secreto fabrique features dentro de los CHECK. La prevención de fuga se verifica en código, pruebas y referencia independiente; no se afirma aislamiento frente al propietario local, administradores o migradores.

## Reproducibilidad e idempotencia

Módulos en `pipelines/ingestion/retailops_gold`, proyecto uv existente Python 3.12, sin dependencias nuevas. El SQL reutilizable contiene calendario/ventanas/lags; una implementación independiente de referencia usa Decimal y búsquedas por fecha, sin compartir SQL ni pandas.

La ejecución toma el mismo advisory lock de sesión que bootstrap (rechaza concurrencia incompatible) y procesa un mes por transacción. Cada bloque inserta features, etiquetas y metadatos juntos. Un fallo revierte solo el mes actual; los meses confirmados se conservan. Una reejecución verifica el hash del código y compara **todos los valores en ambos sentidos mediante EXCEPT**, incluidos NULL, para features y etiquetas de bloques existentes. Diferencias de contenido o código causan error; no se ocultan mediante ON CONFLICT DO NOTHING ni se sobrescriben filas. Una nueva semántica requerirá versión y migración nuevas.

El incremental implementado es por bloques de emisiones faltantes dentro del bootstrap. GOLD v1 rechaza otro corte/último lote: **no incorpora automáticamente meses futuros**. Cambiar el snapshot requiere una ampliación explícita del contrato. No persiste predicciones; las futuras predicciones deberán tener identidad/versionado propio sin sobrescribir backtests históricos.

Volumen proyectado y real esperado por contrato: 730 emisiones × 1782 combinaciones × 7 horizontes = **9 106 020 features**. Calendario/SQL se procesa por mes más 27 días de contexto; no se transfieren millones de objetos Python. Límite PostgreSQL Compose 1 GiB/2 CPU; work_mem=16MB por operación (no es límite total), statement_timeout=300s y lock_timeout=5s. Cliente solo recibe recuentos; el disco disponible antes de ejecutar era 401 GiB. Esta proyección no exigió reducir la cobertura o cambiar sustancialmente el diseño.

## Comandos

Desde la raíz, secretos existentes 0600, sin regenerar credenciales ni volúmenes:

```bash
export UV_CACHE_DIR=/tmp/retailops-uv-cache
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
docker compose --env-file .env.example -f infra/docker/compose.yaml up -d --wait postgres
# Desde apps/api: MAVEN_USER_HOME=/tmp/retailops-maven ./mvnw -B -Dmaven.repo.local=/tmp/retailops-m2 verify
uv run --project pipelines/ingestion --locked python scripts/data_infra.py migrate
RETAILOPS_GOLD_INTEGRATION=1 uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/gold_tests -v
# Ejecutar datos reales solamente después de aprobar las pruebas anteriores:
uv run --project pipelines/ingestion --locked python pipelines/ingestion/materialize_gold.py --execute
uv run --project pipelines/ingestion --locked python pipelines/ingestion/verify_gold.py
# Repetir materialize_gold.py --execute comprueba idempotencia por contenido.
docker compose --env-file .env.example -f infra/docker/compose.yaml stop postgres
```

`POSTGRES_PORT` y `POSTGRES_DB` permiten los valores correspondientes a Compose; endpoint loopback fijo. El módulo lee únicamente pg_ingestor_password o pg_trainer_password y nunca imprime contraseñas. MinIO no se necesita para GOLD. No usar verificadores F1-02 de entorno vacío ni ejecutar down -v.

## Verificación y limitaciones

Las pruebas sintéticas ejecutan el SQL real con fuentes VALUES en una conexión trainer, sin TEMP ni alterar training.sales. Incluyen extremos futuros de 1e20, categorías exclusivamente futuras, horizonte siete, Navidad ausente, cero observado, series recién iniciadas y comparación independiente de cada feature. Las pruebas de almacenamiento validan permisos, unicidad con rollback, rechazo de etiquetas futuras y estado exacto. La verificación real contrasta 63 filas preseleccionadas contra Decimal, conteos, suma exacta de etiquetas, ausencias y límites; no utiliza estadísticas posteriores a 2014.

Resultados medidos, ejemplo real y consumo: [GOLD_INITIAL_EXECUTION.json](GOLD_INITIAL_EXECUTION.json), [GOLD_EXECUTION.json](GOLD_EXECUTION.json), [GOLD_VERIFICATION.json](GOLD_VERIFICATION.json). El RSS cliente excluye el servidor; el muestreo de Docker no prueba un pico universal. NUMERIC stddev tiene redondeo finito; referencia comparada con tolerancia absoluta/relativa 1e-12.

Limitaciones: disponibilidad al cierre es una hipótesis explícita; sin timestamps de publicación comercial. Identificadores de series se descubren desde hechos, sin dimensiones restringidas. No hay disponibilidad certificada de promociones/feriados/petróleo; siguen excluidos. Dos años y ausencias reales limitan features; no se imputa ni recorta por cuantiles EDA. No se entrenó/evaluó un modelo, no se instaló MLflow/Airflow, no se liberaron meses y no se modificaron notebooks ni CSV. Detenerse antes de F1-05.

## Ejemplo real verificado

Tienda 1, GROCERY I, emisión **2014-12-31**, objetivo **2015-01-01**, horizonte 1:

| Feature | Valor / disponibilidad en la emisión |
| --- | --- |
| day_of_week / month / is_weekend | 4 / 1 / false; calendario determinista |
| lag_7 | NULL, available=false: corresponde al 25 de diciembre ausente |
| lag_14 | 3428, available=true: venta observada el 18 de diciembre |
| lag_28 | 2845, available=true: venta observada el 4 de diciembre |
| rolling_mean_7 | 1776,5; seis observaciones del 25 al 31 de diciembre, Navidad excluida |
| rolling_mean_28 | 2557,888888888888888889; 27 observaciones del 4 al 31 de diciembre |
| rolling_std_28 | ≈870,769126574244; desviación muestral de esas 27 observaciones |
| history_count_28 / missing_history_flag | 27 / true |
| Etiqueta real | No existe para 2015-01-01; no se consulta ni inventa |

Hay **49 896** ejemplos con objetivo posterior al corte, válidos como entradas para futuras predicciones y sin etiqueta real. Las features y sus tablas/índices ocupan 2 073 886 720 bytes; etiquetas e índices, 133 038 080 bytes (medidos tras la primera carga). Cliente: RSS máximo 47 232 KiB; PostgreSQL: muestra Docker de 186,8 MiB durante la carga, límite 1 GiB. El muestreo no es medida de pico. Primera carga 83,905 s, 24 bloques confirmados.

La comparación idempotente completa consume más que la primera inserción porque recalcula y compara todos los campos. Una segunda muestra Docker durante esa comprobación registró **423,5 MiB / 1 GiB** y ~101 % CPU; tampoco constituye una medida de pico. El tiempo completo y RSS del cliente de la reejecución se conservan en GOLD_EXECUTION.json.

Reejecución real completa: **302.014 s**, RSS máximo cliente **49484 KiB**, 24 bloques reutilizados, mismos recuentos/contenido, estado SUCCEEDED.
