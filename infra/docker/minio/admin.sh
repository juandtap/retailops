#!/bin/sh
set -eu
export MC_CONFIG_DIR=/tmp/mc
root_user="$(cat /run/secrets/minio_root_user)"
root_password="$(cat /run/secrets/minio_root_password)"
# Credenciales solo en memoria y configuración efímera, sin shell tracing.
mc alias set local "$MINIO_ENDPOINT" "$root_user" "$root_password" >/dev/null
case "${1:-configure}" in
  configure)
    for bucket in retailops-quarantine retailops-released retailops-artifacts retailops-verification; do
      mc mb --ignore-existing "local/$bucket" >/dev/null
      mc anonymous set none "local/$bucket" >/dev/null
      mc version enable "local/$bucket" >/dev/null
    done
    for role in ingestor releaser trainer; do
      mc admin policy create local "retailops-$role" "/policies/$role.json" >/dev/null
      username="$(cat /run/secrets/minio_${role}_user)"
      password="$(cat /run/secrets/minio_${role}_password)"
      mc admin user add local "$username" "$password" >/dev/null
      mc admin policy attach local "retailops-$role" --user "$username" >/dev/null
    done
    printf '%s\n' 'Buckets privados/versionados e identidades configurados; ningún dato publicado.'
    ;;
  check)
    username="$(cat /run/secrets/minio_trainer_user)"
    password="$(cat /run/secrets/minio_trainer_password)"
    mc alias set trainer "$MINIO_ENDPOINT" "$username" "$password" >/dev/null
    mc ls trainer/retailops-released >/dev/null
    expect_denied() {
      if "$@" >/dev/null 2>/tmp/denied; then echo 'ERROR: operación no autorizada permitida'; exit 1; fi
      if ! grep -Eqi 'Access[[:space:]]*Denied|Insufficient permissions' /tmp/denied; then cat /tmp/denied >&2; exit 1; fi
    }
    key="_checks/access-$(cat /proc/sys/kernel/random/uuid)"
    # Fixtures técnicas temporales; nunca son particiones ni una ingesta exitosa.
    cleanup() {
      mc rm --force --versions "local/retailops-quarantine/$key" >/dev/null 2>&1 || true
      mc rm --force --versions "local/retailops-released/$key" >/dev/null 2>&1 || true
    }
    trap cleanup EXIT
    printf '%s' 'access-check-only' | mc pipe "local/retailops-quarantine/$key" >/dev/null
    printf '%s' 'access-check-only' | mc pipe "local/retailops-released/$key" >/dev/null
    test "$(mc cat "trainer/retailops-released/$key")" = access-check-only
    expect_denied mc cat "trainer/retailops-quarantine/$key"
    printf '%s' 'denied' | expect_denied mc pipe "trainer/retailops-released/$key"
    for role in ingestor releaser; do
      username="$(cat /run/secrets/minio_${role}_user)"
      password="$(cat /run/secrets/minio_${role}_password)"
      mc alias set "$role" "$MINIO_ENDPOINT" "$username" "$password" >/dev/null
      test "$(mc cat "$role/retailops-quarantine/$key")" = access-check-only
    done
    printf '%s' 'denied' | expect_denied mc pipe "ingestor/retailops-released/$key"
    cleanup
    trap - EXIT
    if mc ls trainer/retailops-quarantine >/dev/null 2>&1; then echo 'ERROR: acceso futuro permitido'; exit 1; fi
    if mc stat trainer/retailops-quarantine/raw/__verification__/future >/dev/null 2>&1; then echo 'ERROR: lectura futura permitida'; exit 1; fi
    # Prueba de persistencia administrativa, fuera de RAW/BRONZE y sin contenido de dataset.
    if ! mc stat local/retailops-verification/infrastructure-marker >/dev/null 2>&1; then
      printf '%s' 'retailops-infrastructure-check-v1' | mc pipe local/retailops-verification/infrastructure-marker >/dev/null
    fi
    test "$(mc cat local/retailops-verification/infrastructure-marker)" = retailops-infrastructure-check-v1
    for bucket in retailops-quarantine retailops-released retailops-artifacts; do
      test -z "$(mc ls --recursive --versions "local/$bucket")"
    done
    printf '%s\n' 'MinIO: buckets de datos vacíos; entrenador limitado a released; marcador administrativo persistente.'
    ;;
  fingerprint)
    mc stat --json local/retailops-verification/infrastructure-marker
    ;;
  *) echo 'Operación desconocida'  >&2; exit 2 ;;
esac
