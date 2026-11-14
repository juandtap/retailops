# Bootstrap 2013–2014 — contrato y operación

## Aceptación aprobada en F1-03

Se acepta exactamente el período 2013-01-01 a 2014-12-31, 1 297 296 ventas, 54 tiendas y 33 familias. Cada día observado debe contener la cuadrícula completa de 1 782 claves naturales únicas. Las únicas ausencias de calendario aceptadas son 2013-12-25 y 2014-12-25. La cobertura del calendario es incompleta; la integridad de los registros presentes, la cuadrícula observada y la completitud contractual del bootstrap deben ser correctas. No se generan ventas cero para Navidad. El corte final será 2014-12-31 porque es el último día autorizado del período, no una afirmación de ventas en cada día. Contrato máquina: `contracts/bootstrap-v1.json`.

## Auxiliares y aislamiento

Se cargan tiendas/familias para integridad referencial, feriados/petróleo del período y transacciones históricas del período. No se incorpora ninguna fila fechada en 2015 o posterior ni feriados anteriores a 2013. Las familias se derivan de identificadores de ventas seleccionadas, con ordinal del primer registro fuente que las menciona. Las tiendas son un snapshot sin fecha; no se inventa vigencia.

Tiendas, familias, feriados y petróleo mantienen **known_from y availability_evidence NULL**. Sus objetos RAW/BRONZE permanecen en cuarentena y sus vistas de dimensiones/auxiliares no los exponen a entrenamiento. Las etiquetas tienda/familia ya presentes en ventas observadas siguen siendo consultables como identificadores de hechos históricos. Esta política conservadora no presume una fecha de anuncio o validez de clasificación que la fuente no contiene. Transacciones históricas, ventas y ausencias de ventas son publicables; ningún valor de transacciones o promociones de los siete días futuros se calcula ni se usa. Las promociones se conservan como enteros históricos; la vista inicial de ventas no las expone como features.

## Extracción y trazabilidad

El extractor es el único módulo de la ingesta que abre SOURCE. Verifica SHA-256 antes y después, filtra por fechas y crea RAW mensual preservando cabecera y bytes de los registros seleccionados, incluidas comillas/saltos CSV. Los originales nunca se modifican. Los otros módulos reciben únicamente el workspace seleccionado, no abren originales. La CLI realiza los controles de hashes en el proceso extractor también al reejecutar. No se monta SOURCE en PostgreSQL, MinIO, inferencia ni entrenamiento. El administrador local mantiene capacidad de acceder al disco: no se afirma aislamiento frente al propietario de la máquina.

BRONZE usa Parquet/PyArrow con decimal128(38,18), sin float para ventas/petróleo; la escala excesiva o valores no finitos se rechazan en lugar de truncar. Cada fila incluye batch_id, source_file, source_sha256, source_row_number, ingested_at y contract_version. source_row_number es el ordinal 1-based del registro de datos original, excluyendo cabecera, no el número de línea física en un CSV con campos multilínea. Los huecos derivados no tienen registro original: su ordinal es NULL, permitido por V2; apuntan al hash del tren y al contrato como evidencia.

RAW/BRONZE de hechos usan `year=YYYY/month=MM/batch=.../{hash}.{csv,parquet}`. Tiendas sin fecha usan `snapshot=undated`; familias derivadas `snapshot=observed-identifiers`. No se inventa un mes para snapshots. Familias y huecos son derivados explícitos y solo tienen BRONZE, sin inventar un RAW original. El checksum de una partición es independiente del hash del CSV original completo. El buffer global de filas está acotado a 32 768 y se descarga aunque existan varios meses abiertos.

PyArrow, Psycopg y el SDK MinIO son clientes de tecnologías ya aprobadas, bloqueados en uv.lock; no se instalan plataformas adicionales ni se modifica Python del sistema. El perfilador de F1-01 sigue usando solo biblioteca estándar, aunque comparte el proyecto uv con la ingesta.

## Publicación recuperable

Las V1 permanecen intactas. Control V2 añade publications y publication_objects; datos V2 exige COMPLETE en todas las vistas y permite ordinal NULL en huecos. No se afirma atomicidad distribuida.

1. Validar entorno RetailOps, hashes y contrato; adquirir advisory lock de sesión global durante toda la operación. Un índice y trigger impiden otra publicación incompleta/lote incompatible aun si otro cliente omite el lock voluntario.
2. Registrar fuentes/lote/ejecución e inventario esperado. publication_objects fija entidades, capas, filas, bytes, hashes y si cada objeto es publicable.
3. Subir a cuarentena, leer de vuelta los bytes y registrar versiones. Si una clave ya existe, comparar contenido/versión: nunca sobrescribir un conflicto. Carga COPY de todas las tablas en una transacción, con PK/FK/CHECK; commit de silver_loaded junto con datos. Una caída durante COPY deja la carga entera revertida.
4. Validar conteos por entidad/mes, sumas decimales exactas, promociones, ceros/fracciones y Navidades; verificar inventario. Autorizar en SQL: batch RELEASED y publication AUTHORIZED. **El corte todavía no avanza y las vistas exigen COMPLETE.**
5. Solo después de esa autorización, copiar los objetos publicables a released. Fijar origen por version_id; comprobar SHA-256 de bytes y versión destino. Registrar cada copia individualmente. Los auxiliares restringidos no se copian.
6. Si hubo copia S3 pero cayó antes de confirmar SQL, el reintento detecta el objeto existente, verifica sus bytes y registra la misma versión sin duplicar. Los objetos no copiados siguen pendientes; no se recarga Silver si silver_loaded está confirmado.
7. Verificar todo el inventario; en una transacción marcar COMPLETE y actualizar corte/last_batch_id. Solo después puede registrarse SUCCEEDED. Un trigger rechaza éxitos prematuros.

