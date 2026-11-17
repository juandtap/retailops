# Despliegue local — F4

**F4 verificada en el alcance local autorizado:** K3s Ready, tres Deployments disponibles, smoke integrado y actualización/rollback Helm reales. CI #2 GitHub exitosa según usuario después de corregir selector a Temurin 21; GHCR no publicado. Sin F5.

Cierre del ensayo 2026-11-16, America/Guayaquil: workloads app escalados a cero, cuatro dependencias Compose detenidas, puente y forwards cerrados. K3s permanece activo y disabled para autoarranque, igual que al inicio de esta ejecución. Namespace, Secrets, release, PVC, caché, volúmenes y datos conservados.

F5.1 se incorporó después: [observabilidad, recursos y operación](OBSERVABILITY.md). Para activar también métricas usar ese procedimiento y sus values instrumentados, conservando recursos F4.

## Arquitectura y alcance

Compose sigue operando PostgreSQL, MinIO, MLflow y Airflow API existentes; Kubernetes despliega React/nginx → Spring → FastAPI. El navegador solo consulta Spring. API usa retailops_api y viewer Airflow; ML usa trainer sobre training y descarga exclusivamente candidato v1 desde MLflow. No hay ingesta, entrenamiento, aprobación/promoción ni rollback de modelos en Helm.

Chart `infra/helm/retailops`: tres Deployments, tres ClusterIP, tres ServiceAccounts sin token, ConfigMap y tres NetworkPolicies de entrada. Namespace y PVC se crean fuera de Helm, y Secrets se provisionan por archivos locales. No hay Ingress, NodePort, LoadBalancer, Docker socket ni contenedores privilegiados. Web se consulta solo mediante port-forward ligado a 127.0.0.1. La cadena web→api→ML admite entrada entre los componentes correspondientes; web no admite conexiones de red ordinarias. Salida permitida a DNS/dependencias, dentro de las restricciones existentes del host.

K3s de un nodo usa containerd propio, sin sustituir Docker. **Los volúmenes Compose no se montan ni copian a Kubernetes.** La modalidad depende del host, Compose y un puente local; no es una instalación autónoma ni de alta disponibilidad.

## Red y contratos existentes

El puente temporal `python scripts/compose_bridge.py` escucha solo en 10.42.0.1 y acepta clientes 10.42.0.0/16:

| Puerto CNI | Destino loopback Compose |
| --- | --- |
| 15432 | PostgreSQL 5432 |
| 15000 | MLflow 5000 |
| 19000 | MinIO 9000 |
| 18081 | Airflow API 8081 |

Values Compose usan hostAliases postgres/mlflow → 10.42.0.1. Esto conserva la validación de hostname trainer y el Host permitido por MLflow, sin cambiar las imágenes. API/ML usan UID/GID 1000 y seccomp RuntimeDefault. Nginx oficial conserva master root y workers con privilegios reducidos; namespace aplica Pod Security baseline, no se afirma restricted.

API recibe solo sus archivos de Secret 0440. Trainer exige archivo regular 0600 y rechaza symlinks: un initContainer de la misma imagen ML copia únicamente ese archivo desde Secret proyectado a emptyDir en memoria. Comprobado con fixture sintética y dentro del pod real; sin exponer credenciales ni entregar secretos administrativos. Kubeconfig privado .local/f4/kubeconfig permanece 0600, propietario usuario; los permisos globales del kubeconfig y socket containerd no se modificaron.

Red observada: enp6s0 192.168.0.121/24, gateway/DNS 192.168.0.1; Wi-Fi 192.168.0.116/24. Docker 172.17/16 y 172.18/16 no solapan pods 10.42/16 ni servicios 10.43/16. DNS interno y externo comprobados desde pod ML. Durante el ensayo, servicios Compose escucharon en loopback y puente en CNI; sin listeners app LAN, router o Internet. K3s API conserva su configuración Ethernet/TLS previamente autorizada.

## Persistencia y actualizaciones

