# Progreso real de RetailOps

Fecha: 2026-11-17, America/Guayaquil.

## Estado actual

**F5.5-A preparada y validada; ningún incidente ejecutado.** F5.4 completada y Actions verde según usuario. Código/chart/catálogo/pruebas/documentación versionables; toda ejecución F5.5-B, su estado/causa/evidencias privadas y despliegue requieren autorización posterior. Preflight real read-only autentica backup y comprueba fuentes cerradas/nodo/RAM; ejecución bloqueada porque no se ha provisionado namespace de entrenamiento. Sin commits/push/pull/GHCR ni datos persistentes modificados.

## F5.5-A — Preparación del laboratorio, sin ejecución

Inspección de instrucciones/PROGRESS/ROADMAP, arquitectura/decisiones, DEPLOYMENT/SRE/RUNBOOKS/LOGGING/BACKUP_RECOVERY, Compose, charts/policies y scripts existentes. main limpio al inicio; F5.4/CI verde confirmadas por usuario. Se mantiene cierre previo: K3s y herramientas existentes, fuentes cerradas y ningún incidente activo. No se aplicaron namespace, releases, RBAC o cambios de réplicas/políticas/estado.

Nuevo chart `infra/helm/retailops-incident-lab`, namespace/release únicos obligatorios; réplicas de Spring sin perfil integrado y FastAPI sin modelo/credenciales/datos, más gateway stdlib con probes acotadas. No sustituye app comercial/inferencia. UID no root, token ausente, raíz RO/capabilities drop/seccomp, sin PVC/Secrets/hostPath/socket. Deny ingress/egress; solo DNS, gateway→réplicas y scraping autorizado. Quota tres pods, requests225m/288MiB y límites1100m/896MiB (quota1500m/1GiB y ceroPVC); reserva memoria fija48MiB en sonda128MiB, sin OOM/carga de host. Ningún pod de entrenamiento se arrancó para validar esos presupuestos.

Catálogo `infra/incident-lab/scenarios.json`: IL-001 indisponibilidad réplica Spring, IL-002 503 de sonda, IL-003 retraso1.5s acotado, IL-004 ingreso ML bloqueado solo entre recursos propios, IL-005 reserva48MiB, IL-006 marcador emptyDir no disponible. Cada entrada incluye objetivo, precondiciones, inyección, evidencia, recuperación, reversión y límites; duración máxima600s. Todos son futuros, no incidentes ejecutados; 5xx/latencia/almacenamiento de sonda no se presentan como fallos de negocio o recuperación de datos originales.

Controlador `infra/incident-lab/controller.py` y CLI `scripts/incident_lab.py`: preflight/list/start/status/stop/verify/cleanup. Mutaciones con allowlist de recursos/campos, namespace/cluster/UID/owner/resourceVersion ligados, sin shell genérica/delete/restore; solo acciones propias futuras. Start exige aprobación F5.5-B privada0600, escenario, UUID, referencia operadora, backup y hash del bundle, emitida/expiración≤15min; sin generador de aprobación. Ledger anti-replay, exclusión local e idempotencia. Reversión foreground/por deadline/RAM, stop permitido tras expirar aprobación; muerte del controlador requiere stop manual para escala/política. Cleanup conserva datos/backups/estado y espera watch0 antes de escalar solo réplicas propias. No se invocaron start/stop/cleanup reales en A.

Estado público solo ID opaco/fase/deadline, sin causa/escenario elegido. Plantilla evaluadora versionada con placeholders; guía real solo se genera durante B en `.local/f55/facilitator/exercises/<id>/evaluation.md` junto a snapshots/estado privados. Ninguna guía seleccionada/aprobación válida o `.local/f55` creada ahora. Separación operativa, no secreto frente a administrador que inspecciona repo/Kubernetes.

Overlays opt-in `incidentLab.enabled=false` por defecto en observabilidad/logging: tres scrapes/cinco reglas scope=exercise y environment=incident-lab, seis paneles y namespace Alloy nuevo. RBAC futuro mínimo pods/pods-log solo en namespace nuevo, sin permiso adicional aplicado. Prometheus/Grafana/Loki/Alertmanager existentes se reutilizarían únicamente en B autorizada; no se reactivaron para validar. Defaults contrastados por render: Alloy original idéntico, solo Roles previos, seis jobs SRE originales y sin dashboard incidente.

Pruebas ejecutadas: **12 unittest** con FakeBackend, mocks y fixtures temporales (no llamadas Kubernetes ni servidor/carga/memoria real de incidentes), **seis fixtures promtool** sin evaluación en Prometheus real, cinco reglas y seis consultas nuevas válidas, **56 recursos Kubernetes** válidos sin skips y configuración Prometheus/Alloy aceptada por validadores oficiales aislados sin red. Guardas negativas namespace/release, observers sin alerting, autorizaciones vencidas/scope/hash/permisos/symlinks, target original, UID recreado, concurrencia, replay, host/PVC/Secret/NodePort y readonly. actionlint/bash-n/py_compile/diff-check pasan. CI añade validate_incident_lab.sh; nueva versión solo validada localmente. No cambios aplicaciones/pipelines, no suites de negocio repetidas.

Preflight real no destructivo: configuración, backup SHA/MAC y reporte F5.4 mismoID/v1 válidos, nodo Ready, margenRAM≥4GiB, apps/Compose originales cerrados. `ready_for_execution=false` por namespace exclusivo ausente; no se fuerza verde ni se arrancan servicios. No se verifican todavía salud/networkpolicy/RBAC/logs/targets de réplicas no desplegadas. Verificación before/after: UID/spec de deployments/PVC originales idénticos, mismos IDs/imágenes/estados de contenedores originales/restores, namespace no creado y cero estado B. Evidencia ignorada `.local/f55-a/{static-validation-final,unit-tests-final,default-regression,preflight-final,no-incidents-proof,...}`.

Documentación nueva [INCIDENT_LAB.md](INCIDENT_LAB.md): arquitectura, catálogo y límites, preparación posterior con aprobaciones separadas, comandos, reversión, investigación, rúbrica y postmortem. Versionar solo código/chart/overlays/plantillas/pruebas/docs/CI; ignorar `.local/f55/**` y `.local/f55-a/**`, backups/claves/modelos/logs reales. No staging/commit/push/pull/publicación, credenciales/cutoff/v1 o datos persistentes modificados.

Próxima tarea exacta: revisión de F5.5-A y esperar autorización explícita de preparación/ejecución F5.5-B para el primer escenario. No avanzar a otra fase ni ejecutar incidentes por continuación automática.

## F5.4 — Backup cifrado, restauración aislada y recuperación

Inspección de instrucciones/progreso/roadmap, arquitectura/decisiones, DEPLOYMENT/SRE/RUNBOOKS, DATA_STORAGE/infra/docker README y Compose/PG/MinIO/MLflow/PVC. main limpio al iniciar; usuario confirmó push/CI F5.3 exitosa. K3s activo/disabled, diez workloads a cero, siete PVC y todos los contenedores originales detenidos. Se arrancaron solo PostgreSQL/MinIO para backup; MLflow/Airflow/apps originales no se reactivaron. Source no abierto ni alterado.

Estrategia: quiescencia controlada sin escritores, pg_dump -Fc --create de retailops/retailops_mlflow/retailops_airflow y pg_dumpall roles sin contraseñas, inventarios SQL/S3 completos antes/después; MinIO detenido para copia fría mediante docker cp del contenedor existente. No se monta ningún volumen original en un contenedor nuevo. Copia fría conserva VersionId; usuario autorizó explícitamente nombres lógicos de buckets solo en instancia aislada, manteniendo recursos/credenciales/endpoints independientes y sin reescribir referencias. Logs Airflow fríos protegidos también: cinco archivos reales y alias simbólico inventariado, no aplicado automáticamente.

Nuevo core infra/backup/core.py, CLI scripts/backup_recovery.py y validate_backup.sh, seis pruebas de cifrado/MAC, claves/hash/estado inválidos, archivos faltantes/extra, tar traversal/symlinks/duplicados, directorio fuera del repo/no sobrescritura y rechazo de stop sobre recursos originales. Contratos y diez unittest de infra pasan; no ejecutar verify/persistence de entorno vacío. CI nueva añade solo pruebas estáticas sin datos; pendiente ejecución remota. No cambios apps/pipelines/migraciones: no repetir npm/Maven/pytest de negocio.

Backups fuera de Git y volúmenes: /home/diego/Backups/retailops, claves separadas /home/diego/Backups/retailops-keys, restores privados /home/diego/Backups/retailops-restores; directorios 0700/archivos 0600. Payload AES-256-CBC/PBKDF2-SHA256+HMAC-SHA256 y SHA-256, passphrase por FD anónimo sin env/argv. Manifiesto interno cifrado con inventario/hashes/timestamps UTC/versiones e imágenes, envelope público sin valores secretos. Secretos originales solo cifrados, clones no los habilitan. No copia externa ni tareas recurrentes/limpieza automática; perder host y clave sigue siendo riesgo, no DR offsite.

Primera copia backup-20261117T155147Z-94658ff98685: 918722592 bytes cifrados, creación ~59.3s, verify completo ~2.95s/35 archivos. Segunda copia backup-20261117T161854Z-375a34c472b3: incluye código corregido y logs Airflow, creación ~64.0s; conserva la primera, sin sobrescrituras. Inventarios y claves no se versionan ni imprimen valores sensibles.

Aislamiento: cada intento usa prefijo retailops-restore-UUID, red Docker --internal sin puertos publicados, volúmenes propios, bases renombradas y administrador/contraseñas nuevos. IAM heredado MinIO deshabilitado solo en clone; rechazo de credenciales originales contrastado con acceso nuevo. MLflow propio apunta exclusivamente a los almacenes nuevos. No usa caché/modelos del origen, schedulers o conexiones del entorno conservado. Recursos nuevos limitados PG 2GiB/2CPU, MinIO 1GiB/1CPU, MLflow 2GiB/2CPU con swap combinado 3GiB; original MLflow intacto y parado.

Comparación: hashes completos COPY BINARY ordenado de filas de todas las tablas, recuentos, secuencias, propietarios, estado/corte/ventas decimales y constraints; todos los objetos/versiones/delete markers con SHA-256 y referencias SQL exactas. Diferencias textuales nativas PostgreSQL (CHECK normalizado y nombres NOT NULL autogenerados) se verifican mediante parser en tablas temporales del clone, sin cambiar datos, constraints reales, contratos o migraciones. Ocho diferencias de representación equivalentes comprobadas; hash de datos alterado y CHECK alterado rechazados en pruebas reales del clone. No equivale a hash físico de PG/PVC ni auditoría completa de ACL/índices/roles.

Artefacto ya comprobado en clone: candidato v1/run 55257fc2ce414793b73b9d0df4c95fbb, purpose candidate_local_preview, contrato baea56071f5331d0356bea754a09c015aec784ab05757132c8170b1d2962e9b7 y cutoff 2014-12-31; carga sin entrenamiento/inferencia/promoción. Dos informes completos validated: restore-06 y restore-07, recursos/base/contraseñas distintos, mismos datos e identidad. 167 tablas (25 negocio/71 MLflow/71 Airflow), 313 versiones de objetos en cinco buckets (19 MLflow) y 586 referencias SQL exactas, sin remapear VersionId. Cuatro IAM heredados deshabilitados por clone; root MinIO y password API SQL originales rechazados, nuevas credenciales válidas. Backup final 918784032 bytes, 38 archivos; verify 2.65s. Restore-06: 51.74s restauración +43.17s validación=94.91s; restore-07: 51.18+43.04=94.21s. Edades del punto: 240.77/412.23s; no RPO futuro garantizado ni RTO integral de apps. RPO propuesto ≤24h de cambios con backups manuales tras operaciones relevantes; RTO propuesto ≤30min para datos+artefacto con imágenes/clave disponibles, no RTO integral de aplicaciones.

Problemas diagnosticados sin tocar origen: Docker internal no publicó puertos solicitados (se usa IP del bridge privado, sin nuevos permisos/UFW); mc requería directorio propio escribible; nombre del launcher mlflow.py sombreaba el paquete (renombrado); destino de caché de descarga debía existir. Cada intento fallido quedó detenido y se volvió a recursos nuevos, sin sobrescribir los anteriores. Comparador inicial exigía texto de catálogo idéntico; datos binarios ya coincidían y se añadió comparación semántica estricta de CHECK/NOT NULL, con pruebas negativas. Informes validated se crean solo después de todas las verificaciones.

Evidencia privada .local/f54 y directorios externos: backup/verify/restore logs, unit/static validations, constraint-validation/artifact-check, inventarios cifrados, informes privados y estados/volúmenes/PVC. Los artefactos, claves, modelos y logs siguen fuera de Git. Auditoría final de permisos: backup contiene solo envelope/payload cifrado, directorio 0700 y archivos/clave 0600; candidatos revisados sin secretos locales detectados. Guarda tar rechaza también rutas equivalentes duplicadas; verify real adicional pasó después de esa comprobación. Validación final de origen: hashes completos SQL/secuencias/estado/constraints sin cambios, SHA-256 del archivo frío MinIO idéntico al backup final y credenciales originales byte a byte iguales. Cuatro volúmenes Docker con inspect idéntico y siete PVC con UID/spec iguales. CLI real rechazó ciphertext sintético corrupto antes de crear recursos y workspace existente; copias válidas intactas. No se compara hash físico PG activo ni se promete recuperación de historias PVC/host/apps.

Cierre comprobado: diez workloads a cero, ningún pod app/observabilidad, siete PVC Bound, 26 contenedores del ámbito retailops-data/retailops-restore en exited (incluye intentos fallidos retenidos), K3s active/disabled como al inicio. Solo PG/MinIO originales reactivados para backup, ambos detenidos; original MLflow/Airflow/apps nunca arrancados. Volúmenes/redes temporales y workspaces privados retenidos para revisión, sin borrado/prune; dos backups válidos y sus claves separadas conservados fuera de Git.

Próxima tarea exacta: revisión F5.4 y eventual CI remota del usuario; detenerse antes de F5.5. Sin recuperación end-to-end, copia offsite, tareas recurrentes, commit/push/pull/GHCR.

## F5.3 — Alertas, SLI/SLO y runbooks

Inspección de instrucciones, PROGRESS/ROADMAP/DEPLOYMENT/LOGGING/OBSERVABILITY y arquitectura/decisiones, charts/policies/scripts e instrumentación real. main limpio al comenzar; F5.2 CI exitosa tras push confirmada por usuario, sin Git remoto del agente. K3s inicialmente activo/disabled; ocho workloads a cero, cinco PVC Bound y sin contenedores Docker activos. No reinstalación, UFW, sudo o importación nueva. Se reutilizaron imágenes app F5.2 y credenciales/PVC/releases.

Implementación: `retailops-observability` 0.2.0/F5.3 con alerting opcional. Alertmanager 0.35.0 por digest oficial, receptor HTTP stdlib en imagen Python existente, dos PVC externos 256Mi cada uno, retención 48h AM y receptor SQLite ~1000 eventos/48h. Sin tokens/RBAC nuevos, hostPath/socket Docker, privilegios, exposición LAN/Internet o destinatarios externos. Policies de ingreso solo Prometheus→AM/receptor y AM→receptor. Requests nuevos 35m/56MiB; limits 300m/192MiB. No cambios de workers/límites MLflow.

Prometheus: 19 grabaciones, 11 alertas operativas y una sintética separada, seis targets. Reglas cubren disponibilidad observada/deployments, 5xx sostenidos, p95, memoria Kubernetes, reinicios y scraping/secciones/dependencias fiables. Adaptador añade restartCount desde API pods ya autorizada, con prueba de regresión; no amplía permisos. La memoria Compose/MLflow sigue sin serie continua: runbook de diagnóstico puntual, sin inventar alerta automática. Las probes/readiness no prueban inferencia correcta.

ConfigMap lab-state externo Helm con lab_active y señales de validación normalmente cero. Estado activo explícito y réplicas deseadas gobiernan alertas/SLI; cierre espera señal cero en Prometheus antes de escalar. `sre_state.py` usa kubectl fijado, no wrapper host; `observability.sh stop` espera solo sus tres componentes, compatible con logs/AM/receptor aún activos. Nuevos scripts sre.sh, sre_state.py, validate_sre.sh y verify_sre.py; CI incorpora estáticas SRE. No modifica fuentes React/Java/ML: no reconstruye apps ni repite sus suites.

Grafana añade dashboard retailops-sre con 12 paneles y enlaces a HTTP/logs/Alertmanager. 12 consultas ejecutadas directamente y por proxy, dashboards de destino verificados por API y logs Loki reales disponibles. Sin prueba visual de navegador. Alertas incluyen enlaces locales y runbook_url del repositorio; no hay servidor HTTP de documentación. Runbooks reproducibles para API, 5xx, latencia, ML, MLflow memoria, recolección, reinicios y memoria pods, sin recuperación destructiva por defecto.

SLI/SLO propuestos para sesiones activas: disponibilidad observada API/ML 99%/1h, no-5xx 99%/1h con al menos 100 solicitudes y p95 ≤1s/5m con mínimo 20 solicitudes (ML provisional). API HTTP excluye Actuator; ML HTTP exclusivamente /predict. Presupuestos requieren 120 muestras/1h; no se rellenan huecos. Hora incompleta y cero inferencias nuevas: **sin presupuesto horario calculable ni SLO declarado cumplido**. Primera muestra real: disponibilidad observada API/ML=1, API sin 5xx=1 y p95 API ~0.135s; solo dos muestras SLI en esa consulta inicial y diez por servicio en la verificación final. No son carga representativa. ML HTTP sin series de predicción.

