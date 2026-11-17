# Runbooks operativos F5.3

Laboratorio de un nodo, diagnóstico local y recuperación conservadora. No autorizan F5.4, ensayos destructivos, borrados, UFW, cambios de modelo o aumento de límites. Los enlaces de alerta son rutas del repositorio; el dashboard SRE ofrece enlaces HTTP locales a métricas, logs y Alertmanager. Loki solo contiene eventos HTTP propios de api/ml/web; una búsqueda vacía no descarta fallos.

Antes de diagnosticar, registrar hora UTC, alerta, servicio y si hay cierre planificado. Exportar desde la raíz:

```bash
export PATH="$PWD/.local/f4/tools:$PATH"
export KUBECONFIG="$PWD/.local/f4/kubeconfig"
export KUBE_CONTEXT=default
kubectl --context "$KUBE_CONTEXT" get nodes
kubectl --context "$KUBE_CONTEXT" -n retailops-observability get deployments,pods,pvc
kubectl --context "$KUBE_CONTEXT" -n retailops get deployments,pods,pvc
```

Prometheus: `scripts/observability.sh prometheus` (127.0.0.1:9091). Grafana: `scripts/observability.sh grafana` (127.0.0.1:3001, credenciales F5.1). Alertmanager: `scripts/sre.sh alertmanager` (127.0.0.1:9094). Mantener cada forward en su terminal, cerrar solo los propios. Consultar PromQL en Prometheus/Grafana y LogQL en datasource Loki. No imprimir archivos de credenciales, env, tokens, request bodies o cadenas de conexión. `kubectl describe` y logs nativos pueden contener más contexto que Loki: revisar localmente antes de compartir.

## API no disponible

**Síntomas:** `RetailOpsServiceUnavailable{service="api"}` tras 3m, deployment sin réplicas disponibles tras 5m o interfaz sin respuesta. El primero mide scraping, no prueba por sí solo caída comercial.

**Consultas:**

```promql
retailops:lab_active
retailops:service_expected{service="api"}
up{job="spring"}
retailops_kubernetes_deployment_available_replicas{deployment="retailops-api"}
```

```logql
{service="api"} | json | status >= 500
```

**Diagnóstico:** `kubectl --context "$KUBE_CONTEXT" -n retailops get pods`; `kubectl ... -n retailops describe deployment retailops-api`; `kubectl ... -n retailops logs deployment/retailops-api --tail=100`. Comprobar readiness/startup, eventos del pod concreto y puerto/servicio. Comparar web→API con Prometheus→métricas; `/api/actuator/prometheus` por nginx devuelve 404 intencionalmente.

**Hipótesis:** cierre planificado, imagen ausente, credencial/configuración inválida, startup, fallo de dependencia o NetworkPolicy de scraping. Si desired=0 o lab_active=0, confirmar intención; no arrancar automáticamente un cierre.

**Recuperación segura:** corregir únicamente configuración/endpoints identificados, restaurar disponibilidad mediante procedimiento DEPLOYMENT/SRE y esperar rollout. Si el workload debía estar activo, escalar solo `deployment/retailops-api` a su réplica anterior y verificar `/api/actuator/health` y smoke read-only. No migrar datos, ampliar permisos ni reinstalar para ocultar un fallo. Conservar evidencia y escalar el diagnóstico si no hay causa clara.

## Errores HTTP 5xx

**Síntomas:** `RetailOpsHttp5xx`, >5% durante 5m con al menos 20 solicitudes observadas por ventana de 5m. API usa rutas `/v1/*`; ML solo `/predict`. Sin tráfico no hay ratio.

```promql
1 - retailops:sli_non5xx:ratio5m
retailops:http_requests:increase5m
sum by (status,uri) (increase(http_server_requests_seconds_count{job="spring",uri=~"/v1/.*"}[5m]))
```

```logql
{environment="local"} | json | status >= 500
{environment="local"} | json | request_id="<ID real de 32 hex>"
```

**Diagnóstico:** buscar el ID de respuesta en los tres servicios; revisar estado del modelo, dependencias y alertas correlacionadas. `python scripts/smoke_deployment.py` verifica lectura/rechazo sin inferencia nueva. No repetir POST de negocio para reproducir un fallo.

**Hipótesis:** dependencia caída, timeout, contrato/configuración o fallo de la aplicación; un 4xx esperado por cutoff/consentimiento no es 5xx ni un incidente fabricado. Los SLI “sin 5xx” incluyen 4xx: no equivalen a satisfacción de usuario.