PVC `retailops-inference-cache`, 2 GiB, local-path/RWO, Bound durante y después del ensayo. StorageClass usa WaitForFirstConsumer: preflight acepta Pending solo en ese modo; el primer pod permite asignar volumen. El PVC queda fuera de la release y no se elimina al revertir aplicación. MinIO conserva el artefacto autoritativo; caché ML es independiente.

Web/API usan RollingUpdate con surge uno y unavailable cero. ML usa surge cero/unavailable uno para evitar dos escritores de caché; su actualización puede interrumpir inferencia. Probes: web `/`; Java Actuator liveness/readiness; ML `/health` para liveness y `/model` para readiness. Startup admite diez minutos. Las probes se complementan con consultas integradas; no certifican por sí solas la integridad completa de dependencias.

Helm no contiene migraciones/hooks de base de datos ni rollback SQL. El ciclo de software no cambia ML_MODEL_VERSION=1, aliases o aprobación del registro. candidateDemo permanece false: smoke comprueba 409 sin consentimiento. No se afirma nueva inferencia POST de siete días en esta prueba; el recorrido HTTP hasta FastAPI se verifica mediante sus metadatos reales.

## Host e instalación ya completada

CachyOS, 12 CPU lógicos, 30 GiB RAM y ~390 GiB libres al comienzo; cgroups v2 CPU/memory/pids y módulos overlay/br_netfilter/vxlan disponibles. K3s **v1.37.2+k3s1**, containerd 2.3.7-k3s1. Nodo gigabyte-desktop Ready; CoreDNS, local-path-provisioner y metrics-server Running/Ready; job de CRDs Gateway API completado. No se añadieron componentes de F5.

Instalación realizada por el usuario mediante install.sh. Seis excepciones internas UFW autorizadas y aplicadas, manteniendo DROP en entrada/reenvío. [Reglas, revisión y reversión manual](../infra/k3s/FIREWALL_PROPOSAL.md); registro exacto en .local/f4/host-stage-20261116T184903Z. **No repetir prepare-host.py/install.sh, reinstalar ni duplicar/modificar UFW en este host.**

Fallo inicial: la plantilla contenía node-external-ip vacío; el journal confirmó IP inválida y el arranque agotó 180 s. Se omite ahora esa opción, validate_config.py la rechaza y tres pruebas de regresión pasan. El usuario corrigió la instalación y confirmó Ready. [Recuperación puntual](../infra/k3s/RECOVERY.md), sin borrados ni reinstalación.

Kubeconfig copiado por el usuario con install 0600/propietario usuario; endpoint privado accesible https://192.168.0.121:6443 y contexto default. Las tres imágenes app se exportaron a images.tar y el usuario las importó una vez con k3s ctr. Inventario del nodo, eventos «already present» y pods confirman uso de imágenes importadas; no se repitió importación.

## CI, herramientas e imágenes

`ci.yml`: push main, pull_request, workflow_dispatch y workflow_call. Contents:read, checkout sin credenciales persistidas, cachés npm/Maven/uv, concurrencia por workflow/ref y timeout 60 min. Actions por SHA; Node 26.13.1, Java Temurin de la línea 21 y uv 0.13.8/Python 3.12.16 fijados. setup-java conserva su SHA y resuelve un parche disponible de Java 21, sin fijar el build exacto. Ubuntu 24.04 es imagen mantenida del runner, no snapshot de SO inmutable.

Verifica Python sin datos reales, Maven verify, React build/lint, Dockerfiles/Compose, AST y DagBag real Airflow, workflows/Helm/Kubernetes y seis builds Docker. No recibe secretos del desarrollador ni infraestructura histórica. Artefacto CI: manifiestos sin secretos, retención siete días. Herramientas en scripts/ci/tools.lock.json con versión/URL/SHA256, descargadas solo a .local/f4/tools.

