> F5.3 publicada y Actions exitosa según confirmación posterior del usuario. F5.4 autorizada y verificada para [backups/restauración aislada](BACKUP_RECOVERY.md), sin F5.5. El resto conserva el alcance y evidencia SRE histórica.

Nota F5.5-A: [laboratorio de incidentes preparado](INCIDENT_LAB.md), sin despliegue ni incidentes ejecutados. Overlays de observabilidad/logging deshabilitados por defecto; no se aplicaron permisos nuevos. Provisionamiento y ejercicios F5.5-B requieren autorización posterior. Los datos, respaldos y recursos conservados permanecen intactos.

# F5.3 — Alertas, SLI/SLO y operación local

Validación local: 2026-11-17, America/Guayaquil.

Alcance: Alertmanager, notificaciones **solo locales**, reglas operativas, SLO propuestos y [runbooks](RUNBOOKS.md). Sin F5.4, monitor externo, HA, notificaciones externas, backups, cambios de datos/modelo o fallos destructivos. Usuario confirmó F5.2 completada y GitHub Actions exitosa después de su push; no se ejecuta Git remoto en F5.3.

## Arquitectura

Se extiende `retailops-observability` 0.2.0, con `alerting.enabled=true` y `logging.enabled=true`. Conserva Prometheus/Grafana/adaptador y la release Loki/Alloy. Alertmanager **0.35.0 por digest oficial** y receptor stdlib Python sobre imagen existente fijada; no se construyen/importan imágenes app nuevas. No se instalan servicios del SO, operadores ni exportadores privilegiados.

Prometheus carga 19 reglas de grabación, 11 alertas operativas y una regla sintética separada. Scrapes cada 30s, receptor cada 10s; evaluación operativa 30s, sintética 10s. Seis targets: spring, fastapi, lab, prometheus, alertmanager, alert-receiver. Prometheus→Alertmanager:9093→webhook receptor:8090. El receptor guarda solo campos permitidos de notificación, no annotations libres, tokens o URLs arbitrarias; no envía mensajes a terceros. Sus endpoints `/metrics`, `/health`, `/events` solo se usan dentro del namespace o mediante forward operadora local.

Nuevos componentes sin token/RBAC, UID/GID 65534, raíz RO, capabilities drop ALL, seccomp RuntimeDefault, sin privilegios/hostPath/socket Docker. Se reutilizan permisos read-only del adaptador para obtener restartCount de los contenedores principales desde containerStatuses; no se amplía RBAC. NetworkPolicies de ingreso admiten Prometheus→Alertmanager/receptor y Alertmanager→receptor. Solo ClusterIP y forwards **127.0.0.1:9094/8091**, no Ingress/NodePort/LAN/Internet/UFW nueva. El esquema previo de egress no se endurece globalmente: los destinos de notificación están limitados por configuración versionada, no por una nueva garantía de aislamiento de salida.

## Agrupación, deduplicación, inhibición y silencios

Agrupación por `[alertname, environment, scope]`, group_wait 15s, group_interval 1m y repeat_interval 4h. Se mantiene la identidad individual dentro del grupo; la deduplicación no garantiza entrega exactamente una vez. Ruta `scope=validation`: espera 5s, intervalo 10s, repetición 1h. No email/Telegram/Slack ni otros receivers.

Inhibiciones: ServiceUnavailable suprime Http5xx/HttpLatency del mismo servicio/entorno/scope; CollectorUnavailable suprime síntomas derivados del adaptador en el mismo entorno/scope. No ocultan indisponibilidad de Prometheus ante un observador externo inexistente. Revisar inhibidas/silenciadas en Alertmanager; el dashboard de ALERTS muestra evaluación Prometheus, no estado de entrega o de silencio.

Silencios se gestionan en la UI local Alertmanager con matchers acotados, comentario, propietario operativo y expiración. Ejemplo de mantenimiento: `scope=operational`, `environment=local`, servicio/alerta concretos y duración explícita; nunca un silencio global indefinido. Registrar ID y expirarlo al terminar; el cierre normal además debe desactivar la señal de laboratorio, no depender solo de un silencio. La prueba creó un silencio **solo para RetailOpsSilenceProbe/scope=validation**, verificó supresión y persistencia y después lo expiró.