Validaciones estáticas: seis unittest, 12 escenarios promtool (cierre intencional, desired=0, API/ML caídas sintéticas, 5xx/volumen insuficiente, latencia, memoria, reinicio, ventana incompleta/completa y modelo sin telemetría), 31 reglas válidas, 12 expresiones dashboard, configuración amtool con receptor local e inhibiciones, **27 recursos Kubernetes válidos**. Regresión default F5.1 sin alerting: 34 recursos y 22 PromQL válidas. actionlint/bash -n/py_compile/diff --check. CI F5.3 solo local, sin ejecución remota.

Validación real: seis targets UP, tres grupos de reglas health=ok y AM descubierto. Señales scope=validation llegaron como dos alertas agrupadas y luego resolved; sin repetir durante ventana inicial de 25s. Prueba adicional de deduplicación: dos reenvíos idénticos por API AM produjeron una sola notificación agrupada en 25s y una resolución, todo con scope=validation. Dos alertas sintéticas API AM verificaron inhibición efectiva y prueba separada de silencio, sin fallos reales de app/dependencias. Silencio y notificaciones persistieron tras reemplazar AM/receptor, con mismos PVC; silencio de prueba expirado. No se ensayaron incidentes reales. La inyección de routing no valida los umbrales de fallos de servicios: esos se probaron con fixtures.

Recursos: AM 1m/15–17MiB, receptor muestras 1–18m/14–19MiB (incluye startup); Prometheus 47MiB/Grafana 341MiB/adaptador 16MiB/Loki 73MiB/Alloy 45MiB en muestra final. Dos PVC nuevos medidos con sonda temporal sin token/montajes RO y eliminada: AM dos archivos/471 bytes lógicos; receptor un SQLite/8192 bytes. Muestras, no picos ni cuota física garantizada. Retención 48h no probada por espera real, sí lógica del receptor en unitarias.

Integridad: snapshots read-only antes/después idénticos (1 297 296 ventas, suma decimal/fechas, 9 106 020 features, cutoff 2014-12-31, cero autorizaciones/etiquetas futuras, candidato/métricas v1 y 19 versiones de objetos MLflow); cuatro volúmenes Docker completos idénticos en inspect. Sin hashes completos de tablas ni backup. Smoke integrado read-only correcto, sin nueva inferencia/ingesta/entrenamiento/promoción. Evidencia privada `.local/f53`: static-validation/default-observability-regression, helm-*, controlled/notification/inhibition/silence/persistence, live-verification, data-before/after/integrity, volumes-*, resources-*, storage-measured, forwards/bridge y cierre.

Problemas resueltos: promtool test necesita tmpfs /tmp pese a raíz RO; se añadió solo al contenedor efímero aislado. Prueba de presupuesto completo detectó redondeo de resta; fórmula equivalente de presupuesto restante evita cancelación y los 12 escenarios pasan. Primer forward receptor tras restart apuntaba al pod en terminación: se reconectó después del rollout y persistencia final pasó. Wrapper kubectl host avisaba de config privilegiada; script usa binario fijado y kubeconfig/contexto explícitos. No se modificaron permisos del host.

Prueba real de cierre planificado: lab_active=0 confirmado, apps escaladas a cero y ambos targets de app DOWN observados; 32s adicionales de evaluación con cero ALERTS operativas. Evidencia planned-zero-proof.json.

Cierre real: diez Deployments a cero, cero pods app/observabilidad y siete PVC Bound; nueve servicios Compose exited, sin listeners temporales ni forwards/puente propios. Lab-state inactivo, señales sintéticas cero y silencio de prueba expirado. K3s conserva active/disabled como al inicio. closure.json y app/observability/compose-stopped documentan el resultado. No se eliminó persistencia.

Próxima tarea exacta: revisión de F5.3 y eventual ejecución remota de su CI por el usuario; detenerse antes de F5.4. Diseño, objetivos, consultas y procedimientos en [SRE.md](SRE.md), respuesta en [RUNBOOKS.md](RUNBOOKS.md). Sin commit/push/pull/publicación.

## F5.2 — Loki, Alloy y correlación

Autorización posterior al cierre F5.1: centralización local, sin F5.3. Inspección de arquitectura/decisiones/despliegue/observabilidad, chart/policies/Compose/puente e implementación real. main limpio al comenzar. K3s estaba inactive/disabled; el usuario ejecutó su arranque, sin reinstalar/UFW. Usuario autorizó expresamente Roles de Alloy en retailops y retailops-observability (`get/list/watch pods`, `get pods/log`) y realizó una importación nueva de las tres imágenes app necesarias. No sudo ejecutado por el agente.

Implementación: chart separado `infra/helm/retailops-logging` con Loki 3.7.10/Alloy 1.22.0 fijados por digest oficial, dos PVC propios 2 GiB/256 MiB, RBAC namespaced y NetworkPolicies, UID no root/raíz RO/seccomp/capabilities drop. Recolección API, sin socket Docker/hostPath/node proxy/privilegios. Loki TSDB v13/filesystem/WAL, retención 48h con compactor, ingestión 0.005 MB/s/burst 1 MB y límites de streams/consultas/caches. Requests adicionales 150m/384 MiB, limits 750m/768 MiB; no cambios de recursos/workers MLflow.

Spring añade consola JSON y RequestLoggingFilter; ExternalServices propaga X-Request-ID a FastAPI. Python añade request_logging.py/middleware; nginx access JSON sin IP/URL/query/referer/user-agent. Se registra estado, timestamp UTC e identificador validado, y tipo de excepción sin texto/stack sensible. Alloy selecciona eventos HTTP propios de api/ml/web; etiquetas acotadas más service_name automático de Loki. No se centralizan logs libres de framework, init/previous containers, eventos Kubernetes, otros pods o dependencias Compose. No es captura integral de incidentes ni tracing distribuido.

Grafana incorpora datasource Loki opcional y dashboard versionado con cinco consultas: 5xx, excepciones Spring, errores FastAPI, nginx y request_id. Diez ejecuciones desde Loki/Grafana correctas; tres servicios con logs reales (primera muestra: API 30/ML 23/web 27 entradas). GET real `/api/v1/models/active` correlacionado en los tres, sin inferencia nueva. Vistas de errores vacías: no se provocaron errores ni se afirma validación contra incidentes inexistentes. Persistencia: exactamente tres entradas de referencia iguales después de rollout restart de Loki, con mismo PVC.

Pruebas: `./mvnw --batch-mode verify` con Java 21, **11 casos**; `uv run --project apps/ml-service --locked pytest apps/ml-service/tests -q`, **15 casos**, aviso TestClient heredado. Tres imágenes app construidas con etiqueta nueva y exportadas localmente; usuario importó tar una vez. `scripts/validate_logging.sh`: Helm lint/render, **33 recursos** válidos (logging+observabilidad+storage), validadores oficiales Loki/Alloy sin red. `scripts/validate_observability.sh`: tres unittest y 22 PromQL válidas, recursos F5.1 válidos. actionlint/bash -n/py_compile/diff --check pasan. Sin cambios React, no se repite su build/lint; nueva imagen nginx y smoke HTTP real aprobados. CI añade validación logs; **CI remota F5.2 pendiente**, sin invocarla.

Seguridad real: Alloy autorizado a pods/log, denegado a Secrets/exec/nodes-proxy/kube-system; app→Loki rechazado, Grafana/Alloy acceden; Grafana anónima 401. Escaneo de muestras hasta 500 líneas/servicio y secretos locales/patrones sin filtración detectada; no auditoría exhaustiva. Loki 4m/68 MiB y Alloy 2m/43 MiB, muestras, no capacidad comercial. PVC Loki: siete archivos/125170 bytes lógicos medidos con pod temporal RO/sin token, eliminado después. local-path no ofrece cuota física garantizada; retención no se probó durante 48h.

Problemas resueltos: sandbox inicialmente bloqueó Docker/red/caché Maven; pruebas realizadas con acceso no privilegiado del usuario fuera del aislamiento, sin cambiar permisos del host. Primera comprobación de etiquetas detectó service_name automático acotado; validación corregida. Imagen Loki no tiene du; medición sustituida por sonda RO. La reconexión del port-forward después del reemplazo de Loki es necesaria y se ejecutó.

Snapshots read-only antes/después iguales: 1 297 296 ventas, suma decimal/fechas, 9 106 020 features, cutoff 2014-12-31, cero autorizaciones/etiquetas futuras, modelo/métricas v1 y **19 versiones de objetos MLflow**. Inventario de volúmenes Docker igual; no hash completo de tablas ni backup. Evidencia privada `.local/f52`: maven/pytest/build/static/metrics-regression, helm-*, verification-*.json, persistence-before/result, data-before/after/integrity-comparison, resources-*, storage-loki, app/observability-live y cierre. Los archivos nuevos versionables incluyen charts/configs, scripts logging/validate/verify, pruebas Java/Python y LOGGING.md; datasets, secretos, tars, logs y evidencias siguen ignorados.

Cierre real verificado: **ocho Deployments a cero**, sin pods app/observabilidad y **cinco PVC Bound**; las cuatro dependencias reactivadas quedaron detenidas y los nueve servicios Compose están exited. Tres forwards y puente propios cerrados; sin listeners temporales. K3s activo/disabled tras arranque personal del usuario; para volver al inactive inicial requiere `sudo systemctl stop k3s` ejecutado por él. No se eliminó persistencia. `closure.json`, app-stopped/observability-stopped y compose-stopped registran el estado final.

Próxima tarea exacta: revisión de F5.2 y eventual CI remota del usuario; **detenerse antes de F5.3**. Reactivación/cierre y limitaciones en LOGGING.md; sin commit/push/pull ni GHCR.

## F5.1 — Métricas, Prometheus y Grafana

### Inspección y diseño

Se leyeron instrucciones, ROADMAP/PROGRESS/DEPLOYMENT, arquitectura/decisiones e implementación real. Confirmado F4 conservado: tres Deployments 0/0, sin pods app, cuatro volúmenes Compose y ningún contenedor activo; K3s Ready con CoreDNS/local-path/metrics-server existentes. Host 30 GiB RAM, ~20 GiB disponibles al inicio y ~388 GiB disco. Salud no era Prometheus: API solo health, FastAPI sin métricas; imagen MLflow tampoco incluía cliente Prometheus.

Chart separado de observabilidad, sin operador/exporters del host: Prometheus 3.16.0 y Grafana 13.3.1 por digest, adaptador Python stdlib que reutiliza metrics-server. RBAC get/list de nodos/pods/deployments/metrics pods en dos namespaces; pruebas efectivas niegan Secrets, nodes/proxy y pods/exec. Solo adaptador monta ServiceAccount. UID no root/capabilities drop/seccomp/filesystem raíz RO; namespace restricted. Nuevos PVC externos Helm Prometheus 2 GiB/Grafana 1 GiB, sin tocar los anteriores. Retención efectiva 2d/512MiB; Grafana password aleatorio externo 0600, sin anonimato ni unified alerting. Sin nuevo socket/hostPath, reglas UFW o servicios del SO.

API añade Micrometer registry Prometheus, endpoint/histogramas; FastAPI añade prometheus-client 0.26.0 en uv/lock y métricas HTTP/proceso/modelo, sin URLs arbitrarias/features como etiquetas. nginx bloquea métricas por frontend. NetworkPolicies permiten scraping solo desde componentes observabilidad autorizados, conservando negocio F4. Estado dependencias desde probes SQL/HTTP existentes; modelo cargado no significa aprobado. Tres dashboards versionados cubren disponibilidad/modelo, HTTP y recursos. No dashboards con datos sintéticos o cero inventado.

### Recursos e investigación MLflow

MLflow se reactivó normalmente para el laboratorio, sin experimentar reinicios ni tocar imagen/workers/límite/registro. Lectura cgroup/smaps: primera muestra ~991.5 MiB anon, ~0.7 MiB file, ~1017.3 MiB memory.current y ~927.2 MiB swap; segunda ~980.6 MiB anon/~8 MiB file/~972.4 MiB swap. Varios procesos Python, no principalmente caché de archivos. Límite 1 GiB y MemorySwap combinado 2 GiB intactos; sin OOM/reinicios del servicio. Riesgo de presión/swap documentado sin aplicar aumento arbitrario o atribuir causa exacta a un worker.

Grafana inicialmente limitado a 256 MiB sufrió OOM al arrancar; se conservó evidencia, elevó solo este nuevo componente a 512 MiB (request 256 MiB, Go soft limit 384MiB) con host ~18 GiB disponibles y mínimo oficial de evaluación. Presupuesto final adicional requests 225m/416 MiB, limits 1.6 CPU/960 MiB. Muestra final: Prometheus 41 MiB/1m, Grafana 326 MiB/3m, adaptador 16 MiB/1m (~383 MiB/5m); app API 172 MiB, ML 196 MiB, web 10 MiB. Muestras, no picos/capacidad productiva. No métricas continuas Docker privilegiadas, solo diagnóstico operativo/probes.

### Implementación y pruebas estáticas/locales

Cambios: API pom/properties/HealthTests; ML app/main.py, nuevo metrics.py/test_metrics, pyproject/uv.lock; Dockerfile.ml con lock app exportado separado, nginx; chart app 0.2.0/F5.1 con opción observabilidad; nuevo chart retailops-observability (RBAC, ConfigMaps, seguridad, storage refs, tres dashboards), infra/observability/storage/images.lock/tests; scripts build_observability_apps, observability, inspect_mlflow_memory, validate_observability, verify_observability; paso CI estático. Documentos AGENTS/README/ROADMAP/PROGRESS/ARCHITECTURE/DECISIONS/DEPLOYMENT y nuevo OBSERVABILITY.

Maven verify **10 casos pasan**; uv locked pytest **13 pasan**, con aviso heredado TestClient/httpx (fixtures, sin entrenamiento/registro reales); **3 unittest** adaptador pasan. Tres imágenes app nuevas construidas sin sobrescribir F4/MLflow, etiqueta sha-f4fc9b2785b4adf4263b40b33d75e6f3e0b6eaa5. Usuario importó una vez el archivo en containerd y se confirmó inventario; no otros sudo. No cambios React: assets compilados previos reutilizados y comprobados por HTTP, sin repetir build/lint frontend. Helm lint/render + kubeconform **34 recursos válidos**, promtool config y **22 expresiones** válidas, actionlint/bash -n/py_compile/diff --check correctos. CI añade validación de observabilidad, aún sin ejecución remota F5.1.

### Validación real

Tres apps y tres componentes observabilidad Ready; tres PVC Bound. **Cuatro targets UP** (spring/fastapi/lab/prometheus), Grafana datasource health OK y consulta proxy entrega series reales. Tres dashboards/UID/títulos/leyendas/expresiones coinciden con fuentes; **24 consultas ejecutadas**. Modelo real v1/sales-pit-v1/candidate_local_preview cargado, gauge loaded=1 y cinco dependencias observadas UP. CPU/memoria por namespace desde metrics-server, solicitudes/latencias y métricas JVM/proceso reales. Grafana API anónima 401, frontend métricas 404 y cliente app rechazado por policy a Prometheus con servicio accesible desde Grafana autorizado.

Smoke integrado funcional pasa sin datos futuros: contador Spring 400=1 por petición fuera de corte y FastAPI 422=1 por cuerpo inválido. No se realizó nueva inferencia válida ni experimento de fallos. Ventana medida de pruebas/probes: Spring ~0.367 req/s/p95 ~0.028 s, FastAPI ~0.333 req/s/p95 ~0.0095 s; no benchmark comercial. ~1334 series head Prometheus en muestra. Versiones/digests fijados tras consulta oficial; esos números proceden del laboratorio.

Errores encontrados y corregidos: prueba Java inicial 404 por exportación desactivada en contexto de tests, habilitada explícitamente; Grafana OOM inicial, presupuesto corregido; etiqueta namespace del adaptador errónea en primera validación, detectada por PromQL y corregida con regresión. Se conservaron muestras antiguas de métricas: no considerar válido ese tramo previo ni purgar datos. Probe de rechazo inicialmente esperaba timeout y K3s devolvió ConnectionRefused; se contrastó con acceso autorizado positivo sin cambiar policy.

### Integridad y cierre

Snapshots SQL/registro/objetos antes/después idénticos: 1 297 296 ventas, suma decimal/fechas, 9 106 020 features, cutoff 2014-12-31, cero autorizaciones/etiquetas futuras; modelo v1/métricas y 19 versiones de objetos MLflow conservados. Cuatro volúmenes Compose idénticos. No se tocó SOURCE, bootstrap, pipelines, modelos, secretos existentes o permisos globales. No se hicieron hashes exhaustivos de tablas ni backups.

Cierre ejecutado mediante observability.sh stop: seis Deployments 0/0, sin pods app/observabilidad, tres PVC Bound conservados; cuatro dependencias exited(0), sin OOM/reinicios; puente/tres forwards cerrados y sin listeners temporales. K3s previamente activo conserva Ready/activo/disabled. Namespace/Secrets/RBAC/releases/imágenes/métricas/Grafana persistentes conservados. Procedimiento de inicio/detención, comandos y límites en OBSERVABILITY.md.