`publish.yml`: solo workflow_dispatch publish=true, main y propietario, CI previo, environment ghcr-release y packages:write únicamente en publicación. El usuario debe configurar sus protecciones/revisores antes de invocar; el nombre de environment no garantiza aprobación. Falla si no puede demostrar etiqueta libre; no sustituye imágenes existentes. No hay deploy automático ni kubeconfig en Actions. Durante el ensayo local no se invocaron Actions ni GHCR, y no hubo push/pull/remotos modificados. Después, el usuario informó el primer fallo GitHub en setup-java; la corrección a Java 21 aún requiere reejecución remota.

Imágenes retailops-{web,api,ml-service,mlflow,airflow,minio}. CI etiqueta `sha-<github.sha>`; build local usa huella de contenido mediante source_version.py. Seis imágenes construidas previamente; las tres app desplegadas conservan **sha-abd1044fc28d6be41e7a274183cc675899370aa8**. Base ML enlazada mediante ARG MLFLOW_BASE del mismo SHA, sin sobrescribir local-v1 Compose. Bases por digest, locks npm/uv y MinIO por revisión/checksum; Maven Wrapper/BOM fijados. No se verificó identidad bit a bit de builds ni independencia de repositorios externos.

## Reactivar el laboratorio conservado

No ejecutar inicialización, provisionadores, creación de Secrets, migraciones ni importaciones otra vez. Desde la raíz:

```bash
export PATH="$PWD/.local/f4/tools:$PATH"
export KUBECONFIG="$PWD/.local/f4/kubeconfig"
export KUBE_CONTEXT=default
export VALUES_FILE="$PWD/.local/f4/values.yaml"
kubectl --context "$KUBE_CONTEXT" get nodes
# Reutilizar dependencias y sus volúmenes; no --build:
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops --profile airflow \
  up -d --wait --wait-timeout 180 postgres minio mlflow airflow-api
# Terminal separada, mantener hasta el cierre:
python scripts/compose_bridge.py
```

En otra terminal con las mismas variables:

```bash
kubectl --context "$KUBE_CONTEXT" -n retailops scale \
  deployment/retailops-web deployment/retailops-api deployment/retailops-ml --replicas=1
scripts/deploy.sh rollout
scripts/deploy.sh forward # Terminal dedicada; 127.0.0.1:5174
# Terminal adicional:
python scripts/smoke_deployment.py
```

Airflow scheduler/dag processor no se arrancaron en F4: el ensayo usa únicamente API viewer e historial persistido, sin ejecutar/refrescar DAGs. No se afirma verificación de nueva ejecución Airflow en F4.

## Upgrade, ensayo y rollback

Para una nueva versión de software, compilar Java/React, construir con scripts/build_images.sh y otra etiqueta SHA; importar imágenes con sudo local si hace falta, revisar values y `scripts/deploy.sh upgrade`. Contexto explícito, validación Helm/esquemas y preflight de Secrets/PVC. Sin latest ni modelos diferentes de v1. No usar values-validation.yaml para instalar: contiene dominios .invalid.

Ensayo de configuración verificado con values de la release y **puerto 5174 libre**:

```bash
scripts/deploy.sh rehearse
```

Captura revisión anterior, cambia una marca de anotación web, espera rollout, abre su propio port-forward, ejecuta smoke, lo cierra, vuelve mediante Helm y repite smoke con una conexión nueva. La sustitución de un pod invalida un forward anterior; el script administra solo sus procesos. Ante error se detiene y conserva evidencia; no fuerza rollback después de un fallo sin diagnóstico.

Resultado real: **revisión 1 instalada → 2 actualizada → 3 Rollback to 1**, todas con misma imagen. Es rollback real de configuración; no se ensayó cambio de binarios ni rollback de datos/modelos. Para revisión manual:

```bash
scripts/deploy.sh status
REVISION=1 scripts/deploy.sh rollback # Elegir revisión existente tras inspeccionar history.
```

Tras rollback hubo tres Deployments disponibles, pods 1/1, cero reinicios y mismo PVC Bound. El scale a cero posterior es cierre operativo explícito, sin nueva revisión Helm ni eliminación de recursos.