**Recuperación segura:** corregir la causa comprobada, verificar GET de salud/metadatos y disminución natural del ratio. Un restart general puede ocultar evidencia y no es la solución predeterminada. La alerta fuente de indisponibilidad inhibe 5xx/latencia del mismo servicio; revisar también inhibidas en Alertmanager.

## Latencia elevada

**Síntomas:** `RetailOpsHttpLatency`, p95 >1s durante 5m, mínimo 20 solicitudes/5m. No es benchmark ni SLO de producción.

```promql
retailops:sli_latency:p95_5m
retailops:http_requests:increase5m
retailops_kubernetes_container_cpu_cores
retailops_kubernetes_container_memory_working_set_bytes / retailops_kubernetes_container_memory_limits_bytes
```

```logql
{environment="local"} | json | status >= 500
```

**Diagnóstico:** comparar HTTP, CPU/memoria, disponibilidad y timestamps; `kubectl --context "$KUBE_CONTEXT" -n retailops top pods` y `kubectl ... -n retailops-observability top pods`. Revisar swap/presión del host mediante `free -m` y lecturas no privilegiadas. No se registran duraciones por request_id en Loki: analizar el histograma para latencia, sin inventar trazas.

**Hipótesis:** calentamiento, consulta lenta, presión/swap, modelo esperando I/O o bucket ancho con bajo tráfico. Los histogramas solo estiman p95 y pueden dar NaN sin solicitudes.

**Recuperación segura:** esperar startup si corresponde, detener únicamente pruebas/carga propias y corregir configuración demostrada. No ejecutar carga adicional, cambiar workers MLflow, límites o modelos como experimento. Confirmar recuperación en ventanas siguientes sin borrar series.

## FastAPI ML no disponible

**Síntomas:** `RetailOpsServiceUnavailable{service="ml"}`, target fastapi DOWN, modelo cargado=0 o deployment ML no disponible. Loaded=1 sigue siendo candidato, no aprobación ni prueba de una predicción correcta.

```promql
up{job="fastapi"}
retailops_ml_model_loaded
retailops:service_expected{service="ml"}
retailops_dependency_up{service=~"fastapi|mlflow|minio|postgresql"}
```

```logql
{service="ml"} | json | level="ERROR"
{environment="local"} | json | request_id="<ID real de 32 hex>"
```

**Diagnóstico:** `kubectl --context "$KUBE_CONTEXT" -n retailops describe deployment retailops-ml`; logs acotados del contenedor `ml` y, si el init falló, `trainer-credentials`. Verificar PVC cache Bound, endpoint/Host del puente y archivo trainer regular 0600 sin imprimirlo. Revisar estado Compose con `docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops --profile airflow ps -a`.

**Hipótesis:** dependencia conservada detenida, puente ausente, modelo no cargado, imagen ausente o contrato de credencial. No confundir falta de telemetría del modelo con un cero observado.

**Recuperación segura:** reactivar solo dependencias que deberían estar activas, restaurar el puente/contrato según LOGGING/DEPLOYMENT, mantener versión 1 y rollout ML. Verificar GET `/api/v1/models/active`; no entrenar, registrar, promover o sustituir el modelo. Si la dependencia es PostgreSQL/MinIO, comprobar su salud sin cambiar tablas, secretos o volúmenes.

## MLflow próximo al límite de memoria

**Síntomas:** observaciones puntuales próximas a 1 GiB, swap o timeout. **No existe una serie Prometheus continua de memoria Compose/MLflow** y no se configura una alerta automática falsa. `RetailOpsMemoryHigh` cubre pods Kubernetes, no este contenedor Docker.

```promql
retailops_dependency_up{service="mlflow"}
retailops_collector_section_success{section="dependencies"}
```

```logql
{service="ml"} | json | status >= 500
```

**Diagnóstico:** `docker stats --no-stream retailops-data-mlflow-1`; `python scripts/inspect_mlflow_memory.py` solo con MLflow activo, sin reiniciarlo. El script conserva evidencia privada y mide cgroup/anon/file/swap sin leer argv/env. `docker inspect --format '{{.State.OOMKilled}} {{.RestartCount}} {{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}' retailops-data-mlflow-1` muestra estado/límites, no credenciales.

