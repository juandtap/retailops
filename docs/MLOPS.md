# ML y MLOps funcional — F1-06

## Arquitectura implementada

Un único algoritmo global: **HistGradientBoostingRegressor** de scikit-learn, pérdida Poisson, 80 iteraciones, learning_rate=0.1, 31 hojas, min_samples_leaf=30, l2=1, random_state=42 y early_stopping=false. No hay búsqueda de hiperparámetros, ajuste posterior a los resultados ni reentrenamiento de producción después del holdout.

`app.training` → vistas training GOLD con trainer → evaluación temporal → tracking/registro MLflow → artefactos MinIO. FastAPI carga una **versión explícita** del registro al arrancar; cada POST consulta siete filas de training.gold_features, sin aceptar features del cliente. El servicio no entrena ni escribe datos de negocio.

OrdinalEncoder aprende tienda/familia únicamente durante el ajuste; HGB recibe ambos campos como categorías nativas, sin tratarlos como magnitudes ordenadas. Categorías desconocidas y valores faltantes siguen NaN. Se usan las 17 columnas declaradas en app/data.py: tienda, familia, horizonte, calendario y todas las features GOLD. Las entradas numéricas se convierten a float32 para el ajuste/inferencia; las métricas se acumulan en float64. No se modifica NUMERIC almacenado ni se reemplazan ausencias por cero. Poisson produce predicciones no negativas sin clipping. Fechas/etiquetas quedan fuera de las entradas.

Versiones bloqueadas por uv: **Python 3.12.16, scikit-learn 1.9.1 y MLflow 3.18.0**. Mismo proyecto apps/ml-service, nuevas dependencias en su pyproject/uv.lock; ningún paquete global. La imagen MLflow usa Python oficial fijado por digest y requirements.lock exportado de uv con hashes. .dockerignore excluye datasets, secretos y entornos del contexto de build.

### Persistencia y responsabilidades

| Componente | Almacenamiento / permisos |
| --- | --- |
| Negocio | Base retailops, GOLD/vistas existentes sin cambios; trainer solo lectura |
| MLflow backend/registro | Base **retailops_mlflow**, propietario/login dedicado retailops_mlflow sin superusuario/CREATEDB/CREATEROLE/BYPASSRLS; sin acceso a negocio |
| MLflow artefactos | Bucket privado/versionado **retailops-mlflow**, identidad MinIO exclusiva; sin permisos en buckets de negocio |
| Backend persistente | Volumen PostgreSQL existente; MLflow administra sus tablas con sus propias migraciones en su base, sin competir con Flyway de negocio |
| Artefactos persistentes | Volumen MinIO existente, accedido por proxy de artefactos MLflow; el cliente no necesita credenciales S3 |
| Checkpoint local | .local/mlops/fit.joblib, privado, reutilizable para reintentos; no sustituye el modelo registrado en MinIO |

scripts/mlops_infra.py utiliza administración **solo para provisionar la base/identidades nuevas**; no transforma datos. Sus secretos son archivos 0600 nuevos, sin reemplazar los existentes. Entrenamiento/FastAPI reutilizan exclusivamente pg_trainer_password para SQL. Compose modular añade compose.mlflow.yaml, perfil mlops, puerto loopback configurable 5000, health check, límite 1 GiB/2 CPU. MLflow y FastAPI son servicios locales HTTP sin autenticación de aplicación/TLS: acceso confiable de la PC, no despliegue multiusuario de producción.

## División temporal fijada antes del ajuste

| División | Emisiones | Etiquetas disponibles como máximo | Uso |
| --- | --- | --- | --- |
| Entrenamiento | Lunes de 2013-01-07 a 2014-10-27, todos los pares/horizontes | **2014-10-31** | Único ajuste; se excluyen objetivos posteriores a la fecha de ajuste |
| Validación | 2014-11-01..2014-11-23 | 2014-11-30 | Informe sin selección de parámetros ni refit |
| Evaluación independiente | **2014-12-08..2014-12-24** | 2014-12-31 | Holdout, objetivos 2014-12-09..2014-12-31 |

