#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
mkdir -p .local/f53
python -m unittest discover -s infra/observability/tests -v
python -m py_compile scripts/sre_state.py infra/helm/retailops-observability/files/alerting/receiver.py
helm lint --strict infra/helm/retailops-observability --set logging.enabled=true --set alerting.enabled=true
helm template retailops-observability infra/helm/retailops-observability -n retailops-observability --set logging.enabled=true --set alerting.enabled=true > .local/f53/observability-rendered.yaml
kubeconform -strict -summary -kubernetes-version 1.37.0 .local/f53/observability-rendered.yaml infra/observability/alerting-storage.yaml
python - <<'PY'
from pathlib import Path
import json
base=Path('infra/helm/retailops-observability/files')
Path('.local/f53/prometheus.yml').write_text((base/'prometheus.yml').read_text()+(base/'alerting/prometheus-extra.yml').read_text())
dashboard=json.loads((base/'alerting/dashboard.json').read_text())
Path('.local/f53/dashboard-rules.json').write_text(json.dumps({'groups':[{'name':'syntax_only','rules':[{'record':f'validation_sre_query_{i}','expr':p['targets'][0]['expr']} for i,p in enumerate(dashboard['panels'])]}]}))
PY
prom=$(sed -n 's/^  prometheus: //p' infra/helm/retailops-observability/values.yaml)
am=$(sed -n 's/^  image: //p' infra/helm/retailops-observability/values.yaml)
D=(docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL --security-opt no-new-privileges)
"${D[@]}" --entrypoint promtool -v "$PWD/.local/f53/prometheus.yml:/tmp/prometheus.yml:ro" \
  -v "$PWD/infra/helm/retailops-observability/files/alerting/rules.yml:/etc/retailops/rules.yml:ro" "$prom" check config /tmp/prometheus.yml
"${D[@]}" --entrypoint promtool -v "$PWD/infra/helm/retailops-observability/files/alerting:/rules:ro" -w /rules "$prom" test rules rules-tests.yml
"${D[@]}" --entrypoint promtool -v "$PWD/.local/f53/dashboard-rules.json:/tmp/rules.json:ro" "$prom" check rules /tmp/rules.json
"${D[@]}" --entrypoint /bin/amtool -v "$PWD/infra/helm/retailops-observability/files/alerting/alertmanager.yml:/tmp/alertmanager.yml:ro" "$am" check-config /tmp/alertmanager.yml