Evidencia privada .local/f51: logs Maven/pytest/build/static/Helm, images/digests/tag, mlflow-memory*, recursos, verification-*.json, verified-series/http-series, rbac-verified/network-deny/prometheus-flags, data-before/data-after/data-comparison/volumes-comparison, observability-live/app-live y closure/app-stopped/observability-stopped. Sin datos sintéticos presentados como medición real.

Próxima tarea exacta: detenerse para revisión de F5.1; no iniciar F5.2, Loki, Alertmanager, backups o incidentes. Pendientes fuera de esta evidencia: CI remota del cambio F5.1, revisión visual de navegador, medición bajo carga/fallos y diagnóstico detallado de workers MLflow. Sin commit/push/pull/publicación.

## Corrección puntual CI — selector Java 21

El usuario informó fallo de actions/setup-java por selector exacto de parche/build no resuelto. `.github/workflows/ci.yml` ahora usa `distribution: temurin` y `java-version: '21'`; la misma referencia en publish.yml se alineó para evitar el mismo fallo. SHA de ambas acciones, cachés, permisos, disparadores y pasos restantes conservados. DEPLOYMENT.md refleja que se fija la línea Java 21, no un build exacto.

Validación local: actionlint en ambos workflows y comprobación de distribución/selector/SHA correctos; git diff --check pasa. No se repitieron builds ni se invocaron workflows/publicación/servicios. Sin commit/push. Próxima tarea exacta: revisión/commit del usuario y reejecución de CI en GitHub para confirmar la resolución del JDK; sin ampliar F4 ni avanzar a F5.

## Cierre verificado F4 — despliegue y rollback reales

- Acceso privado 0600 y contexto default verificados; server https://192.168.0.121:6443 accesible. Nodo gigabyte-desktop Ready, v1.37.2+k3s1/containerd 2.3.7-k3s1. CoreDNS, local-path-provisioner y metrics-server Running/Ready; job Gateway API CRD completado. Las tres imágenes app con SHA abd1044fc28d6be41e7a274183cc675899370aa8 constan en inventario del nodo y pods usaron caché local. No se repitió instalación/importación ni se modificó UFW.
- Arrancadas solo PostgreSQL/MinIO/MLflow/Airflow API Compose preexistentes y puente CNI. Sin provisionadores o runner Flyway ni trabajo de datos. Scheduler/dag processor permanecieron inicialmente detenidos: viewer consultó cuatro DAGs e historial persistido, sin ejecutar nuevos DAGs ni refrescar su catálogo.
- Namespace/Secrets externos creados sin imprimir credenciales; PVC 2 GiB local-path/RWO Bound tras primer consumidor. Helm install revision 1: tres Deployments disponibles, pods 1/1 y cero reinicios. Contratos reales de aliases postgres/mlflow, archivo trainer regular 0600 y DNS interno/externo comprobados desde pod ML; puente funcional con SQL, MLflow y viewer. Web solo por port-forward 127.0.0.1:5174, servicios ClusterIP y dependencias loopback/CNI.
- **Tres smokes completos aprobados, 12 comprobaciones por ejecución**: HTML/bundle, Actuator, plataforma/dependencias UP, bootstrap 1 297 296 filas/corte, catálogos 54/33, 30 observaciones diciembre de tienda 1/GROCERY I y Navidad ausente, enero rechazado 400, metadatos reales FastAPI v1/run original sin aprobación, cuatro DAGs viewer y predicción sin consentimiento rechazada 409. candidateDemo siguió false; no se ejecutó nueva inferencia POST de siete días ni prueba visual de navegador en F4.
- **Ensayo real scripts/deploy.sh rehearse:** revisión 1→2 con marca de anotación web; rollout y smoke pasan; rollback crea revisión 3, descripción Rollback to 1; rollout/smoke vuelven a pasar. Misma imagen, tres Deployments disponibles, cero reinicios y PVC Bound tras revertir. Se verificó rollback de configuración, no cambio de binarios ni rollback de datos/modelos. Corrección del helper: cada smoke administra su forward, porque sustituir el pod web invalida la conexión anterior; comprobado realmente durante ensayo.
- **Integridad antes/después:** snapshots SQL read-only iguales en metadatos/lotes/publicaciones y count/min/max/suma decimal/catálogos de ventas; 9 106 020 features, cero etiquetas futuras y cero autorizaciones nuevas. API/trainer para negocio; releaser en transacción read-only solo para count de autorizaciones. Registro/métricas v1 iguales; 19 versiones de objetos MLflow conservan VersionId/ETag/tamaño. Cuatro volúmenes Compose idénticos en identidad/configuración. No se releyó SOURCE ni se entrenó/registró/promovió. No se afirma hash exhaustivo de todas las tablas ni backup/restore.
- **Recursos reales, muestras no picos:** pods API 13m/170 MiB, ML 2m/194 MiB, web 4m/10 MiB (~374 MiB total pods app). Compose PostgreSQL 78.47 MiB, MinIO 93.18 MiB, Airflow API 221.5 MiB, MLflow 994 MiB de 1 GiB; MLflow sin OOM ni reinicios, cercano a límite. MemoryCurrent unidad K3s 3 355 607 040 bytes (~3.13 GiB) durante ensayo y 3 315 404 800 (~3.09 GiB) al cierre; incluye contabilidad/cachés del cgroup y no es solo RSS ni memoria exclusiva sumable a pods. Mantener margen antes de cargas nuevas.
- **Cierre conservador verificado:** app escalada a cero, pods terminados, release Helm revisión 3/Secrets/namespace/PVC conservados (Bound). Puente y forwards propios cerrados. Cuatro dependencias Compose exited(0), sin OOM/reinicios; sin contenedores Docker activos ni listeners temporales 5174/puente/5432/5000/8081/9000. K3s ya estaba activo al iniciar: permanece active/running, disabled y nodo Ready; componentes de sistema sin tocar. No se borraron datos, volúmenes, PVC o configuraciones.

Evidencia privada `.local/f4`: node-before.json, system-before/system-after.json, helm-install.log, helm-history.json, rehearse.log, smoke-*.json/logs, network-contract.log, data-before/data-before-drill/data-after.json y state-comparison.json; resources-*, workloads-after/workloads-stopped.json, volumes-before-kubernetes/volumes-after.json, dependencies-final.json, listeners-final.txt y k3s-final.txt. Kubeconfig/Secrets/archivo imágenes/evidencias ignorados por Git.

Archivos de este cierre: scripts/deploy.sh y smoke_deployment.py; AGENTS/README/ARCHITECTURE/DECISIONS/ROADMAP/PROGRESS/DEPLOYMENT. Validación previa Helm/esquemas y nueva ejecución real de helpers pasan; bash -n, py_compile y git diff --check correctos. Sin cambios en fuentes de apps que justifiquen repetir builds/suites ya aprobados en F4 (11 pytest/9 JUnit/build-lint React). Actions: validación estática y builds locales previos, sin ejecución remota/publicación ni commit/push/pull. Limitaciones restantes: CI remota, cambio de binarios, nuevo DAG, nueva inferencia POST, seguridad multiusuario/HA y backups fuera de la evidencia; no se declara validación productiva.

Próxima tarea exacta: detenerse para revisión de F4, sin iniciar F5. Si se solicita reactivar el laboratorio, reutilizar DEPLOYMENT.md, recursos/volúmenes existentes y kubeconfig privado; no repetir bootstrap, reglas ni importación.


## F4 — CI y preparación Kubernetes/Helm (historial)

Los apartados siguientes conservan resultados de etapas anteriores; el estado vigente y cierre verificable están arriba.

- Workflows `.github/workflows/ci.yml` (push main, PR, manual, reusable) y `publish.yml` (solo manual con publish=true/main/propietario, CI previo, environment ghcr-release). Actions por SHA, herramientas con versiones/SHA256, permisos mínimos, cachés, concurrencia y sin deploy automático. Publicación separada, no invocada; protección del environment debe configurarla el usuario en GitHub. Ejecución remota CI pendiente; validación local no equivale a Actions ejecutado.
- Seis imágenes construidas con **sha-abd1044fc28d6be41e7a274183cc675899370aa8** (huella local anterior al cierre documental): web/api/ml-service/mlflow/airflow/minio. Locks y bases existentes fijadas; ML acepta MLFLOW_BASE por ARG para enlazar la base con el mismo SHA sin cambiar local-v1 Compose. CI usa SHA del commit. No se publicó ni sobrescribió imagen Compose. No se comprobó identidad bit a bit entre builds.
- Chart `infra/helm/retailops`: 3 Deployments, 3 ClusterIP, 3 ServiceAccounts sin token, ConfigMap y 3 NetworkPolicies de entrada. Probes, requests/limits, Secrets externos por archivos, validación de endpoints/tag SHA/modelo v1. Namespace/PVC declarados fuera del chart; caché independiente conservada por rollback. Web/API con surge; ML sin dos escritores concurrentes de caché y con interrupción prevista durante update.
- Dependencias Compose explícitas, sin copiar/migrar volúmenes: puente TCP optativo CNI 10.42.0.1→loopback, restringido a origen pod CIDR. **No probado con pods reales**, cni0 todavía ausente. Scripts build/deploy/smoke/rehearse/rollback e instalador revisable con guardia de autorización, checksum, versión y sin arranque/habilitación automáticos. No se ejecutó instalador.
- Host inspeccionado en modo lectura: CachyOS, 12 CPU, 30 GiB RAM (~22 disponibles), ~390 GiB disco libre, Docker activo, sin K3s/kubectl/Helm iniciales. Sin contenedores activos. Puertos previstos libres; rutas Docker/LAN observadas no solapan CIDRs propuestos. Dos interfaces LAN activas; configuración propone Ethernet explícita. Sin cambios de firewall/red/servicios del host. API Kubernetes requiere revisar filtrado antes de arrancar; aplicaciones siguen ClusterIP/port-forward.
- **Pruebas reales locales:** `uv run --project apps/ml-service --locked pytest apps/ml-service/tests -q`: 11 pasan (aviso heredado TestClient/httpx). `./mvnw --batch-mode verify`: 9 pasan, BUILD SUCCESS. React `npm run build`/`npm run lint`: pasan, advertencias heredadas y bundle grande. `scripts/ci/validate.sh`: AST DAGs, compileall, Compose 2.39.4 config, hadolint, actionlint, Helm 3.17.3 lint/render y kubeconform 0.8.0/Kubernetes 1.37: **15/15 recursos válidos**, sin skips. Values incompletos/latest rechazados. `bash -n` scripts pasa.
- **DagBag real Airflow 3.3.2**, contenedor efímero sin red/credenciales/volúmenes: cuatro DAGs importados, cero errores, sin ejecutar tareas. Primera llamada falló por include_examples eliminado; corregida al módulo/firma reales y verificación final pasa. Hadolint 2.12 no interpretaba ADD --checksum existente; se fijó 2.14 antes de la validación final. Helm no admitió lookahead del esquema inicial; se movió la restricción de loopback a plantilla y pasó el render.
- Herramientas descargadas a `.local/f4/tools`, sin instalar al SO; K3s **v1.37.2+k3s1** y kubectl 1.37.2 fijados tras consultar release oficial. Fallos iniciales del sandbox con cachés Maven/uv y red resueltos mediante ejecuciones autorizadas; Helm inicialmente buscó el nombre original del tar en checksum, corregido verificando bytes antes de extraer. No quedan verificaciones fallidas presentadas como éxito.
- Consumo: requests app 550m/800 MiB, limits 5 CPU/1920 MiB; sumar surge y dependencias. Tamaños Docker: Airflow 5.76 GB, MLflow/ML 1.37 GB cada una (capas compartidas), API 457 MB, web 112 MB, MinIO 207 MB. Sin medición runtime K3s. Evidencia privada `.local/f4/{validation.log,build-images.log,maven.log,web-build.log,web-lint.log,dagbag.log,rendered.yaml}`.

Límites: **no hay clúster/despliegue/readiness/smoke Kubernetes/rollout/rollback verificados**. No se iniciaron dependencias Compose, no se entrenó/registró, liberó meses ni modificó v1. Contenedores efímeros eliminados al terminar, datos/volúmenes conservados. Inspección inicial detectó scheduler y DAG processor exited(1), distinto del cierre previo documentado: se registra estado observado sin atribuir causa ni reiniciarlos.

Archivos: workflows; infra/helm/retailops/{Chart,values,values-validation,values.schema,templates}; infra/k3s/{namespace,cache,config.example,values-compose.example,install}; scripts/{build_images,source_version,deploy,compose_bridge,smoke_deployment} y scripts/ci/{tools.lock,install_tools,validate,check_dags,check_dagbag}; Dockerfile.ml; DEPLOYMENT, AGENTS, README, ARCHITECTURE, DECISIONS, ROADMAP y PROGRESS. Sin staging/commit. Revisión final del cierre declarativo: 32 archivos candidatos, cero coincidencias con secretos locales y git diff --check correcto; contenedores activos al cierre: cero. Hay remoto origin preexistente; no se consultó su URL ni se modificó.

### Autorización controlada y preflight real del host

El usuario autorizó instalar mediante infra/k3s/install.sh y arrancar K3s, con detención obligatoria antes de cambios en firewall/rutas globales/seguridad. Se revisó de nuevo el host antes de cualquier instalación:

- Ethernet enp6s0 UP, 192.168.0.121/24, gateway 192.168.0.1 y prioridad 100; Wi-Fi 192.168.0.116/24, prioridad 600. Rutas Docker 172.17/16 y 172.18/16; sin solapamiento observado con 10.42/16 y 10.43/16. DNS efectivo del host 192.168.0.1. Puertos K3s/app previstos libres durante inspección.
- cgroups v2 con cpu/memory/pids; overlay cargado y módulos br_netfilter/vxlan disponibles (sin cargarlos). IPv4 forwarding ya valía 1. Docker activo sin contenedores ejecutándose; Hyprland activo, sin conflicto de puertos observado. No se afirma compatibilidad runtime antes de iniciar K3s.
- Hash del instalador coincide con tools.lock.json, versión fija v1.37.2+k3s1. Se inspeccionó service_enable_and_start: SKIP_ENABLE=true retorna antes de enable/start; wrapper fija también SKIP_START=true. K3s y directorios de instalación siguen ausentes.
- **UFW activo y habilitado**, confirmado por systemctl/configuración; DEFAULT_INPUT_POLICY=DROP y DEFAULT_FORWARD_POLICY=DROP, OUTPUT=ACCEPT. user.rules/user6.rules sin reglas de usuario y before.rules sin excepciones K3s. Esta observación corrige la impresión anterior basada solo en firewalld inactivo. Ruleset efectivo no accesible sin root; nft list ruleset devuelve Operation not permitted.
- **sudo -n true exige contraseña**. La aprobación de instalación no proporciona autenticación administrativa al proceso. No se intentó eludir sudo ni solicitar/registrar contraseñas.

Se detuvo la operación antes de instalar/arrancar o cambiar firewall, conforme al límite expreso. Propuesta concreta no aplicada: infra/k3s/FIREWALL_PROPOSAL.md (cni0/pod CIDR → API/kubelet/puente, tráfico entre pods y DNS al router, manteniendo DROP y sin nuevas aperturas LAN). Requiere primero ruleset efectivo y luego autorización específica. Helper infra/k3s/preflight-root.sh solo lee reglas y escribe informe privado 0600; pendiente ejecución local autenticada por el usuario. `bash -n` de helpers y git diff --check pasan; no se repitieron suites/builds de aplicaciones sin cambios.

Evidencia privada `.local/f4/host-preflight.json`, modo 0600 y directorio endurecido a 0700. No hay evidencia nueva de despliegue/rollout/rollback ni consumo K3s. Ningún servicio fue iniciado; instalación, Docker, Hyprland, datos y modelo siguen sin cambios por esta operación. Sin commit/push/pull y sin F5.

### Revisión del informe efectivo y autorización condicional UFW

El usuario proporcionó `.local/f4/firewall-live.R6bO63` y autorizó condicionalmente las seis excepciones internas de la propuesta, sujetas a revisar reglas efectivas, evitar duplicados y conservar DROP/Docker/conectividad. Informe revisado: UFW activo, IPv4/IPv6 INPUT/FORWARD DROP y OUTPUT ACCEPT; cadenas ufw-user-input/forward vacías; FORWARD pasa por DOCKER-USER (vacía) y DOCKER-FORWARD antes de UFW. Docker acepta sus interfaces docker0/br-38a0a366adc2, no cni0. NAT limitado a 172.17/16 y 172.18/16. No hay excepciones equivalentes para los seis flujos; no se observó conflicto estático que exija reglas adicionales.

Revalidación actual: Ethernet enp6s0 192.168.0.121/24, gateway/DNS 192.168.0.1; Wi-Fi y rutas/CIDRs sin cambios, puertos previstos libres, Docker/UFW activos y K3s ausente. Contenedor efímero Alpine existente con read-only/cap-drop verificó DNS Docker y fue eliminado; HTTPS desde host correcto. **sudo -n true / sudo -n -l / sudo -n ufw status verbose siguen exigiendo contraseña**. No se aplicaron reglas ni se instaló/arrancó K3s. No es falta de aprobación ni rechazo de revisión automática: falta autenticación administrativa del SO.

