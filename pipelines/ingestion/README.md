# Perfilado local de fuentes — F1-01

El perfilador usa biblioteca estándar en un proyecto Python 3.12/uv. Desde F1-03 el mismo proyecto incluye clientes bloqueados PyArrow/Psycopg/MinIO para el bootstrap; el perfilador no depende de ellos. Usa `csv`, `sqlite3`, cálculo incremental propio y otras utilidades de la biblioteca estándar. No realiza ETL, entrenamiento ni liberación de lotes.

Desde la raíz del repositorio:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv run --project pipelines/ingestion --locked python pipelines/ingestion/profile_dataset.py --source data/source/favorita --output docs
uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/tests -v
```

Desde esta carpeta también se puede ejecutar:

```bash
uv run --locked python -m retailops_profiling --source ../../data/source/favorita --output ../../docs
```

`--batch-size` controla las filas de cada bloque (10 000 por defecto, entero positivo). Para comprobar independencia del tamaño de bloque, repetir con `--batch-size 7777 --output /tmp/retailops-profiling-repeat` y comparar los tres archivos generados. El directorio de salida no puede ser SOURCE ni un subdirectorio suyo; se resuelven enlaces simbólicos antes de escribir.

Salidas deterministas:

- `DATA_PROFILING.md`: informe en español, método, tablas, anomalías interpretadas y recomendaciones Bronze/Silver/Gold.
- `DATA_PROFILING.json`: estadísticas, relaciones, cobertura por serie/tienda/familia y meses. No exporta filas originales.
- `DATA_BATCH_MANIFEST.json`: plan de bootstrap y meses incrementales. `released=false` y `historical_cutoff=null`; no crea ni publica particiones.

Los hashes antes/después y al terminar deben coincidir; comparar también contra `docs/DATA_INVENTORY.json` para conservar la referencia de Fase 0. Un archivo ausente se documenta; una cabecera vacía/ambigua aborta explícitamente. Las filas con longitud incorrecta se contabilizan como malformadas y se excluyen de agregados. No se certifica cobertura de ventas con claves inválidas/nulas o filas malformadas. Los nulos se definen como celdas vacías o solo espacios. No se imputan, deduplican ni corrigen fuentes.

Duplicados y percentiles se calculan con índices y tablas auxiliares SQLite **temporales**, ajenos al almacenamiento de la aplicación. Esto evita guardar millones de claves o ventas como objetos Python. Caché principal SQLite: 16 MiB; bloques y caché de inferencia acotados. El trabajo temporal se elimina al terminar. Se requiere espacio temporal suficiente; su ubicación depende de `TMPDIR`/sistema operativo y puede ser tmpfs. El RSS informado por Linux mide el proceso, no toda la caché de archivos del sistema.

Las estadísticas numéricas usan float64; los percentiles tienen interpolación lineal exacta sobre esa representación. Preservar el CSV original y decidir la precisión de NUMERIC al diseñar esquemas. Las recomendaciones SQL no aplican conversiones, restricciones ni tablas. SQLite solo sirve de herramienta de análisis de la biblioteca estándar, no sustituye PostgreSQL.

El perfil global incluye observaciones posteriores al corte inicial y sirve únicamente para auditar la fuente. No reutilizar sus medias, cuantiles, categorías ni valores futuros como features o parámetros ajustados para el bootstrap. Las ausencias de calendario y transacciones requieren interpretación; no son automáticamente errores o ventas cero.

## Bootstrap F1-03

`bootstrap_dataset.py --execute` implementa el bootstrap fijo 2013–2014; no ofrece ingestas mensuales. El extractor es el único módulo que abre los originales; loader y publicador reciben el workspace seleccionado. Los artefactos viven en `.local/bootstrap/`, nunca en Git. Leer [BOOTSTRAP.md](../../docs/BOOTSTRAP.md) antes de operar.

La suite `tests/` incluye perfilado y extracción/Parquet; la integración optativa en `integration/` usa servicios reales y bases/objetos sintéticos separados. El loader conserva Decimal mediante Parquet y COPY; todas las tablas Silver se confirman en una transacción. El publicador mantiene inventario y versiones para retomar copias sin duplicar observaciones.

## GOLD F1-04B

El mismo entorno uv incorpora `retailops_gold`: features point-in-time desde training.sales, sin abrir SOURCE. Ejecutar pruebas sintéticas y de permisos antes del materializador. Operación, comandos, contrato, tablas, límites e idempotencia por contenido en [FEATURE_ENGINEERING.md](../../docs/FEATURE_ENGINEERING.md). Entrypoints: `materialize_gold.py --execute` y `verify_gold.py`. No entrenan ni liberan datos.
