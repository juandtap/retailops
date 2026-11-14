# F2 — Apache Airflow y orquestación manual

## Alcance y arquitectura

Airflow **3.3.2**, imagen oficial Python 3.12 fijada por digest, extendida con los dos entornos uv bloqueados existentes para ingesta y ML. Las dependencias de Airflow no se mezclan con pandas/sklearn/MLflow del modelo. LocalExecutor, sin Celery/Redis ni workers distribuidos; una tarea RetailOps a la vez mediante pool `retailops_serial` de un slot. Los DAGs tienen `schedule=None`, catchup=false y max_active_runs=1.

| Servicio | Función / acceso | Límite por defecto |
| --- | --- | --- |
| airflow-api | API/UI autenticada en 127.0.0.1:8081; Execution API interna | 1 GiB, 2 CPU |
| airflow-scheduler | LocalExecutor y subprocesos de tareas | 3 GiB, 2 CPU |
| airflow-dag-processor | Descubre/serializa DAGs; health por heartbeat de la API | 1 GiB, 2 CPU |
| PostgreSQL existente | Base **retailops_airflow** e identidad independientes | Conserva volumen postgres_data |
| Logs | Volumen nombrado **retailops-data_airflow_logs** compartido | Persistente |
| MinIO/MLflow existentes | Publicación y registro futuros; validación de v1 | Sin alterar almacenamiento anterior |

Airflow administra únicamente sus tablas de metadatos; Flyway sigue siendo el runner único de negocio. Nuevas migraciones control/data V4; V1/V2/V3 sin editar. No se modificó Java; se empaquetaron recursos con `-DskipTests package`, sin JUnit.

SimpleAuthManager utiliza usuario `admin` y contraseña aleatoria generada en `.local/secrets/airflow_users.json`, nunca hardcodeada ni mostrada en logs/comandos. El fichero inicial RO se copia a `.local/airflow/auth/users.json`, privado y persistente, porque SimpleAuthManager lo abre para escritura. Fernet/JWT/base de metadatos tienen secretos separados 0600. El entrypoint oficial configura NSS para AIRFLOW_UID (por defecto UID local 1000). HTTP local sin TLS: no es un despliegue multiusuario seguro de producción.

Los contenedores no montan SOURCE, Docker socket ni secretos administrativos o de la identidad operadora pg_api. El extractor prepara solo el workspace de un mes autorizado desde el host; Airflow monta esa selección RO, no el CSV completo. Scheduler/tareas son código confiable con secretos de ingesta/publicación y trainer según funciones; no se afirma sandbox frente al administrador de Airflow/PC ni aislamiento de archivos entre subprocesos del mismo scheduler. La conexión ML consulta únicamente vistas training con trainer.

## DAGs y dependencias

| DAG | Cadena de tareas |
| --- | --- |
| retailops_monthly_release | authorize → ingest_publish → verify → gold → record |
| retailops_train_candidate | verify_snapshot → train_evaluate_register → record |
| retailops_full_pipeline | authorize → ingest_publish → verify → gold → train_evaluate_register → record |
| retailops_validate_existing | historical_state → gold_contract → registered_model → dependencies |

Las tareas ejecutan adaptadores en `pipelines/orchestration` y reutilizan el extractor/publicador, SQL de GOLD y entrenamiento F1-06; no contienen transformaciones de negocio en el DAG. Dependencia por defecto all_success: tras un fallo no se ejecuta el siguiente paso; un reintento usa la misma identidad lógica. Airflow conserva estados de cada tarea, reintentos y logs; control.orchestration_runs conserva el resumen final exitoso. Un fallo previo sigue visible en Airflow y no se registra como éxito final.

El DAG seguro solo lee estado, contratos/vistas y modelo v1; escribe únicamente metadatos/logs propios de Airflow. Es el único DAG ejecutado realmente durante este bloque.

## Inicio y parada

Desde la raíz, mismo uv/Python del proyecto, secretos y volúmenes existentes:

```bash
export UV_CACHE_DIR=/tmp/retailops-uv-cache
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv run --project apps/ml-service --locked python scripts/airflow_infra.py prepare
# Inicia solo los servicios existentes requeridos:
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops up -d --wait postgres minio mlflow
# Empaquetar V4 si el JAR todavía no las incluye, desde apps/api:
# MAVEN_USER_HOME=/tmp/retailops-maven ./mvnw -B -Dmaven.repo.local=/tmp/retailops-m2 -DskipTests package
uv run --project pipelines/ingestion --locked python scripts/data_infra.py migrate
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile airflow build airflow-api
uv run --project apps/ml-service --locked python scripts/airflow_infra.py provision
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile airflow up -d --wait --wait-timeout 180 airflow-api airflow-scheduler airflow-dag-processor
```

Usar `.env` en lugar de `.env.example` si corresponde. AIRFLOW_PORT/UID/MEMORY/SCHEDULER_MEMORY/CPUS están documentados en el ejemplo. Provisionamiento crea solo la identidad/base Airflow y migra sus metadatos/pool; no autoriza ni libera meses. La configuración de credenciales siempre se conserva, no se regenera ni rota sobre volúmenes existentes.

UI: http://127.0.0.1:8081; API: `/api/v2`; token mediante `/auth/token`, sin imprimirlo. El helper seguro autentica leyendo el archivo privado:

```bash
uv run --project pipelines/ingestion --locked python scripts/airflow_smoke.py
```

Para detener únicamente los servicios del bloque que estaban detenidos inicialmente:

```bash
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile airflow --profile mlops stop airflow-scheduler airflow-dag-processor airflow-api mlflow minio postgres
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile airflow --profile mlops ps -a
```

Sin down -v, prune ni eliminación de contenedores/volúmenes. No inicializar Git ni crear commits desde los operadores.

## Autorización y liberación de un mes

**Este bloque no autorizó ni liberó enero de 2015.** Los comandos siguientes describen una futura acción explícita del operador, no pasos rutinarios de inicio.

1. Consultar el corte; solicitar solo el siguiente mes según `DATA_BATCH_MANIFEST.json`.
2. Emitir autorización SQL usando pg_api_password, identidad no entregada a Airflow:

```bash
# SOLO tras autorizar expresamente este mes:
uv run --project pipelines/ingestion --locked python pipelines/orchestration/core.py authorize --batch 2015-01 --confirm
```

3. Con el authorization_id devuelto, preparar localmente el workspace del mes:

```bash
uv run --project pipelines/ingestion --locked python pipelines/orchestration/core.py prepare --batch 2015-01 --authorization-id ID_AUTORIZACION
```

El extractor existente es el único que abre originales: verifica checksums, selecciona fechas, preserva RAW, genera BRONZE Decimal y valida cuadrícula. No vuelve a insertar tiendas/familias del bootstrap; nuevas claves sin dimensión se rechazan por integridad. Auxiliares siguen restringidos por ausencia de evidencia. El último lote termina en **2017-08-15**, no crea datos hasta el fin nominal de agosto.

4. Despausar/lanzar manualmente `retailops_monthly_release` con configuración:

```json
{"batch":"2015-01","authorization_id":"ID_AUTORIZACION","cutoff":"2015-01-31","logical_id":"release-2015-01"}
```

La función de autorización comprueba corte y secuencia enero 2015 → ... → agosto 2017; un trigger rechaza staging mensual no autorizado. No se permite autorizar el mes siguiente mientras falte GOLD del anterior. El DAG verifica UUID/corte, usa el workspace y el protocolo SQL/S3 existente: cuarentena → Silver transaccional → autorización SQL → copias released recuperables → publicación COMPLETE/corte → GOLD. No hay transacción distribuida S3/SQL. Una falla GOLD puede dejar el mes publicado con GOLD pendiente; se reintenta GOLD y se bloquea otra autorización incompatible.

