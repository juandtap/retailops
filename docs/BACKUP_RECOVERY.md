# F5.4 — Backup cifrado y restauración aislada

Alcance autorizado: PostgreSQL lógico, MinIO frío con versiones originales, configuración/metadatos y comprobación de candidato v1 en aislamiento. Sin F5.5, incidentes destructivos, alteración del cutoff/modelo, reinstalación K3s, UFW, programación recurrente o transferencias externas. F5.3 y su Actions después de push fueron confirmadas correctas por el usuario.

## Datos protegidos y límites

| Fuente | Tratamiento |
| --- | --- |
| Volumen PostgreSQL Compose | `pg_dump -Fc --create` nativo por retailops, retailops_mlflow y retailops_airflow; roles mediante pg_dumpall --roles-only --no-role-passwords. Nunca copiar archivos de PG activo |
| Volumen MinIO Compose | Contenedor existente detenido, `docker cp /data -` a archivo frío. Incluye RAW/BRONZE, artefactos, historial/VersionId y metadatos internos sensibles; todo cifrado |
| Logs Airflow Compose | Copia fría adicional; archivos regulares extraídos al workspace aislado. Alias simbólicos se registran en un inventario y no se aplican automáticamente |
| Configuración | Snapshot de fuentes versionables por git ls-files (sin .git/datasets/ignored), contratos, migraciones, charts, manifiestos/configmaps de dos namespaces, values app privado e inventario de imágenes; tres imágenes necesarias exportadas con docker save |
| Secretos de recuperación | Solo dentro del payload cifrado, jamás en el manifiesto público o Git. No se habilitan en clones; allí se generan credenciales independientes |
| Cachés ML (Docker/PVC) | Regenerables desde artefactos MinIO; no respaldadas ni montadas en restore. La carga validada usa directorio nuevo |
| PVC observabilidad | Se conservan sin montar. Prometheus/Loki/AM/Grafana/receptor y sus historias/SQLite NO se incluyen como backup de datos operativos; configuración versionada y credenciales Grafana protegidas para reconstruir. No afirmar recuperación de esas historias |
| SOURCE Favorita | No abierto, modificado ni respaldado de nuevo; su custodia independiente sigue siendo necesaria. El bootstrap materializado sí está protegido |

No es un backup completo del host, K3s/etcd, kubeconfig, imágenes app/Airflow, sesiones o todos los PVC. La restauración comprobada cubre el plano de datos, metadatos Airflow/MLflow y carga del artefacto ML; no React/Spring/FastAPI, Airflow UI ni observabilidad reconstruidos. No se declara recuperación integral de RetailOps ni RTO end-to-end.

## Consistencia y quiescencia

PostgreSQL y MinIO no comparten snapshot/transacción distribuida. Se exige ventana de mantenimiento **sin escritores**: apps/observabilidad a cero y lab_active=0, Airflow API/scheduler/dag processor, MLflow y servicios app Compose detenidos; no provisionadores/migradores/bootstrap/operadores SQL/S3 concurrentes. No se detienen servicios ajenos automáticamente.

El comando verifica réplicas en los dos namespaces y contenedores Compose del proyecto; solo permite PG/MinIO, y rechaza clientes SQL de trabajo conectados. Un administrador postgres u otro cliente externo al laboratorio podría eludir este procedimiento: la operadora debe impedirlo durante toda la ventana. Lock local evita comandos backup/verify/restore/stop incompatibles del helper; no bloquea administradores externos.

Secuencia: inventario SQL completo y objetos/versiones/hashes → dumps nativos → segundo inventario SQL/objetos idéntico → detener únicamente MinIO de esta ventana → copiar frío → cifrar/manifiestos/verificar. PG permanece activo solo para lectura/backup. Las bases se vuelcan secuencialmente y dependen de esa quiescencia, no de snapshots sincronizados entre bases.

**VersionId es parte del contrato:** cargar objetos por PUT S3 puede generar IDs nuevos y romper control.objects/publication_objects. Se eligió copia fría de la misma versión MinIO. El usuario autorizó conservar nombres lógicos de buckets únicamente dentro de la instancia aislada; contenedores/redes/volúmenes/bases/endpoints/contraseñas son nuevos. No se modifican referencias SQL ni objetos para ocultar diferencias. Si VersionId/SHA/tamaño no coincide, detener y no promover la restauración.