Preparado `infra/k3s/prepare-host.py` para ejecución local autenticada: compara reglas normalizadas con la revisión privada y rechaza deriva antes de modificar; comprueba topología, DNS, puertos, cgroups, imágenes y conectividad; aplica solo los seis flujos ya autorizados, registra salidas y comandos de reversión por cada cambio; llama al install.sh ya autorizado, confirma servicio disabled, lo arranca, espera nodo Ready, crea kubeconfig privado 0600 e importa las tres imágenes app existentes. Revisa al final DROP IPv4/IPv6, conservación de reglas anteriores, rutas por defecto, Docker y HTTPS. En fallo posterior a start detiene K3s conservando instalación/reglas/evidencia; no revierte ni borra nada automáticamente. Rechaza reejecución parcial/deriva para revisión. Mantiene K3s ejecutándose si termina bien para continuar pruebas F4; aún no despliega aplicación.

Evidencia privada nueva `.local/f4/firewall-reviewed.json`, con SHA256 del informe y normalización IPv4/IPv6; configuración .local/f4/k3s-config.yaml preparada 0600 sin tocar /etc. Verificación sin privilegios: normalización coincide con informe; las seis órdenes son idénticas a propuesta; guardia root rechaza también Python -O; py_compile y git diff --check pasan. El helper administrativo **no fue ejecutado con root ni validado end-to-end**. No se repitieron builds/suites de aplicaciones sin cambios.

### Fallo del arranque y recuperación de la instalación existente

El usuario ejecutó la etapa administrativa: evidencia `.local/f4/host-stage-20261116T184903Z` inspeccionada. install.log confirma descarga, checksum e instalación de v1.37.2+k3s1; seis salidas ufw-N.txt indican Rule added y applied-6.json contiene las seis órdenes. after-ufw.txt confirma DROP para entrada/reenvío y solo excepciones internas. revert-proposed.txt conserva reversión propuesta. No existen nodes-ready.json, kubeconfig, import-images.log o success.json de esa etapa: no se presenta como completada.

El usuario informó timeout de 180 s en systemctl start y estado failed. Journal accesible confirma `invalid node-external-ip: invalid ip format ''`. Error de la plantilla preparada por el asistente: incluía `node-external-ip: ""`. Corregido omitiendo el parámetro; sin sustituirlo por una IP externa. En inspección posterior systemctl muestra active/running, Result=success, disabled y arranque 13:59:54 America/Guayaquil, posterior al fallo. cni0/flannel presentes; **esto no demuestra nodo Ready**. Configuración instalada 0600 no legible por el asistente. No se reinició ni modificó el servicio durante esta corrección.

Cambios: infra/k3s/config.yaml.example; validate_config.py rechaza esa opción en laboratorio, con guardia CLI antes de instalar en install.sh y prepare-host.py; CI ejecuta validación y tres unittest de regresión. Configuración privada .local/f4/k3s-config.yaml corregida solo en la línea vacía, con copia previa 0600 k3s-config.before-empty-external-ip.yaml. Sin cambios automáticos en /etc. RECOVERY.md proporciona retirada puntual con backup temporal, restart solo si falta corrección y wait de Ready con --server explícito. No volver a ejecutar prepare-host.py, reinstalar o duplicar UFW.

Verificación real: tres unittest pasan (plantilla, opciones vacías/no necesarias y rechazo CLI sin modificar archivo); py_compile, bash -n y git diff --check correctos. Validación de la configuración privada corregida pasa. No se repiten builds de aplicaciones sin cambios. Evidencia de recuperación local en .local/f4/recovery-status.json; no se declara recuperación del clúster verificada ni datos/modelo revalidados todavía.

### Continuación desde Ready confirmado

El usuario confirmó `node/gigabyte-desktop condition met` mediante wait de Ready. Se revalidó servicio active/running, disabled, MemoryCurrent 1 271 037 952 bytes (~1.18 GiB); cni0 10.42.0.1 y API TCP 192.168.0.121:6443 accesibles. Aún no se accedió a la API autenticada para comprobar componentes/red de pods: kubeconfig global 0600 root y socket containerd root:root 0660; no hay kubeconfig privado ni importación verificada. No se intentó eludir esos permisos.

Operaciones no privilegiadas completadas: tres imágenes app originales inspeccionadas por ID y exportadas juntas a `.local/f4/images.tar` (463 MiB, modo 0600), con SHA256 en images.tar.sha256; values privados 0600 preparados con etiquetas originales. Registrados cuatro volúmenes Compose y contenedores iniciales en volumes-before-kubernetes.json/compose-before-kubernetes.json. Ninguna dependencia Compose estaba activa; no se arrancó aún para evitar dejar servicios temporales esperando acceso al clúster.

Contraste del chart con las imágenes detectó tres incompatibilidades declarativas: Config trainer solo acepta postgres/loopback y exige archivo regular 0600; MLflow acepta Host mlflow:*; PVC local-path puede necesitar primer consumidor antes de Bound. Ajustes limitados al chart/script: hostAliases postgres/mlflow → 10.42.0.1, endpoints conservan esos nombres; initContainer con la misma imagen ML copia únicamente trainer desde Secret proyectado a emptyDir en memoria, regular 0600; preflight admite Pending exclusivamente cuando StorageClass declara WaitForFirstConsumer. Sin cambios de código/permisos de roles/credenciales reales ni rebuild de imágenes, sin modificar UFW.

Verificación: Helm lint estricto y render de values locales pasan; kubeconform 15/15 recursos válidos sin skips. Contrato real de la imagen ML probado en contenedor efímero sin red con fixture sintética: Config(host=postgres,port=15432) acepta archivo regular 0600; sin SQL/secretos reales. bash -n y git diff --check pasan. Evidencia ready-continuation.json/rendered-compose.yaml y archivo de imágenes privados. Pendientes: API autenticada/componentes, importación real, dependencias/puente, Helm/pods/readiness/smoke/rollout/rollback, comparación SQL/modelo y recursos de aplicación. No se declara F4 completa.

Próxima tarea de aquella etapa (histórico): el usuario ejecuta las dos operaciones sudo de DEPLOYMENT.md (copiar kubeconfig a .local/f4 con propietario usuario/0600 e importar images.tar con /usr/local/bin/k3s ctr). Después el asistente ajusta únicamente endpoint del kubeconfig privado si apunta a loopback, verifica API/componentes e imágenes y continúa despliegue/pruebas/cierre. No volver a instalar/preparar host ni modificar UFW, y no repetir la confirmación Ready ya completada. Sin F5/commits/push/pull.


## F3 — Aplicación funcional integrada

- Spring `/v1`: plataforma, histórico/lotes, tiendas/familias, ventas paginadas, modelo/métricas, pipelines y predicción delegada a FastAPI. DTOs, parámetros preparados, errores seguros y límites temporales/HTTP/SQL. Rol API read-only sobre training/metadatos, sin migraciones. Airflow viewer con credencial privada separada; consulta cuatro DAGs y tres runs por DAG, sin trigger.
- React/TailAdmin conserva layout/licencia y añade dashboard, explorador de ventas con gráfico de página, pronósticos, modelo y pipelines; carga/vacío/error, filtros y consentimiento candidato. Claves en los cuatro catálogos existentes. Sin navegador → PostgreSQL/MLflow ni credenciales VITE.
- Compose modular añade FastAPI, Spring y nginx/React; nueve servicios healthy en validación. Puertos internos ML/Java no publicados; acceso web loopback 5173. Caché de inferencia persistente independiente, secretos de mínimo acceso, límites de memoria. Helper de conexión EDA admite DNS Docker `postgres` conservando trainer/consultas read-only; no se ejecutaron notebooks.
- Validación real: bootstrap RELEASED/COMPLETE 1 297 296 filas, 54 tiendas/33 familias, corte 2014-12-31; ventas tienda 1/GROCERY I diciembre: 30 observaciones y 25 ausente. Histórico posterior al corte rechazado (400); demo sin consentimiento (409); predicción real siete días con v1 y sin aprobación. Parada de FastAPI produjo 503 ML_UNAVAILABLE y recuperación del mismo v1. Respuestas contrastadas con secretos locales sin coincidencias.
- Predicción emisión 2014-12-31, tienda 1/GROCERY I, enero 1…7: 10.53490163; 2343.58832739; 1791.86781423; 931.47117528; 1865.60140568; 2814.96193602; 2814.96193602. Son predicciones, no datos observados liberados.
- MLflow run 55257fc2ce414793b73b9d0df4c95fbb/version 1: HGB MAE 125.633166/WAPE 0.2619214115/RMSLE 0.522605386; Seasonal Naïve 120.912959/0.252080672/0.573126019. **HGB no supera MAE/WAPE del holdout**, no hay modelo aprobado; demo explícita no modifica registro.
- Pruebas mínimas: cuatro casos JUnit relevantes verificados (tres pasan en primera ejecución, consentimiento corregido y caso reejecutado correctamente); un pytest de carga/inferencia pasa; build/lint React pasan con advertencias heredadas y bundle ApexCharts grande. Smoke reproducible `python scripts/smoke_application.py --check-ml-outage`, evidencia privada `.local/application/smoke.json`. No se repitieron suites completas ni se entrenó/registró.

Archivos: API clases Platform/History/External/DTO/errores, perfil integrated y JUnit; runtime ML/métricas y prueba puntual; frontend rutas/sidebar/páginas/catálogos; Dockerfiles/nginx/compose.app; scripts prepare_app/smoke_application; helper conexión EDA; AGENTS, arquitectura/decisiones/roadmap/progreso y APPLICATION.md. [Comandos, endpoints y límites](APPLICATION.md).

Pendiente fuera de alcance: autenticación comercial ADMIN/ANALYST, aprobación/promoción real del modelo, ingesta mensual productiva y fases DevOps. La aplicación local no representa seguridad multiusuario ni disponibilidad productiva. No avanzar sin nueva autorización.

## F2 — Airflow y orquestación end-to-end

La solicitud actual anticipa Airflow respecto al roadmap original y se registró el ajuste antes de implementar. Se revisaron instrucciones, arquitectura/decisiones, almacenamiento/features/MLOps y scripts reales: no existía publicador mensual y GOLD v1 rechazaba cortes distintos. Se conservó v1 y se implementaron adaptadores/contrato v2.

- Airflow **3.3.2/Python 3.12**, imagen oficial por digest, Compose modular: API/UI loopback 8081, scheduler LocalExecutor y DAG processor; sin Celery/Redis. Base/identidad retailops_airflow independientes, logs en volumen nombrado y autenticación SimpleAuthManager con secretos privados persistentes. Entornos uv aislados de ingesta/ML, sin mezclar dependencias con Airflow ni montar SOURCE/Docker socket.
- Cuatro DAGs manuales schedule=None: retailops_monthly_release, retailops_train_candidate, retailops_full_pipeline y retailops_validate_existing. Pool global de un slot, max_active_runs=1, dependencias all_success y reintentos acotados.
- Control/data **V4 nuevas**, aplicadas con Flyway único, V1/V2/V3 intactas. Autorización operadora explícita no disponible en contenedores; trigger exige siguiente mes. El operador prepara solo el workspace seleccionado con extractor existente; DAG ingiere/publica reutilizando recuperación SQL/S3. GOLD v2 append-only reutiliza bootstrap por vistas UNION ALL, sin recalcular/copiar nueve millones de filas. Se bloquea otra autorización si GOLD del mes anterior está pendiente.
- ML existente parametrizado por corte, dataset semanal y validación/evaluación anteriores al corte; contrato v2 explícito. Identidad lógica, checkpoints y recuperación de run/versión impiden duplicación normal; ambigüedad o ajuste iniciado sin checkpoint falla para revisión. Candidatos separados de inferencia v1, sin promoción automática.
- **DAG real seguro safe-f2-20261114T012419: success**, cuatro tareas success al primer intento (historical_state, gold_contract, registered_model, dependencies). UI GET 200 y API autenticada; DAG processor reportó cuatro DAGs y cero errores de importación. Evidencia .local/airflow/execution.json, metadatos/logs persistentes.
- Comprobación posterior: bootstrap RELEASED/COMPLETE, corte 2014-12-31; autorizaciones mensuales 0, meses nuevos liberados 0, features/etiquetas incrementales productivas 0. Vista v2 expone las 9 106 020 filas bootstrap sin copiarlas. Registro MLflow conserva solo v1 READY/run 55257fc2ce414793b73b9d0df4c95fbb; resultados/evidencias F1-06 preservados (HGB no supera baseline en MAE/WAPE).
- Pruebas mínimas: **3 unittest nuevos aprobados** (secuencia/autorización, extremos futuros, escritura/idempotencia en DB sintética propia eliminada después), **2 pytest nuevos aprobados** (plan temporal y retry de candidato sin ajustar/registrar), carga de DAGs vía CLI/API y flujo seguro real. No se repitieron suites de fases previas ni notebooks. Maven únicamente `-DskipTests package` para SQL, sin Java/JUnit modificados.
- Recursos: muestras API 272,2 MiB, scheduler 315,9 MiB, processor 163,3 MiB (~751 MiB total); límites 1/3/1 GiB y 2 CPU cada uno. No son picos ni incluyen PostgreSQL/MinIO/MLflow o un entrenamiento futuro.

Archivos: nuevas V4 control/data; pipelines/orchestration/{core,incremental_gold}.py y pruebas; adaptaciones mínimas extractor/register/cliente bootstrap; apps/ml-service/app/{plan,orchestrated}.py, cambios parametrizados data/training y test_orchestrated.py; infra/airflow/dags/retailops.py; compose.airflow.yaml, Dockerfile/start.py y Compose raíz/.dockerignore; scripts/airflow_infra.py y airflow_smoke.py; contrato gold-features-v2.json; docs/AIRFLOW.md y AGENTS/ROADMAP/PROGRESS/DECISIONS/ARCHITECTURE, README infra, .env.example. Sin frontend, GitHub/CI, Kubernetes u observabilidad.

Problemas resueltos: entrypoint oficial necesario para NSS/UID; password file SimpleAuthManager requiere copia privada escribible; healthcheck CLI independiente perdía DSN y consultaba SQLite, sustituido por heartbeat API. Inspección DagBag inicial usó firma antigua; se sustituyó por CLI y registro real del processor. No se abrieron permisos ni se regeneraron secretos existentes.

Límites: publicación mensual productiva, nuevo entrenamiento v2 y recuperación S3 mensual no se ejecutaron por restricción; se verificaron código/conexión, autorización, fixtures aisladas y coordinación real segura. No se afirma rendimiento de un candidato nuevo ni backup/restore/seguridad multiusuario. La v1 inferida sigue fija, candidatos v2 no son aprobación de producción. Comandos, recuperación y límites en AIRFLOW.md.

### Cierre operativo F2

Los seis servicios iniciados (Airflow API, scheduler, DAG processor, PostgreSQL, MinIO y MLflow) se detuvieron mediante Compose. `docker compose ps -a` confirmó **exited, código 0** para los seis, conservando contenedores, volúmenes, metadatos, logs y artefactos. Solo se ejecutó el DAG seguro; sin publicación/entrenamiento/registro real. Este cierre precedió al commit F2 autorizado posteriormente: 8f753a3, sin push.

## Preparación Git local — historial previo al commit inicial

Autorización explícita posterior al cierre F1-06 para auditar exclusiones e inicializar Git local, sin remoto, push ni commit. Se revisaron instrucciones, arquitectura/decisiones, roadmap/progreso, configuraciones del stack y archivos reales.

- `.gitignore` adaptado a datasets/capas, CSV/Parquet y matrices generadas (con excepciones acotadas para fixtures/muestras), secretos/.env privados, .local, entornos/caches Python y Jupyter, compilados Maven/React, modelos, SQLite/dumps/backups, bind mounts y runtime futuro de Airflow/K3s/observabilidad. No se añadieron Terraform/Ansible ni tecnologías nuevas.
- Se conservan código, pyproject/uv.lock/package-lock, Maven Wrapper, SQL Flyway, contratos, notebooks fuente sin outputs, Compose/Dockerfiles, charts/manifests/workflows declarativos y gráficos/informes agregados revisados. Sin reglas globales que oculten .sql, YAML, JSON o carpetas de código de modelos.
- Auditoría previa con repositorio temporal fuera del proyecto y auditoría posterior con Git local: **708 candidatos**, aproximadamente **13,3 MiB**. Ninguno supera 5 MiB; el mayor es `apps/web/banner.png`, 1 430 718 bytes, recurso de TailAdmin. Tres notebooks con outputs vacíos/contadores null.
- Revisión básica de claves privadas/tokens/URI y literales sensibles, más comparación contra secretos reales locales sin mostrarlos: ninguna coincidencia con secretos reales detectada. Alertas heurísticas en scripts de infraestructura revisadas: son referencias a variables/archivos de secretos, no credenciales hardcodeadas. .env.example contiene solo configuración pública.
- `git check-ignore` comprobó exclusión de datos/secretos/modelos/entornos y conservación de 16 rutas de código/configuración, incluidas muestras, workflows y plantillas Helm; 17 rutas locales excluidas. Sin ocultar ni mover datasets existentes.
- El directorio .git visible inicialmente estaba vacío/protegido y Git no reconocía un repositorio. `git init --initial-branch=main` ejecutado con acceso autorizado al directorio de metadatos; repositorio local inicializado en la raíz. Índice vacío, sin commits ni remotos. Candidatos siguen como untracked, pendientes de autorización para el primer commit.

