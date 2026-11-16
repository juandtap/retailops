# Excepciones internas autorizadas condicionalmente — no aplicadas

Inspección del 2026-11-16: UFW habilitado y activo, entrada/reenvío DROP y salida ACCEPT; archivos user.rules/user6.rules sin reglas de usuario. No se pudo consultar el ruleset efectivo: requiere root y `sudo -n true` solicita contraseña. No se instaló ni arrancó K3s. La autorización de instalación ya existe; esta propuesta requiere autorización adicional de firewall conforme al límite expreso del usuario.

Primero obtener evidencia efectiva, sin cambiar configuración, desde la terminal del usuario:

```bash
sudo bash infra/k3s/preflight-root.sh
```

El script guarda un informe privado 0600 en `.local/f4/firewall-live.*`, sin imprimir reglas ni solicitar contraseñas a través del asistente. No concede privilegios a esta sesión. El usuario introduce la contraseña únicamente en su terminal; no debe compartirla. El informe permitirá confirmar si hay excepciones dinámicas existentes y revisar el orden de cadenas Docker/UFW antes de aplicar reglas.

Si la revisión confirma que faltan excepciones, se propone autorizar únicamente estos flujos IPv4 en este nodo:

| Flujo | Restricción |
| --- | --- |
| Pods → API Kubernetes | Entrada cni0, origen 10.42/16, destino 192.168.0.121 TCP 6443 |
| Pods → kubelet/metrics-server | Entrada cni0, origen 10.42/16, destino 192.168.0.121 TCP 10250 |
| Pods → puente Compose | Entrada cni0, origen 10.42/16, destino 10.42.0.1 TCP 15432/15000/19000/18081 |
| Pods → pods | Reenvío cni0 → cni0, origen y destino 10.42/16 |
| CoreDNS → DNS observado del router | Reenvío cni0 → enp6s0, origen 10.42/16, destino 192.168.0.1 TCP/UDP 53 |

Comandos revisables, **no ejecutados**; no copiarlos antes de aprobar la propuesta y revisar el informe efectivo:

```bash
sudo ufw allow in on cni0 proto tcp from 10.42.0.0/16 to 192.168.0.121 port 6443 comment 'RetailOps K3s pods API'
sudo ufw allow in on cni0 proto tcp from 10.42.0.0/16 to 192.168.0.121 port 10250 comment 'RetailOps K3s pods kubelet'
sudo ufw allow in on cni0 proto tcp from 10.42.0.0/16 to 10.42.0.1 port 15432,15000,19000,18081 comment 'RetailOps Compose bridge'
sudo ufw route allow in on cni0 out on cni0 from 10.42.0.0/16 to 10.42.0.0/16 comment 'RetailOps same-node pods'
sudo ufw route allow in on cni0 out on enp6s0 proto udp from 10.42.0.0/16 to 192.168.0.1 port 53 comment 'RetailOps pod DNS UDP'
sudo ufw route allow in on cni0 out on enp6s0 proto tcp from 10.42.0.0/16 to 192.168.0.1 port 53 comment 'RetailOps pod DNS TCP'
```

Son excepciones propuestas para la topología inspeccionada, **no una configuración ya probada**. Mantienen políticas DROP, sin permitir nuevas conexiones entrantes por Ethernet/Wi-Fi ni abrir VXLAN a la LAN. No habilitan salida general de pods a Internet. K3s/CNI/kube-proxy también crean reglas NAT/forwarding y rutas propias de las redes del clúster: se debe aceptar ese efecto dentro de la operación K3s y revisar su interacción con UFW/Docker. No modificar rutas por defecto ni políticas globales. Cualquier necesidad adicional requiere revisión y autorización específica.

La autenticación administrativa local sigue siendo un requisito independiente. La aprobación del usuario dentro de la conversación no hace que sudo deje de requerir contraseña. No usar Docker u otros mecanismos para eludir esa barrera.

Referencia: [requisitos oficiales K3s para UFW y red](https://docs.k3s.io/installation/requirements). Se propone un alcance más acotado a este nodo que las aperturas generales del ejemplo oficial; debe verificarse con las reglas efectivas.

## Revisión efectiva y ejecución autorizada

El usuario autorizó condicionalmente estos seis flujos. Se revisó firewall-live.R6bO63: DROP efectivo IPv4/IPv6, cadenas de usuario vacías y reglas Docker solo para sus bridges; no hay equivalentes observados. La red sigue coincidiendo con la propuesta. DNS Docker y HTTPS host pasan antes de cambios. Falta autenticación sudo local; no falta autorización de estos flujos. Aplicadas: **cero**.

`sudo python infra/k3s/prepare-host.py` revalida reglas/topología, registra cada adición y continúa la instalación ya autorizada mediante install.sh. Si el ruleset cambió respecto al revisado, se detiene sin aplicar reglas. No ejecutar parcialmente y repetir sin revisar evidencia. El script no borra reglas ni cambia políticas globales.

Comandos de reversión manual de las seis reglas propuestas, **solo si la evidencia confirma que esta etapa las añadió**; no ejecutarlos sobre reglas preexistentes o sin revisar el estado actual. No forman parte del cierre automático de F4:

```bash
sudo ufw route delete allow in on cni0 out on enp6s0 proto tcp from 10.42.0.0/16 to 192.168.0.1 port 53 comment 'RetailOps pod DNS TCP'
sudo ufw route delete allow in on cni0 out on enp6s0 proto udp from 10.42.0.0/16 to 192.168.0.1 port 53 comment 'RetailOps pod DNS UDP'
sudo ufw route delete allow in on cni0 out on cni0 from 10.42.0.0/16 to 10.42.0.0/16 comment 'RetailOps same-node pods'
sudo ufw delete allow in on cni0 proto tcp from 10.42.0.0/16 to 10.42.0.1 port 15432,15000,19000,18081 comment 'RetailOps Compose bridge'
sudo ufw delete allow in on cni0 proto tcp from 10.42.0.0/16 to 192.168.0.121 port 10250 comment 'RetailOps K3s pods kubelet'
sudo ufw delete allow in on cni0 proto tcp from 10.42.0.0/16 to 192.168.0.121 port 6443 comment 'RetailOps K3s pods API'
```

Consultar primero `sudo ufw status numbered` y el registro privado applied-N.json/revert-proposed.txt. La retirada de reglas no elimina rutas/CNI ni restaura datos; no usar flush/reset/disable ni restaurar snapshots completos sobre reglas nuevas de otros servicios.
