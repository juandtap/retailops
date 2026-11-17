# Infraestructura de datos — F1-02

PostgreSQL 18.7 y MinIO local, sin CSV montados en contenedores. Solo se crean roles, esquemas, migraciones, buckets privados e identidades. No se ejecuta bootstrap ni ingesta.

## Preparación y comandos

Docker Engine y Compose ya deben estar instalados y accesibles. No instalar PostgreSQL/MinIO en el SO. Desde la raíz, todos los comandos Python siguientes usan Python 3.12 mediante uv:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv run --project pipelines/ingestion --locked python scripts/data_infra.py init-secrets
uv run --project pipelines/ingestion --locked python scripts/data_infra.py config
uv run --project pipelines/ingestion --locked python scripts/data_infra.py build
uv run --project pipelines/ingestion --locked python scripts/data_infra.py up
```

El helper toma `.env` si existe, o `.env.example` si no. Variables exportadas en la terminal tienen prioridad. El ejemplo no contiene contraseñas. `init-secrets` genera valores aleatorios en `.local/secrets/` (directorio 0700, archivos 0600), no muestra ni reemplaza los existentes. **Conservar los secretos junto con los volúmenes**; no regenerarlos para intentar recuperar un volumen existente. La rotación de credenciales no está implementada.

Las credenciales se montan como Compose secrets. En Compose local son archivos montados, no un gestor cifrado de secretos. El wrapper de PostgreSQL lee archivos antes del cambio a su usuario interno y pasa los valores en el entorno interno, sin tracing ni valores en la configuración de Docker. Quien controla Docker o la máquina puede acceder a ellos. MinIO ejecuta como root del contenedor para leer estos archivos 0600; no es un contenedor privilegiado y no monta SOURCE ni Docker socket. No es aislamiento frente al administrador local.

Compilar la API y aplicar migraciones con el perfil de mantenimiento:

```bash
cd apps/api
./mvnw verify
cd ../..
uv run --project pipelines/ingestion --locked python scripts/data_infra.py migrate
uv run --project pipelines/ingestion --locked python scripts/data_infra.py configure-minio
uv run --project pipelines/ingestion --locked python scripts/data_infra.py verify
uv run --project pipelines/ingestion --locked python scripts/data_infra.py persistence
```

`migrate` ejecuta el JAR con `storage` y `web-application-type=none`; obtiene URL/puerto/base de la configuración Compose resuelta y secretos de configtree. Falla si no hay JAR, URL o directorio de secretos. Solo este proceso recibe credenciales migradoras. El arranque web habitual conserva su funcionamiento sin base de datos; no aplica migraciones automáticamente. Las dos historias Flyway son independientes, con validación de checksum y `cleanDisabled=true`. Ejecutar `migrate` otra vez valida sin repetir V1.

`configure-minio` es idempotente para los mismos secretos: crea buckets vacíos/versionados y políticas. No da acceso anónimo ni publica objetos. El cliente oficial compilado vive en la misma imagen, no se instala en el host.

`verify` exige tablas/buckets de datos vacíos y corte nulo: es una comprobación específica de F1-02, no un health check utilizable después de ingerir datos. Comprueba contratos, permisos con credenciales reales, SQL transaccional, MinIO y los siete checksums. Las fixtures SQL se revierten con ROLLBACK; las fixtures S3 de permisos se crean solo bajo `_checks/` y se eliminan junto con sus versiones al terminar. No se registran ingestas exitosas. El único objeto persistente de prueba está en `retailops-verification`, fuera de los buckets de datos.

`persistence` guarda una marca administrativa en el comentario del esquema y un objeto de comprobación, compara OID/comentario y ETag/versionID/tamaño antes y después de stop/up y repite `verify`. No inserta ventas ni lotes. Puede interrumpir temporalmente conexiones locales; usarlo solo en este entorno de prueba.

## Estado, parada y limpieza conservadora

```bash
uv run --project pipelines/ingestion --locked python scripts/data_infra.py status
uv run --project pipelines/ingestion --locked python scripts/data_infra.py stop
uv run --project pipelines/ingestion --locked python scripts/data_infra.py up
uv run --project pipelines/ingestion --locked python scripts/data_infra.py down
```

`stop` conserva contenedores y volúmenes. `down` elimina solo contenedores/red del proyecto, **sin `-v`**, preservando volúmenes. No hay comando automático para destruir datos. No usar prune, down -v ni borrar `.local/secrets` como parte de verificaciones rutinarias. El borrado de volúmenes, imágenes, caché de compilación o secretos requiere una acción deliberada posterior y copia de seguridad si corresponde.

## Configuración y red

| Servicio | DNS dentro de Docker | Dirección local por defecto | Límite por defecto |
| --- | --- | --- | --- |
| PostgreSQL | `postgres:5432` | `127.0.0.1:5432` | 1 GiB, 2 CPU, 256 procesos |
| MinIO API | `minio:9000` | `127.0.0.1:9000` | 2 GiB, 2 CPU, 512 procesos |
| MinIO tools | `minio-admin`, ejecución temporal | Sin puerto publicado | 256 MiB, 1 CPU |

Variables públicas: POSTGRES_DB/PORT/MEMORY/CPUS, MINIO_PORT/MEMORY/CPUS e MINIO_INTERNAL_ENDPOINT. POSTGRES_DB debe ser un identificador simple en minúsculas (letras, números y guion bajo; máximo 63 caracteres). La consola web de MinIO está desactivada y 9001 no se publica. Health checks: pg_isready y HTTP `/minio/health/ready`. El verificador prueba además autenticación, migraciones y autorización. Los volúmenes nombrados son `retailops-data_postgres_data` y `retailops-data_minio_data`; PostgreSQL 18 monta `/var/lib/postgresql` según su distribución oficial.

La red bridge permite DNS interno y acceso de loopback publicado. No se marca `internal:true`: en este Docker esa opción impidió la publicación efectiva de puertos y bloqueó el runner de migraciones del host. No se abren interfaces de la LAN. HTTP y PostgreSQL locales no usan TLS en esta fase; no trasladar esta configuración sin revisión a una red compartida.

## MinIO: procedencia y mantenimiento

La descarga del tag histórico oficial en Quay devolvió 401. El [repositorio oficial](https://github.com/minio/minio) está archivado y documenta distribución solo de fuentes. La imagen local `retailops-minio:7aac2a2-77f82e1` compila los commits oficiales MinIO `7aac2a2c5b7c882e68c1ce017d8256be2feea27f` y mc `77f82e18b5401a65958f1619df6ebb994634bd88` con Go **solo en el builder Docker**. Se fijan SHA-256 de archivos y digests de Go/Alpine; los módulos siguen go.sum upstream. No se clona ni inicializa Git. El contexto de build solo permite Dockerfile, sin CSV, secretos o código de la aplicación.

Los commits y bases fijados no equivalen a mantenimiento de seguridad. MinIO comunitario no tiene mantenimiento upstream y esta imagen local no se recomienda para producción. No se cambió de tecnología ni se adoptó una edición comercial sin autorización. Se conservan licencias AGPL del servidor/cliente en `/licenses` de la imagen y se referencian las fuentes originales; no se publica ni redistribuye la imagen en esta tarea. Cualquier distribución futura debe revisar esas obligaciones.

Modelo, contratos, límites y protocolo de liberación pendiente: [DATA_STORAGE.md](../../docs/DATA_STORAGE.md).

Pruebas sin daemon Docker:

```bash
uv run --project pipelines/ingestion --locked python scripts/storage_contracts.py
uv run --project pipelines/ingestion --locked python -m unittest discover -s infra/docker/tests -v
```

## Entorno después de F1-03

La infraestructura ya contiene el bootstrap real, con migraciones V2 aplicadas. No ejecutar las comprobaciones de vacío `verify/persistence` para intentar recuperar este estado: deben rechazar datos existentes. Usar `scripts/verify_bootstrap.py --restart` según [BOOTSTRAP.md](../../docs/BOOTSTRAP.md). Los comandos up/stop/down sin -v conservan datos. Nunca regenerar secretos ni borrar volúmenes para resolver una publicación pendiente.

GOLD F1-04B añade migraciones control/data V3 con el mismo runner; no requiere servicio nuevo ni MinIO encendido. Usar [FEATURE_ENGINEERING.md](../../docs/FEATURE_ENGINEERING.md) para pruebas/materialización. Mantener volúmenes y secretos existentes; nunca usar verify/persistence F1-02 con datos cargados.

## F1-06 — MLflow

Perfil `mlops` en compose.mlflow.yaml, backend PostgreSQL y bucket MinIO propios. Preparar secretos MLflow, provisionar y arrancar siguiendo [MLOPS.md](../../docs/MLOPS.md). La imagen se construye con Python fijado y requirements.lock exportado de uv; no monta SOURCE/CSV. No usar los comandos F1-02 de entorno vacío.

## F2 — Airflow manual

Perfil airflow con LocalExecutor y base/metadatos independientes, puerto 8081 y logs persistentes. Preparación, arranque, DAG seguro y autorización mensual futura en [AIRFLOW.md](../../docs/AIRFLOW.md). Sin SOURCE ni Docker socket montados. No lanzar comandos de publicación como parte del arranque; no down -v.

## F5.4 — Recuperación aislada

Usar [BACKUP_RECOVERY.md](../../docs/BACKUP_RECOVERY.md), no init-secrets, migraciones ni verify/persistence de entorno vacío sobre los volúmenes cargados. Backup lógico PG y MinIO frío en contenedor existente; restore sobre recursos nuevos de red interna, sin montar volúmenes originales, sin sobrescritura o remapeo de VersionId. Backups cifrados/claves/workspaces fuera del repo. No hay limpieza automática, conmutación de apps o autorización para F5.5.
