#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --project apps/ml-service --locked python -m unittest discover -s infra/backup/tests -v
uv run --project apps/ml-service --locked python -m py_compile infra/backup/core.py scripts/backup_recovery.py
# Solo contratos/configuración estáticos; nunca verify/persistence de entorno vacío.
python scripts/storage_contracts.py
python -m unittest discover -s infra/docker/tests -v
