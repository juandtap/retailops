#!/usr/bin/env bash
# F5.5-A: validadores offline; nunca apply/upgrade/start, no pods ni incidentes.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
mkdir -p .local/f55-a
chmod 700 .local/f55-a
uv run --project apps/ml-service --locked python -m unittest discover -s infra/incident-lab/tests -v
uv run --project apps/ml-service --locked python -m py_compile scripts/incident_lab.py infra/incident-lab/controller.py infra/helm/retailops-incident-lab/files/gateway.py
helm lint --strict infra/helm/retailops-incident-lab -n retailops-incident-lab
helm template retailops-incident-lab infra/helm/retailops-incident-lab -n retailops-incident-lab > .local/f55-a/lab-rendered.yaml
helm template retailops-observability infra/helm/retailops-observability -n retailops-observability --set logging.enabled=true --set alerting.enabled=true --set incidentLab.enabled=true > .local/f55-a/observability-rendered.yaml
helm template retailops-logging infra/helm/retailops-logging -n retailops-observability --set collectionAuthorized=true --set incidentLab.enabled=true > .local/f55-a/logging-rendered.yaml
kubeconform -strict -summary -kubernetes-version 1.37.0 .local/f55-a/lab-rendered.yaml .local/f55-a/observability-rendered.yaml .local/f55-a/logging-rendered.yaml infra/incident-lab/namespace.yaml
uv run --project apps/ml-service --locked python - <<'PY'
from pathlib import Path
import json,yaml
base=Path('.local/f55-a')
objects=list(yaml.safe_load_all((base/'observability-rendered.yaml').read_text()))
config=next(o for o in objects if o and o['kind']=='ConfigMap' and o['metadata']['name']=='retailops-observability-config')['data']
(base/'prometheus.yml').write_text(config['prometheus.yml'])
assert '/etc/retailops/incident-rules.yml' in yaml.safe_load(config['prometheus.yml'])['rule_files']
config=next(o for o in yaml.safe_load_all((base/'logging-rendered.yaml').read_text()) if o and o['kind']=='ConfigMap' and o['metadata']['name']=='retailops-alloy-config')['data']['config']
(base/'config.alloy').write_text(config)
dashboard=json.loads(Path('infra/helm/retailops-observability/files/incident-lab/dashboard.json').read_text())
(base/'queries.json').write_text(json.dumps({'groups':[{'name':'syntax','rules':[{'record':f'incident_syntax_{i}','expr':p['targets'][0]['expr']} for i,p in enumerate(dashboard['panels'])]}]}))
PY
prom=$(sed -n 's/^  prometheus: //p' infra/helm/retailops-observability/values.yaml)
alloy=$(sed -n 's/^  alloy: //p' infra/helm/retailops-logging/values.yaml)
D=(docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges)
"${D[@]}" --entrypoint promtool -v "$PWD/.local/f55-a/prometheus.yml:/tmp/prometheus.yml:ro" \
  -v "$PWD/infra/helm/retailops-observability/files/alerting/rules.yml:/etc/retailops/rules.yml:ro" \
  -v "$PWD/infra/helm/retailops-observability/files/incident-lab/rules.yml:/etc/retailops/incident-rules.yml:ro" "$prom" check config /tmp/prometheus.yml
"${D[@]}" --entrypoint promtool -v "$PWD/.local/f55-a/queries.json:/tmp/queries.json:ro" "$prom" check rules /tmp/queries.json
"${D[@]}" --tmpfs /tmp:rw,noexec,nosuid,size=64m --entrypoint promtool -v "$PWD/infra/helm/retailops-observability/files/incident-lab:/rules:ro" -w /rules "$prom" test rules rules-tests.yml
"${D[@]}" -v "$PWD/.local/f55-a/config.alloy:/etc/alloy/incident.alloy:ro" "$alloy" validate /etc/alloy/incident.alloy
# Guardas de render: no hay bypass de namespace ni observers sin alerting.
if helm template bad infra/helm/retailops-incident-lab -n retailops > /dev/null 2>&1; then exit 1; fi
if helm template obs infra/helm/retailops-observability -n retailops-observability --set incidentLab.enabled=true > /dev/null 2>&1; then exit 1; fi