Ningún contenedor nuevo monta los volúmenes originales. Backup lee MinIO/logs desde contenedores originales detenidos, sin montar esos volúmenes en helpers nuevos; restore solo monta volúmenes con prefijo único y etiqueta propia.

## Privacidad y formato

`infra/backup/core.py` y `scripts/backup_recovery.py` implementan comandos separados. Backup fuera del repositorio y volúmenes originales: `/home/diego/Backups/retailops/backup-<UTC>-<UUID>`, directorio 0700, archivos 0600, sin sobrescrituras. Clave aleatoria 64 bytes separada en `/home/diego/Backups/retailops-keys`; workspaces en `/home/diego/Backups/retailops-restores`, también privados y fuera de Git.

Payload tar cifrado mediante OpenSSL AES-256-CBC, PBKDF2-SHA256 200000 iteraciones y passphrase por descriptor anónimo; HMAC-SHA256 encrypt-then-MAC con clave derivada independiente. No claves en argv/env/logs. SHA-256/MAC del ciphertext se validan **antes de descifrar**. El manifiesto interno cifrado enumera cada archivo, bytes y SHA-256; el inventario incluye tablas/recuentos/hashes, objetos y versiones, corte, identidades de imagen y metadatos de reconstrucción. El envelope público contiene formato, ID, timestamps UTC, duración, bytes, hash/MAC y nombre de clave, nunca su valor. El punto recuperado se obtiene del inventario interno protegido.

La clave separada en el mismo host no es almacenamiento externo ni protección ante pérdida total del disco/host. No se transfirió nada fuera ni se programaron tareas. Custodiar una copia independiente y la clave por canales adecuados requiere autorización y procedimiento posterior. Perder la clave impide restaurar. No compartir payload.tar, staging, recovery-secrets o workspaces descifrados; el artefacto final compartible es el cifrado, pero contiene datos privados y tampoco se publica sin autorización.

No se borra automáticamente ningún backup válido. Staging/archivo tar plaintext creados por el propio backup se retiran solo después de completar verificación del backup cifrado; no se borran volúmenes ni recursos originales. Si falla, se conserva estado privado para diagnóstico y el comando no informa éxito. Verify/restore conservan sus workspaces privados; no hay limpieza automática del material descifrado ni de volúmenes de prueba. Borrado físico seguro en SSD no se garantiza.

## Comandos reproducibles

Desde raíz, Docker del usuario, herramientas/kubeconfig F4 conservados, OpenSSL disponible y dependencias bloqueadas del proyecto ML. No sudo ni servicios del SO nuevos:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
export PATH="$PWD/.local/f4/tools:$PATH"
export KUBECONFIG="$PWD/.local/f4/kubeconfig"
export KUBE_CONTEXT=default
scripts/validate_backup.sh
# Confirmar primero el cierre SRE y ausencia de escritores según SRE.md.
# Solo si estos dos estaban inicialmente detenidos:
docker compose --env-file .env.example -f infra/docker/compose.yaml \
  up -d --wait --wait-timeout 120 postgres minio
uv run --project apps/ml-service --locked python scripts/backup_recovery.py backup \
  --destination /home/diego/Backups/retailops --keys /home/diego/Backups/retailops-keys
```

El backup detiene MinIO para copia fría; no lo vuelve a arrancar ni decide reabrir escritores. Registrar qué servicios se iniciaron y conservarlos detenidos al cerrar. No ejecutar en un entorno con trabajo concurrente: rechazos de quiescencia deben investigarse, no sortearse.

Sustituir `<backup>` y `<clave>` por las rutas exactas devueltas, y elegir **workspaces nuevos**. Ejecutar secuencialmente (lock compartido del helper):

```bash
uv run --project apps/ml-service --locked python scripts/backup_recovery.py verify \
  --backup <backup> --key <clave> --workspace /home/diego/Backups/retailops-restores/verify-<ID-nuevo>
