#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
mkdir -p .local/f52
helm lint --strict infra/helm/retailops-logging
helm template retailops-logging infra/helm/retailops-logging -n retailops-observability --set collectionAuthorized=true > .local/f52/logging-rendered.yaml
helm template retailops-observability infra/helm/retailops-observability -n retailops-observability --set logging.enabled=true > .local/f52/observability-rendered.yaml
kubeconform -strict -summary -kubernetes-version 1.37.0 .local/f52/logging-rendered.yaml .local/f52/observability-rendered.yaml infra/observability/logging-storage.yaml
loki=$(sed -n 's/^  loki: //p' infra/helm/retailops-logging/values.yaml)
alloy=$(sed -n 's/^  alloy: //p' infra/helm/retailops-logging/values.yaml)
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD/infra/helm/retailops-logging/files/loki.yaml:/etc/loki/f52.yaml:ro" "$loki" -config.file=/etc/loki/f52.yaml -verify-config=true
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD/infra/helm/retailops-logging/files/config.alloy:/etc/alloy/config.alloy:ro" "$alloy" validate /etc/alloy/config.alloy
