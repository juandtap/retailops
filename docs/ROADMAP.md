# Roadmap de implementación

**F5.2 implementada y validada localmente**, sin F5.3. F5.1 publicada/CI remota exitosa según usuario; CI nueva F5.2 solo validada localmente. Sin commit/push/pull/publicación.

## F5.2 — Loki, Alloy y correlación

| Hecha | ID | Alcance | Evidencia / límites |
| --- | --- | --- | --- |
| [x] | F52-LOG01 | Inspección y permiso mínimo API | Usuario autorizó Roles pods/pods-log en dos namespaces; sin hostPath/socket/proxy |
| [x] | F52-LOG02 | JSON HTTP y correlación | 11 JUnit/15 pytest; request_id real web→Spring→FastAPI, sin inferencia nueva |
| [x] | F52-LOG03 | Loki/Alloy persistentes y acotados | Ready, PVC propios, retención/ingestión limitada; validadores oficiales y 33 recursos válidos |
| [x] | F52-LOG04 | Grafana y consultas reales | Tres servicios con logs, cinco consultas por Loki/Grafana; errores vacíos sin fabricar incidentes |
| [x] | F52-LOG05 | Persistencia, integridad y cierre | Tres entradas idénticas tras reemplazar Loki; histórico/cutoff/v1/19 objetos iguales; ocho workloads a cero/cinco PVC Bound |

Cobertura limitada a eventos HTTP propios de tres contenedores app. Compose, logs libres, eventos Kubernetes y contenedores previos quedan fuera. Sin prueba de 48h, fallos destructivos, backup o carga. [Arquitectura, operación y evidencia](LOGGING.md).

Próxima tarea exacta: revisar F5.2 y CI remota del usuario; detenerse antes de F5.3.

## F5.1 — Métricas, Prometheus y Grafana

| Hecha | ID | Alcance | Evidencia / límites |
| --- | --- | --- | --- |
| [x] | F51-OBS01 | Inspección F4 conservado y presupuesto | App 0/0 inicial; MLflow anon/swap medidos, límite intacto; riesgo documentado |
| [x] | F51-OBS02 | Instrumentación Java/FastAPI | 10 JUnit/13 pytest; endpoints reales, etiquetas acotadas y candidato explícito |
| [x] | F51-OBS03 | Prometheus/Grafana/adaptador seguros y persistentes | 34 recursos estáticos válidos, tres PVC Bound, RBAC mínimo y sin UFW/host mounts |
| [x] | F51-OBS04 | Dashboards/targets/PromQL reales | Cuatro targets UP, datasource OK, tres dashboards y 24 consultas; 22 expresiones validadas |
| [x] | F51-OBS05 | Integridad, operación y cierre | Histórico/v1/19 versiones de objetos/cuatro volúmenes iguales; seis workloads a cero, PVC y K3s conservados |

Cierre histórico F5.1; autorización y siguiente tarea F5.2 actualizadas en el bloque superior. Procedimiento para reactivar/detener en OBSERVABILITY.md, sin repetir instalación/importación/UFW. No afirmar pruebas de CI remota nueva, navegador, carga, fallos o backups no ejecutadas.

## F4 autorizada — CI/CD, K3s y Helm

| Hecha | ID | Alcance | Estado y evidencia |
| --- | --- | --- | --- |
| [x] | F4-DEV01 | Verificar Git/host y fijar estrategia externa de datos | main limpio inicial, commit F3 confirmado; host/red/recursos inspeccionados |
| [x] | F4-DEV02 | CI y publicación manual separada | actionlint válido; primer intento falló en setup-java; selector Temurin 21 corregido y CI #2 exitosa según usuario; sin publicación |
| [x] | F4-DEV03 | Imágenes versionadas y chart | Seis imágenes nuevas; Helm lint/render y 15 recursos Kubernetes válidos |
| [x] | F4-DEV04 | Operación reproducible y documentación | DEPLOYMENT.md; scripts build/upgrade/smoke/rollout/rehearse/rollback; Secrets/PVC externos |
| [x] | F4-DEV05 | Instalar K3s y verificar despliegue/actualización/rollback | Ready y tres Deployments disponibles; Helm 1→2→3 rollback a 1, tres smokes completos y datos/v1 conservados; cierre local verificado |

F4 cerrada en alcance local autorizado: contexto privado, imágenes importadas, SQL/modelo/19 versiones de objetos y cuatro volúmenes verificados antes/después. CI local validada; CI #2 GitHub exitosa según usuario tras corregir selector Java. GHCR no invocado. Cierre: app a cero, PVC/release conservados, dependencias/puente/forwards detenidos; K3s activo y disabled. Evidencia y límites en DEPLOYMENT/PROGRESS.