Modificados únicamente `.gitignore`, AGENTS y documentación PROGRESS/ROADMAP/DECISIONS para registrar alcance y resultados. Sin cambios funcionales, pruebas, entrenamientos, dependencias ni ejecución de servicios Docker. F1-06 y sus resultados permanecen intactos; Airflow no iniciado.

## F1-06 — ML y MLOps funcional

Se leyeron instrucciones, roadmap/progreso, arquitectura/decisiones, contrato/features y resultados baseline; inspeccionados FastAPI, vistas GOLD y Compose. Se informó la ampliación respecto al roadmap antes de implementar y se añadió F1-06 sin alterar fases completadas.

- Un único HGB Poisson global (sklearn 1.9.1, 80 iteraciones, semilla 42, sin búsqueda/early stopping). OrdinalEncoder ajustado solo con entrenamiento, tienda/familia como categorías nativas, NaN conservados; entradas cerradas excluyen etiquetas. Mismo proyecto uv/Python 3.12.16, lock actualizado, sin paquetes globales.
- Ajuste al 2014-10-31: emisiones de lunes 2013-01-07..2014-10-27, objetivos ≤ fecha de ajuste, **1 177 902 ejemplos**, 1 782 etiquetas ausentes excluidas. Validación noviembre 1..23; holdout emisiones diciembre 8..24, objetivos diciembre 9..31, posterior al último objetivo F1-05 (diciembre 7). Sin refit con evaluación.
- Holdout común **199 584 ejemplos** de 212 058 predicciones por método; 12 474 etiquetas de Navidad ausentes excluidas, nunca imputadas. Cobertura de predicciones 100 % en ambos, etiquetas 94,12 %. HGB: **MAE 125,6332, WAPE 26,1921 %, RMSLE 0,5226**. Seasonal Naïve: **120,9130 / 25,2081 % / 0,5731**. Se informa pérdida en MAE/WAPE y mejora en RMSLE sin manipular selección ni períodos.
- MLflow 3.18.0 en Compose modular, healthy, loopback 5000 y límite 1 GiB/2 CPU. Base retailops_mlflow con propietario/login separado; bucket privado/versionado retailops-mlflow e identidad MinIO restringida. Persisten en volúmenes PG/MinIO existentes. Solo provisionador usa administradores; entrenamiento/API SQL usan trainer. MLflow administra su propia base y no compite con Flyway de negocio.
- Experimento **retailops-sales-pit-v1** (ID 1), run **55257fc2ce414793b73b9d0df4c95fbb** FINISHED, modelo **retailops-sales-global v1**. Artefactos: modelo/firma, evaluación, contrato/lock, código y evidencia HTTP. Fit exitoso 4,325 s; flujo exitoso 29,712 s, RSS cliente 1 005 132 KiB. Checkpoint privado evita ajustes/evaluaciones de nuevo en reintentos compatibles.
- FastAPI: GET /health, GET /model, POST /predict y OpenAPI. Versión explícita del registro, validación del contrato/hash y fecha de ajuste; petición solo emisión/tienda/familia, extras rechazados. HTTP 422 para fechas fuera de 2014-10-31..2014-12-31, 404 sin features y 503 ante indisponibilidad; consultas limitadas a siete filas autorizadas.
- Prueba real: carga desde registro → FastAPI en 127.0.0.1:8180 → emisión 2014-12-31, tienda 1/GROCERY I → **siete predicciones finitas/no negativas para enero 1..7**, sin etiquetas/ingesta de enero. GET health/model y POST predict HTTP 200; proceso terminó limpiamente. JSON y logs privados en .local/mlops, ejemplo completo en MLOPS.md y artefacto del run.

Archivos: apps/ml-service/app/{__init__,data,model,training,runtime,main}.py, tests/test_ml.py, pyproject.toml/uv.lock; scripts/mlops_infra.py; infra/docker/compose.mlflow.yaml, compose.yaml, mlflow/{Dockerfile,start.py,configure-minio.sh,policy.json,requirements.lock}; .dockerignore, .env.example; docs/MLOPS.md y actualizaciones AGENTS/ROADMAP/ARCHITECTURE/DECISIONS/README infra. Sin cambios en Spring Boot, frontend, notebooks, GOLD/contratos, migraciones o CSV.

Verificación mínima: `uv run --directory apps/ml-service --locked pytest -q`: inicialmente ocho casos aprobados y uno fallido; tras corregir fixture, solo ese caso pasó. Control temporal actualizado ejecutado individualmente y aprobado. **Nueve casos verificados**, incluyendo dos nuevos de temporalidad y carga/contrato. Funcional principal `python -m app.training` y smoke HTTP real con v1, sin repetir suites de infra/ingesta/GOLD/Java. Hashes del contrato/código coinciden con el run; logs revisados sin contraseñas. Comandos y resultados en MLOPS.md.

Problemas: herramienta MinIO necesitó el mismo usuario root del contenedor que la ya existente para leer secretos 0600; no se abrieron permisos. MLflow/skops exigió lista explícita de tres tipos internos del pipeline propio: primer run 820796e88c5843c8b7126907430f40ee FAILED preservado; segundo intento con idénticos parámetros completó (dos ajustes por serialización, sin búsqueda). Se guarda checkpoint para no repetir ese coste. Fixture inicial enteramente NaN activó fallo de sklearn al ajustar; se corrigió a historial mixto con un cero sintético observado, sin cambiar/imputar datos reales. La limitación de columnas enteramente desconocidas en futuros ajustes queda documentada. TestClient conserva deprecación httpx ya conocida.

La inspección posterior detectó que PostgreSQL/MinIO/MLflow seguían ejecutándose, pese a la afirmación anterior de cierre. En el cierre autorizado se detuvieron únicamente esos tres servicios del proyecto retailops-data mediante `docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops stop mlflow minio postgres`. La comprobación `docker compose ... --profile mlops ps -a` confirmó los tres contenedores en `exited`, con código 0. Contenedores, datos, volúmenes, registro y artefactos conservados. FastAPI del smoke ya había terminado. Sin Airflow/Git/CI/K3s/observabilidad ni liberaciones. Limitaciones: servidor local sin autenticación/TLS multiusuario, artefactos propios confiables, hipótesis de ventas disponibles al cierre, muestreo semanal y un solo holdout. Candidato servido explícitamente como preview, no aprobación/promoción de producción.

### Cierre documental y operativo de F1-06

Corregidos exclusivamente ROADMAP.md (incluida la fila F1-06 dentro de la tabla), PROGRESS.md y MLOPS.md. Se conservaron resultados, modelo v1 y evidencias; HGB continúa por debajo de Seasonal Naïve en MAE/WAPE del holdout. No se ejecutaron entrenamiento, registro, pruebas, instalaciones ni cambios de código funcional. No se eliminaron contenedores o volúmenes; no se inicializó Git ni se avanzó a Airflow. Cierre completado, sin otra tarea iniciada.

## F1-05 — Baselines y evaluación temporal

Se revisaron instrucciones/documentos, contrato GOLD, vistas y entorno Jupyter. Se informó antes de implementar que el roadmap anterior incluía MLflow; la solicitud actual excluye esa parte y se actualizó solo F1-05. No se modificaron GOLD, migraciones ni notebooks 01/02.

- Creados `notebooks/03_baseline_backtesting.ipynb`, `notebooks/retailops_baselines.py`, `notebooks/tests/test_baselines.py`, `docs/BASELINE_RESULTS.md` y cuatro PNG en `docs/baseline_figures/`.
- Actualizados `notebooks/run_notebooks.py` (selección --only y evidencia local), README de notebooks, AGENTS, ROADMAP, DECISIONS y este registro. Mismo uv.lock/Python 3.12.16, sin dependencias nuevas.
- Solo trainer, conexiones read-only, consultas parametrizadas a training.gold_features/gold_labels, cursor de servidor en bloques de 20 000 filas. Sin SOURCE, Silver, tablas GOLD directas, auxiliares o estadísticas futuras. Las etiquetas solo puntúan, no generan predicciones.
- Folds de emisiones julio/septiembre/noviembre 2014: **1 135 134 ejemplos**; cobertura individual y común **100 %** para los tres métodos, cero etiquetas ausentes y cero objetivos posteriores al corte en estos folds. Métricas completas por fold/horizonte/familia/tienda en notebook y resumen local.
- Seasonal Naïve gana MAE/WAPE global: **71,7157 / 19,6473 %**, RMSLE 0,7927. Rolling Mean 7: MAE 96,3464 / WAPE 26,3951 % / RMSLE **0,6683** (mejor RMSLE). Rolling Mean 28: 105,8060 / 28,9867 % / 0,7312. Misma población comparable, sin ajuste.
- BOOKS tiene ventas cero en los folds, MAE/RMSLE cero y WAPE indefinido, no convertido en 0 %. NULL sigue ausente; no se recortan predicciones ni se imputan ventas.
- Pruebas esenciales: `uv run --project notebooks --locked python -m unittest discover -s notebooks/tests -p test_baselines.py -v`: **3 aprobadas**, métricas/ausencias, independencia de etiquetas y fechas de folds. No se repitieron suites anteriores ni Maven/infraestructura/GOLD.
- Verificación funcional: `uv run --project notebooks --locked python notebooks/run_notebooks.py --only 03_baseline_backtesting.ipynb`: **7 celdas completas, SUCCEEDED, 9,153 s**; consultas/evaluación 7,378 s. Resultados y hashes en `.local/baselines/results.json` y `execution.json`; SHA notebook y comandos en BASELINE_RESULTS. Outputs persistidos vacíos; cuatro gráficos, global y ejemplo revisados visualmente.
- PostgreSQL estaba detenido: iniciado con Compose y esperado healthy para el notebook, detenido al cierre con volumen conservado. MinIO no se inició. No se escribieron datos, no se avanzó el corte ni se liberaron meses.

Límites: solo tres meses de emisión, etiquetas solapadas y unidades mixtas; no hay muestras independientes ni garantía de generalización. Hipótesis de ventas disponibles al cierre heredada de GOLD. Baselines de medias no modelan día de semana. Recomendado un experimento global supervisado con evaluación temporal posterior reservada de antemano; no implementado ni autorizado aquí. Advertencia del kernel TCP local sin cifrado ya conocida, sin afectar ejecución; no se afirma servicio remoto seguro.

## F1-04B — GOLD point-in-time

Se leyeron instrucciones, roadmap/progreso, arquitectura, decisiones, almacenamiento, bootstrap y EDA; revisados contratos, migraciones, notebooks/módulos y estado real. La subdivisión A/B ya existía y coincidía con la solicitud; no se alteraron fases completadas. PostgreSQL confirmó bootstrap RELEASED, publicación COMPLETE, corte 2014-12-31 y último lote bootstrap-2013-2014.

### Implementación y archivos

- `pipelines/ingestion/retailops_gold/{query,reference,pipeline}.py`, `__init__.py`: SQL point-in-time, referencia independiente Decimal, conexión de trabajo y materialización mensual con locks, transacciones, hashes y comparación completa en reintentos.
- `materialize_gold.py`, `verify_gold.py`, `gold_tests/test_features.py`, `gold_tests/test_storage.py`: comandos reproducibles, comprobación real y pruebas sintéticas/permisos.
- Control V3 `V3__gold_snapshot_guard.sql`: función mínima con search_path fijo, valida y bloquea estado/lote/publicación. Data V3 `V3__point_in_time_gold.sql`: gold.features, gold.labels, gold.materializations; vistas training.gold_features/gold_labels y grants mínimos.
- `contracts/gold-features-v1.json`, `docs/FEATURE_ENGINEERING.md`, `GOLD_INITIAL_EXECUTION.json`, `GOLD_EXECUTION.json`, `GOLD_VERIFICATION.json`: contrato, semántica, ejemplo real, resultados y evidencia.
- Documentación AGENTS, ROADMAP, ARCHITECTURE, DECISIONS ADR020, DATA_STORAGE, README raíz/ingestion/infra y este registro actualizados según alcance; BOOTSTRAP conservado. No se modificaron notebooks, aplicaciones funcionales, dependencias uv, originales, manifiesto de lotes ni V1/V2.

### Resultados reales

| Elemento | Resultado |
| --- | --- |
| Features / etiquetas | **9 106 020 / 1 297 296** |
| Emisiones / horizontes | 730 días, 2013-01-01..2014-12-31; horizontes 1..7 |
| Objetivos | 2013-01-02..2015-01-07; 49 896 ejemplos posteriores al corte sin etiqueta futura |
| Última etiqueta / suma exacta | 2014-12-31 / 349893260.221161100000000000 |
| Lags semanales NULL / historia incompleta | 62 370 / 773 388 ejemplos |
| Navidad | Sin etiquetas en ambos 25 de diciembre; lag correspondiente NULL, nunca cero |
| Bloques mensuales | 24, cada uno transaccional y trazable por hash/fechas/recuentos |
| Primera materialización | 83,905 s; cliente RSS máximo 47 232 KiB |
| PostgreSQL | Muestras carga 186,8 MiB / comparación 423,5 MiB, límite 1 GiB/2 CPU; no se afirma pico |
| Almacenamiento tabla+índices | Features 2 073 886 720 bytes; etiquetas 133 038 080 bytes |
| Referencia independiente real | 63 filas preseleccionadas, todas las features coinciden con tolerancia NUMERIC 1e-12 |

### Pruebas y comandos

Mismo Python 3.12.16/uv.lock de ingestion, sin dependencias nuevas. Se inició solo PostgreSQL con volumen existente. Conexiones del pipeline con ingestor; verificación de superficies con trainer. Migradores solo en runner Flyway; sin superusuario para materializar o consultar datos de entrenamiento.

- `MAVEN_USER_HOME=/tmp/retailops-maven ./mvnw -B -Dmaven.repo.local=/tmp/retailops-m2 verify` desde apps/api: BUILD SUCCESS, cinco pruebas API.
- `uv run --project pipelines/ingestion --locked python scripts/data_infra.py migrate`: V3 control/data aplicadas por Flyway; validación de tres migraciones por historial, sin repair.
- `RETAILOPS_GOLD_INTEGRATION=1 uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/gold_tests -v`: **15 pruebas aprobadas**, cuatro unitarias, cinco SQL sintéticas y seis de almacenamiento/permisos. Primero pasaron 14 antes de la carga; la decimoquinta verifica detección de diferencias NULL/cero/filas adicionales con la comparación de reejecución.
- Suite previa `unittest discover -s pipelines/ingestion/tests -v`: **26 pruebas aprobadas**.
- Infra `unittest discover -s infra/docker/tests -v`: **10 pruebas aprobadas**.
- `materialize_gold.py --execute`: primera carga completa, sin conflictos; `verify_gold.py`: VERIFIED, límites/NULL/sumas/referencia comprobados.
- Segunda ejecución del runner Flyway: ambos historiales en V3, tres migraciones validadas por propietario, ninguna pendiente. V1/V2 conservan checksums; sin repair.
- Estado final SQL: corte 2014-12-31, último lote bootstrap-2013-2014, cero lotes mensuales RELEASED, 24 bloques GOLD completos. PostgreSQL detenido al cierre conservando volumen; MinIO no se inició.
- Reejecución completa: **24 bloques reutilizados, 302.014 s**, cliente RSS máximo 49484 KiB, SUCCEEDED. EXCEPT bidireccional sobre todas las features y etiquetas, sin UPDATE/DELETE ni duplicación. Evidencia GOLD_EXECUTION.json.

### Evidencia de ausencia de fuga y límites

Fixtures VALUES con extremos 1e20 después de issue_date y categorías exclusivamente futuras; comparación independiente por fecha/Decimal para todos los horizontes. Horizonte siete usa lag del día de emisión, no ventas de los seis días pronosticados; ventanas terminan en emisión. Se conservan ausencias, cero observado y poco historial. Etiquetas posteriores al corte rechazadas por CHECK. Trainer no puede leer gold/silver/control, escribir, crear TEMP o SET ROLE ingestor; el ingestor tampoco puede DDL/UPDATE/DELETE GOLD ni cambiar el corte. Las consultas no incluyen auxiliares ni estadísticas globales.

Semántica supone disponibilidad de ventas al cierre; no hay timestamps históricos de llegada y no se prueba disponibilidad intradiaria. Rol ingestor es pipeline confiable, no una defensa contra programas maliciosos con su secreto. Snapshot v1 fijo: otros cortes requerirán ampliación/versionado explícito. Sin predicciones/modelos/evaluación/MLflow/Airflow ni publicaciones nuevas.

Problemas resueltos: alias SQL month necesitó AS; una aserción de fixture de poco historial esperaba lag NULL incluso cuando un cero anterior sí era observable y se corrigió; escritura en vista no actualizable falla antes de comprobar ACL, así que se comprueba además el privilegio DELETE ausente. No se cambiaron permisos para ocultar errores.

## F1-04A — EDA y series temporales con Jupyter

### Preparación y alcance

Se leyeron AGENTS, PROGRESS, ROADMAP, ARCHITECTURE, DECISIONS, DATA_PROFILING, DATA_STORAGE y BOOTSTRAP y se revisaron las vistas/migraciones de acceso. El roadmap agrupaba GOLD bajo F1-04; se informó y se desglosó conforme a la nueva solicitud en F1-04A (EDA) y F1-04B (GOLD pendiente), actualizando la dependencia de F1-05.

