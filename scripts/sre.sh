#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
: "${KUBE_CONTEXT:?Contexto explícito requerido}"
: "${KUBECONFIG:?Kubeconfig privado requerido}"
K=(kubectl --context "$KUBE_CONTEXT" -n retailops-observability)
case "${1:-}" in
  start)
    python scripts/sre_state.py prepare
    "${K[@]}" apply -f infra/observability/alerting-storage.yaml
    helm --kube-context "$KUBE_CONTEXT" -n retailops-observability upgrade retailops-observability \
      infra/helm/retailops-observability --set logging.enabled=true --set alerting.enabled=true --wait --timeout 5m
    ;;
  active) python scripts/sre_state.py active ;;
  inactive) python scripts/sre_state.py inactive ;;
  alertmanager) exec "${K[@]}" port-forward --address 127.0.0.1 service/alertmanager 9094:9093 ;;
  receiver) exec "${K[@]}" port-forward --address 127.0.0.1 service/alert-receiver 8091:8090 ;;
  stop)
    # Ejecutar primero inactive y verificar señal en Prometheus antes de cerrar apps.
    "${K[@]}" scale deployment/alertmanager deployment/alert-receiver --replicas=0
    "${K[@]}" wait --for=delete pods -l 'app.kubernetes.io/part-of=retailops-observability,app.kubernetes.io/component in (alertmanager,alert-receiver)' --timeout=90s
    ;;
  status) "${K[@]}" get deployments,pods,pvc ;;
  *) echo 'Uso: sre.sh start|active|inactive|alertmanager|receiver|status|stop' >&2; exit 2 ;;
esac
