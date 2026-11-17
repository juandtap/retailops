#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.local/f4/tools:$PATH"
mkdir -p .local/f51
python -m unittest discover -s infra/observability/tests -v
python -m py_compile apps/ml-service/app/metrics.py infra/helm/retailops-observability/files/collector.py scripts/verify_observability.py
helm lint --strict infra/helm/retailops-observability
helm template retailops-observability infra/helm/retailops-observability -n retailops-observability > .local/f51/observability-rendered.yaml
helm template retailops infra/helm/retailops -n retailops -f infra/helm/retailops/values-validation.yaml --set observability.enabled=true > .local/f51/app-validation.yaml
kubeconform -strict -summary -kubernetes-version 1.37.0 .local/f51/observability-rendered.yaml .local/f51/app-validation.yaml infra/observability/storage.yaml
python - <<'PY'
from pathlib import Path
import json
pins=json.loads(Path("infra/observability/images.lock.json").read_text())
values=Path("infra/helm/retailops-observability/values.yaml").read_text()
assert all(ref in values for ref in pins.values()), "Digests de imagen inconsistentes"
queries=[]
for path in sorted(Path('infra/helm/retailops-observability/files/dashboards').glob('*.json')):
    dashboard=json.loads(path.read_text())
    assert dashboard['uid'] and dashboard['panels']
    queries += [target['expr'] for panel in dashboard['panels'] for target in panel['targets']]
rules={'groups':[{'name':'syntax_only','rules':[{'record':f'retailops_validation_query_{i}','expr':expr} for i,expr in enumerate(queries)]}]}
Path('.local/f51/dashboard-rules.json').write_text(json.dumps(rules)+'\n')
PY
prom_image=$(python -c 'import json; print(json.load(open("infra/observability/images.lock.json"))["prometheus"])')
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --entrypoint promtool \
  -v "$PWD/infra/helm/retailops-observability/files/prometheus.yml:/tmp/prometheus.yml:ro" "$prom_image" check config /tmp/prometheus.yml
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --entrypoint promtool \
  -v "$PWD/.local/f51/dashboard-rules.json:/tmp/rules.json:ro" "$prom_image" check rules /tmp/rules.json