Cierre F4 histórico: CI corregida y #2 exitosa; F5.1 autorizada posteriormente arriba. Reactivación solo si el usuario la solicita, reutilizando recursos existentes según DEPLOYMENT.md. **No reinstalar ni repetir prepare-host.py/install.sh, importación o reglas UFW.** Sin commits/push/pull.

## Fase 0 — Foundation

| Hecha | ID | Descripción | Dependencias | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- | --- |
| [x] | F0-01 | Inspeccionar entorno y presencia del dataset | — | Siete archivos comprobados y herramientas identificadas | Completada |
| [x] | F0-02 | Crear documentación persistente | F0-01 | AGENTS, README y cuatro documentos operativos presentes y consistentes | Completada |
| [x] | F0-03 | Integrar TailAdmin gratuito oficial | F0-01 | Fuente/licencia fijadas, npm ci, build y lint verificados con Node 26 | Completada |
| [x] | F0-04 | Inicializar Spring Boot y Maven Wrapper | F0-01 | Java 21, compilación y pruebas HTTP de salud/probes correctas | Completada |
| [x] | F0-05 | Inicializar FastAPI con uv y Python 3.12 | F0-01 | pyproject, uv.lock, runtime aislado y pruebas de salud/configuración correctas | Completada |
| [x] | F0-06 | Externalizar configuración y proteger secretos/datos | F0-03,F0-04,F0-05 | Ejemplo sin secretos, exclusiones, loopback y parámetros verificados | Completada |
| [x] | F0-07 | Verificar y cerrar Foundation | F0-02 a F0-06 | Comandos/resultados registrados, smoke HTTP, limitaciones y siguiente tarea documentados; detenerse | Completada |

## Fase 1 — Ingeniería de datos y modelo inicial

| Hecha | ID | Descripción | Dependencias | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- | --- |
| [x] | F1-01 | Inspeccionar contenido, tipos, fechas y calidad de los siete CSV | F0-07 + autorización F1-01 | Informe reproducible; rangos reales, nulos, duplicados, decimales y semántica de promociones sin alterar originales | Completada |
| [x] | F1-02 | Diseñar almacenamiento, contratos y separación de acceso; configurar PostgreSQL/MinIO y migraciones en Compose | F1-01 + autorización F1-02 | Versiones fijadas, salud/persistencia, migraciones, contratos y aislamiento de futuros verificados; sin bootstrap/liberación | Completada |
| [x] | F1-03 | Ejecutar bootstrap 2013–2014 y publicación recuperable | F1-01,F1-02 | SOURCE inmutable, RAW/BRONZE trazables, SILVER con integridad y corte verificable 2014-12-31 tras publicación recuperable completa | Completada |
| [x] | F1-04A | EDA y series temporales en Jupyter, vistas training hasta 2014-12-31 | F1-03 + autorización F1-04A | Notebooks completos ejecutados, dependencias uv bloqueadas, consultas restringidas y acotadas, gráficos/conclusiones verificadas | Completada |
| [x] | F1-04B | Construir GOLD y controles temporales | F1-04A + autorización F1-04B | 9 106 020 features, etiquetas separadas, pruebas de fuga/permisos, referencia e idempotencia verificadas | Completada |
| [x] | F1-05 | Evaluar Seasonal Naïve y medias 7/28 con backtesting temporal | F1-04B + autorización F1-05 | Notebook 03 ejecutado, tres pruebas mínimas, métricas/coberturas comparables por fold/horizonte/familia/tienda; sin MLflow | Completada |
| [x] | F1-06 | Modelo global HGB, evaluación temporal, MLflow e inferencia FastAPI | F1-05 + autorización F1-06 | Modelo v1 registrado, holdout independiente informado, predicción HTTP real de siete días y pruebas mínimas verificadas | Completada |

Cierre F1-06: PostgreSQL, MinIO y MLflow detenidos mediante `docker compose stop`; `docker compose ps -a` confirmó los tres contenedores en `exited`, código 0. Contenedores, datos, volúmenes y artefactos conservados. HGB no supera Seasonal Naïve en MAE/WAPE del holdout; sigue siendo candidato sin promoción de producción.

F1-05 excluyó MLflow; la solicitud posterior F1-06 autorizó su incorporación con el primer modelo supervisado. No equivale a completar aprobación/promoción/rollback de Fase 4.

## Preparación de Git local autorizada tras F1-06

Auditoría e inicialización en main completadas. Primer commit local autorizado y creado: cf195fcd0358f7284c113dcca6d776aa99d7537e, 708 archivos. Sin remotos/push; GitHub/CI siguen pendientes. F2 se desarrolla sin commits automáticos.

## F2 autorizada — Airflow y orquestación end-to-end

