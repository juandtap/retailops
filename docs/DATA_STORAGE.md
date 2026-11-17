# Diseño y contratos de almacenamiento — F1-02

## Alcance implementado

F1-02 se amplió explícitamente desde «PostgreSQL y MinIO en Compose» a diseño, contratos, migraciones y separación de acceso. Se mantiene el límite previo a F1-03: **cero observaciones, cero fuentes registradas, cero lotes, cero ejecuciones y corte histórico NULL**. Los 32 meses del manifiesto local siguen sin liberar. Las pruebas sintéticas no son ingestas y se revierten/eliminan.

PostgreSQL almacena datos relacionales y metadatos; MinIO almacena objetos. No se sustituye SOURCE por una copia mutable ni se instalan servicios en el SO. [Contrato verificable v1](../contracts/data-storage-v1.json), [operación Compose](../infra/docker/README.md).

## Capas y propiedad

| Capa | Ubicación / propietario lógico | Estado F1-02 |
| --- | --- | --- |
| SOURCE | `data/source/favorita`, archivos originales privados del desarrollador | Inmutables, hashes iguales a Fase 0; no montados en los servicios |
| RAW | MinIO, prefijo raw; ingestor escribe cuarentena | Buckets vacíos; contrato de bytes/checksum/versión preparado |
| BRONZE | MinIO, prefijo bronze; Parquet tipado con trazabilidad | Sin archivos ni transformación todavía |
| SILVER | PostgreSQL `silver`; propietario migrador de datos | Tablas vacías, integridad y permisos aplicados |
| GOLD | PostgreSQL `gold`; propietario migrador de datos | Solo esquema vacío; features/ETL pendientes de F1-04 |
| Acceso de entrenamiento | PostgreSQL `training`; vistas de seguridad | Aplicado y probado con fixtures revertidas; no hay entrenamiento |

## Modelo relacional

| Tabla / vista | Clave y contenido | Controles |
| --- | --- | --- |
| control.source_files | sha256, nombre original, bytes, timestamp real | Hash SHA-256 y archivo esperado; cero filas |
| control.batches | batch_id; tipo BOOTSTRAP/MONTHLY/AUXILIARY; entidad y período | Identidad única por tipo/entidad/período; estados PLANNED/STAGED/VALIDATED/RELEASED/FAILED; released_at consistente con RELEASED |
| control.batch_sources | batch_id + source_sha256 | Enlace entre lote y originales; FK desde toda observación |
| control.historical_state | Singleton; released_through y last_batch_id | Única fila técnica inicial, ambos NULL; no representa un bootstrap ejecutado |
| control.objects | bucket, key, version_id; lote/capa/hash/bytes | Referencia exacta y auditable a versiones, no asumir ETag como SHA-256 |
| control.ingestion_runs | run_id y batch_id | PENDING/RUNNING/SUCCEEDED/FAILED, tiempos reales, correlación Airflow futura, error en fallo; sin ejecuciones actuales |
| silver.stores | store_nbr | Ciudad/estado/tipo/cluster; known_from y evidencia, snapshot inicial sin vigencias inferidas |
| silver.families | family TEXT | Dimensión por nombre original, sin ID que sustituya la clave natural de ventas |
| silver.sales | **(date, store_nbr, family)**; source_id único | Ventas NUMERIC sin escala restrictiva (no truncar); onpromotion INTEGER ≥ 0; FK tienda/familia; sin FK obligatoria a transacciones |
| silver.holidays_events | event_id y unicidad del evento completo | Fecha/tipo/ámbito/nombre/descripción/transferred; fecha sola no es única |
| silver.oil_prices | date | dcoilwtico NUMERIC nullable, positivo si conocido; known_from/evidencia |
| silver.store_transactions | (date, store_nbr) | Conteo entero no negativo y FK tienda, sin multiplicar por familia |
| silver.observation_gaps | (date, entity, scope_key) | NOT_IN_SOURCE/UNKNOWN/PARTIAL_PERIOD, procedencia y lote; no crea ventas cero |
| training.* | Vistas con security_barrier | Predicados impuestos por servidor y privilegios; no exponen onpromotion de sales |
| training.holiday_features | Una fila por (date, store_nbr) | Flags agregados, count de eventos aplicables; evita fan-out |

