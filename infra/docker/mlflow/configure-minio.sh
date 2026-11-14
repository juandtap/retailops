#!/bin/sh
set -eu
export MC_CONFIG_DIR=/tmp/mc
mc alias set local http://minio:9000 "$(cat /run/secrets/minio_root_user)" "$(cat /run/secrets/minio_root_password)" >/dev/null
mc mb --ignore-existing local/retailops-mlflow >/dev/null
mc anonymous set none local/retailops-mlflow >/dev/null
mc version enable local/retailops-mlflow >/dev/null
mc admin policy create local retailops-mlflow /tools/mlflow-policy.json >/dev/null
mc admin user add local "$(cat /run/secrets/minio_mlflow_user)" "$(cat /run/secrets/minio_mlflow_password)" >/dev/null
mc admin policy attach local retailops-mlflow --user "$(cat /run/secrets/minio_mlflow_user)" >/dev/null
printf '%s\n' 'Bucket MLflow privado/versionado e identidad separada preparados.'
