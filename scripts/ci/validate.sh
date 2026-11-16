#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$PWD/.local/f4/tools:$PATH"
mkdir -p .local/f4
python scripts/ci/check_dags.py
python infra/k3s/validate_config.py infra/k3s/config.yaml.example
python -m unittest discover -s infra/k3s/tests -p 'test_*.py'
bash -n infra/k3s/install.sh infra/k3s/preflight-root.sh scripts/deploy.sh scripts/build_images.sh
# Compile sin importar ni ejecutar pipelines o entrenamiento.
python -m compileall -q apps/ml-service/app pipelines/orchestration infra/airflow/dags infra/k3s scripts/ci
compose --env-file .env.example -f infra/docker/compose.yaml --profile app --profile airflow --profile mlops config --quiet
# Advertencias heredadas de apt/pip: no ocultar errores.
hadolint --failure-threshold error infra/docker/app/Dockerfile.* infra/docker/airflow/Dockerfile infra/docker/mlflow/Dockerfile infra/docker/minio/Dockerfile
helm lint --strict infra/helm/retailops -f infra/helm/retailops/values-validation.yaml
helm template retailops infra/helm/retailops -n retailops -f infra/helm/retailops/values-validation.yaml > .local/f4/rendered.yaml
# Values inseguros/incompletos deben fallar.
if helm template retailops infra/helm/retailops > /dev/null 2>&1; then echo 'Values incompletos aceptados' >&2; exit 1; fi
if helm template retailops infra/helm/retailops -f infra/helm/retailops/values-validation.yaml --set images.api.tag=latest > /dev/null 2>&1; then exit 1; fi
kubeconform -strict -summary -kubernetes-version 1.37.0 .local/f4/rendered.yaml infra/k3s/namespace.yaml infra/k3s/cache.yaml
actionlint