**Hipótesis:** memoria anónima y swap ya observadas en F5.1, caché/procesos o presión del host; el uso alto no identifica por sí solo un worker culpable. working set de `docker stats` y memory.current no son la misma magnitud.

**Recuperación segura:** detener pruebas propias y liberar carga ajena solo con su responsable. Mantener límite/imagen/workers originales. No ensayar restart, workers o aumento arbitrario de RAM en el servicio conservado. Si sigue sin margen, conservar evidencia y pedir una decisión de capacidad autorizada; no matar procesos, borrar artefactos ni cambiar registro/backend.

## Memoria elevada

**Síntomas:** `RetailOpsMemoryHigh`, working set de pod >85% del límite durante 10m. Es ratio observado, no prueba de OOM ni de fuga.

```promql
retailops_kubernetes_container_memory_working_set_bytes / retailops_kubernetes_container_memory_limits_bytes
retailops_kubernetes_container_restarts_total
retailops_collector_section_success{section="usage"}
```

**LogQL:** `{environment="local"} | json | level="ERROR"` solo para contenedores app cubiertos. **Diagnóstico:** top/describe del pod concreto, requests/limits y contexto de startup. **Hipótesis:** calentamiento, caché, carga o memoria retenida; metrics-server no expone todo cgroup. **Recuperación segura:** retirar pruebas propias y revisar evidencia; no cambiar recursos ni reiniciar otros servicios sin diagnóstico. Para MLflow usar el runbook específico, no esta regla.

<a id="recoleccion-de-metricas"></a>

## Recolección de métricas

**Síntomas:** target DOWN, `RetailOpsCollectorUnavailable`, `RetailOpsCollectorSectionFailed`, `RetailOpsMetricsEndpointUnavailable` o `RetailOpsLabSignalUnavailable`. Esta última avisa si falta el receptor/señal mientras Prometheus sigue evaluando.

```promql
up
retailops_collector_section_success
retailops:lab_active
retailops_kubernetes_deployment_desired_replicas
```

```logql
{service="api"} | json | status >= 500
```

**Diagnóstico:** revisar `/api/v1/targets` y `/api/v1/rules` en Prometheus; comparar servicio y NetworkPolicy permitida. `kubectl --context "$KUBE_CONTEXT" -n retailops-observability logs deployment/collector --tail=100` y describe del componente concreto. Comprobar metrics-server existente; RBAC metrics-reader conserva get/list originales. Receptor/Alertmanager no necesitan token/RBAC.

**Hipótesis:** timeout, error de sección, DNS/policy, app cerrada, métricas deshabilitadas o API metrics-server sin muestra. Ausencia de series no significa dependencia UP o memoria cero. Si Prometheus está apagado no puede alertar sobre sí mismo; no hay monitor externo/watchdog.

**Recuperación segura:** corregir el scrape/puerto/contrato demostrado y verificar target UP y reglas health=ok. No conceder Secrets/exec/nodes-proxy ni abrir UFW. Reaplicar únicamente el chart versionado según SRE.md; no crear credenciales, reinstalar metrics-server o borrar la TSDB.

## Reinicios inesperados

**Síntomas:** `RetailOpsContainerRestarts`, incremento positivo de restartCount en 10m sostenido 1m. Se observan contenedores principales existentes; recrear un pod puede perder el contador anterior y no equivale a restart del mismo contenedor.

```promql
increase(retailops_kubernetes_container_restarts_total[10m])
retailops_kubernetes_pod_ready
retailops_kubernetes_container_memory_working_set_bytes
```

```logql
{environment="local"} | json | level="ERROR"
```

**Diagnóstico:** `kubectl --context "$KUBE_CONTEXT" -n retailops get pods`; describir el pod afectado para lastState/reason/exitCode y eventos; `kubectl ... -n retailops logs POD -c CONTENEDOR --previous --tail=100`. Los logs anteriores no se recuperan automáticamente en Loki; no se promete que todavía existan. Para observabilidad usar su namespace.

**Hipótesis:** OOM, probe, proceso fallido o restart controlado; contrastar timestamps y cambios autorizados. La métrica no registra la causa.

**Recuperación segura:** conservar evidencia y corregir la causa antes de otro restart. Rollout de configuración solo si el cambio fue identificado y revisado; mantener PVC/Secrets/modelo. No matar pods en bucle, borrar datos ni elevar límites a ciegas. Un restart controlado puede producir señales transitorias reales: anotarlo, no purgar métricas para ocultarlo.