Cada observación incluye batch_id, source_sha256, source_row_number y ingested_at real. La FK compuesta exige que esa fuente pertenezca al lote. source_file se resuelve mediante control.source_files. NUMERIC se mantiene sin una escala forzada para no perder decimales; el contrato limita NaN/infinito y valores negativos observados fuera del dominio. Las fechas deben ser finitas. Los identificadores de tienda/cluster positivos caben en SMALLINT según el perfil; futuros valores que no quepan requieren una migración, no truncamiento.

El ingestor tiene INSERT/SELECT sobre Silver y no UPDATE/DELETE. Un trigger SECURITY DEFINER con search_path fijo bloquea inserciones si el lote no existe o está RELEASED, tomando un bloqueo compartido sobre el lote para coordinar escrituras con la liberación. El propietario migrador es confiable y puede administrar el esquema. La idempotencia de reintentos deberá comparar contenido ante conflictos de PK; aún no se implementa el cargador.

## Responsables de migraciones

- Provisionamiento inicial Docker: solo base, logins y esquemas. No crea tablas de negocio. Se ejecuta una vez en volumen nuevo; reiniciar un volumen existente no repite init scripts.
- Plano de control: `retailops_control_migrator` administra únicamente `control`, scripts `apps/api/src/main/resources/db/control`. Historial `control.flyway_schema_history`.
- Ingeniería de datos: `retailops_data_migrator` administra `data_meta`, `silver`, `gold`, `training`, scripts `.../db/data`. Historial `data_meta.flyway_schema_history`.
- Un único runner de mantenimiento de Spring Boot/Flyway, perfil `storage`, ejecuta primero control y después datos con credenciales separadas. No hay migraciones paralelas de Airflow, scripts DDL de pipelines ni Hibernate ddl-auto. `spring.sql.init.mode=never`; limpieza Flyway deshabilitada.
- El rol de datos tiene SELECT/REFERENCES de los metadatos necesarios y UPDATE limitado a batch_id para que el guard tome FOR SHARE; no es credencial de trabajo. El rol API normal solo lee metadatos/vistas previstos y no posee el esquema.
- Las V1 aplicadas son inmutables desde su verificación. Cambios posteriores serán V2 y siguientes, nunca editar checksums ni usar repair para ocultar drift. El runner valida ambos historiales al repetir la ejecución.

## Buckets y prefijos

| Bucket privado | Contenido permitido | Acceso |
| --- | --- | --- |
| retailops-quarantine | RAW/BRONZE no liberado | Ingestor read/write; releaser read; trainer denegado explícitamente |
| retailops-released | Solo objetos cuya liberación ya fue autorizada | Releaser read/write; trainer read; ingestor sin permisos |
| retailops-artifacts | Modelos/experimentos futuros | Solo administración en esta fase; MLflow no desplegado |
| retailops-verification | Marcador de persistencia de infraestructura | Solo administración; no contiene datos comerciales |

Prefijos previstos: `raw/{entity}/year={YYYY}/month={MM}/batch={batch_id}/{source_sha256}.csv` y `bronze/{entity}/year={YYYY}/month={MM}/batch={batch_id}/{content_sha256}.parquet`. Artefactos futuros: `models/{model_name}/{version}/...`, sujetos a aprobación/versionado propios. No se crean carpetas ficticias ni objetos de datos vacíos para aparentar particiones.

Todos los buckets son privados y versionados. La versión debe registrarse junto con SHA-256 y bytes; versionado **no es WORM** ni impide por sí mismo un PutObject sobre la misma clave. Los roles de trabajo no tienen DeleteObject/administración. Idempotencia futura: identidad determinista de lote/objeto, comparación de checksum, rechazo de contenido diferente y referencia a version_id fija; no reutilizar «latest».

## Separación efectiva de acceso

El entrenador no tiene USAGE de silver/control/data_meta/gold, ni CREATE/TEMP en la base, ni membresía de roles privilegiados. Solo SELECT sobre vistas training. Estas vistas comprueban en el servidor que:

1. El lote esté RELEASED.
2. El singleton tenga un corte no nulo.
3. Para hechos observados, la fecha no exceda released_through.
4. Para dimensiones/calendario/petróleo, known_from sea conocido, no supere el corte y exista evidencia explícita.

Un lote STAGED con fecha antigua no pasa. Una fila con fecha futura en un lote marcado RELEASED tampoco pasa para hechos observados. Cambiar una variable de sesión de fecha no cambia estos predicados. Consultar directamente Silver, modificar el corte, asumir el rol migrador o crear tablas temporales se prueba con conexiones autenticadas del entrenador y se deniega.