## Cierre intencional y ausencia de datos

ConfigMap **externo a Helm** `retailops-lab-state` contiene `lab_active` (0/1) y dos señales de validación (api/ml, normalmente 0). `scripts/sre_state.py prepare` crea estado inactivo únicamente si falta; upgrades nunca lo activan ni reinicializan silencios/credenciales. El receptor publica la señal; no controla aplicaciones o datos.

`scripts/sre.sh active` declara una sesión operativa tras comprobar sus componentes. Para cierre: `python scripts/verify_sre.py inactive` fija 0, espera propagación ConfigMap/scrape/evaluación y confirma cero alertas operativas antes de escalar. No basta con ejecutar inactive e inmediatamente apagar la aplicación: el volumen ConfigMap puede tardar en actualizarse. La regla usa la última señal observada hasta 5m; si el receptor falla, `RetailOpsLabSignalUnavailable` avisa independientemente del estado, mientras Prometheus siga vivo.

Alertas y disponibilidad app requieren laboratorio activo y réplicas deseadas positivas. Targets app intencionalmente en cero no se interpretan como outage. Las alertas de recursos/probes también se inhiben por laboratorio inactivo; contenedores retirados desaparecen tras scrape. Las grabaciones HTTP de volumen pueden conservar historia y no afirman que haya tráfico actual. Con Prometheus apagado no hay evaluación, y con el host apagado no hay notificación: no se promete disponibilidad continua del sistema de alerta.

## Reglas operativas

| Regla | Categoría | Condición y duración |
| --- | --- | --- |
| RetailOpsServiceUnavailable | Aplicación | Disponibilidad observada API/ML=0 durante 3m, servicio esperado |
| RetailOpsHttp5xx | Aplicación | >5% 5xx/5m, ≥20 solicitudes/5m, sostenido 5m |
| RetailOpsHttpLatency | Aplicación | p95 >1s/5m, ≥20 solicitudes/5m, sostenido 5m |
| RetailOpsDeploymentUnavailable | Infraestructura | Disponibles < deseadas y deseadas >0 durante 5m |
| RetailOpsMemoryHigh | Infraestructura | working set pod/límite >85% durante 10m |
| RetailOpsContainerRestarts | Infraestructura | increase(restartCount[10m]) >0 durante 1m |
| RetailOpsMetricsEndpointUnavailable | Infraestructura | Target esperado spring/fastapi/AM/receptor DOWN durante 3m |
| RetailOpsCollectorUnavailable | Infraestructura | Scrape adaptador DOWN durante 2m |
| RetailOpsCollectorSectionFailed | Infraestructura | Sección observada fallida durante 3m; dependencias requieren API esperada |
| RetailOpsDependencyUnavailable | Aplicación | Probe fiable existente UP=0 durante 3m (SQL/HTTP) |
| RetailOpsLabSignalUnavailable | Infraestructura | Receptor/señal DOWN durante 2m mientras Prometheus evalúa |

