> F5.2 publicada y CI GitHub Actions exitosa según confirmación posterior del usuario. F5.3 incorpora alertas locales y estado de cierre explícito: seguir [SRE.md](SRE.md) para reactivar/cerrar el laboratorio con Alertmanager, sin F5.4. El resto registra la evidencia histórica F5.2.

# F5.2 — Logs locales con Loki y Alloy

Fecha de validación: 2026-11-17, America/Guayaquil. Implementación y prueba real en K3s; sin F5.3, alertas, backups, entrenamiento o promoción. F5.1 y su CI remota fueron confirmadas como publicadas/correctas por el usuario al autorizar esta fase. La nueva CI F5.2 solo se ha validado localmente.

## Arquitectura y fuentes

Chart independiente `infra/helm/retailops-logging`, release `retailops-logging`, namespace existente `retailops-observability`. Loki 3.7.10 y Alloy 1.22.0 con digests verificados en imágenes oficiales. Alloy descubre pods mediante API y usa `loki.source.kubernetes`; no requiere DaemonSet, Promtail, nodos/proxy, archivos del host ni socket Docker. Loki monolítico usa TSDB v13/filesystem y WAL sobre PVC propio; no consume MinIO ni PostgreSQL existentes.

El usuario autorizó explícitamente ServiceAccount `retailops-log-reader` y Roles/Bindings en **retailops y retailops-observability**: `get/list/watch pods`, `get pods/log`. No se conceden permisos globales ni Secrets, exec, eventos o escrituras. El token solo lo monta Alloy. Verificados permisos positivos en app y negativos para Secrets, exec, nodes/proxy y logs en kube-system. Autorizar namespace no significa recolectar todos sus contenedores: el filtro actual selecciona únicamente `api`, `ml`, `web`.

| Fuente | Formato y cobertura real |
| --- | --- |
| Spring Boot | Consola JSON Logstash; eventos HTTP propios, estado y request_id MDC; excepciones del filtro solo por tipo, sin mensaje/stack libre |
| FastAPI | Eventos HTTP JSON propios con timestamp UTC, nivel, servicio, estado, request_id y tipo de excepción no manejada |
| React/nginx | React no es proceso servidor; nginx access JSON con estado/request_id, sin IP, URL/query, usuario, referer o user-agent |
| Pods Kubernetes | stdout/stderr de los tres contenedores principales seleccionados mediante API; no initContainers, journal, eventos Kubernetes ni recuperación garantizada del contenedor anterior |
| Dependencias Compose | Sin recolección automática: no se autorizó socket Docker/hostPath. Sus logs permanecen locales. No se leen logs Airflow persistidos ni se modifican servicios conservados |

Alloy **descarta líneas que no sean eventos HTTP propios** (`Solicitud HTTP completada/fallida`). Por tanto no se centralizan logs de arranque/framework, trazas libres, error_log nativo nginx, Alloy/Loki u otros pods. Es una limitación deliberada de cobertura: no equivale a un archivo íntegro de logs de cada pod. El error_log nativo nginx queda en stderr con nivel crit y puede incluir contexto propio de nginx; no se exporta. Los logs nativos Uvicorn permanecen locales, fuera del flujo centralizado. No se afirma auditoría integral de secretos de esas fuentes.

Etiquetas almacenadas: `service` (api/ml/web), `namespace`, `container`, `environment=local`; Loki añade automáticamente `service_name` igual a `service`. No hay request_id, pod UID, usuarios, payloads ni rutas como etiquetas. Los campos JSON se extraen en tiempo de consulta; esos campos resultantes no son índices persistentes. La selección de targets conserva la identidad Kubernetes interna necesaria para leer cada contenedor.

Spring acepta solo identificadores de 32 caracteres hexadecimales minúsculos o genera uno; limpia MDC al finalizar. El RestClient de FastAPI propaga `X-Request-ID`. nginx genera su identificador, lo pasa a Spring y registra el mismo; FastAPI valida/retorna la cabecera. No se propaga a Airflow/MLflow/SQL y no se añaden spans ni tracing distribuido.

## Seguridad, persistencia y presupuesto

Solo ClusterIP. NetworkPolicy de Loki permite Alloy y Grafana; Alloy no recibe ingreso ordinario. Acceso operativo solo port-forward a **127.0.0.1:3101**, Grafana a **127.0.0.1:3001**. Sin Ingress/NodePort/LAN, UFW nueva, servicios del SO, hostPath o contenedores privilegiados. UID/GID 10001, raíz RO, capabilities drop ALL, no-new-privileges y seccomp RuntimeDefault. Egress conserva el patrón previo de F5.1: no se afirma aislamiento de salida completo. Loki sin autenticación depende del aislamiento de red y de la identidad operadora del clúster; no es un backend multiusuario.