## GOLD incremental v2

Contrato [gold-features-v2.json](../contracts/gold-features-v2.json). Las tablas gold.features/labels/materializations y vistas training GOLD **v1 permanecen intactas**, con snapshot bootstrap. V4 añade:

- gold.incremental_features, gold.incremental_labels e incremental_materializations, append-only.
- training.gold_features_v2: bootstrap v1 expuesto con versión lógica compatible v2 mediante UNION ALL, más emisiones nuevas; no se copian nueve millones de filas.
- training.gold_labels_v2: etiquetas anteriores y nuevas separadas, sin duplicar objetivos. Trainer solo SELECT en vistas; sin acceso directo a tablas ni nuevos privilegios de escritura.

Se conserva semántica lag respecto a target_date, ventanas terminadas en issue_date, calendario denso transitorio, NUMERIC, NULL y señales de ausencia. Solo se materializan emisiones del nuevo período y se leen 27 días de contexto; no se recalcula todo el histórico. historical_cutoff significa **primera disponibilidad del bloque**, no una copia completa de todo el dataset para cada corte. El consumidor selecciona bloques con historical_cutoff ≤ snapshot solicitado y etiquetas disponibles antes de su fecha de ajuste/evaluación. Este cambio de contrato es explícito; v1 sigue disponible para el modelo existente.

Materialización con el mismo advisory lock de publicación y bloqueo del snapshot; una transacción por mes. Reejecución compara hash de SQL, todas las features/etiquetas por EXCEPT bidireccional y recuentos; conflicto detiene, no sobrescribe. No se imputa Navidad ni se inventan fechas al final parcial. El rol de ingesta es una autoridad de transformación confiable; las vistas protegen al trainer, no a un administrador malicioso.

## Entrenamiento independiente y coordinación completa

Tras disponer de GOLD al corte publicado, lanzar manualmente `retailops_train_candidate` con:

```json
{"cutoff":"2015-01-31","confirm_training":true,"logical_id":"candidate-2015-01"}
```

Solo un ejemplo futuro, no ejecutado en este bloque. F2 parametriza el entrenamiento existente; no duplica algoritmo, métricas o registro en DAGs. Una configuración HGB Poisson sin búsqueda extensa, categorías de entrenamiento y valores ausentes nativos. Plan por corte: últimos 14 días de emisiones cuyos siete objetivos terminan antes/al corte para evaluación; validación anterior de 21 días; ajuste semanal con etiquetas conocidas antes de iniciar validación. No usa etiquetas posteriores a la fecha de ajuste.

`retailops_full_pipeline` requiere tanto autorización mensual como `cutoff` y `confirm_training=true` antes de publicar. Usa las mismas etapas que los DAGs independientes, sin disparar dos entrenamientos. Se pueden inspeccionar tareas fallidas/upstream_failed y pendientes en Grid/Graph, con retry de tareas específicas.

El logical_id se reutiliza para reintentos de la misma operación; no reutilizarlo con otro corte/configuración. Checkpoints en `.local/airflow/ml/<hash>/`, distintos de `.local/mlops` de F1-06. Se retoma el mismo run MLflow, se recupera versión asociada al run y se evita duplicar registro. Si hay ajuste iniciado sin checkpoint compatible, modelos logueados sin asociación persistida o múltiples runs/versiones ambiguos, se falla para revisión manual en lugar de reentrenar/registrar automáticamente. No borrar marcadores para forzar éxito sin investigar. Un nuevo logical_id representa una nueva ejecución solicitada.

No hay promoción automática ni modificación del modelo v1. Los candidatos v2 no se activan en el runtime v1, que valida su contrato. El modelo configurado para inferencia, los candidatos y las versiones anteriores permanecen separados; aprobación/rollback son tareas futuras, no se implementa una promoción silenciosa.

## Logs y recuperación