Solo se inició PostgreSQL con su volumen existente. El cliente usó exclusivamente `retailops_trainer`, su archivo de contraseña 0600 y vistas training. No se utilizaron secretos administrativos, SOURCE/CSV/Parquet/Silver ni estadísticas del perfil global. La población visible confirmó 1 297 296 filas entre 2013-01-01 y 2014-12-31, coherente con el bootstrap publicado. La lectura directa de control.historical_state no está permitida al rol: se validan los límites de datos visibles y la ausencia posterior al corte, sin elevar permisos ni afirmar lectura del singleton.

### Archivos creados/modificados

- `notebooks/01_exploratory_data_analysis.ipynb` y `02_time_series_analysis.ipynb`: dos notebooks reproducibles independientes, cinco celdas de código cada uno más preguntas, método, interpretación y límites en español.
- `notebooks/pyproject.toml`, `.python-version`, `uv.lock`: Python 3.12.16, entorno virtual local, 105 paquetes resueltos por uv. Principales versiones efectivas: JupyterLab 4.6.6, pandas 3.1.1, NumPy 2.5.4, matplotlib 3.11.2, Psycopg 3.3.9, nbclient 0.11.0, nbformat 5.11.1 e ipykernel 7.4.0. Nada instalado globalmente.
- `notebooks/retailops_eda/data.py` y `queries.py`: conexión de solo lectura, consultas cerradas/parametrizadas y ventana/lote fijados. Máximo 5000 filas aceptadas (LIMIT SQL 5001 para detectar exceso), máximo tres tiendas/familias por consulta temporal, timeout SQL 30 s, lock 3 s e inactividad en transacción 30 s. Cierre/rollback de cada conexión garantizado.
- `analysis.py`: calendario con NaN sin imputación, normalización mensual por días observados, correlaciones por pares a retardos de calendario, estilo/figuras y resúmenes agregados locales. Sin tablas o features persistidas.
- `runtime.py`, `lab.py`: kernel privado del venv, configuración/caches locales ignoradas, JupyterLab en 127.0.0.1 con token automático, carpeta notebooks y terminales deshabilitadas. Hook de guardado elimina outputs/contadores, conservando código y markdown.
- `run_notebooks.py`: ejecución completa NBClient, kernel Python 3.12 verificado, timeout de celda 120 s y fallo ante errores. No persiste notebooks ejecutados ni salidas de celdas; guarda hashes/estado sin credenciales.
- `notebooks/tests/test_analysis.py`, `test_connection.py`: ocho casos unitarios y cuatro de integración real sin fixtures persistidas ni privilegios elevados.
- `notebooks/README.md`: instalación, configuración, inicio de PostgreSQL/JupyterLab, ejecución, pruebas, límites y parada conservadora.
- `docs/EDA_FINDINGS.md`, `EDA_EXECUTION.json` y diez PNG en `docs/eda_figures/`: hallazgos y gráficos agregados de datos autorizados, evidencia de ejecución sin microdatos/outputs.
- Actualizados `.gitignore`, AGENTS, README, ROADMAP, ARCHITECTURE, DECISIONS y este registro. No se modificaron aplicaciones, pipeline de bootstrap, migraciones, contratos de almacenamiento ni manifiesto de lotes.

### Resultados observados

| Pregunta | Resultado verificado |
| --- | --- |
| Distribución | Media 269,71, mediana 3, P75 136, P95 1421, P99 4339, máximo 46271; asimetría fuerte |
| Ceros / decimales | 568 354 ceros (43,81 %) y 172 071 no enteros (13,26 %); sin negativos |
| Cobertura | 728 fechas de 730, 1782 claves por día observado; Navidades 2013/2014 ausentes conservadas como NaN |
| Tiendas / familias | 54/33 identificadores observados en hechos; tienda 44 concentra 6,20 % y GROCERY I 35,44 % del volumen registrado |
| Evolución anual | Media diaria 385766,52 en 2013 y 575478,70 en 2014 (+49,18 % descriptivo), con ceros de 50,45 % a 37,17 % |
| Cambios mensuales | Media por día observado: mayor subida marzo 2014 +52,80 %, mayor caída abril 2014 -34,74 %; candidatos de revisión, no cambios de régimen probados |
| Calendario | Sábado/domingo con medias agregadas mayores; diciembre elevado en ambos años. Solo dos ciclos anuales, sin estacionalidad anual estable demostrada |
| Dependencia por retardo | Pearson por pares a lag 7: 0,822 serie original y 0,420 en primera diferencia de log1p; calendario conservado, sin bandas de significación |
| Auxiliares restringidos | stores/families/holidays/oil devuelven cero filas; sin incorporar metadatos o asociaciones externas para completarlos |

La suma exacta leída de SQL fue 349893260.221161100000000000. Las cantidades mezclan unidades/peso por familia: no son ingresos monetarios ni demanda no censurada. No se infieren causas de diferencias/picos, aperturas o promociones. Las hipótesis y baselines (último observado, naive semanal, medias/medianas retrospectivas) solo se proponen para evaluación temporal posterior; no se implementó ni entrenó un modelo.

Figuras: distribución, tiendas, familias, mensual total/media, extremos agregados, tendencia, perfil semanal, perfil mensual por año, ejemplos de segmentos y correlación por retardo. Se revisó visualmente la legibilidad de tendencia y autocorrelación; los ejes de fechas se limitan a 2013–2014.

### Comandos y resultados de verificación

Comandos uv con Python gestionado y cache local/temporal. No se usaron paquetes globales. El sandbox requirió autorización para descargas, socket Docker y conexiones/kernels locales; las consultas mantuvieron las mismas credenciales restringidas.

| Comando / verificación | Resultado |
| --- | --- |
| `uv lock --project notebooks` y `uv sync --project notebooks --locked` | Dependencias compatibles bloqueadas e instaladas en notebooks/.venv |
| `docker compose --env-file .env.example -f infra/docker/compose.yaml up -d --wait --wait-timeout 120 postgres` | PostgreSQL existente healthy, sin recrear volúmenes ni iniciar MinIO |
| `uv run --project notebooks --locked python notebooks/lab.py --version` | JupyterLab 4.6.6, launcher/configuración locales disponibles |
| `uv run --project notebooks --locked python -m unittest discover -s notebooks/tests -v` | Pruebas locales aprobadas; integración omitida por defecto |
| `RETAILOPS_EDA_INTEGRATION=1 ... python -m unittest discover -s notebooks/tests -v` | **12 pruebas aprobadas**, ocho unitarias/cuatro de conexión/consultas reales; 3,312 s |
| `uv run --project notebooks --locked python notebooks/run_notebooks.py` | Ambos notebooks completos, sin errores; diez celdas de código en total y diez figuras |
| Guardado real con FileContentsManager y hook configurado | Archivo temporal guardado con outputs=[] y contador null, conservando código; sin registro global |
| Verificación de entregables | Hashes de notebooks/módulos/lock coinciden con EDA_EXECUTION; diez PNG, enlaces y notebooks limpios; contraseña trainer ausente de documentos/notebooks/logs inspeccionados |
| Notebook 01, última ejecución | 5 celdas completas, 5.39 s |
| Notebook 02, última ejecución | 5 celdas completas, 5.354 s |

Los hashes de notebooks/módulos/lock y el estado SUCCEEDED se guardan en EDA_EXECUTION.json. Todos los .ipynb entregados mantienen execution_count=null y outputs=[], sin contraseñas; solo se exportan agregados/figuras. No se descargaron las 1,3 millones de filas: las consultas devuelven agregados, hasta 2184 filas para tres series temporales.

### Problemas y límites

1. DNS y sockets bloqueados en sandbox: se usó ejecución autorizada con las mismas restricciones SQL, sin cambiar permisos o roles del servidor.
2. `month` se usó inicialmente como alias SQL sin comillas y PostgreSQL lo rechazó; se corrigió a alias explícito entrecomillado. La consulta y ambos notebooks posteriores pasan.
3. El kernelspec genérico python3 usaba un ejecutable relativo y no ofrecía la garantía exigida de venv. Se creó un kernelspec local retailops-eda con ejecutable absoluto, sin instalar/registrar kernels globales.
4. Jupyter advierte transporte TCP local sin cifrado entre kernel/cliente. Se mantiene en la propia PC; no se afirma seguridad de servicio remoto/multiusuario. No se realizó QA en navegador de la interfaz JupyterLab; se comprobaron la versión y ejecución completa real de kernels/notebooks.
5. El rol no puede observar metadatos auxiliares/control: se documenta y no se elevan privilegios. No se usaron estadísticas o vocabularios de 2015–2017; el conteo booleano de presencia futura es una comprobación de seguridad, no un insumo analítico.
6. Dos años, unidades mixtas, ceros, posible cambio de composición y asociación temporal limitan conclusiones. Los cuantiles/medias de este EDA retrospectivo no se deben reutilizar como parámetros ajustados en folds anteriores. F1-04B deberá recalcular cada transformación usando únicamente pasado disponible al emitir.

Al cierre se detuvo únicamente PostgreSQL, preservando contenedor/volumen/bootstrap. No se inició MinIO ni un servidor JupyterLab persistente; los kernels de ejecución automática terminaron. Los comandos de inicio y de lectura se documentan en notebooks/README.md.

## Historial: F1-03 completada

## F1-03 — Bootstrap histórico y publicación recuperable

### Alcance y aceptación

Se leyeron instrucciones, progreso, roadmap, arquitectura/decisiones, perfilado/almacenamiento, contratos, manifiesto, migraciones, código y pruebas de F1-01/F1-02 antes de implementar. La instrucción posterior autoriza expresamente ejecutar el bootstrap real una vez, después de pruebas sintéticas. No se amplió a F1-04 ni ingestas mensuales.

`contracts/bootstrap-v1.json` acepta exactamente 2013-01-01 a 2014-12-31, 1 297 296 ventas, 54 tiendas y 33 familias. La integridad de las filas presentes y la cuadrícula de días observados deben ser completas. Las ausencias conocidas de 2013-12-25 y 2014-12-25 se aceptan explícitamente como calendario incompleto; el lote cumple su contrato sin inventar ceros. Se registraron dos huecos, no 3 564 ventas adicionales.

### Implementación y archivos

- `pipelines/ingestion/retailops_bootstrap/extract.py`: único módulo que abre SOURCE, verificación SHA-256 antes/después, selección temporal estricta, RAW con bytes originales, BRONZE Parquet decimal y trazabilidad. Buffer global acotado a 32 768 registros. Dimensiones derivadas y huecos no fabrican RAW.
- `storage.py`: clientes de trabajo Psycopg/MinIO, control de entorno RetailOps, hashes de bytes y versiones S3, conflicto sin sobrescritura. Loader/publicador no abren originales ni usan credenciales administrativas.
- `pipeline.py`: lock global de sesión, registro de inventario, COPY transaccional de Silver, autorización SQL previa a copiar, confirmación por objeto, verificación completa, corte final y estados de ejecución. Reintentos sin duplicar filas/versiones; fallos no se registran como éxito.
- `pipelines/ingestion/bootstrap_dataset.py`: CLI fija del bootstrap, proceso extractor separado y verificación idempotente; no ofrece ingestas mensuales. Workspace privado `.local/bootstrap/bootstrap-2013-2014` ignorado.
- `pyproject.toml`/`uv.lock`: PyArrow 24.0.0, Psycopg 3.3.9 y MinIO SDK 7.2.20, bibliotecas para el stack ya aprobado. Python 3.12.16 mediante uv; sin cambios en Python del sistema.
- Control **V2__recoverable_publication.sql**: publications STAGING/AUTHORIZED/COMPLETE, inventory publication_objects, versiones pendientes/completadas, unicidad de publicación incompatible pendiente, triggers de transiciones/inventario y rechazo de SUCCEEDED prematuro.
- Datos **V2__completed_publication_views.sql**: vistas requieren COMPLETE; source_row_number nullable solo para huecos sin fila fuente. **Las V1 no se editaron**; siguen validadas por Flyway.
- Pruebas: `tests/bootstrap_fixture.py`, `tests/test_bootstrap.py`, `integration/test_publication.py`; fixtures heredadas de `infra/docker/tests/access.sql` adaptadas al gate V2, siempre revertidas.
- `scripts/verify_bootstrap.py`: conteos/claves/totales, acceso real de trainer, inventario de bytes/versiones, corte y reinicio conservador, evidencia agregada persistente.
- Documentación: `docs/BOOTSTRAP.md`, `docs/BOOTSTRAP_EVIDENCE.json` y actualización de AGENTS, README, ROADMAP, ARCHITECTURE, DATA_STORAGE, DECISIONS (ADR-018), manuales de pipelines/infra y este registro. El manifiesto de planificación y los resultados de perfilado no se modificaron.

### Resultado real y disponibilidad auxiliar

| Entidad Silver | Filas cargadas | Filas visibles en training / política |
| --- | --- | --- |
| sales | **1 297 296** | 1 297 296; fechas 2013-01-01 a 2014-12-31, clave natural única |
| stores | 54 | 0: known_from/evidencia NULL, snapshot privado necesario para FK |
| families | 33 | 0 en dimensión: known_from/evidencia NULL; identificadores de hechos siguen presentes en ventas |
| holidays_events | 118 | 0: calendario del período sin fecha de anuncio demostrada, privado |
| oil_prices | 522 | 0: cotizaciones del período sin disponibilidad histórica demostrada, privado; nulos conservados |
| store_transactions | 34 046 | 34 046 transacciones históricas observadas; sin valores futuros |
| observation_gaps | 2 | Dos Navidades ausentes, no ventas cero; ordinal de fila NULL porque no existe registro fuente |

Se registraron cinco archivos fuente usados (train/stores/holidays/oil/transactions), además de verificar los hashes de los siete originales. test y submission no se cargaron ni registraron como observaciones. No se inventó ninguna fecha known_from ni evidencia de disponibilidad de auxiliares.

Totales de control exactos del bootstrap: ventas **349893260.2211611**, promociones **459114**, ventas cero **568354**, ventas no enteras **172071**. Se compararon entre extracción Decimal y PostgreSQL NUMERIC; no se usó float para transformar ventas ni calcular estos controles. No son features de entrenamiento. Conteos anuales: 648 648 ventas en 2013 y 648 648 en 2014; el JSON conserva los 24 recuentos mensuales.

Inventario real: **195 objetos en cuarentena**, cada uno con SHA-256, bytes y version_id registrados. Se copiaron **98 objetos autorizados a released**. Los otros 97 objetos de auxiliares restringidos permanecen solo en cuarentena. Familias/huecos derivados tienen solo BRONZE. El inventario completo está en `docs/BOOTSTRAP_EVIDENCE.json`; los archivos comerciales permanecen privados en workspace/MinIO, no en documentación ni servicios externos.

Estado SQL: batch `bootstrap-2013-2014` RELEASED, publicación COMPLETE, `released_through=2014-12-31`, `last_batch_id=bootstrap-2013-2014`. El corte avanzó únicamente tras verificación completa de copias. La ejecución inicial y una segunda ejecución de verificación idempotente constan como SUCCEEDED, con run_id distintos; la segunda validó las filas, no insertó otras 1 297 296 ventas. processed_rows de los intentos no debe sumarse como ventas únicas. No hay lotes mensuales liberados ni registrados por el pipeline.

Los 32 meses del manifiesto original siguen released=false, histórico del plan NULL y release_performed=false. Su SHA-256 continúa siendo `a7993e90b03297e779b2c5e6409281918a7fc356808d6005c89d9c6a6c208c71`, igual a F1-01. La realidad operativa reside en control, no se falsificó el plan.

### Verificaciones ejecutadas y evidencia

Todos los comandos Python se ejecutaron mediante `uv run --project pipelines/ingestion --locked python`, con UV_PYTHON_INSTALL_DIR dentro del repositorio y cache temporal. Se usó acceso autorizado para red/Docker/sockets locales.

| Verificación | Resultado real |
| --- | --- |
| Resolución/instalación uv y bloqueo de dependencias | Correctos, Python 3.12.16; sin instalación de herramientas globales |
| Maven Wrapper verify | BUILD SUCCESS, **cinco pruebas API aprobadas**, V2 empaquetadas |
| Aplicar migraciones V2 sobre V1 existentes | Control y data_meta en v2, sin borrar datos/volúmenes ni cambiar V1 |
| Suite `unittest discover -s pipelines/ingestion/tests -v` | **26 pruebas aprobadas**: 18 de perfilado y 8 de extracción/Parquet |
| Integración `RETAILOPS_INTEGRATION=1 ... unittest discover -s pipelines/ingestion/integration -v` | **Cinco pruebas reales aprobadas**, 15,256 s, sobre bases/objetos temporales separados |
| Suite `unittest discover -s infra/docker/tests -v` | **Diez pruebas aprobadas**, contrato/configuración conservados |
| Regresión F1-02 con V2, antes de cargar fuentes reales | Correcta: estado principal vacío, ACL SQL/S3 y hashes originales verificados |
| Validación previa al bootstrap real | Proyecto/contenedores RetailOps healthy, base principal sin ventas; hashes originales verificados por el extractor antes de seleccionar filas |
| Bootstrap real `bootstrap_dataset.py --execute` | SUCCEEDED, carga única y publicación completa; sin fallos del dataset real |
| Repetir el mismo comando | `idempotent=true`, mismos conteos/versiones, sin nuevas observaciones ni versiones S3 |
| `scripts/verify_bootstrap.py --restart` | Persistencia real verificada tras stop/up de PostgreSQL y MinIO; mismas claves/conteos/versiones/corte y permisos trainer; siete hashes originales correctos |