El último fold de F1-05 tenía objetivos hasta 2014-12-07: no se solapan con el holdout. La validación de noviembre no se presenta como un período virgen respecto a F1-05. Se conserva la misma versión ajustada al 31 de octubre para validación, holdout e inferencia. El snapshot GOLD es el autorizado hasta 2014-12-31, pero **ninguna etiqueta posterior al 31 de octubre entra al ajuste**. El muestreo semanal se fijó para reducir recursos, sin seleccionar tiendas/familias por rendimiento. Orden de filas estable y semilla fija.

Lectura SQL con cursor de servidor y bloques de 20 000 filas. Solo el conjunto de ajuste seleccionado se reúne en memoria; no se cargan los 9,1 millones de ejemplos. Las emisiones se interpretan al cierre del día: hipótesis heredada de GOLD, sin timestamps históricos de llegada.

## Resultados verificados

Entrenamiento: **1,177,902 ejemplos**, 1,782 etiquetas ausentes excluidas, sin imputación. Ajuste exitoso 4.325 s; flujo exitoso 29.712 s; RSS máximo del proceso 1,005,132 KiB (incluye bibliotecas/lectura/modelo, excluye servidores).

| División | Método | n común | MAE | WAPE (%) | RMSLE |
| --- | --- | --- | --- | --- | --- |
| validation | hgb | 286902 | 57.8521 | 15.6533 | 0.4873 |
| validation | seasonal_naive_7 | 286902 | 66.7710 | 18.0665 | 0.5185 |
| evaluation | hgb | 199584 | 125.6332 | 26.1921 | 0.5226 |
| evaluation | seasonal_naive_7 | 199584 | 120.9130 | 25.2081 | 0.5731 |

**El modelo no supera al Seasonal Naïve en MAE/WAPE del holdout**; sí mejora RMSLE. Se registra ese resultado sin cambiar el período, parámetros o población. El modelo se sirve como **candidate_local_preview**, no como una promoción aprobada de producción. El baseline semanal sigue siendo la referencia principal por MAE/WAPE.

Ambos métodos producen predicciones en el 100 % de los ejemplos seleccionados. Validación: 286 902 etiquetados/comparables. Holdout: 212 058 predicciones por método, **199 584 comparables** y **12 474 sin etiqueta** por el 25 de diciembre ausente; se excluyen de métricas, no se completan con cero. No hay objetivos posteriores al corte en esos conjuntos. Cobertura de etiquetas en holdout: 94,12 %. Métricas individuales coinciden con las comunes aquí. MAE/WAPE/RMSLE reutilizan las funciones de F1-05, con denominador WAPE cero indefinido y predicciones no negativas. Emisiones solapadas no constituyen muestras independientes.

## Registro real y consultas

- Experimento: **retailops-sales-pit-v1**, ID `1`.
- Run exitoso: `55257fc2ce414793b73b9d0df4c95fbb` (FINISHED).
- Modelo registrado: **retailops-sales-global**, versión **1**, URI `models:/retailops-sales-global/1`.
- Tags: fecha real de entrenamiento, fit_date, snapshot, propósito candidato; parámetros/semilla/configuración, métricas de validación/evaluación, contrato y hashes.
- Artefactos: modelo skops y firma, evaluación JSON, contrato GOLD, uv.lock y código fuente del run; evidencia HTTP. Metadatos locales en .local/mlops/candidate.json y smoke.json.

La UI se consulta en http://127.0.0.1:5000 al iniciar el servicio. También desde apps/ml-service:

```python
from mlflow.tracking import MlflowClient
client = MlflowClient(tracking_uri="http://127.0.0.1:5000")
print(client.search_experiments())
print(client.search_runs(["1"]))
print(client.search_model_versions("name='retailops-sales-global'"))
```

No se configura alias mutable de producción ni promoción automática. La versión se fija mediante ML_MODEL_VERSION. El primer run (820796e88c5843c8b7126907430f40ee) quedó FAILED por la serialización inicial; se conserva el registro y no se presenta como exitoso. Hubo dos ajustes idénticos por esa corrección, no dos algoritmos/configuraciones. El checkpoint ahora permite reintentar sin ajustar ni evaluar de nuevo si coinciden código de datos/modelo y lock; otra invocación explícita registra un nuevo run/versión, no ocurre al arrancar FastAPI.

## Comandos reproducibles

Desde la raíz, sin regenerar secretos ni borrar volúmenes:

```bash
export UV_CACHE_DIR=/tmp/retailops-uv-cache
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv sync --project apps/ml-service --locked
uv run --project apps/ml-service --locked python scripts/mlops_infra.py prepare
# Usar .env si existe; aquí se muestra la configuración pública por defecto.
docker compose --env-file .env.example -f infra/docker/compose.yaml up -d --wait postgres minio
uv run --project apps/ml-service --locked python scripts/mlops_infra.py provision
# requirements.lock ya está generado y fijado; regenerar solo al cambiar dependencias:
# uv export --project apps/ml-service --locked --no-dev --no-emit-project --format requirements-txt --output-file infra/docker/mlflow/requirements.lock
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops build mlflow
docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops up -d --wait --wait-timeout 180 mlflow
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
uv run --directory apps/ml-service --locked python -m app.training
```

POSTGRES_PORT configura el provisionador; EDA_PG_HOST/PORT/DATABASE configuran la conexión trainer reutilizada. Si cambia MLFLOW_PORT, ajustar también MLFLOW_TRACKING_URI. Las credenciales se mantienen en .local/secrets, nunca en comandos/notebooks/respuestas. La imagen no recibe secretos de negocio ni SOURCE; los secretos administrativos no se entregan al proceso de ajuste.

### Iniciar FastAPI

```bash
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
export ML_MODEL_VERSION=1
# Necesario en MLflow 3.18 para cargar nuestro artefacto confiable del registro local:
export MLFLOW_ALLOW_MODEL_CODE_EXECUTION=true
uv run --directory apps/ml-service --locked python -m app
```

ML_HOST=127.0.0.1 y ML_PORT=8000 por defecto. Si falta versión, /health conserva liveness y /model/predict responden 503; una versión inválida o incompatible falla al arrancar. Se comprueban feature_version, corte, fit_date, lista de entradas y hash del contrato antes de cargar. El modelo se descarga desde el registro a un cache local; la copia autoritativa permanece en MinIO. Nunca cargar artefactos de terceros no confiables: la serialización puede ejecutar código. La lista explícita de tipos skops contiene únicamente functools.partial, TreePredictor y check_array usados por este pipeline propio; no se acepta automáticamente cualquier tipo declarado por un artefacto.

### Contrato HTTP

| Endpoint | Comportamiento |
| --- | --- |
| GET /health | Liveness del proceso, {"status":"ok"}; no certifica acceso SQL |
| GET /model | Nombre, versión, run_id, fit_date, corte, feature_version y propósito; 503 si no hay modelo |
| POST /predict | Recibe únicamente issue_date, store_nbr positivo entero y family no vacía; devuelve siete horizontes con fechas, cantidades y versión |
| GET /docs | OpenAPI interactivo del contrato |

Issue_date debe estar entre **2014-10-31 y 2014-12-31**. Rechazar emisiones anteriores al ajuste evita usar un modelo entrenado con etiquetas futuras respecto a la petición. Features, versión o etiquetas arbitrarias como campos extra → 422. Entrada inválida/fuera de rango → 422; combinación sin features → 404; indisponibilidad SQL/modelo o GOLD incompleto → 503. No se devuelve pronóstico parcial ni información de conexión. Los objetivos pueden ser enero de 2015 porque son predicciones basadas en información autorizada; no hay etiquetas de enero ni liberación de ese mes.

## Petición y respuesta reales

El smoke HTTP se ejecutó en 127.0.0.1:8180, cargando desde MLflow la versión 1; GET health/model y POST predict dieron 200. Para el puerto predeterminado:

```bash
curl --fail http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"issue_date":"2014-12-31","store_nbr":1,"family":"GROCERY I"}'
```

Respuesta verificada, sin etiquetas reales futuras:

```json
{
  "store_nbr": 1,
  "family": "GROCERY I",
  "issue_date": "2014-12-31",
  "model_name": "retailops-sales-global",
  "model_version": "1",
  "feature_version": "sales-pit-v1",
  "historical_cutoff": "2014-12-31",
  "predictions": [
    {
      "target_date": "2015-01-01",
      "horizon": 1,
      "prediction": 10.534901631836364
    },
    {
      "target_date": "2015-01-02",
      "horizon": 2,
      "prediction": 2343.5883273862487
    },
    {
      "target_date": "2015-01-03",
      "horizon": 3,
      "prediction": 1791.867814230838
    },
    {
      "target_date": "2015-01-04",
      "horizon": 4,
      "prediction": 931.471175284304
    },
    {
      "target_date": "2015-01-05",
      "horizon": 5,
      "prediction": 1865.6014056777592
    },
    {
      "target_date": "2015-01-06",
      "horizon": 6,
      "prediction": 2814.961936019694
    },
    {
      "target_date": "2015-01-07",
      "horizon": 7,
      "prediction": 2814.961936019694
    }
  ]
}
```