- UI/API: consultar DagRun y TaskInstances; un fallo detiene dependencias posteriores.
- Logs persistentes en volumen airflow_logs; `docker compose ... logs --tail 100 airflow-scheduler` y vista Log de cada tarea. No imprimir secretos/configuraciones completas con credenciales.
- Publicación interrumpida: reutilizar authorization_id/workspace, reintentar la misma tarea; no volver a extraer/sobrescribir archivos autorizados. El protocolo compara inventario/versiones y recupera copias existentes.
- Mes publicado y GOLD pendiente: reintentar solo gold; next-month authorization permanece bloqueada hasta terminar.
- Entrenamiento: reutilizar logical_id/checkpoints/run; ante estado ambiguo investigar primero. No manipular métricas, cutoff o versiones para aparentar éxito.

## Verificación real y limitaciones

Airflow 3.3.2: cuatro DAGs registrados, sin errores de importación reportados por DAG Processor y sin calendarios. UI GET HTTP 200, API autenticada funcional. Ejecución real **safe-f2-20261114T012419** de retailops_validate_existing: **success**, cuatro tareas en success, todas try_number=1. Evidencia `.local/airflow/execution.json`, metadatos Airflow y logs persistentes. No se volvió a entrenar/registrar ni se ejecutaron DAGs mutadores.

Comprobación posterior: corte **2014-12-31**, bootstrap RELEASED/COMPLETE, autorizaciones mensuales **0**, lotes mensuales liberados **0**, filas de GOLD incremental productivo **0**. La vista v2 reutiliza las **9 106 020** filas bootstrap sin materializarlas de nuevo. MLflow conserva solamente **retailops-sales-global v1 READY**, run 55257fc2ce414793b73b9d0df4c95fbb; no se sobrescribieron sus evidencias. HGB sigue sin superar al baseline semanal en MAE/WAPE del holdout de F1-06.

Pruebas esenciales: tres unittest de secuencia/autorización, seguridad temporal con extremos futuros y escritura/idempotencia en una base sintética aislada (eliminada al acabar); dos pytest de plan temporal ML y reutilización de candidato sin ajuste/registro; carga de DAGs por CLI y ejecución real segura. No se repitieron suites de bootstrap/GOLD/infra/Java ni se ejecutaron notebooks. Un intento de inspección DagBag usó una firma anterior y falló; se sustituyó por CLI/API oficiales de Airflow 3 y evidencia del processor.

Muestra observada durante ejecución: API **272,2 MiB**, scheduler **315,9 MiB**, processor **163,3 MiB** (~751 MiB sumados, excluye servicios previos y cachés del SO). No es una medida de pico; un futuro entrenamiento consume memoria adicional dentro del límite de scheduler de 3 GiB. Los cortes grandes pueden requerir revisar esa capacidad antes de ejecutarlos.

Limitaciones: la liberación real mensual y el entrenamiento v2 desde un mes nuevo se implementaron/conectaron pero **no se ejecutaron sobre datos productivos**, por restricción de este bloque. No se afirma prueba completa de recuperación S3 mensual, nueva precisión de modelo, backup/restore ni seguridad multiusuario. Se verificaron adaptadores, permisos de autorización, SQL temporal/escritura sintética y coordinación real de lectura. Los fallos de arranque se corrigieron sin abrir secretos: NSS/UID y SimpleAuthManager requerían preparación; el health check CLI del processor usaba SQLite fuera del entorno del wrapper y se sustituyó por el heartbeat de API.

Referencias primarias: [Airflow 3.3.2](https://airflow.apache.org/docs/apache-airflow/3.3.2/release_notes.html), [configuración de LocalExecutor, Execution API y autenticación](https://airflow.apache.org/docs/apache-airflow/3.3.2/configurations-ref.html). No se añadió frontend, autenticación comercial, Kubernetes, CI ni observabilidad. El trabajo permanece sin commit/push para revisión del usuario. Cierre operativo verificado: los seis servicios iniciados quedaron en exited, código 0, según docker compose ps -a; contenedores, volúmenes, logs y artefactos conservados.
