#!/usr/bin/env bash
# Inspección privilegiada de solo lectura; no instala ni cambia reglas/servicios.
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ "$EUID" == 0 ]] || { echo 'Ejecutar con sudo en una terminal local.' >&2; exit 1; }
[[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]] || { echo 'Usar sudo desde la cuenta operadora.' >&2; exit 1; }
[[ -d .local/f4 && ! -L .local/f4 ]] || exit 1
umask 077
report=$(mktemp "$PWD/.local/f4/firewall-live.XXXXXX")
trap 'chown "$SUDO_UID:$SUDO_GID" "$report"; chmod 600 "$report"' EXIT
{
  date -u --iso-8601=seconds
  ufw status verbose
  iptables-save
  ip6tables-save
  nft list ruleset
} > "$report" 2>&1
chown "$SUDO_UID:$SUDO_GID" "$report"
chmod 600 "$report"
printf 'Informe privado creado: %s\n' "$report"