En MinIO el entrenador solo puede leer/listar released; no puede leer/listar quarantine ni artifacts ni escribir released. El ingestor tampoco puede escribir released. Las pruebas suben marcadores **técnicos temporales**, comprueban un GET permitido y GET/PUT denegados por Access Denied, y eliminan sus versiones. Todos los buckets de datos quedan vacíos.

Este control protege frente a credenciales de entrenamiento, no frente a quien posee root de MinIO, superusuario PostgreSQL, roles migradores o Docker. El runtime de entrenamiento todavía no existe: F1-05 deberá ejecutarlo en un contenedor sin SOURCE, Docker socket, volúmenes internos de PostgreSQL/MinIO, secretos administrativos o configuración de perfilado global; solo credenciales trainer. Un proceso del usuario local con acceso al CSV completo podría saltarse estos límites. No se afirma que la PC entera sea una sandbox de datos.

### Publicación futura y consistencia entre almacenes

No existe una transacción distribuida PostgreSQL/S3 ni se ha implementado un servicio de liberación. En F1-03 deberán serializarse ingesta/promoción y verificarse contratos, conteos, hashes y versiones. El rol releaser es una autoridad confiable, no se entrega a training/ingestor. Para no adelantar objetos a la autorización SQL, la copia a released solo podrá comenzar **después** de que se confirme la liberación en PostgreSQL. Esto puede dejar objetos temporalmente no disponibles; no debe afirmarse atomicidad de disponibilidad entre almacenes.

El cargador futuro deberá reintentar publicaciones pendientes sin reescribir observaciones liberadas y marcar SUCCEEDED solo al verificar inventario publicado completo. Si falla una copia, conservar trazabilidad de objetos pendientes/errores y bloquear la siguiente liberación incompatible. El avance del corte deberá usar el máximo observado autorizado, no el fin nominal de un mes parcial (agosto de 2017 termina el día 15). Este protocolo y su recuperación necesitan implementación/pruebas en F1-03; F1-02 comprueba permisos y las barreras, no una promoción real. Nunca precopiar datos no autorizados a released para depender después de un filtro voluntario.

## Ausencias y disponibilidad al emitir

| Variable | Regla propuesta al emitir | Prohibido |
| --- | --- | --- |
| Ventas | Observadas en lotes liberados hasta el corte | Etiquetas/medias/quantiles posteriores, incluso del perfil global |
| Transacciones | Solo histórico liberado; lags seguros al horizonte | Valores reales de los siete días futuros |
| Promociones | Conteo original conservado en Silver; excluido de la vista de entrenamiento inicial | Suponer disponibilidad futura por aparecer en test o rellenar 2013 |
| Petróleo | Observaciones con fecha y known_from dentro del corte; NULL sigue desconocido | Interpolación/backfill futuros; suponer cotización publicada a tiempo sin evidencia |
| Feriados | known_from/evidencia y lote liberado; pueden referirse a un día objetivo futuro si ya eran conocidos | Usar anuncios retrospectivos desconocidos al emitir |
| Tiendas/familias | Snapshot con hipótesis de conocimiento aprobada y registrada | Inferir aperturas solo de ventas cero o asumir vigencias no presentes |

Las 43 cotizaciones nulas, los 118 tienda/día con ventas positivas sin transacciones y los 25 de diciembre ausentes se conservan como desconocidos/ausencias, no errores automáticos. observation_gaps permite distinguir hueco del origen, desconocimiento y período parcial sin crear observaciones falsas. known_from NULL/evidencia ausente deniega la exposición de auxiliares; no se asignan fechas inventadas para llenar las tablas.

Para feriados, National aplica al país del dataset; Regional se cruza con state y Local con city. Se agregan bool_or por tipo/actividad antes de unir con ventas. Un Holiday transferido no activa por sí mismo la fecha original; se consideran Transfer/Additional/Bridge, Event y Work Day como señales distintas. La prioridad comercial de Work Day frente a feriado se definirá en Gold, no se inventa aquí. La vista devuelve como máximo una fila por fecha/tienda; un LEFT JOIN posterior debe preservar ese contrato sin convertir «evento desconocido» en «no festivo conocido» automáticamente.

## Contratos, validación y verificación