PVC externos Helm, local-path/RWO: `retailops-loki` 2 GiB y `retailops-alloy` 256 MiB. Se conservan los tres PVC anteriores. WAL/índice/chunks/marcadores del compactor persisten; Alloy conserva su directorio de trabajo, pero no se promete entrega exactamente una vez, replay completo tras ausencia ni durabilidad ante pérdida del nodo. El reinicio real de Loki conservó exactamente las tres entradas correlacionadas de referencia con timestamp y contenido iguales. No se borró el PVC.

Retención 48h, compactor habilitado con índice 24h y demora de eliminación 2h. Ingestión 0.005 MB/s, burst 1 MB; 100 streams máximos, líneas 16 KB, consultas paralelas 2 y caches 16+32 MiB. El límite de ingestión no es una cuota de disco. local-path no garantiza una cuota física de 2 GiB; WAL/índice/marcadores y demora de borrado añaden espacio. Retención no significa borrado inmediato a las 48h, y requiere que el laboratorio esté encendido. No se ejecutó una prueba de 48 horas ni de saturación; vigilar espacio del nodo sin borrar volúmenes.

| Componente | Request CPU/memoria | Límite CPU/memoria | Muestra real CPU/memoria |
| --- | --- | --- | --- |
| Loki | 100m / 256 MiB | 500m / 512 MiB | 4m / 68 MiB |
| Alloy | 50m / 128 MiB | 250m / 256 MiB | 2m / 43 MiB |

Adicional solicitado: 150m/384 MiB, límites 750m/768 MiB. GOMEMLIMIT 384/192 MiB respectivamente. Muestra durante el laboratorio: Prometheus 55 MiB, Grafana 323 MiB, adaptador 17 MiB; API 172 MiB, ML 203 MiB, web 10 MiB. Host tenía ~22 GiB disponibles antes del ensayo. MLflow conserva imagen/workers/límite original; no se realizaron experimentos de memoria. Medición de almacenamiento: **125170 bytes lógicos en siete archivos** del PVC Loki, mediante pod temporal no root/sin token con montaje RO, eliminado después; no mide bloques físicos ni capacidad sostenida. Imagen Loki no trae `/bin/du`: el primer intento de medición falló y se sustituyó por esa sonda, sin montar el host.

## Grafana y consultas

La release existente `retailops-observability` admite `logging.enabled=true`: provisiona datasource UID `retailops-loki` y dashboard `retailops-logs`, manteniendo Prometheus predeterminado y los tres dashboards anteriores. Credenciales externas F5.1 reutilizadas; no regeneradas. El textbox request_id es para búsqueda, no etiqueta.

```logql
# HTTP 5xx: ausencia de resultados no equivale a error de la consulta.
{environment="local"} | json | status >= 500
# Excepciones interceptadas por Spring.
{service="api"} | json | exception_type != ""
# FastAPI.
{service="ml"} | json | level="ERROR"
# nginx.
{service="web"}
# Reemplazar por un ID real obtenido de X-Request-ID.
{environment="local"} | json | request_id="<32 hex>"
```

Las cinco consultas se ejecutaron desde Loki y desde el proxy Grafana. Hay logs reales de los tres servicios y correlación web→Spring→FastAPI. Las vistas de 5xx/excepciones devolvieron vacío durante el ensayo; no se provocaron fallos para llenarlas. No se validaron esas vistas contra incidentes reales inexistentes. Para un pod que falla, correlacionar el intervalo con recursos/disponibilidad de F5.1, `kubectl --context default -n retailops get pods` y, como operador, `kubectl ... logs POD -c CONTENEDOR --previous`; este último historial no se incorpora automáticamente a Loki ni está garantizado. No hay dashboard de eventos/reinicios ni afirmación de incidentes ensayados.

## Reactivación reproducible

No reinstalar K3s ni repetir UFW, importar las mismas imágenes, generar secretos o reconstruir MLflow. Si el host está apagado, el usuario arranca el servicio existente con `sudo systemctl start k3s`. Herramientas/kubeconfig F4 conservados:

