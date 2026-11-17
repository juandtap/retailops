#!/usr/bin/env bash
# F5.2: ningún sudo, instalador, importación, secreto ni dependencia Compose.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
: "${KUBE_CONTEXT:?Definir contexto K3s revisado}"
: "${KUBECONFIG:?Definir kubeconfig privado}"
K=(kubectl --context "$KUBE_CONTEXT" -n retailops-observability)
case "${1:-}" in
  prepare) "${K[@]}" apply -f infra/observability/logging-storage.yaml ;;
  start)
    : "${LOGGING_VALUES_FILE:?Values revisados con collectionAuthorized=true y replicas=1}"
    "${K[@]}" get nodes >/dev/null
    "$0" prepare
    helm --kube-context "$KUBE_CONTEXT" -n retailops-observability upgrade --install retailops-logging \
      infra/helm/retailops-logging -f "$LOGGING_VALUES_FILE" --wait --timeout 5m
    ;;
  forward) exec "${K[@]}" port-forward --address 127.0.0.1 service/loki 3101:3100 ;;
  status) "${K[@]}" get deployments,pods,pvc,services ;;
  stop)
    "${K[@]}" scale deployment/loki deployment/alloy --replicas=0
    "${K[@]}" wait --for=delete pods -l app.kubernetes.io/part-of=retailops-logging --timeout=90s
    ;;
  *) echo 'Uso: logging.sh prepare|start|forward|status|stop' >&2; exit 2 ;;
esac