Pruebas sintéticas cubren: período correcto/exclusión de FUTURE, decimal 1.1250001, promociones originales, Navidad sin cero, hashes inválidos, inventario determinista, alteración de contenido local, fuente/workspace separados, cuadrícula/count inválidos y rechazos de no finitos/escala excesiva.

Integración real cubre: lock incompatible, PK natural en PostgreSQL, trainer sin Silver ni auxiliares restringidos, lectura S3 permitida/denegada sobre objetos existentes, fallos antes/después de autorización SQL, copia existente sin confirmación, publicación parcial, bloqueo del lote siguiente, no SUCCEEDED prematuro, recuperación sin recargar Silver ni versiones nuevas, conflicto S3 sin sobrescribir y reinicio con publicación completada conservada. En el escenario de recuperación se mantuvieron cuatro intentos FAILED y un reintento SUCCEEDED en la base sintética; no se ocultaron los fallos ni se contaminó el entorno real. Las bases/objetos de prueba fueron retirados sin borrar volúmenes.

Los servicios se detuvieron al cierre conservando volúmenes y el bootstrap; `data_infra.py up` los inicia de nuevo. No se elimina el workspace ni se modifican credenciales.

Ejecución real inicial: run_id `8286536d-4903-435f-a611-c7837bcaf379`, **76,963 s**, RSS máximo del worker **508 480 KiB (~496,6 MiB)**, extractor **153 304 KiB (~149,7 MiB)**. Reejecución de verificación: run_id `c72cf66e-5cea-4f04-aff8-a40d62d5b873`, **1,361 s**, worker 96 200 KiB. Muestra posterior al procesamiento: PostgreSQL ~151,8 MiB y MinIO ~280,9 MiB, con límites 1/2 GiB; no se presenta esa muestra como máximo de los servicios. Las métricas son locales y no constituyen un benchmark universal.

### Problemas, correcciones y riesgos pendientes

- El sandbox bloqueó PyPI/Docker/sockets; las operaciones necesarias se repitieron con autorización. uv usó copia por diferencia entre sistemas de archivos al no poder hacer hardlinks; instalación correcta.
- Una prueba inicial pasó las verificaciones de reinicio pero su limpiador intentó usar una conexión admin invalidada por ese reinicio. Se corrigió para reconectar; se retiró exclusivamente la DB sintética residual identificada y se repitió la suite completa correctamente. No hubo fallo de carga del dataset real ni pérdida de datos.
- La publicación no es una transacción distribuida: las copias autorizadas aparecen gradualmente en S3. Las vistas requieren COMPLETE y el corte no avanza durante publicación parcial. El inventario/roles/versiones permiten recuperación, no alta disponibilidad de un único equipo.
- Versionado S3 no equivale a WORM; cambios de bytes o de versión se rechazan, no se sobrescriben silenciosamente. Un administrador/root todavía puede alterar almacenamiento: no se protege contra la propia autoridad local.
- Tiendas/familias/feriados/petróleo no se exponen como auxiliares sin evidencia; esto limita futuros features y exige una decisión explícita antes de ampliarlos. No hay modelos, features GOLD, Airflow ni ingestas mensuales.
- MinIO comunitario sigue archivado/sin mantenimiento upstream; permanecen los límites de TLS local, secretos de archivos, rotación y backups/restauración pendientes documentados en F1-02.
- El workspace privado conserva artefactos de recuperación; no borrarlo ni editar contratos/inventarios para resolver conflictos. Nunca borrar volúmenes o tocar migraciones aplicadas como reparación automática.

## Historial: F1-02 completada

## F1-02 — Diseño e infraestructura de datos

Se leyeron las instrucciones, los documentos de arquitectura/decisiones/progreso/roadmap, el informe y los JSON de perfilado/manifiesto y el código existente. Se informó antes de modificar el roadmap de que la propuesta amplía el alcance anterior de Compose básico. La ampliación fue solicitada explícitamente; F1-03 permanece fuera de alcance.

### Implementación

- Compose modular: `infra/docker/compose.yaml`, `compose.postgres.yaml`, `compose.minio.yaml`. PostgreSQL **18.7-alpine fijado por digest**; MinIO compilado desde fuente oficial fijada. Volúmenes nombrados, health checks, puertos configurables publicados solo en 127.0.0.1, DNS `postgres`/`minio` y límites efectivos 1 GiB/2 CPU y 2 GiB/2 CPU respectivamente.
- `infra/docker/minio/Dockerfile` y `.dockerignore`: commits oficiales MinIO `7aac2a2c5b7c882e68c1ce017d8256be2feea27f` y mc `77f82e18b5401a65958f1619df6ebb994634bd88`; checksums de archivos y digests de Go/Alpine. Go solo en builder Docker, sin instalación en el SO, clonación Git o publicación de imagen. Licencias originales conservadas en la imagen.
- `infra/docker/postgres/entrypoint.sh` e `init.sh`: lectura segura de secretos antes de cambiar usuario, seis roles sin superusuario/creación de roles o bases y cinco esquemas con propietarios separados. No crea tablas de negocio fuera de Flyway.
- `infra/docker/minio/admin.sh` y políticas JSON: buckets privados/versionados quarantine, released, artifacts y verification. Ingestor no publica; trainer solo lee released y tiene denegación explícita sobre cuarentena/artefactos.
- `scripts/data_infra.py`: generación de secretos locales aleatorios 0600, validación, build/up/migrate/configure-minio/verify/persistence/status/stop/down. No muestra secretos ni los reemplaza; down no usa -v. Usa `.env` si existe, si no `.env.example`.
- API: `pom.xml` incorpora starter Flyway, soporte PostgreSQL y driver siguiendo el BOM; `StorageMigrationConfiguration.java`, `application-storage.properties` y propiedades base separan mantenimiento de proceso web. Mantenimiento optativo `storage` no inicia servidor HTTP. El proceso web normal conserva salud sin requerir base de datos.
- Migración **control V1** en `apps/api/src/main/resources/db/control`: source_files, batches, batch_sources, historical_state, objects, ingestion_runs. Historial `control.flyway_schema_history`, propietario retailops_control_migrator.
- Migración **datos V1** en `.../db/data`: stores, families, sales, holidays_events, oil_prices, store_transactions, observation_gaps; ocho vistas training (incluye holiday_features), esquemas data_meta/gold y guard de inserción en lote no liberado. Historial `data_meta.flyway_schema_history`, propietario retailops_data_migrator. Gold queda vacío.
- `contracts/data-storage-v1.json`, `scripts/storage_contracts.py`: contratos de Source/Raw/Bronze/Silver y verificación contra perfil y plan. `infra/docker/tests/test_contracts.py`, `test_configuration.py`, `access.sql`: pruebas de casos límite e integración.
- Documentación nueva `docs/DATA_STORAGE.md`, `infra/docker/README.md`; actualizados AGENTS, README, ARCHITECTURE, DECISIONS (ADR-017), ROADMAP, PROGRESS y `.env.example`.

Los secretos reales están únicamente en `.local/secrets`, ignorados, sin valores en código, archivos públicos o logs inspeccionados. Los CSV no se montan en ningún servicio. No se modificaron perfilador, manifiesto ni resultados F1-01.

### Modelo y control de acceso verificados

Ventas mantiene PK `(date, store_nbr, family)`, NUMERIC sin truncar y promociones INTEGER. NULL y huecos explícitos no se convierten en cero. Feriados conservan ámbitos y transferencias, con agregación previa a join para no multiplicar ventas. known_from y evidencia son necesarios para exponer auxiliares a entrenamiento; promociones futuras no se exponen en la vista inicial de ventas.

El entrenador solo dispone de SELECT sobre vistas de servidor con security_barrier, lote RELEASED y corte persistido no nulo; no puede acceder a Silver, cambiar el corte, crear temporales o asumir el rol migrador. Una fecha vieja en lote STAGED queda oculta; una fecha futura en lote RELEASED también. El ingestor no puede liberar lotes ni insertar más observaciones en un lote liberado; el guard bloquea la fila de lote para coordinarse con su actualización. Esto no es un filtro voluntario del código cliente.

En MinIO se probaron lecturas permitidas en released, lectura denegada de un objeto existente en cuarentena y escrituras denegadas para trainer e ingestor sobre released. Se verificó el mensaje de autorización, no solo un error genérico. Los marcadores de permisos son fixtures técnicas efímeras bajo `_checks/`, eliminadas con todas sus versiones; no representan particiones ni una ingesta exitosa.

### Comandos y resultados reales

Los comandos Python se ejecutaron con `uv run --project pipelines/ingestion --locked python`, Python 3.12.16 y las rutas locales UV_PYTHON_INSTALL_DIR/UV_CACHE_DIR. Docker requirió acceso autorizado fuera del sandbox. No se modificó Python del sistema ni se instalaron servicios en el SO.

| Comando / prueba | Resultado verificado |
| --- | --- |
| `docker version`, `docker compose version` | Engine 29.9.3 y Compose 5.7.0 accesibles con autorización |
| Pull PostgreSQL/Go/Alpine y `docker build ... infra/docker/minio` | Imagen PostgreSQL y compilación de MinIO/mc correctas; archivos/digests fijados |
| `scripts/data_infra.py init-secrets` y `config` | Secretos locales sin sobrescritura; configuración/puertos/permisos validados |
| `scripts/data_infra.py up` | Ambos servicios healthy, puertos efectivos 127.0.0.1:5432 y :9000; sin consola publicada |
| `./mvnw -B -Dmaven.repo.local=/tmp/retailops-m2 verify` (MAVEN_USER_HOME temporal) | **BUILD SUCCESS; cinco pruebas API aprobadas**, JAR ejecutable generado |
| `scripts/data_infra.py migrate` | Ambas V1 aplicadas correctamente, propietarios e historiales independientes |
| Repetir `migrate` con el JAR final | Validación correcta; control/data_meta up to date, sin repetir migraciones |
| `scripts/data_infra.py configure-minio` | Cuatro buckets privados/versionados, usuarios/políticas separados, sin objetos de datos |
| `scripts/storage_contracts.py` | Contrato consistente con siete fuentes, hashes, nulabilidad y plan sin liberación |
| `python -m unittest discover -s infra/docker/tests -v` | **Diez pruebas unitarias aprobadas**, 0,015 s |
| `scripts/data_infra.py verify` | Contratos; login real trainer; denegación de Silver/corte/escalada/TEMP; SQL con ROLLBACK; permisos MinIO; hashes de los siete originales correctos |
| `scripts/data_infra.py persistence` | stop/up de ambos servicios; OID/comentario de esquema y ETag/versionID/tamaño del marcador MinIO conservados; verificaciones repetidas |
| Proyecto separado retailops-data-init-check, puerto 15432, volumen nuevo | Arranque automático corregido healthy; seis roles creados; contenedor/red retirados con down sin -v |
| Escaneo de logs de herramientas | Sin valores de los secretos locales encontrados |

Pruebas SQL: granularidad/PK única, decimales, ventas/promociones negativas, conservación de NULL, auxiliares sin disponibilidad o con known_from posterior al corte, feriado transferido no activo en fecha original, ámbitos y agregación sin fan-out, fechas futuras/lotes no liberados ocultos, variable de fecha del cliente sin efecto y escritor sin permiso de liberar o modificar lotes liberados. Todas las fixtures se revierten. No se contaron estas comprobaciones como pruebas JUnit individuales.

### Estado de datos y persistencia

Cero filas en ventas, tiendas, familias, feriados, petróleo, transacciones, huecos, fuentes, lotes, objetos registrados y ejecuciones. historical_state contiene solo el singleton técnico con released_through/last_batch_id NULL. Buckets quarantine/released/artifacts vacíos incluso al listar versiones. Los 32 lotes del manifiesto local siguen released=false; bootstrap no ejecutado.

Las únicas marcas persistentes de prueba son un comentario administrativo en el esquema y un objeto en el bucket verification. Los volúmenes principales son retailops-data_postgres_data y retailops-data_minio_data. El volumen adicional retailops-data-init-check_postgres_data se conserva tras la prueba de arranque nuevo: no se borraron volúmenes automáticamente. Debe retirarse deliberadamente solo si se decide que ya no se necesita.

### Problemas encontrados, resolución y límites

1. El sandbox bloqueó Docker; se usó acceso autorizado al daemon, sin modificar permisos del socket.
2. Los tags históricos oficiales MinIO/mc en Quay devolvieron 401. El repositorio oficial de MinIO está archivado y distribuido solo como fuente. Se compilaron revisiones oficiales fijadas dentro de Docker. **No hay mantenimiento upstream de MinIO**; usar solo como entorno local educativo, no afirmar seguridad de producción ni sustituir la tecnología sin aprobación.
3. Primer arranque PostgreSQL falló al leer archivos 0600 tras cambiar usuario interno. El wrapper lee antes de ese cambio, sin hacer los archivos públicos. Se confirmó ausencia de roles/datos en el volumen parcial, se completó provisionamiento sin borrar el volumen y se comprobó aparte un arranque automático limpio.
4. `internal:true` impedía publicar puertos en este Docker. Se utilizó red bridge con publicación exclusiva en loopback. No se expone a la LAN.
5. El cliente mc humaniza algunas denegaciones como «Insufficient permissions». La comprobación reconoce ese mensaje y Access Denied, mantiene un caso permitido y prueba una clave existente para no confundir ausencia con aislamiento.
6. No existe todavía promoción transaccional S3/PostgreSQL, ETL ni ingesta. El protocolo futuro deberá autorizar SQL antes de copiar a released, gestionar publicación parcial/reintentos y no marcar SUCCEEDED hasta verificar el inventario completo. Versionado S3 no es WORM.
7. La protección aplica a credenciales de trabajo, no al administrador local/Docker/root de los servicios. El futuro entrenamiento deberá ejecutarse sin montar SOURCE o secretos privilegiados. No se ha implementado aún su runtime.
8. Compose secrets local son archivos, sin cifrado administrado; no hay rotación automática, TLS de red compartida ni restauración/backups ensayados. Un único equipo no ofrece alta disponibilidad. Al cierre se detuvieron los dos servicios conservando contenedores y volúmenes; pueden iniciarse con el comando up documentado.

## Historial: F1-01 completada

## F1-01 — Perfilado y calidad del dataset

Se leyeron AGENTS, PROGRESS, ROADMAP, ARCHITECTURE y DECISIONS y se contrastó la implementación. F1-01 era la primera tarea pendiente. Los siete CSV siguen presentes y coinciden con los hashes de Fase 0.

### Implementación y archivos