```bash
export PATH="$PWD/.local/f4/tools:$PATH"
export KUBECONFIG="$PWD/.local/f4/kubeconfig"
export KUBE_CONTEXT=default
export VALUES_FILE="$PWD/.local/f52/values-app.yaml"
export LOGGING_VALUES_FILE="$PWD/.local/f52/values-logging.yaml"
# Values logging revisados: collectionAuthorized: true, replicas: 1.
# Mantener el values app privado con endpoints existentes, v1 y las imágenes F5.2.
kubectl --context "$KUBE_CONTEXT" get nodes
scripts/validate_logging.sh
scripts/validate_observability.sh
# Solo si estaban detenidas, registrar cuáles arranca la sesión:
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops --profile airflow \
  up -d --wait --wait-timeout 180 postgres minio mlflow airflow-api
# Terminal dedicada:
python scripts/compose_bridge.py
```

Con esas variables, en otra terminal:

```bash
scripts/logging.sh start
helm --kube-context "$KUBE_CONTEXT" -n retailops-observability upgrade retailops-observability \
  infra/helm/retailops-observability --set logging.enabled=true --wait --timeout 5m
scripts/deploy.sh upgrade
# Cada forward en su terminal dedicada:
scripts/deploy.sh forward
scripts/observability.sh grafana
scripts/logging.sh forward
# Validaciones, otra terminal:
python scripts/smoke_deployment.py
python scripts/verify_logging.py
```

Los scripts no instalan herramientas ni usan sudo. `collectionAuthorized` es una guarda de configuración; no sustituye autorización humana. El chart rechaza arrancar sin autorización declarada o usar imágenes sin digest, salvo override explícito de validación. Para nuevas imágenes app: verificar Java/Python, construir con etiqueta nueva, exportar tar y solicitar al usuario `sudo k3s ctr images import /ruta/absoluta/app-images.tar`; nunca importar de nuevo sin cambios. Loki/Alloy se descargaron normalmente por containerd mediante imágenes oficiales, sin importación sudo.

## Evidencia y cierre

`.local/f52` contiene maven.log (11 pruebas), pytest.log (15 pruebas), build-apps.log, app-image-tag/tar/checksum, static-validation.log (33 recursos), metrics-regression.log (3 unittest, 22 PromQL y recursos F5.1), helm-*, verification-*.json, persistence-before/result, data-before/after, resources-*, storage-loki, app-live/observability-live y evidencia de cierre. Docker/archivos privados no se versionan. Sin cambios React, no se repitieron build/lint frontend; nginx fue reconstruido y verificado por HTTP.

Snapshot de lectura antes/después compara histórico, ventas/fechas/suma decimal, GOLD, autorizaciones/etiquetas futuras, modelo/métricas v1 y 19 versiones de objetos MLflow. No es hash completo de tablas ni backup. Escaneo de hasta 500 líneas por servicio comparó valores de archivos de secretos locales y patrones; no se hallaron filtraciones en esas muestras, sin garantizar auditoría exhaustiva. Grafana anónima 401; app→Loki rechazado y Grafana/Alloy sí acceden. Sin pods reiniciados por fallo, inferencias nuevas, entrenamiento o mutación de datos.

Cierre, solo si esta sesión inició las apps/observabilidad/dependencias y estaban detenidas:

```bash
scripts/logging.sh stop
scripts/observability.sh stop
# Ctrl-C únicamente a forwards y puente propios.
```

Los ocho Deployments quedan a cero y se conservan cinco PVC, releases, credenciales, imágenes y volúmenes. `observability.sh stop` detiene las cuatro dependencias Compose del laboratorio: no usarlo si pertenecen a otra sesión activa. K3s estaba inactive/disabled al iniciar F5.2; el usuario lo arrancó personalmente para validar. Queda activo/disabled al cerrar el trabajo no privilegiado; para volver al estado inicial, el usuario ejecuta `sudo systemctl stop k3s`, sin disable/reinstalación. No ejecutar down -v/prune/uninstall ni borrar PVC/namespaces.

Fuentes primarias: [Alloy Kubernetes source](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.kubernetes/), [retención Loki](https://grafana.com/docs/loki/latest/operations/storage/retention/), [almacenamiento filesystem](https://grafana.com/docs/loki/latest/operations/storage/filesystem/). Las cifras y resultados anteriores proceden del laboratorio local.

Cierre observado: ocho Deployments a cero, cero pods en los dos namespaces y cinco PVC Bound; nueve servicios Compose exited (solo cuatro reactivados en esta sesión), puente y tres forwards cerrados. Evidencia `closure.json`, `app-stopped.json`, `observability-stopped.json`, `compose-stopped.json`, `listeners-final.txt`. K3s activo/disabled; retorno al inactive inicial reservado al comando sudo personal indicado arriba.
