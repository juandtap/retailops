# EDA reproducible — F1-04A

Dos notebooks sobre **2013-01-01 a 2014-12-31**, exclusivamente mediante vistas PostgreSQL `training` y el rol `retailops_trainer`. No se abre SOURCE, Silver, CSV/Parquet, perfilado global ni el manifiesto para obtener estadísticas. No se escribe en PostgreSQL ni se modifica el corte. No se construye GOLD ni se entrenan modelos.

## Preparación

Desde la raíz del repositorio, reutilizando runtime/secretos/volumen de F1-03:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv sync --project notebooks --locked
# Iniciar solo PostgreSQL; no hace falta MinIO ni un nuevo bootstrap.
docker compose --env-file .env.example -f infra/docker/compose.yaml up -d --wait --wait-timeout 120 postgres
```

Si se usa `.env` con puerto/base personalizados, sustituir `--env-file .env.example` por `--env-file .env` y exportar los valores públicos `EDA_PG_PORT` y `EDA_PG_DATABASE` correspondientes. El módulo no importa helpers de administración ni necesita Docker para consultar.

Dependencias del proyecto uv/Python 3.12, con lock: JupyterLab e ipykernel (interfaz/kernel), nbformat/nbclient (formato y ejecución completa), pandas/NumPy (agregados y correlaciones), matplotlib (figuras) y Psycopg (cliente PostgreSQL). No se instala nada global ni se registra un kernel global. Las versiones concretas están en uv.lock y PROGRESS.

Configuración opcional:

| Variable | Valor por defecto / restricción |
| --- | --- |
| EDA_PG_HOST | 127.0.0.1; solo localhost/loopback |
| EDA_PG_PORT | 5432; entero entre 1 y 65535 |
| EDA_PG_DATABASE | retailops |
| EDA_PASSWORD_FILE | `<raíz>/.local/secrets/pg_trainer_password`; archivo 0600, sin symlinks y con ese nombre |

El usuario SQL está fijado a trainer; no hay variable para cambiarlo a administrador. La contraseña se lee únicamente desde su archivo, no se copia a notebooks, código, argumentos, outputs o figuras. No se leen otros secretos. No regenerar credenciales de un volumen existente.

## JupyterLab interactivo

```bash
uv run --project notebooks --locked python notebooks/lab.py
```

Abrir la URL local que presenta Jupyter y conservar su autenticación por token automático. No copiar el token a documentación ni notebooks. El servidor se limita a 127.0.0.1, carpeta notebooks, terminales deshabilitadas y kernel `retailops-eda` de este entorno uv. Configuración/caches/runtime/kernel local están en `.local/eda/` (directorio 0700 ignorado), sin archivos globales. Detener con Ctrl+C.

Abrir cada notebook y ejecutar **Restart Kernel and Run All**. El notebook 01 trata distribución, ceros/decimales, tiendas/familias, evolución mensual, extremos y cobertura. El 02 trata tendencias, perfiles semanales/mensuales, ejemplos por segmento y correlación por retardo de calendario.

El servidor/kernel local no equivale a una sandbox del usuario de la PC: quien ejecute código arbitrario con su usuario podría abrir archivos del equipo. Los notebooks y módulos entregados no lo hacen. Jupyter advierte que el transporte TCP local entre kernel y cliente no está cifrado; no exponerlo a la LAN ni usar el despliegue como servicio multiusuario. No se montan volúmenes ni sockets privilegiados.

## Ejecución automática y evidencia

```bash
uv run --project notebooks --locked python notebooks/run_notebooks.py
```

El runner verifica Python 3.12, venv y kernel local, ejecuta ambos notebooks completos con NBClient y falla ante cualquier error o celda sin ejecutar. Timeout por celda: 120 segundos; los kernels se cierran al terminar. **No guarda notebooks ejecutados ni outputs/tracebacks de celdas**. Los .ipynb entregados conservan execution_count=null y outputs=[]; el launcher de JupyterLab instala además un pre_save_hook que limpia outputs y contadores al guardar (sin borrar código/markdown). Los checkpoints están ignorados.

Salidas deliberadas:

- `docs/eda_figures/*.png`: diez gráficos de agregados autorizados, sin filas originales ni credenciales.
- `.local/eda/eda.json` y `time_series.json`: resúmenes agregados locales; no son entradas autorizadas para entrenar ni features GOLD.
- `.local/eda/execution.json` y `docs/EDA_EXECUTION.json`: Python, hashes de notebooks/módulos/uv.lock, estado, número de celdas ejecutadas y duración. Sin credenciales o microdatos.
- `docs/EDA_FINDINGS.md`: resultados e interpretaciones revisadas después de ejecutar, con límites e hipótesis pendientes.

## Consultas y seguridad temporal

`retailops_eda/data.py` centraliza conexión/validación; `queries.py` es un registro cerrado de consultas parametrizadas. El notebook no suministra SQL arbitrario ni puede sustituir fechas/lote. Cada consulta de negocio está acotada al bootstrap; las comprobaciones de identidad/permisos usan solo metadatos de sesión. La comprobación booleana `future_visible` no devuelve observaciones/estadísticas futuras: se detiene si aparece acceso posterior al corte.

Transacciones con `default_transaction_read_only=on`, statement_timeout=30s, lock_timeout=3s, idle_in_transaction_session_timeout=30s y cierre/rollback garantizados. Límite SQL de 5001 filas para detectar exceso; solo se aceptan hasta 5000. Se agregan los 1,3 millones de registros en servidor; se descargan 728 días, 24 meses, 54 tiendas, 33 familias y como máximo tres series por consulta segmentada (hasta 2184 filas). Las consultas de cuantiles pueden ordenar datos del período en PostgreSQL, pero no descargan filas completas al notebook.

Las vistas aplican liberación/corte en servidor y el cliente fija además 2013–2014. El rol no puede leer control/Silver ni modificar datos. Se comprueba una población visible de 1 297 296 observaciones y fechas límite; esto no sustituye una lectura directa del singleton histórico, que no está permitida. No se elevan permisos para leerlo.

Las dimensiones stores/families y auxiliares holidays/oil devuelven cero filas por falta de known_from/evidencia. Se documenta la restricción y se agrupa por identificadores de los hechos; no se incorporan ciudad, cluster, promociones, petróleo o feriados desde otra fuente. `training.observation_gaps` permite describir las dos Navidades sin inventar ventas cero.

Los huecos se reindexan como NaN; el cero real permanece cero. Los retardos usan días de calendario, no posiciones tras eliminar huecos. Medias móviles, cuantiles y cambios son descriptivos del bootstrap completo: no reutilizarlos como transformaciones ajustadas de folds temporales anteriores. Las cantidades mezclan unidades/peso por familia, no son ingresos monetarios. No se infiere causalidad de tendencias/correlaciones.

## Pruebas

```bash
# Ocho pruebas unitarias; cuatro de conexión se omiten sin activación explícita.
uv run --project notebooks --locked python -m unittest discover -s notebooks/tests -v
# Doce pruebas, incluidas cuatro de integración, solo con el rol trainer.
RETAILOPS_EDA_INTEGRATION=1 uv run --project notebooks --locked python -m unittest discover -s notebooks/tests -v
```

En un sandbox con sockets bloqueados, la integración y ejecución de kernels requieren permiso para conexiones/procesos locales; no cambiar roles ni reglas de PostgreSQL para resolverlo. Las pruebas no crean fixtures, tablas ni datos persistentes.

Al terminar se puede detener únicamente PostgreSQL, conservando los volúmenes:

```bash
docker compose --env-file .env.example -f infra/docker/compose.yaml stop postgres
```

No ejecutar down -v, init-secrets, ingestas o migraciones como parte de este EDA. F1-04B requiere autorización posterior.

## F1-05 — Baselines

`03_baseline_backtesting.ipynb` usa exclusivamente training.gold_features/gold_labels con el mismo rol trainer y kernel uv. Seasonal Naïve y medias 7/28, folds de emisión julio/septiembre/noviembre 2014. No ajusta parámetros ni modifica GOLD.

```bash
uv run --project notebooks --locked python -m unittest discover -s notebooks/tests -p test_baselines.py -v
uv run --project notebooks --locked python notebooks/run_notebooks.py --only 03_baseline_backtesting.ipynb
```

Iniciar PostgreSQL y JupyterLab con los comandos de este README; detener PostgreSQL después si estaba detenido inicialmente. MinIO no hace falta. --only evita repetir notebooks anteriores; sin esa opción se mantiene la ejecución EDA 01/02. El notebook 03 se ejecuta completo sin persistir outputs; cuatro figuras en docs/baseline_figures y resumen/evidencia en .local/baselines. [Resultados, metodología y limitaciones](../docs/BASELINE_RESULTS.md).