## Verificación, archivos y limitaciones

- **Nueve pruebas Python del servicio verificadas**: siete existentes de salud/configuración y dos nuevas de temporalidad y carga/contrato de inferencia. La primera ejecución tuvo ocho aprobadas y una fallida; se corrigió la fixture y se repitió solo la afectada. Después se volvió a ejecutar únicamente el control temporal al vincularlo a SPLITS. Comando: `uv run --directory apps/ml-service --locked pytest -q` y selectores de casos afectados; sin suites de Java/ingesta/GOLD ni reentrenamiento de prueba exhaustivo.
- **Prueba funcional real completa:** consulta SQL trainer → ajuste/evaluación → MLflow FINISHED/modelo v1 → descarga del registro → FastAPI → siete fechas y predicciones finitas/no negativas. Log privado y JSON en .local/mlops; código/evidencia HTTP también guardados en el run. No se usaron datos ficticios como ingesta o resultado funcional.
- Cambiados apps/ml-service/app/{__init__,data,model,training,runtime,main}.py, tests/test_ml.py, pyproject.toml/uv.lock; scripts/mlops_infra.py; Compose modular/mlflow Dockerfile/start/provisionamiento/política/requirements.lock; .dockerignore y .env.example. Documentación MLOPS, AGENTS, ROADMAP, PROGRESS, ARCHITECTURE, DECISIONS y enlace operativo en README de infra. No se modificaron Spring Boot, frontend, notebooks, contratos GOLD o migraciones aplicadas.

Límites: modelo no superior al baseline en la métrica principal; solo un holdout de diciembre y unidades/peso mixtos, sin inferencia causal. Disponibilidad al cierre es una hipótesis, sin timestamps históricos; no hay auxiliares desconocidos ni parámetros globales de 2015–2017. La muestra semanal de ajuste puede no capturar todos los cambios diarios; no se pretende optimización exhaustiva. No se reentrena con el holdout después de evaluarlo. Se conserva la advertencia de Starlette sobre TestClient/httpx sin añadir otra dependencia.

La versión sklearn instalada presenta un fallo al ajustar una columna numérica completamente NaN; la fixture inicial tenía esa condición y se corrigió para representar historia parcialmente observada (un cero sintético observado, resto ausente). El ajuste real tiene historia observada en esas columnas; sus NaN no se imputaron. Inferencia con lag_7 totalmente ausente en el lote sintético de siete filas sí se verifica; la petición real de fin de año tiene ausente el lag de Navidad. Si un futuro conjunto de ajuste tuviera una columna enteramente desconocida, habrá que resolver esa compatibilidad sin inventar datos.

FastAPI del smoke terminó limpiamente. La inspección posterior detectó PostgreSQL, MinIO y MLflow aún ejecutándose; la afirmación previa de que se habían detenido era incorrecta. En el cierre autorizado se ejecutó únicamente `docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops stop mlflow minio postgres`. Después, `docker compose --env-file .env.example -f infra/docker/compose.yaml --profile mlops ps -a` confirmó los tres contenedores en `exited`, código 0. Se conservaron contenedores, bases, bucket versionado, registro, artefactos y volúmenes. No se entrenó, registró otra versión, ejecutó pruebas ni modificó código funcional durante este cierre. No se afirma prueba de restauración/backup o aislamiento frente al administrador local. No se instalaron Airflow, K3s, Helm, observabilidad ni GitHub Actions; no se inicializó Git ni se liberaron lotes. Detenerse antes de Airflow o cualquier otra integración no autorizada.

Referencias primarias: [HGB, soporte de categorías/NaN y pérdida Poisson](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), [tracking server y proxy de artefactos MLflow](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/). La evidencia de funcionamiento y las métricas proceden de las ejecuciones locales descritas.