Las copias ya autorizadas pueden ser visibles en S3 mientras faltan otras; no se declara disponibilidad atómica de todo el inventario. Las vistas SQL permanecen cerradas hasta completar. Un fallo deja FAILED para el intento y conserva autorización/inventario recuperable; un proceso interrumpido que quedó RUNNING se marca INTERRUPTED al adquirir el lock en el siguiente intento. Se crea un run_id nuevo por intento, no se reescribe el historial de fallos. Si el proceso cae tras COMPLETE antes de SUCCEEDED, el siguiente intento verifica y finaliza sin duplicar ventas ni objetos.

Un conflicto de contenido se detiene y requiere investigación: no borrar volúmenes ni sobrescribir objetos para hacerlo pasar. Versionado no es WORM; se comparan tanto versiones registradas como actuales y checksums de bytes. Estas barreras no protegen frente a credenciales administrativas o un publicador privilegiado deliberadamente malicioso.

## Comandos

Desde la raíz, con secretos/volúmenes ya existentes de F1-02:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv sync --project pipelines/ingestion --locked
uv run --project pipelines/ingestion --locked python scripts/data_infra.py up
# Compilar la API desde apps/api con ./mvnw verify antes de migrate.
uv run --project pipelines/ingestion --locked python scripts/data_infra.py migrate
uv run --project pipelines/ingestion --locked python pipelines/ingestion/bootstrap_dataset.py --execute
```

El último comando ejecuta únicamente el bootstrap fijo. Repetirlo verifica idempotentemente la publicación existente; no libera enero de 2015 ni ofrece opciones de ingesta mensual. Workspace privado 0700 en `.local/bootstrap/bootstrap-2013-2014`, ignorado. El manifiesto original `DATA_BATCH_MANIFEST.json` sigue siendo un plan sin liberación; la realidad operativa está en PostgreSQL. No regenerar secretos de volúmenes existentes.

Pruebas antes de procesar fuentes reales:

```bash
uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/tests -v
RETAILOPS_INTEGRATION=1 uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/integration -v
```

La integración crea bases temporales con nombres retailops_test_UUID y objetos bajo batch=test-bootstrap-UUID. Usa los servicios reales, las migraciones Flyway reales y credenciales de trabajo reales. Limpia solo esos recursos; nunca borra volúmenes. Incluye reinicio de ambos servicios, por lo que debe ejecutarse sin otra operación local concurrente. Las pruebas de estado vacío `data_infra.py verify/persistence` pertenecen a F1-02: después del bootstrap se rechazan deliberadamente, no deben usarse para borrar ni reinicializar datos.

Al terminar se guarda evidencia agregada e inventario en docs/BOOTSTRAP_EVIDENCE.json. Las filas comerciales/Parquet/RAW permanecen privados en workspace y servicios; no se publican en GitHub ni servicios externos.

## Resultado real verificado

| Concepto | Resultado |
| --- | --- |
| Ventas Silver / claves únicas | 1 297 296 / 1 297 296 |
| Tiendas / familias | 54 / 33, dimensiones restringidas sin known_from inventado |
| Feriados / petróleo / transacciones | 118 / 522 / 34 046 |
| Ausencias explícitas | Dos Navidades, sin ventas cero |
| Objetos RAW/BRONZE en cuarentena / publicados | 195 / 98, checksums y versiones en el inventario |
| Lote / publicación / ejecución | RELEASED / COMPLETE / SUCCEEDED |
| Corte / último lote | 2014-12-31 / bootstrap-2013-2014 |
| Meses incrementales liberados | 0; los 32 del plan siguen sin liberar |
| Reejecución | Idempotente; mismas observaciones y versiones |
| Reinicio del lote real | PostgreSQL/MinIO conservan datos, versiones y corte |

Carga inicial: 76,963 s; máximo del worker 508 480 KiB y del extractor 153 304 KiB. Reejecución de verificación: 1,361 s. Se ejecutaron 26 pruebas de perfilado/extracción, diez de infraestructura/contratos, cinco API y cinco de integración real. Los cuatro fallos simulados pertenecen a la base sintética de pruebas; la carga real no falló. El informe completo y los límites están en PROGRESS; el inventario/estados/métricas están en BOOTSTRAP_EVIDENCE.json.

Para repetir la comprobación completa y persistencia del entorno con datos:

```bash
uv run --project pipelines/ingestion --locked python scripts/data_infra.py up
uv run --project pipelines/ingestion --locked python scripts/verify_bootstrap.py --restart
```

No se avanzó a F1-04 ni se entrenó un modelo.