| Hecha | ID | Alcance | Evidencia / límites | Estado |
| --- | --- | --- | --- | --- |
| [x] | F2-AF01 | Airflow 3.3.2, LocalExecutor, metadatos/logs persistentes | API/UI y componentes healthy, cuatro DAGs registrados | Completada |
| [x] | F2-AF02 | Autorización y publicación mensual; GOLD incremental compatible | V4, SQL temporal y escritura sintética aislada; no mes real liberado | Implementada y validada en alcance seguro |
| [x] | F2-AF03 | DAG de entrenamiento y coordinación completa | Reutiliza HGB/MLflow, corte parametrizado y recuperación lógica; sin nuevo ajuste real | Implementada; ejecución mutadora diferida |
| [x] | F2-AF04 | Ejecución segura y documentación | safe-f2-20261114T012419: cuatro tareas success, corte/v1 intactos | Completada |

El bloque original se conserva como referencia comercial; F3 autoriza posteriormente la integración local de lectura, sin autenticación comercial. AIRFLOW.md documenta las rutas mutadoras que no se ejecutaron por restricción explícita.

## F3 autorizada — Aplicación integrada local

| Hecha | ID | Alcance | Evidencia / límite | Estado |
| --- | --- | --- | --- | --- |
| [x] | F3-APP01 | Spring: estado, catálogos, ventas, modelo, predicción y Airflow | Datos reales del bootstrap; validación temporal y viewer | Completada |
| [x] | F3-APP02 | React/TailAdmin: cinco pantallas y gráficos | APIs reales, estados de carga/error/vacío; candidato explícito | Completada |
| [x] | F3-APP03 | Compose integrado y smoke real | Nueve servicios; inferencia siete días y fallo ML controlado | Completada |
| [x] | F3-APP04 | Documentación y cierre conservador | APPLICATION.md y evidencia privada; commit posterior 7d2bcd0 | Completada |

F2 commit local `8f753a3`; F3 commit local 7d2bcd0. La nueva solicitud autoriza únicamente F4 CI/K3s/Helm. Autenticación y roles comerciales del bloque original siguen pendientes. No se liberaron lotes ni entrenaron/promovieron modelos.

## MVP full-stack — pendiente (Fase 2 del roadmap original)

| Hecha | ID | Descripción | Dependencias | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- | --- |
| [ ] | F2-01 | Aprobar e implementar autenticación y roles | F1-06 + autorización Fase 2 | Hash, sesión/CSRF y pruebas de permisos ADMIN/ANALYST en Spring Security | Pendiente |
| [ ] | F2-02 | Crear APIs comerciales y conectar React/Spring/FastAPI | F2-01 | Ventas y predicciones reales consultables con contratos y errores probados | Pendiente |
| [ ] | F2-03 | Mostrar dashboard comercial y administrativo | F2-02 | Filtros, horizonte de siete días, estados sin datos/error y permisos efectivos verificados | Pendiente |

## Fase 3 — Ingesta incremental

| Hecha | ID | Descripción | Dependencias | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- | --- |
| [ ] | F3-01 | Configurar Airflow y DAG mensual | F2-03 + autorización Fase 3 | retailops_monthly_ingestion procesa siguiente mes con trazabilidad y estados reales | Pendiente |
| [ ] | F3-02 | Conectar solicitud administrativa e historial | F3-01 | Botón ADMIN, correlación solicitud/DAG/lote, tiempos y registros visibles | Pendiente |
| [ ] | F3-03 | Verificar idempotencia, exclusión, reintentos y evaluación | F3-02 | Reejecución sin duplicados, fallo sin avance indebido y métricas sobre predicciones guardadas | Pendiente |

## Fase 4 — MLOps

| Hecha | ID | Descripción | Dependencias | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- | --- |
| [ ] | F4-01 | Entrenar candidatos y comparar métricas | F3-03 + autorización Fase 4 | Experimentos versionados y comparación temporal reproducible con activo | Pendiente |
| [ ] | F4-02 | Implementar aprobación, promoción y despliegue | F4-01 | Solo versiones aprobadas, auditoría y actualización verificable de inferencia | Pendiente |
| [ ] | F4-03 | Implementar rollback de modelo | F4-02 | Restauración de versión aprobada previa con pruebas y trazabilidad, independiente de software | Pendiente |

## Fase 5 — DevOps y SRE

| Hecha | ID | Descripción | Dependencias | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- | --- |
| [ ] | F5-01 | Autorizar e inicializar Git/GitHub y CI | F4-03 + autorización explícita Git/GitHub | Datos/secretos excluidos; pruebas y artefactos automatizados en Actions | Pendiente |
| [ ] | F5-02 | Desplegar K3s local con Helm | F5-01 | Un nodo, persistencia, probes y configuración; sin dependencia de runners siempre conectados | Pendiente |
| [ ] | F5-03 | Incorporar Prometheus, Grafana y Loki | F5-02 | Métricas técnicas/datos/modelos, logs correlacionados y alertas verificadas | Pendiente |
| [ ] | F5-04 | Definir SLOs, runbooks y ensayar recuperación | F5-03 | Fallos controlados, restauración/backups probados y límites de disponibilidad documentados | Pendiente |
