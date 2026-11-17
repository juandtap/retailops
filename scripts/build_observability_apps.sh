#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IMAGE_TAG:?Definir SHA de contenido de F5.1}"
[[ "$IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]] || exit 1
for image in api ml-service web; do
  if docker image inspect "retailops-$image:$IMAGE_TAG" > /dev/null 2>&1; then
    echo "Conservar etiqueta existente: retailops-$image:$IMAGE_TAG" >&2
    exit 1
  fi
done
# Reutilizar base MLflow inmutable de F4; nunca reconstruir/alterar su servicio.
docker build -f infra/docker/app/Dockerfile.api -t "retailops-api:$IMAGE_TAG" .
docker build -f infra/docker/app/Dockerfile.ml -t "retailops-ml-service:$IMAGE_TAG" .
docker build -f infra/docker/app/Dockerfile.web -t "retailops-web:$IMAGE_TAG" .