- `pipelines/ingestion/pyproject.toml`, `.python-version`, `uv.lock`: proyecto independiente Python 3.12.16/uv, sin dependencias externas.
- `pipelines/ingestion/retailops_profiling/core.py`: lectura por bloques, inferencia sobre todos los valores, estadísticas incrementales, duplicados exactos, cardinalidades, integridad, cobertura y manifiesto de planificación.
- `pipelines/ingestion/retailops_profiling/report.py`: generador de informe español a partir de resultados; tablas por columna y fuente, anomalías y recomendaciones Bronze/Silver/Gold.
- `pipelines/ingestion/retailops_profiling/__main__.py`, `__init__.py`, `profile_dataset.py`: CLI, validación de salida, checksums antes/después y globales, y limpieza de trabajo temporal.
- `pipelines/ingestion/tests/test_profiling.py`: 18 pruebas automatizadas con archivos sintéticos temporales.
- `pipelines/ingestion/README.md`: comandos reproducibles, criterios de completitud, consumo y limitaciones.
- `docs/DATA_PROFILING.md`, `DATA_PROFILING.json`, `DATA_BATCH_MANIFEST.json`: informe, resultados completos y plan de lotes, sin datos liberados.
- Actualizados `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (ADR-016), `docs/ROADMAP.md` y este registro. `docs/DATA_INVENTORY.json` conserva la referencia original sin cambios.

SQLite de la biblioteca estándar se utiliza únicamente como archivo temporal de análisis, no como almacenamiento de la aplicación. Se elimina al terminar. No hay servidor ni nueva dependencia; PostgreSQL sigue siendo la tecnología prevista. El archivo temporal puede contener representaciones auxiliares de la fuente para consultas exactas, pero no produce capas de datos ni particiones.

### Hallazgos verificados

| Fuente | Filas | Columnas | Hallazgos principales |
| --- | --- | --- | --- |
| train.csv | 3 000 888 | 6 | Sin nulos, claves repetidas, IDs repetidos ni filas malformadas |
| stores.csv | 54 | 5 | 54 tiendas, 22 ciudades, 16 estados; claves únicas |
| holidays_events.csv | 350 | 6 | 31 fechas con eventos múltiples, sin duplicados de fila; 12 feriados transferidos y 12 eventos Transfer |
| oil.csv | 1 218 | 2 | 43 cotizaciones nulas; 521 días de train sin observación disponible (481 sin fila y 40 con nulo) |
| transactions.csv | 83 488 | 3 | Clave tienda/día única; 118 tienda/día con ventas positivas sin transacción |
| test.csv | 28 512 | 5 | 2017-08-16 a 2017-08-31; mismas tiendas/familias, sin solapamiento de IDs/claves con train |
| sample_submission.csv | 28 512 | 2 | IDs coinciden exactamente con test; sales son ceros de plantilla, no etiquetas reales |

- Train: **2013-01-01 a 2017-08-15**, 1 684 fechas, 54 × 33 = **1 782 series**. Cada fecha observada tiene exactamente la cuadrícula esperada. Cada serie comparte rango y cobertura. Ausencias de calendario: 2013-12-25, 2014-12-25, 2015-12-25 y 2016-12-25.
- Ventas: 939 130 ceros (31,30 %), 462 113 valores no enteros, 0 negativos; mediana 11, P99 5 507 y máximo 124 717. Decimales, ceros y colas altas no se marcan como errores automáticamente.
- Promociones: 0 negativos/no enteros, máximo 741; primera promoción positiva el 2014-04-01 y todo 2013 en cero. Investigar disponibilidad/registro, sin concluir ausencia comercial real antes de esa fecha.
- Transacciones: 7 448 tienda/día de train sin fila; 118 tienen ventas positivas. No imputar cero ni imponer FK obligatoria desde ventas. Sin tiendas huérfanas en train, test o transactions, ni familias desconocidas en test.
- Bootstrap 2013–2014: **1 297 296 filas**, dos fechas de Navidad ausentes; INCOMPLETE respecto a calendario, sin inconsistencias en cuadrículas de días observados.
- Incrementales: **32 lotes**, enero de 2015 a agosto de 2017; 29 completos y 3 incompletos respecto al calendario (diciembre de 2015, diciembre de 2016, agosto de 2017). Agosto contiene 26 730 filas y termina el día 15.
- Manifiesto: `purpose=PLAN_ONLY`, `historical_cutoff=null`, `release_performed=false`; bootstrap y todos los meses `released=false`. Distingue calendario completo de cuadrícula observada completa. No son estados administrativos de ingesta ni autorizaciones para consumir datos futuros.

### Comandos y verificaciones reales

Desde la raíz, se usaron `UV_CACHE_DIR=/tmp/retailops-uv-cache` y `UV_PYTHON_INSTALL_DIR=<raíz>/.local/python` para mantener runtime/cache en las áreas previstas.

| Comando / comprobación | Resultado |
| --- | --- |
| `uv lock --project pipelines/ingestion --offline` | Lock generado sin red; proyecto sin dependencias externas |
| `uv run --project pipelines/ingestion --locked python --version` | Python 3.12.16 |
| `uv lock --project pipelines/ingestion --check --offline` | Lock consistente |
| `uv run --project pipelines/ingestion --locked python pipelines/ingestion/profile_dataset.py --source data/source/favorita --output docs` | Siete archivos analizados; código 0; 30,10 s; RSS máximo Linux 72 776 KiB (~71,1 MiB) |
| Mismo comando con `--batch-size 7777 --output /tmp/retailops-profiling-repeat` | Código 0; 30,23 s; RSS máximo 70 908 KiB |
| Comparación binaria de las tres salidas entre bloques 10 000 y 7 777 | Markdown, JSON y manifiesto idénticos byte por byte |
| `uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/tests -v` | **18 pruebas, todas aprobadas**, 0,017 s |
| Lectura independiente con `csv.DictReader` y contadores acotados | Filas, meses, 1 782 claves por día, tiendas/familias, ceros/negativos/fracciones/promociones y suma bootstrap + incrementales coinciden |
| Comprobación independiente de claves | Orden textual estricto sin repeticiones; los 54 identificadores de tienda son representaciones enteras canónicas, sin colisiones por normalización |
| CLI con `--output data/source/favorita/reports` | Rechazo esperado, código 2, antes de escribir; no se creó el directorio |
| SHA-256 de los siete originales frente a `DATA_INVENTORY.json` y nuevo perfil | Todos coinciden; archivos originales intactos |

Las pruebas cubren tipos/fechas inválidos, NaN/infinito, nulos, filas malformadas, cabeceras ambiguas/vacías, duplicados entre bloques y con distinto ID, cuantiles interpolados, negativos sin reescritura, mes bisiesto, Navidad ausente, mes final parcial, cuadrícula vs calendario, fuentes faltantes, esquemas auxiliares incompatibles, relaciones huérfanas, bootstrap/meses sin liberación, claves inválidas y protección de SOURCE incluso con symlinks/cambios de hash.

No se repitieron builds ni suites de las aplicaciones: no se modificó código ni dependencias de web/API/ML. Sus resultados previos se conservan en el historial.

### Interpretación, riesgos y límites

- Los 25 de diciembre ausentes y el mes truncado son observaciones de cobertura, no corrupción demostrada. El contrato de aceptación de lotes se decidirá al implementar su fase; no se rellenan ventas automáticamente.
- Petróleo: diferenciar nulos de días sin cotización; evitar interpolación/backfill desde el futuro. Transacciones futuras desconocidas no son features disponibles. Los feriados requieren ámbito, semántica de transferencia y agregación antes del join para evitar multiplicar ventas.
- El CSV de feriados no incluye fecha de anuncio; stores es una fotografía sin vigencias; las promociones no certifican su disponibilidad al emitir. Documentar hipótesis antes de utilizarlos.
- Conservar ventas decimales, conteo de promociones y ausencia vs cero. Proponer NUMERIC en Silver y no UNIQUE(date) para feriados. Separar bootstrap, test y submission.
- Este perfil usa todo el histórico como diagnóstico autorizado. **No reutilizar** sus medias, cuantiles, vocabularios ni otras estadísticas como parámetros ajustados del modelo al corte 2014-12-31. Validación temporal y lags/ventanas seguros también dentro del horizonte de siete días.
- El RSS medido corresponde al proceso; excluye la caché de archivos del SO y no prueba un máximo universal para cualquier fuente. SQLite y sus ordenaciones requieren espacio temporal; TMPDIR puede ser tmpfs. Los números descriptivos usan float64; preservar las fuentes al diseñar precisión NUMERIC.

### Problemas encontrados y resolución

- No hay bloqueos ni descargas externas necesarias. `/usr/bin/time` no estaba disponible; se midieron tiempo y RSS con la biblioteca estándar, sin instalar herramientas.
- El primer contraste independiente asumió orden numérico de tiendas y falló esa aserción. La fuente está ordenada por el identificador textual (1, 10, …, 19, 2, …), no por entero. Se corrigió el verificador y confirmó unicidad/orden textual. Es una propiedad de orden, no un error del dataset. El perfilador agrupa mediante índices y no presupone orden de entrada.

## Próxima tarea exacta

**F2 terminada en el alcance autorizado; detenerse y esperar revisión.** Sin nuevos commits/push ni otra fase automática. Publicar enero o ejecutar entrenamiento candidato real requiere una acción/autorización posterior explícita; no se hizo en este bloque. El MVP comercial y autenticación siguen pendientes.

## Historial: Fase 0 completada

Los siguientes resultados corresponden al cierre anterior de Foundation; las instrucciones actuales de continuidad son las indicadas arriba.

## Trabajo realizado en Fase 0


- Inspeccionado el directorio existente, preservado `.gitignore` y ampliado sus exclusiones. No se ha inicializado Git, creado repositorios remotos ni publicado archivos. Los directorios de metadatos protegidos del entorno no se modificaron.
- Confirmados los siete CSV esperados en `data/source/favorita/`. Inventario de nombres, bytes, columnas y SHA-256 en `DATA_INVENTORY.json`. No se descargaron ni modificaron los originales. Sin análisis estadístico ni ETL.
- Documentación persistente en español: AGENTS, README, ARCHITECTURE, DECISIONS, ROADMAP y este registro.
- TailAdmin React gratuito 2.5.0 integrado en `apps/web` desde commit oficial `df1e9f37e56e0bf83030e8063f5353da2e0ecf18`, mediante archivo sin Git. Licencia MIT original conservada; instrucciones y README propios en español. Se conservan componentes, gráficos, tablas, formularios, assets y ejemplos de la plantilla. La navegación activa muestra solo Foundation, sin ventas, perfiles o autenticación simulados.
- Configurados idioma español, portada de estado inicial, layout/sidebar de TailAdmin, tema y etiquetas accesibles propias en español. `package-lock.json`, `engines` y `packageManager` para el entorno Node 26/npm 12.
- Spring Boot 4.1.2, Java 21, Maven Wrapper 3.3.4/Maven 3.10.0, Spring MVC y Actuator en `apps/api`. Salud pública limitada, liveness/readiness y validación de host/puerto. JAR ejecutable generado. Spring Security y Flyway todavía no integrados, conforme al alcance sin autenticación ni base de datos.
- FastAPI 0.162.7 y Uvicorn 0.54.0 en `apps/ml-service`, Python 3.12.16 gestionado por uv dentro de `.local/python`, `.venv`, pyproject y uv.lock. `/health` indica salud del proceso, sin inferencia disponible. Configuración de enlace validada.
- `.env.example` sin secretos; configuración local de direcciones/puertos y proxy Vite `/api` configurable hacia Spring. Valores locales por defecto; ningún secreto obligatorio en esta fase.
- Script reproducible `scripts/smoke_foundation.py`: procesos temporales en loopback, HTTP de servicios/probes/proxy, cierre de procesos propios y logs locales ignorados.

## Archivos creados o modificados

| Grupo | Archivos |
| --- | --- |
| Raíz | `AGENTS.md`, `README.md`, `.env.example`; `.gitignore` existente ampliado |
| Documentación | `docs/ARCHITECTURE.md`, `DECISIONS.md`, `ROADMAP.md`, `PROGRESS.md`, `DATA_INVENTORY.json` |
| Frontend importado | Árbol oficial `apps/web/`, incluido `LICENSE.md`, componentes, assets, configuración y lock |
| Frontend adaptado | AGENTS/README, package/lock, index.html, vite.config.ts, App.tsx, página foundation, header/sidebar/datos de navegación, theme-toggler, configuración i18n/routing y cuatro catálogos de mensajes |
| API | `pom.xml`, `mvnw`, `mvnw.cmd`, `.mvn/wrapper/maven-wrapper.properties`, `.gitignore`, `.gitattributes`, `HELP.md`, aplicación Java, ApiBindingConfiguration, application.properties y tres clases de pruebas |
| ML | `.python-version`, `pyproject.toml`, `uv.lock`, `app/__init__.py`, `app/main.py`, `app/__main__.py`, `tests/test_health.py` |
| Verificación | `scripts/smoke_foundation.py` |

Los directorios generados `node_modules`, `dist`, `target`, `.venv`, `.local` y caches no son entregables versionables. No se crearon carpetas vacías para infraestructura/pipelines todavía.

## Comandos y resultados

Las verificaciones se ejecutaron en las carpetas indicadas. Las rutas de cache temporales evitan escribir caches de herramientas fuera del área autorizada.

| Comando / operación | Resultado real |
| --- | --- |
| `pwd`, `ls -la`, `rg --files`, búsqueda de AGENTS y `ls -lh data/source/favorita` | Base mínima existente y siete archivos confirmados |
| `java -version`, `mvn -version`, `node -v`, `npm -v`, `uv --version` | Java 21.0.13; Maven 3.10.0; Node 26.13.1; npm 12.2.2; uv 0.13.8 |
| `curl -fL` a API GitHub, archivo codeload del commit, Spring Initializr y metadatos de Maven Central; `tar -xzf`, `unzip -q` | Fuente oficial y proyecto base obtenidos; sin clonación o inicialización de Git |
| `npm ci --cache /tmp/retailops-npm-cache --no-audit --no-fund` en web | 348 paquetes instalados desde lock; sin errores de engines/peer dependencies |
| `npm run build` en web | TypeScript y Vite 8.3.5 compilan correctamente |
| `npm run lint` en web | Código de salida 0, sin errores; 25 advertencias heredadas de la plantilla |
| `WEB_PORT=0 npm run dev` en web | Código 1 esperado: rechaza puerto fuera de rango antes del arranque |
| `MAVEN_USER_HOME=/tmp/retailops-maven ./mvnw -B -Dmaven.repo.local=/tmp/retailops-m2 verify` en API | BUILD SUCCESS; 5 pruebas, 0 fallos/errores; JAR `target/api-0.0.1-SNAPSHOT.jar` |
| `UV_CACHE_DIR=/tmp/retailops-uv-cache UV_PYTHON_INSTALL_DIR=<raíz>/.local/python uv python install 3.12` | Python 3.12.16 instalado localmente; Python del sistema intacto |
| Mismas variables de uv + `uv lock` y `uv sync --locked` en ML | Lock de 24 entradas, 22 paquetes instalados en entorno virtual |
| Mismas variables de uv + `uv run --locked pytest -q` en ML | 7 pruebas aprobadas; 1 advertencia de deprecación heredada de Starlette TestClient/httpx |
| Smoke HTTP de tres procesos temporales | HTTP 200: web, API health/liveness/readiness, ML health y proxy `/api/actuator/health`; procesos detenidos al terminar |
| Inventario y verificación SHA-256 con biblioteca estándar | Siete checksums y tamaños coinciden al cierre; sin escrituras en los originales |
| `python scripts/smoke_foundation.py` | Código 0; seis comprobaciones HTTP correctas y procesos detenidos; logs en `.local/verification/` |
| Comprobación documental y sintaxis | Documentos obligatorios, enlaces locales, locks, licencia y sintaxis del script correctos |

Pruebas API: arranque de contexto; salud sin detalles sensibles; probes; rechazo de host vacío/puertos inválidos; aceptación de loopback y puerto efímero de pruebas. Pruebas ML: contrato HTTP de salud y seis casos de configuración válida/inválida.

## Problemas encontrados y resolución

1. DNS del sandbox bloqueó GitHub, Spring Initializr, npm, PyPI y Maven. Se registró el fallo y se reintentó con acceso de red autorizado; descargas completadas. No se intentó instalar infraestructura.
2. Spring Initializr generó `4.1.2.RELEASE`, inexistente en Maven Central. Se consultó el registro oficial y se fijó `4.1.2`; compilación y pruebas posteriores correctas.
3. Primera aserción HTTP esperaba únicamente status; Actuator añade grupos de probes. Se corrigió para verificar estado y ausencia de detalles sensibles. La ejecución final pasa.
4. Primer pytest no encontraba `app` desde tests. Se añadió `pythonpath = ["."]` a la configuración de pytest. La ejecución final pasa.
5. El sandbox bloqueó/inmovilizó pruebas con sockets/instrumentación JVM y TestClient. Se interrumpieron esos procesos y las verificaciones finales se ejecutaron fuera del sandbox con autorización.
6. uv intentó crear un enlace de ejecutable de usuario ya existente; no se forzó ni reemplazó. El runtime quedó en `.local/python`; README indica `UV_PYTHON_BIN_DIR` dentro del proyecto para futuras instalaciones. También apareció un aviso de hardlinks entre sistemas de archivos: uv usó copia y terminó correctamente.

## Limitaciones y bloqueos

- Al cerrar Foundation no había autorización para Fase 1. La solicitud posterior autorizó únicamente F1-01, registrada arriba.
- No se realizó prueba visual en navegador: sin herramienta de preview visual disponible. Build y smoke HTTP no garantizan por sí solos la apariencia o interacción responsive.
- Lint conserva advertencias originales sobre Fast Refresh, efectos/estado, pureza y tipado en componentes/demos de TailAdmin. No impiden build/lint ni se ocultaron mediante desactivación global de reglas.
- Starlette advierte que TestClient/httpx está deprecado; las siete pruebas pasan. Revisar el transporte de pruebas al actualizar dependencias, sin añadir otra librería en esta fase.
- La plantilla conserva la fuente Outfit desde Google Fonts con fallback sans-serif. Sin red se usa la alternativa del sistema; no se ha verificado la apariencia offline.
- Maven usa parent/BOM y Wrapper fijados, sin lock equivalente al de npm/uv. Cachés y artefactos iniciales necesitan red.
- No hay autenticación, persistencia, ETL, inferencia, predicciones, modelos, Compose, Airflow, MLflow, K3s ni observabilidad desplegada. La propuesta de sesión de Fase 2 todavía requiere revisión.

## Cierre

Todos los criterios de F0-01 a F0-07 se verificaron; ROADMAP actualizado. No se inicia una fase nueva. Los comandos de compilación y las suites pueden repetirse con las instrucciones de README.


Verificación Chromium/Playwright temporal: cinco pantallas con respuestas HTTP reales 200, gráficos, 30 filas históricas, consentimiento obligatorio, siete predicciones y viewport móvil 390 px sin desbordamiento ni errores JavaScript. Evidencia y capturas privadas en `.local/application/{browser.json,dashboard.png,sales.png,forecast.png,mobile.png}`. La primera espera del comprobador se corrigió para opciones HTML nativas ocultas; no era un fallo de la aplicación.

Cierre operativo F3 verificado con `docker compose ps -a`: los nueve servicios (PostgreSQL, MinIO, MLflow, Airflow API/scheduler/dag processor, FastAPI, Spring y web) quedaron exited. Ocho con código 0; Java con 143 (terminación SIGTERM de Compose). Se conservaron contenedores, volúmenes, datos y artefactos; evidencia privada `services-stopped.json`. Cambios F3 sin commit.