## Evidencia y recursos medidos

Tres smokes completos aprobados: antes del ensayo, después de upgrade y después de rollback. Cada uno: HTML/bundle HTTP 200, Actuator UP, plataforma con dependencias UP/corte, bootstrap 1 297 296 filas, 54 tiendas/33 familias, 30 observaciones tienda 1/GROCERY I diciembre sin inventar Navidad; histórico enero rechazado 400, candidato v1/run original sin aprobación, cuatro DAGs visibles y predicción sin consentimiento rechazada 409. No es una nueva prueba visual de navegador.

Comparación SQL read-only antes/después: histórico/lotes/publicaciones, recuento/fechas/suma decimal de ventas, 9 106 020 features y cero etiquetas futuras/autorizaciones nuevas iguales. Roles de consulta API/trainer; releaser en transacción read-only solo para contar autorizaciones. Registro/métricas v1 iguales; **19 versiones de objetos MLflow con VersionId/ETag/tamaño iguales**. Cuatro volúmenes Docker conservan identidad/configuración. No se comparó hash completo de todas las tablas ni se ensayó backup/restore.

Muestras puntuales, no picos ni suma de memoria exclusiva:

| Componente | Memoria observada | CPU pods |
| --- | --- | --- |
| API Kubernetes | 170 MiB | 13m |
| ML Kubernetes | 194 MiB | 2m |
| Web Kubernetes | 10 MiB | 4m |
| PostgreSQL Compose | 78.47 MiB | — |
| MinIO Compose | 93.18 MiB | — |
| Airflow API Compose | 221.5 MiB | — |
| MLflow Compose | 994 MiB de límite 1 GiB | — |
| Unidad systemd K3s | ~3.13 GiB MemoryCurrent durante ensayo; ~3.09 GiB al cerrar | — |

MemoryCurrent incluye la contabilidad de su cgroup y cachés, no solo RSS de un proceso. MLflow estuvo próximo al límite; no hubo OOM ni reinicios. Requests app 550m/800 MiB, limits 5 CPU/1920 MiB; init ML solicita 10m/16 MiB durante preparación. Reservar margen para infraestructura/surge; no afirmar capacidad productiva a partir de este ensayo.

Evidencia privada .local/f4: node-before/system-before/system-after, helm-install.log, helm-history.json, rehearse.log, tres smoke-*.json, network-contract.log, data-before/data-before-drill/data-after/state-comparison, resources-*, workloads-after/workloads-stopped, volumes-before-kubernetes/volumes-after, dependencies-final, listeners-final y k3s-final. Configuración privada y modelos/datasets/logs quedan ignorados por Git.

## Diagnóstico y cierre conservador

`deploy.sh status`, `kubectl describe pod`, `kubectl logs deployment/retailops-{api,ml}` y eventos permiten diagnosticar. Revisar salidas localmente antes de compartirlas. ImagePullBackOff: etiqueta/importación containerd; Pending: PVC/StorageClass/recursos; ML no ready: contrato/registro/credencial regular 0600/endpoints; API 503: SQL o dependencia. No entrenar, ampliar permisos o cambiar cutoff para ocultar fallos.

Al cerrar, detener forwards propios y puente; escalar solo workloads app a cero y esperar terminación de pods; detener solo dependencias arrancadas por el ensayo. No borrar release, Secrets, namespace, PVC, volúmenes o caché; nunca down -v/prune/killall/uninstall.

Cierre verificado: tres Deployments 0/0, sin pods app, PVC Bound; PostgreSQL/MinIO/MLflow/Airflow API exited(0), sin OOM/reinicios; sin listeners puente/5174 ni puertos Compose del ensayo. K3s y componentes de sistema conservados, nodo Ready y autoarranque disabled. No se modificó UFW durante esta ejecución. CI remota/publicación, actualización de binarios, ejecución nueva de DAGs y recuperación de backups permanecen fuera de la evidencia de este cierre. No avanzar a F5.
