#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IMAGE_TAG:?Definir IMAGE_TAG=sha- seguido de 40 dígitos hexadecimales}"
[[ "$IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]] || { echo 'Etiqueta inválida' >&2; exit 1; }
for image in mlflow ml-service api web airflow minio; do
  if docker image inspect "retailops-$image:$IMAGE_TAG" > /dev/null 2>&1; then
    echo "Etiqueta existente: retailops-$image:$IMAGE_TAG; usar una versión nueva." >&2
    exit 1
  fi
done
# Ejecutar npm build y Maven package/verify antes. Sin secretos de build.
docker build -f infra/docker/mlflow/Dockerfile -t "retailops-mlflow:$IMAGE_TAG" .
docker build --build-arg "MLFLOW_BASE=retailops-mlflow:$IMAGE_TAG" -f infra/docker/app/Dockerfile.ml -t "retailops-ml-service:$IMAGE_TAG" .
docker build -f infra/docker/app/Dockerfile.api -t "retailops-api:$IMAGE_TAG" .
docker build -f infra/docker/app/Dockerfile.web -t "retailops-web:$IMAGE_TAG" .
docker build -f infra/docker/airflow/Dockerfile -t "retailops-airflow:$IMAGE_TAG" .
docker build -t "retailops-minio:$IMAGE_TAG" infra/docker/minio