Los umbrales son heurísticas conservadoras del laboratorio, con margen frente a startup, bajo tráfico y ruido; no se derivan de una prueba de carga. No hay alertas falsas de memoria MLflow: no existe esa serie continua Docker. Su proximidad al límite se diagnostica puntualmente con el [runbook específico](RUNBOOKS.md#mlflow-próximo-al-límite-de-memoria), conservando workers/límites. El adaptador SQL/HTTP tampoco identifica siempre la causa raíz: fallo de su sección es pérdida de observación, no todas las dependencias DOWN. RestartCount no cubre reemplazos de pods ni initContainers y no identifica OOM por sí solo.

Las reglas llevan summary, runbook_url relativo al repositorio y enlaces locales a métricas/logs. No hay servidor HTTP de documentación: abrir runbooks desde el repo. Los enlaces a dashboards requieren los forwards propios.

## SLI y objetivos propuestos

**Propuestas para sesiones locales, no acuerdos de producción ni resultados cumplidos.** Ventana móvil 1h, solo muestras del laboratorio activo/servicio deseado. Scrapes cada 30s; presupuestos temporales requieren **120 muestras en 1h**. No se rellenan huecos con ceros/unos. Una muestra es una observación puntual, no garantía de los 30 segundos intermedios. No se evalúa el apagado esperado como indisponibilidad comercial.

| Indicador | Consulta grabada | Propuesta y limitación |
| --- | --- | --- |
| API disponible observada | `retailops:sli_availability:ratio{service="api"}` | 99%/1h; usa `up{job="spring"}`, mide acceso al exporter, no salud end-to-end ni SQL |
| ML disponible observada | `retailops:sli_availability:ratio{service="ml"}` | 99%/1h; scrape fastapi y loaded=1; no prueba de inferencia correcta ni promoción |
| Solicitudes sin 5xx | `retailops:sli_non5xx:ratio5m` / `ratio1h` | 99%/1h y ≥100 solicitudes; incluye 4xx esperados, no satisfacción del usuario |
| Latencia p95 HTTP | `retailops:sli_latency:p95_5m` | p95 ≤1s por ventana 5m con ≥20 solicitudes; percentil aproximado por buckets, no presupuesto aditivo |

API HTTP usa solo `uri=~"/v1/.*"`, excluye Actuator/scraping. ML HTTP usa **solo `/predict`**, excluye `/health` y `/model` para no aparentar fiabilidad de inferencia con probes. Sin predicciones nuevas en esta fase: ratio/latencia de inferencia no evaluables. API/ML readiness se informa separadamente. Un modelo sin telemetría no se convierte en cero inventado: si scrape falla observado se registra indisponibilidad; si loaded falta con scrape UP, no se afirma readiness.

PromQL base, además de las 19 grabaciones versionadas en `files/alerting/rules.yml`:

```promql
# Disponibilidad observada solo en sesión/servicio esperado:
retailops:sli_availability:ratio
# Muestras de cobertura de cada servicio (máximo esperado 120 por hora):
retailops:sli_availability:samples1h
# Ventana completa antes de calcular objetivo/presupuesto:
retailops:sli_availability:ratio1h
# Presupuesto restante, 1=todo, 0=agotado, negativo=sobreconsumo:
retailops:slo_availability:budget_remaining1h
retailops:slo_non5xx:budget_remaining1h
```

Presupuesto = `1 - (1 - SLI) / (1 - 0.99)`. Para disponibilidad propuesta: 1% de 1h = **36s**, con resolución de muestreo 30s; no presentar esa cifra como precisión operativa real. Para solicitudes: 1% de solicitudes observadas, con conteos `increase` extrapolados al intervalo; no equivalen necesariamente a enteros auditados. Se exige hora completa de cobertura y 100 solicitudes para presupuesto HTTP. Un percentile p95 no se traduce a segundos de indisponibilidad: no se publica presupuesto de latencia calculado a partir de p95.

Se proponen 99% para observar errores dentro de sesiones activas, con cálculo simple y sensibilidad a una muestra fallida; no es una capacidad validada del nodo. El umbral API de 1s deja margen frente a la muestra local (~0.135s p95), que no es carga representativa. El mismo umbral ML es provisional y requiere mediciones de inferencia autorizadas antes de adoptarlo como objetivo.

El historial Prometheus conserva 48h/512MB de F5.1; no soporta SLO mensual confiable. La ventana real F5.3 fue corta, por lo que **no hubo datos suficientes para presupuesto/SLO horario**, ni para HTTP de inferencia. Los escenarios completos de 1h se probaron con fixtures promtool, diferenciados de la medición real.

## Dashboard y navegación

Grafana mantiene unified alerting deshabilitado: solo Prometheus evalúa estas reglas, sin motor duplicado. Dashboard `retailops-sre` con 12 paneles: actividad, ALERTS operativas/sintéticas separadas, disponibilidad, no-5xx, p95, memoria/límite, reinicios, cobertura y presupuestos condicionados. Enlaces a `retailops-http`, `retailops-logs` y Alertmanager local. Las alertas contienen dashboard_url y logs_url; seleccionar servicio e intervalo del evento y después request_id real en logs. No hay tracing automático ni correlación de métricas por ID de alta cardinalidad.

Se verifican por API los dashboards de destino, expresiones guardadas, consultas directas/proxy y logs reales por datasource Loki. Eso no sustituye prueba visual de navegación en navegador. ALERTS=1 significa evaluación pending/firing; revisar `alertstate`. La ausencia de errores durante la sesión no valida un incidente real inexistente.

## Reactivación

K3s ya estaba activo/disabled al comenzar F5.3; no se toca su unidad. Si está detenido en otra sesión, el usuario ejecuta personalmente `sudo systemctl start k3s`. No reinstalar/importar imágenes app otra vez ni regenerar secrets. Desde raíz:

```bash
export PATH="$PWD/.local/f4/tools:$PATH"
export KUBECONFIG="$PWD/.local/f4/kubeconfig"
export KUBE_CONTEXT=default
export VALUES_FILE="$PWD/.local/f52/values-app.yaml"
# Reutiliza el values privado con imágenes F5.2, endpoints conservados y v1.
kubectl --context "$KUBE_CONTEXT" get nodes
scripts/validate_sre.sh
scripts/sre.sh start
# Reutilizar únicamente dependencias paradas que necesite esta sesión:
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops --profile airflow \
  up -d --wait --wait-timeout 180 postgres minio mlflow airflow-api
# Terminal dedicada:
python scripts/compose_bridge.py
```

Con las mismas variables en otra terminal:

```bash
kubectl --context "$KUBE_CONTEXT" -n retailops scale \
  deployment/retailops-api deployment/retailops-ml deployment/retailops-web --replicas=1
scripts/deploy.sh rollout
kubectl --context "$KUBE_CONTEXT" -n retailops-observability scale deployment/loki deployment/alloy --replicas=1
scripts/sre.sh active
# Cada forward en una terminal dedicada:
scripts/observability.sh prometheus
scripts/observability.sh grafana
scripts/sre.sh alertmanager
scripts/sre.sh receiver
scripts/deploy.sh forward
# Otra terminal, cuando targets y reglas tengan muestras nuevas:
python scripts/smoke_deployment.py
python scripts/verify_sre.py live
```

`sre.sh start` añade/actualiza solamente chart de observabilidad y sus dos PVC; no arranca Compose/apps/Loki, no resetea estado lab existente. El modo live exige lab_active=1 y servicios observados UP. Conservar evidencia de qué se reactivó; no detener servicios ajenos al cerrar.

<a id="validacion-controlada"></a>

## Validación controlada

```bash
python scripts/verify_sre.py controlled
```

Activa dos gauges identificados `retailops_alert_test_signal{case="api|ml"}`, publica **RetailOpsValidationSignal/scope=validation**, comprueba entrega firing agrupada, ausencia de repetición durante 25s y resolución al devolverlos a cero. El modo adicional `python scripts/verify_sre.py dedup` reenvía dos veces alertas idénticas por API AM, verifica una sola entrega agrupada durante 25s y resolución; son probes sintéticas de routing, separadas del pipeline Prometheus.

Después inyecta dos alertas **explícitamente sintéticas** por API Alertmanager para comprobar inhibición y un silencio acotado; las resuelve. Estas pruebas de routing no son fallos reales de API/ML ni validan sus umbrales de incidente. Guardar el resultado y el silencio temporal para prueba de persistencia; si se interrumpe, devolver señales a cero y expirar solo los silencios creados por la sesión. Nunca expirar silencios ajenos.

Para verificar persistencia durante una sesión autorizada, después de controlled: registrar eventos/ID del silencio; `kubectl ... -n retailops-observability rollout restart deployment/alertmanager deployment/alert-receiver`, esperar ambos rollout, volver a conectar sus forwards y ejecutar `python scripts/verify_sre.py persistence`. Comprueba el silencio activo y eventos originales, y expira el silencio de prueba. No se borra ningún PVC. No repetir restart sin motivo ni tocar MLflow/bases.

## Persistencia, recursos y retención

PVC nuevos externos a Helm: `retailops-alertmanager` 256Mi y `retailops-alert-receiver` 256Mi, local-path/RWO, preservando los cinco existentes. Alertmanager conserva silencios y notification log, retención 48h; no es archivo completo de incidentes. Receptor SQLite conserva ~1000 notificaciones y máximo 48h, purga al atender peticiones; no persiste anotaciones libres ni envía contenido fuera del clúster. El tamaño declarado local-path no es una cuota física garantizada. No se probó expiración real de 48h; sí retención/cota con pruebas temporales unitarias.

Requests adicionales: **35m CPU/56MiB**; límites: **300m CPU/192MiB**. Alertmanager request 25m/32MiB, límite 200m/128MiB, GOMEMLIMIT 96MiB; receptor 10m/24MiB, límite 100m/64MiB. Muestra real inicial: AM 1m/17MiB y receptor 1m/19MiB. Prometheus 44MiB, Grafana 255MiB, adaptador 17MiB, Loki 66MiB, Alloy 45MiB; muestras, no picos ni capacidad productiva. MLflow no cambió imagen/workers/límites ni fue sometido a experimentos.

## Cierre seguro

Solo si estos componentes estaban detenidos antes de la sesión, con los forwards todavía abiertos:

```bash
python scripts/verify_sre.py inactive
# Ahora sí, detener logs y app/métricas/dependencias de esta sesión:
scripts/logging.sh stop
scripts/observability.sh stop
scripts/sre.sh stop
# Ctrl-C únicamente a forwards y puente propios.
```

El cierre selectivo de observability.sh espera solo sus tres componentes, sin bloquearse por Loki/Alloy/Alertmanager/receptor todavía activos. Conservar diez Deployments a cero, siete PVC Bound, releases/Secrets, notificaciones y métricas. No down -v/prune/uninstall/borrados ni cambios de autoarranque K3s. Fuentes originales, tablas/cutoff y candidato v1 no se modifican.

Fuentes primarias: [Alertmanager y deduplicación](https://prometheus.io/docs/alerting/latest/alertmanager/), [configuración y webhooks](https://prometheus.io/docs/alerting/latest/configuration/), [reglas de grabación](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/). Evidencia local y límites de ejecución se registran en PROGRESS.md y `.local/f53`; no se publican logs, secretos o datos.

Muestra final adicional tras restart: AM 1m/15MiB, receptor 18m/14MiB (startup); PVC AM dos archivos/471 bytes lógicos y receptor un archivo SQLite/8192 bytes, medidos por sonda temporal de solo lectura, sin token ni host mounts. Persistencia del silencio y notificaciones confirmada; primer intento de forward receptor apuntó al pod anterior en terminación, se reconectó al terminar rollout y la prueba final pasó.

Prueba de cierre planificado ejecutada: lab_active=0 confirmado antes de escalar; apps a cero, targets spring/fastapi DOWN observados y 32s adicionales de evaluación sin alertas operativas. La prueba de deduplicación adicional produjo una notificación firing y una resolved con dos alertas agrupadas, pese a dos reenvíos idénticos; ventana observada 25s, sin afirmar retención/deduplicación de horas.

Cierre final comprobado: diez Deployments a cero, sin pods en app/observabilidad y siete PVC Bound; nueve servicios Compose exited y cero listeners temporales, cinco forwards propios y puente cerrados. K3s permanece activo/disabled como al inicio. ConfigMap de sesión inactiva y señales cero, silencio sintético expirado. Evidencias `.local/f53/{closure,planned-zero-proof,inactive-proof,integrity-comparison,persistence-result,dedup-proof}.json`, snapshots/recursos/estáticas y estados stopped. Ningún commit/push/pull/GHCR; CI nueva solo validada localmente, sin F5.4.
