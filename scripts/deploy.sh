#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
# Cada operación mutadora exige contexto explícito, sin elegir otro cluster.
: "${KUBE_CONTEXT:?Definir el contexto K3s local revisado}"
K=(kubectl --context "$KUBE_CONTEXT" -n retailops)
H=(helm --kube-context "$KUBE_CONTEXT" -n retailops)
# Cada smoke abre/cierra su propio forward: una actualización sustituye el pod web.
smoke_with_forward() {
  python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",5174)); s.close()'
  local forward_log
  forward_log=$(mktemp "$PWD/.local/f4/forward-smoke.XXXXXX")
  "${K[@]}" port-forward --address 127.0.0.1 service/web 5174:80 > "$forward_log" 2>&1 &
  owned_forward_pid=$!
  trap 'kill "$owned_forward_pid" 2>/dev/null || true; wait "$owned_forward_pid" 2>/dev/null || true' EXIT
  python - <<'READY'
import time, urllib.request
for attempt in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:5174/api/actuator/health', timeout=2) as response:
            if response.status == 200: break
    except OSError:
        time.sleep(0.25)
else:
    raise RuntimeError('Port-forward o API no disponible para smoke')
READY
  python scripts/smoke_deployment.py
  kill "$owned_forward_pid" 2>/dev/null || true
  wait "$owned_forward_pid" 2>/dev/null || true
  trap - EXIT
}

case "${1:-}" in
  validate)
    : "${VALUES_FILE:?Ruta a values privados ignorados}"
    helm lint --strict infra/helm/retailops -f "$VALUES_FILE"
    helm template retailops infra/helm/retailops -n retailops -f "$VALUES_FILE" | kubeconform -strict -summary -kubernetes-version 1.37.0
    ;;
  preflight)
    "${K[@]}" get nodes -o json | python -c 'import json,sys; nodes=json.load(sys.stdin)["items"]; assert len(nodes)==1 and any(c["type"]=="Ready" and c["status"]=="True" for c in nodes[0]["status"]["conditions"]), "Se requiere un nodo local Ready"'
    storage_class=$("${K[@]}" get pvc retailops-inference-cache -o jsonpath='{.spec.storageClassName}')
    binding_mode=$("${K[@]}" get storageclass "$storage_class" -o jsonpath='{.volumeBindingMode}')
    "${K[@]}" get pvc retailops-inference-cache -o json | PVC_BINDING_MODE="$binding_mode" python -c 'import json,os,sys; p=json.load(sys.stdin); phase=p.get("status",{}).get("phase"); assert phase=="Bound" or (phase=="Pending" and os.environ["PVC_BINDING_MODE"]=="WaitForFirstConsumer"), "PVC requiere revisión"'
    "${K[@]}" get secret retailops-api -o json | python -c 'import base64,json,sys; d=json.load(sys.stdin)["data"]; assert base64.b64decode(d["pg_api_password"]).strip(); r=json.loads(base64.b64decode(d["airflow_reader.json"])); assert r["username"].strip() and r["password"].strip(), "Viewer vacío"'
    "${K[@]}" get secret retailops-trainer -o json | python -c 'import base64,json,sys; assert base64.b64decode(json.load(sys.stdin)["data"]["pg_trainer_password"]).strip(), "Trainer vacío"'
    echo 'Nodo Ready, PVC compatible con su modo de asignación y claves requeridas presentes; valores no mostrados.' 
    ;;
  upgrade)
    "$0" validate
    "$0" preflight
    "${H[@]}" upgrade --install retailops infra/helm/retailops -f "$VALUES_FILE" --wait --timeout 10m --history-max 5
    "$0" rollout
    ;;
  rollout)
    for name in web api ml; do "${K[@]}" rollout status "deployment/retailops-$name" --timeout=600s; done
    ;;
  status)
    "${K[@]}" get pods,svc,pvc
    "${K[@]}" get events --sort-by=.metadata.creationTimestamp
    "${H[@]}" history retailops
    ;;
  rollback)
    : "${REVISION:?Definir revisión anterior revisada con helm history}"
    [[ "$REVISION" =~ ^[1-9][0-9]*$ ]] || exit 1
    "${H[@]}" rollback retailops "$REVISION" --wait --timeout 10m
    "$0" rollout
    ;;
  rehearse)
    # Configuración del frontend: sin cambios de modelo, datos o migraciones.
    "$0" validate
    revision=$("${H[@]}" history retailops -o json | python -c 'import json,sys; print(json.load(sys.stdin)[-1]["revision"])')
    marker="drill-$(date -u +%Y%m%dT%H%M%SZ)"
    echo "Revisión previa: $revision; ensayo: $marker"
    "${H[@]}" upgrade retailops infra/helm/retailops -f "$VALUES_FILE" --set-string "rolloutMarker=$marker" --wait --timeout 10m
    "$0" rollout
    smoke_with_forward
    REVISION="$revision" "$0" rollback
    smoke_with_forward
    ;;
  forward) exec "${K[@]}" port-forward --address 127.0.0.1 service/web 5174:80 ;;
  *) echo 'Uso: deploy.sh validate|preflight|upgrade|rollout|status|rollback|rehearse|forward' >&2; exit 2 ;;
esac