`contracts/data-storage-v1.json` define columnas/nulabilidad del SOURCE, identidad/checksum, rutas RAW/BRONZE, metadatos y claves Silver. RAW debe preservar bytes de la partición extraída autorizada, con su checksum propio; el hash del CSV completo original identifica procedencia y no se confunde con el del subconjunto mensual. Bronze valida tipos y trazabilidad sin imputaciones futuras. Silver aplica PK/FK/CHECK y disponibilidad; Gold calculará features por corte en su fase.

`storage_contracts.py` contrasta el contrato contra los perfiles ya medidos y valida que el manifiesto sea un plan, esté ordenado, no tenga solapes/gaps entre períodos, preserve hashes y cuadre con el número de ventas. No es todavía un validador Parquet ni ETL. Las diez pruebas unitarias de contrato/configuración incluyen casos inválidos y protección de secretos. `access.sql` prueba integridad/aislamiento con ROLLBACK; `data_infra.py verify/persistence` ejecuta las comprobaciones del servicio. Ninguna prueba marca un lote real como exitoso.

Riesgos restantes: mantenimiento de MinIO archivado, acceso privilegiado local, secretos de archivos sin cifrado administrado, HTTP local sin TLS, ausencia de backups/restauración ensayada y ausencia del protocolo transaccional de promoción. Un solo nodo no ofrece alta disponibilidad. Fuentes técnicas: [PostgreSQL — vistas](https://www.postgresql.org/docs/18/sql-createview.html), [Spring Boot — migraciones](https://docs.spring.io/spring-boot/how-to/data-initialization.html), [Compose](https://docs.docker.com/reference/compose-file/services/), [MinIO oficial](https://github.com/minio/minio).

## Actualización F1-03

Los apartados anteriores conservan el diseño y alcance de F1-02. F1-03 aplicó V2 y ejecutó el bootstrap real. `control.publications` registra STAGING/AUTHORIZED/COMPLETE y `publication_objects` el inventario esperado/versiones por objeto. Las vistas training ahora exigen COMPLETE. La autorización no avanza por sí sola el corte. El trigger de ejecuciones rechaza SUCCEEDED prematuro y los guards cierran el inventario autorizado e impiden un lote incompatible pendiente. La publicación copia solo hechos autorizados, registra cada versión y finaliza junto con el corte en SQL tras verificar todos los objetos.

El corte actual es 2014-12-31, last_batch_id bootstrap-2013-2014. Hay 1 297 296 ventas y dos huecos de Navidad, no ventas cero. source_row_number de huecos puede ser NULL por V2 porque no existe fila original; los demás datos conservan ordinal original. Familias y huecos son derivados con BRONZE, sin fabricar RAW. Snapshot de tiendas sin fecha permanece restringido, al igual que familias, feriados y petróleo sin known_from/evidencia. El entrenador ve hechos históricos de ventas/transacciones/huecos, pero no esos auxiliares restringidos ni objetos de cuarentena.

Los 32 lotes mensuales del manifiesto siguen sin liberar. Los scripts de prueba vacía de F1-02 se conservan como controles específicos de esa fase, no se ejecutan sobre el entorno cargado. Comandos, política temporal, pruebas y recuperación: [BOOTSTRAP.md](BOOTSTRAP.md). Evidencia agregada e inventario completo: [BOOTSTRAP_EVIDENCE.json](BOOTSTRAP_EVIDENCE.json).

## Evolución F1-04B (estado posterior al diseño F1-02)

GOLD ya contiene features/etiquetas del snapshot bootstrap y metadatos de 24 bloques. Control/data V3 son nuevas e inmutables tras aplicación; Flyway sigue siendo el único runner. El ingestor recibe SELECT de training.sales y SELECT/INSERT GOLD; trainer recibe solo SELECT de training.gold_features y training.gold_labels, sin USAGE en gold ni escritura. [Contrato y verificación real](FEATURE_ENGINEERING.md). Las descripciones de tablas vacías anteriores corresponden al cierre F1-02, no al estado actual.

## F5.4 — Backup y restauración del plano de datos

La ausencia de backups descrita en F1-02 es histórica. [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) documenta pg_dump nativo, MinIO frío con VersionId preservado y dos restores nuevos con hashes lógicos completos/identidad v1. No se editaron migraciones/contratos ni se ejecutaron verificaciones de entorno vacío. PVC/historias operativas y recuperación integral de apps/host quedan fuera del alcance validado.
