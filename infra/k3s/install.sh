#!/usr/bin/env bash
# Preparación revisable; NO ejecutar sin autorización de instalación del host.
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ "${AUTHORIZE_HOST_INSTALL:-}" == 'install-k3s' ]] || { echo 'Requiere autorización explícita para modificar el host.' >&2; exit 1; }
[[ "$EUID" == 0 ]] || { echo 'La instalación requiere root.' >&2; exit 1; }
[[ -f .local/f4/k3s-config.yaml ]] || { echo 'Preparar y revisar config local primero.' >&2; exit 1; }
[[ ! -e /etc/rancher/k3s/config.yaml && ! -e /usr/local/bin/k3s ]] || { echo 'Instalación existente: inspeccionar y reutilizar.' >&2; exit 1; }
# Descargado primero: el operador puede revisar el instalador antes de ejecutarlo.
[[ -f .local/f4/tools/k3s-install ]] || { echo 'Ejecutar scripts/ci/install_tools.py y revisar el instalador fijado antes.' >&2; exit 1; }
# Validar antes de copiar configuración o ejecutar el instalador.
python infra/k3s/validate_config.py .local/f4/k3s-config.yaml
python - <<'CHECK'
import hashlib, json
from pathlib import Path
spec = json.loads(Path('scripts/ci/tools.lock.json').read_text())['k3s-install']
assert hashlib.sha256(Path('.local/f4/tools/k3s-install').read_bytes()).hexdigest() == spec['sha256'], 'Checksum del instalador inválido'
CHECK
install -D -m 600 .local/f4/k3s-config.yaml /etc/rancher/k3s/config.yaml
INSTALL_K3S_SKIP_ENABLE=true INSTALL_K3S_VERSION='v1.37.2+k3s1' INSTALL_K3S_SKIP_START=true sh .local/f4/tools/k3s-install server
# No arrancar automáticamente: revisar red/firewall/configuración antes.