uv run --project apps/ml-service --locked python scripts/backup_recovery.py restore \
  --backup <backup> --key <clave> --workspace /home/diego/Backups/retailops-restores/restore-<ID-nuevo>
# Detener solo los tres contenedores temporales de ese intento:
uv run --project apps/ml-service --locked python scripts/backup_recovery.py stop \
  --workspace /home/diego/Backups/retailops-restores/restore-<ID>
```

Restore verifica MAC y archivos antes de crear contenedores. Falla ante workspace existente, recurso conflictivo, archivo faltante, hash inválido o incompatibilidad. No hay modo de sobrescribir/restaurar encima del origen ni reparación de referencias. Ejecutar sin Python -O (comprobaciones obligatorias). El comando stop exige nombre con prefijo y etiqueta del ID exacto; rechaza nombres originales antes de invocar Docker. Conserva volúmenes/red para revisión, no hace prune/down -v/rm de datos.

## Aislamiento y credenciales

Cada intento genera `retailops-restore-<UUID>-*`: red Docker **--internal**, PostgreSQL y MinIO sobre volúmenes nuevos, MLflow propio. Sin puertos publicados, sin host network ni redes Compose/K3s compartidas. El host accede a las IP del bridge privado para verificar; no se abre LAN/Internet ni UFW. En este Docker los puertos publicados de una red internal no quedaron operativos; la implementación final usa acceso al bridge sin publicar puertos.

DBs restauradas se renombran dentro del clone con prefijo único (propiedad/ACL preservadas por dump nativo); nombres de tablas y claves intactos. PostgreSQL inicial tiene administrador nuevo y todos los logins recuperados reciben contraseñas nuevas. MinIO usa root nuevo y deshabilita todas las cuentas IAM heredadas en el clone. Se prueba rechazo de root MinIO y contraseña API SQL originales, con contraprueba positiva en endpoints aislados. Los secretos originales empaquetados para contingencia no se montan en servicios restaurados.

MLflow apunta solo al PostgreSQL/MinIO de la red nueva y versión 1; descarga/carga el modelo en caché nueva, sin entrenar, promover, registrar o inferir. Se exige purpose candidate_local_preview, contrato feature SHA, versión sales-pit-v1 y corte 2014-12-31. No se arranca ningún scheduler o DAG sobre metadatos restaurados; pueden contener URLs/conexiones del entorno original y requieren revisión antes de uso real.

Presupuesto de prueba: PG aislado 2 GiB/2 CPU, MinIO 1 GiB/1 CPU, MLflow aislado 2 GiB/2 CPU (swap combinado 3 GiB), pids 256 cada uno. Ese límite MLflow corresponde solo a la instancia nueva que carga el artefacto; no cambia workers/límites/imagen del servicio conservado. Helpers son efímeros, no privilegiados, sin Docker socket ni hostPath; el extractor MinIO solo escribe su volumen nuevo. Directorio mc nuevo escribible/privado, no configuración original.

## Verificación de recuperación

- Todas las tablas ordinarias de las tres bases: inventario, propietario, recuento y SHA-256 completo de COPY BINARY ordenado por PK (o fila textual con collation C sin PK), no solo agregados.
- Secuencias last_value/is_called, ventas con suma decimal/fechas, 1 297 296 ventas, 9 106 020 features, cutoff 2014-12-31 y cero autorizaciones nuevas.
- PK/FK/unique y validación de constraints; pg_restore falla si la reconstrucción no valida. PostgreSQL puede normalizar CHECK y cambiar nombres automáticos de NOT NULL: se exige equivalencia mediante parser en tablas **temporales del clone**, y mismo conjunto de columnas NOT NULL. No se cambian constraints de negocio ni migraciones para acomodar diferencias. Diferencias de representación se registran; hashes de datos siguen siendo exactos. Pruebas negativas rechazan datos/CHECK alterados.
- Todos los buckets, versiones y delete markers: identidad, latest, tamaño, ETag y SHA-256 completo leído por versión. ETag no sustituye SHA-256. Se comprueban referencias exactas SQL de control.objects y quarantine/released_version de publication_objects.
- Metadatos MLflow por hashes de tablas y comprobación API de nombre/version/run_id/purpose, contrato y carga real del artefacto. Se repite fingerprint SQL después del arranque/carga para detectar modificaciones inesperadas.
- Logs Airflow se recuperan como archivos, sin ejecutar sus procesos. Alias simbólicos se preservan solo en inventario/tar original, no se materializan en la extracción segura.

Estos hashes son **de datos lógicos completos de las tablas y de cada versión de objeto**, no hashes de cada archivo físico PostgreSQL/etcd/PVC ni verificación integral de índices, roles/ACL o el host. El dump nativo conserva ACL/propiedad, pero no se afirma un hash completo de permisos/roles; sus contraseñas cambian intencionadamente en el clone. Arrancar/parar PostgreSQL/MinIO puede actualizar WAL, estadísticas y metadatos técnicos: identidad/configuración de volúmenes y contenido lógico se contrastan por separado. Nunca copiar PG activo como sustituto de pg_dump.

## RPO/RTO propuestos

RPO propuesto: **≤24h de cambios autorizados**, con backup manual tras cada ingesta/registro/cambio relevante y antes de cerrar la sesión. No es garantía mientras no exista disciplina/copia independiente; no se programó nada. Bajo quiescencia el punto observado corresponde al estado estable capturado, no a fechas de negocio (2014-12-31 es cutoff, no hora del backup).

RTO propuesto **≤30min para recuperar/validar el plano de datos y artefacto ML** con imágenes, clave y espacio ya disponibles en este host. Objetivo integral orientativo ≤2h solo tras ensayar aplicaciones/credenciales/red/observabilidad; **no medido ni comprometido**. Pérdida de host/disco puede requerir recuperar imágenes, código, herramientas, secretos y K3s, fuera de lo probado. El backup contiene imágenes de los tres componentes de datos; en host vacío su importación se hace solo tras verificar y revisar el archivo, no automáticamente sobre imágenes existentes.

`restore-report.json` separa restauración (incluye descifrado/verificación y aprovisionamiento nuevo), validación (hashes/modelo/segunda comprobación) y total; informa antigüedad del punto recuperado desde UTC interno autenticado. `verification.json` mide verify. No sumar o comparar esas cifras como RTO integral de la aplicación. Resultados reales y evidencia se completan al cerrar en PROGRESS.md.

## Resultados ejecutados el 2026-11-17

Backup final recomendado: `/home/diego/Backups/retailops/backup-20261117T161854Z-375a34c472b3`, **918784032 bytes cifrados**, creación **64.00s**, verify **2.65s** y 38 archivos internos verificados. Clave en el directorio separado documentado, con mismo ID y extensión .key; nunca copiar su contenido a logs/Git. Se conserva también la primera copia única del ensayo.

| Medición | Restore-06 | Restore-07 (repetición nueva) |
| --- | --- | --- |
| Restauración/aprovisionamiento/verificación previa | 51.74s | 51.18s |
| Validación SQL/objetos/modelo y SQL posterior | 43.17s | 43.04s |
| Total observado | **94.91s** | **94.21s** |
| Antigüedad del punto al terminar | 240.77s | 412.23s |

Ambas restauraciones tienen `status=validated`, recursos/bases/contraseñas nuevos e inventario equivalente: **167 tablas** (25 negocio, 71 MLflow, 71 Airflow), **313 versiones de objetos en cinco buckets**, incluyendo **19 versiones de objetos MLflow**, y **586 referencias SQL** exactas entre control.objects y publication_objects. El candidato v1 y su run_id original, propósito, contrato y corte se verificaron y el artefacto cargó desde los servicios nuevos, sin inferir o entrenar. Cuatro usuarios IAM heredados se deshabilitaron en cada clone; credenciales originales SQL/API y root MinIO rechazadas con servicio nuevo accesible.

Ocho diferencias de representación de constraints PostgreSQL resultaron equivalentes mediante parser; no se cambiaron tablas/referencias. Pruebas negativas reales rechazaron hash de datos/CHECK adulterados y CLI rechazó ciphertext sintético inválido antes de crear recursos, además de un workspace existente. La prueba sintética no modificó ningún backup válido.

Origen después del ensayo: todos los hashes completos de sus tablas/constraints/secuencias/estado iguales al punto final, archivo MinIO frío SHA-256 idéntico, archivos de credenciales originales idénticos, cuatro volúmenes originales con identidad/configuración iguales y siete PVC con UID/spec/Bound conservados. El hash físico PG no se compara: su arranque/paro actualiza estructuras técnicas legítimas.

No se perdió ningún cambio del estado quiescente observado, pero los 240.77/412.23s son **edad del punto**, no garantía de RPO futuro. Los ~95s son recuperación de datos/artefacto con imágenes/cache/herramientas disponibles en este host; no representan RTO integral ni recuperación de disco perdido o sistema frío.

Pruebas estáticas: seis unitarias backup con Python 3.12/uv, contrato de almacenamiento y diez unittest de infra; actionlint, bash -n, py_compile y diff --check. Sin suites frontend/API/ML de negocio porque no se modificaron. CI nueva solo validada localmente, no ejecutada remotamente.

Se conservaron intentos fallidos privados para diagnóstico, detenidos sin sobrescribirlos: puerto en Docker internal no disponible, directorio mc inicialmente RO, launcher con nombre que sombreaba mlflow y caché de descarga inicialmente ausente. El código final corrige esos casos, detecta contenedor muerto sin esperar innecesariamente y pasó las dos restauraciones completas.

## Procedimiento ante pérdida real

1. Detener nuevos escritores y preservar evidencia. No borrar datos/volúmenes sospechosos ni cambiar DNS/configuración de la aplicación al primer clone.
2. Identificar backup/clave independientes, versiones y punto requerido. Verificar criptografía/manifiesto/hash; ante ausencia de clave o corrupción, detener y buscar otra copia, no forzar restauración.
3. Preparar directorios nuevos privados y las imágenes exactas. No inicializar sobre volúmenes existentes ni aplicar migraciones/repair para ocultar conflictos. Usar restore aislado y comprobar informe validated y todos los campos de alcance.
4. Revisar inventario, restricciones temporales, referencias/versiones y candidato. Si hay discrepancias de VersionId, no reescribir referencias ni artefactos: detener y presentar alternativa revisable.
5. Solo tras revisión de datos, planificar credenciales/endpoints nuevos y reactivación de aplicaciones con consentimiento explícito del operador. No automatizar failover, promoción de modelo o sustitución de servicios originales. Esa recuperación integral debe tener smoke independiente antes de declarar RTO global.
6. Detener únicamente recursos de prueba identificados y servicios fuente arrancados para el backup; conservar backups, claves, originales y workspaces para revisión.

## Conservación y evidencia

Propuesta: conservar copias después de cambios relevantes y al menos las últimas siete verificadas, sin borrado programado; cualquier depuración manual necesita revisión de IDs, clave disponible y prueba de otra copia. Hoy no hay transferencia externa, scheduler o borrado automático de backups válidos. Mantener claves separadas y acceso 0700/0600; workspaces descifrados y volúmenes fallidos consumen disco y no son artefactos compartibles.

Evidencia privada: `.local/f54` para comandos/logs/resultados resumidos; backups/claves/restores reales fuera del repo. CI solo ejecuta unitarias y contratos estáticos sin datos ni Docker real de origen. Prueba real usa recursos del host y no publica imágenes, commits o archivos.

Referencias primarias: [pg_dump PostgreSQL 18](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_dumpall y roles sin passwords](https://www.postgresql.org/docs/18/app-pg-dumpall.html), [IDs de versiones MinIO](https://min.io/docs/minio/linux/administration/object-management/object-versioning.html). Las mediciones y verificaciones locales se registran aparte; esas fuentes no certifican esta instalación.

Cierre real verificado: **diez Deployments a cero, siete PVC Bound con UID/spec intactos**, 26 contenedores del ámbito original/pruebas en exited y K3s active/disabled como al inicio. Se conservaron dos backups cifrados y claves separadas; los workspaces, redes y volúmenes de intentos aislados también se retienen privados para revisión, sin limpieza destructiva automática. El verify adicional con la guarda final de rutas equivalentes pasó sin arrancar servicios. No commit/push/pull/publicación, transferencia externa o F5.5.
