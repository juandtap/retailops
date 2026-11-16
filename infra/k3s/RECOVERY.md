# Recuperar el arranque existente tras node-external-ip vacío

No volver a ejecutar prepare-host.py ni install.sh sobre esta instalación. Las seis reglas UFW ya están aplicadas; no repetirlas ni reinstalar K3s.

La plantilla inicial incluía `node-external-ip: ""`, que K3s v1.37.2+k3s1 rechaza como IP inválida. La opción debe omitirse en este laboratorio. El repositorio y la configuración privada preparatoria ya están corregidos; no se modificó automáticamente `/etc/rancher/k3s/config.yaml`.

Estado observado después del fallo comunicado: systemd muestra **active/running**, Result=success y UnitFileState=disabled, con un arranque posterior al fallo a las 13:59:54 America/Guayaquil. El journal confirma los errores anteriores. La configuración instalada es 0600 y no fue legible por el asistente. No se conoce todavía el estado Ready ni se presume que la configuración instalada haya sido corregida.

Si ya corregiste y arrancaste K3s, comprueba directamente:

```bash
sudo /usr/local/bin/k3s kubectl --server=https://192.168.0.121:6443 wait --for=condition=Ready nodes --all --timeout=180s
```

Si la configuración instalada todavía contiene exactamente la opción vacía, estos son los cambios mínimos; la primera orden conserva una copia con sufijo temporal y retira únicamente esa línea:

```bash
sudo sed -i."$(date -u +%Y%m%dT%H%M%SZ)".bak '/^[[:space:]]*node-external-ip:[[:space:]]*""[[:space:]]*$/d' /etc/rancher/k3s/config.yaml
sudo systemctl restart k3s
sudo /usr/local/bin/k3s kubectl --server=https://192.168.0.121:6443 wait --for=condition=Ready nodes --all --timeout=180s
```

No cambiar node-ip, interfaz, puertos, reglas UFW o políticas de seguridad. No ejecutar enable, uninstall, killall, flush, borrados ni migraciones. La corrección no requiere daemon-reload: solo cambia configuración de K3s, no su unidad systemd. Si vuelve a fallar, conservar estado y consultar localmente `sudo journalctl -u k3s -n 50 --no-pager`, revisando posibles secretos antes de compartir salida.

Tras confirmación del usuario de Ready, continuar desde kubeconfig/importación de imágenes, no desde bootstrap del host. Todavía pendientes Helm/readiness app/smoke/rollout/rollback y cierre conservador. Las siguientes operaciones privilegiadas se proporcionarán exactamente para ejecutar en la terminal local; no suponer que sudo está disponible al asistente.
