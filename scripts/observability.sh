#!/usr/bin/env bash
# Operación local; no instala K3s, no importa imágenes y no cambia UFW.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
: "${KUBE_CONTEXT:?Definir contexto K3s local revisado}"
: "${KUBECONFIG:?Definir kubeconfig privado}"
K=(kubectl --context "$KUBE_CONTEXT")
H=(helm --kube-context "$KUBE_CONTEXT" -n retailops-observability)
D=(docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops --profile airflow)
case "${1:-}" in
  prepare)
    "${K[@]}" apply -f infra/observability/storage.yaml
    if ! "${K[@]}" -n retailops-observability get secret retailops-grafana-admin -o name >/dev/null 2>&1; then
      python - <<'PY'
from pathlib import Path
import secrets
base=Path('.local/f51');base.mkdir(exist_ok=True,mode=0o700);base.chmod(0o700)
for name,value in [('grafana-admin-user','admin'),('grafana-admin-password',secrets.token_urlsafe(32))]:
    path=base/name
    if not path.exists():
        with path.open('x') as file:file.write(value+'\n')
        path.chmod(0o600)
PY
      "${K[@]}" -n retailops-observability create secret generic retailops-grafana-admin \
        --from-file=admin-user=.local/f51/grafana-admin-user --from-file=admin-password=.local/f51/grafana-admin-password
    fi
    ;;
  start)
    : "${VALUES_FILE:?Ruta a values app instrumentados, con observability.enabled=true}"
    "$0" prepare
    # Validar inventario antes de iniciar dependencias; no importar otra vez.
    helm template retailops infra/helm/retailops -n retailops -f "$VALUES_FILE" > .local/f51/start-app.yaml
    python - <<'PY'
from pathlib import Path
import json,os,re,subprocess
node=json.loads(subprocess.check_output(['kubectl','--context',os.environ['KUBE_CONTEXT'],'get','nodes','-o','json']))
names={n for item in node['items'] for image in item['status']['images'] for n in image['names']}
images=set(re.findall(r'^\s+image: "([^"]+)"',Path('.local/f51/start-app.yaml').read_text(),re.M))
assert images and all('docker.io/library/'+image in names or image in names for image in images),'Falta importar imagen: solicitar sudo local, no instalar'
PY
    "${D[@]}" up -d --wait --wait-timeout 180 postgres minio mlflow airflow-api
    "${H[@]}" upgrade --install retailops-observability infra/helm/retailops-observability --wait --timeout 5m
    # El puente se mantiene en otra terminal, con su ciclo de vida explícito.
    echo 'Iniciar python scripts/compose_bridge.py en otra terminal antes de deploy-app.'
    ;;
  deploy-app)
    : "${VALUES_FILE:?Ruta a values instrumentados}"
    scripts/deploy.sh upgrade
    ;;
  status)
    "${K[@]}" -n retailops-observability get deployments,pods,pvc,services
    "${K[@]}" -n retailops get deployments,pods,pvc
    "${H[@]}" history retailops-observability
    ;;
  prometheus) exec "${K[@]}" -n retailops-observability port-forward --address 127.0.0.1 service/prometheus 9091:9090 ;;
  grafana) exec "${K[@]}" -n retailops-observability port-forward --address 127.0.0.1 service/grafana 3001:3000 ;;
  verify) exec python scripts/verify_observability.py ;;
  stop)
    "${K[@]}" -n retailops scale deployment/retailops-web deployment/retailops-api deployment/retailops-ml --replicas=0
    "${K[@]}" -n retailops wait --for=delete pods --all --timeout=90s
    "${K[@]}" -n retailops-observability scale deployment/prometheus deployment/grafana deployment/collector --replicas=0
    "${K[@]}" -n retailops-observability wait --for=delete pods --all --timeout=90s
    # Invocar solo cuando esas dependencias se hayan iniciado para el laboratorio.
    "${D[@]}" stop airflow-api mlflow minio postgres
    echo 'Cerrar con Ctrl-C únicamente los forwards/puente iniciados para esta sesión; conservar PVC/Secrets/releases.'
    ;;
  *) echo 'Uso: observability.sh prepare|start|deploy-app|status|prometheus|grafana|verify|stop' >&2; exit 2 ;;
esac
