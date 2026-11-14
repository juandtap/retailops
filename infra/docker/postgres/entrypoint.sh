#!/bin/sh
set -eu
# Leer archivos 0600 antes de que el entrypoint oficial cambie al usuario postgres.
for role in admin control data api ingestor releaser trainer; do
  value="$(cat "/run/secrets/pg_${role}_password")"
  test -n "$value"
  upper="$(printf '%s' "$role" | tr '[:lower:]' '[:upper:]')"
  export "PG_${upper}_PASSWORD=$value"
done
export POSTGRES_PASSWORD="$PG_ADMIN_PASSWORD"
unset POSTGRES_PASSWORD_FILE
exec /usr/local/bin/docker-entrypoint.sh "$@"
