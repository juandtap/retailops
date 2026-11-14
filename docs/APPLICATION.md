# F3 — Aplicación integrada local

React/TailAdmin → nginx `/api` → Spring Boot `/v1` → FastAPI → MLflow + GOLD autorizado. PostgreSQL y las APIs internas nunca se consultan desde el navegador. La aplicación es una consola local de lectura, sin autenticación comercial ADMIN/ANALYST ni exposición pública. Los puertos publicados se enlazan a loopback; no usar este despliegue como servicio multiusuario.

## Preparar y construir

Requiere Docker Compose, Java 21, Node/npm y el almacenamiento/modelo existentes de F1/F2. No inicializar un entorno vacío con estos comandos. Mantener los secretos privados y los volúmenes anteriores.

```bash
python scripts/prepare_app.py
(cd apps/api && ./mvnw -Dtest=PlatformApiTests verify)
(cd apps/web && npm ci && npm run build && npm run lint)
docker compose -f infra/docker/compose.yaml --profile app --profile mlops --profile airflow build ml-service api web
```

El script prepara una identidad Airflow **viewer**, conserva las contraseñas existentes y solo entrega su archivo lector a Spring. Airflow debe haberse preparado con el procedimiento F2. La imagen ML reutiliza `retailops-mlflow:local-v1`, construida según MLOPS.md; no instala dependencias adicionales al arrancar. Java/nginx se fijan por digest. Los builds Java/React se realizan fuera del contenedor y se copian únicamente sus artefactos compilados.

```bash
docker compose -f infra/docker/compose.yaml --profile app --profile mlops --profile airflow up -d --wait --wait-timeout 180 postgres minio mlflow airflow-api airflow-scheduler airflow-dag-processor ml-service api web
docker compose -f infra/docker/compose.yaml --profile app --profile mlops --profile airflow ps
python scripts/smoke_application.py
# Opcional: interrumpe solo FastAPI y lo restaura en finally:
python scripts/smoke_application.py --check-ml-outage
```

Abrir **http://127.0.0.1:5173** (`APP_PORT` configurable). Conserva accesos de mantenimiento F2 en loopback: PostgreSQL 5432, MinIO 9000/9001, MLflow 5000 y Airflow 8081, según configuración existente. FastAPI y Spring no publican puertos nuevos. DNS internos `postgres`, `ml-service`, `mlflow`, `airflow-api`, `minio`, `api`; frontend utiliza exclusivamente rutas relativas `/api/v1`.

## Contratos de consulta

| Método/ruta tras `/api/v1` | Comportamiento |
| --- | --- |
| GET `/platform` | Corte/publicación y disponibilidad sin DSN, tokens ni excepciones internas |
| GET `/history/state`, `/history/batches` | Estado real y hasta 40 lotes RELEASED/COMPLETE dentro del corte |
| GET `/catalog/stores`, `/catalog/families` | Identificadores distintos de hechos `training.sales` autorizados, máximo 100 |
| GET `/sales?storeNbr=1&family=GROCERY%20I&from=2014-12-01&to=2014-12-31&page=0&size=100` | Ventana ≤366 días, página 0–1000, tamaño 1–200; rechazo de fechas posteriores al corte |
| GET `/models/active` | `NO_APPROVED_MODEL`, candidato v1 explícito, métricas permitidas del run existente |
| GET `/pipelines` | Cuatro DAGs permitidos, hasta tres ejecuciones por DAG; identidad viewer sin rutas de trigger |
| POST `/predictions` | Inferencia delegada a FastAPI, siete horizontes verificados; candidato solo con consentimiento explícito |

Ejemplo de cuerpo de demostración:

```json
{"storeNbr":1,"family":"GROCERY I","issueDate":"2014-12-31","candidateDemo":true}
```

`CANDIDATE_DEMO_ENABLED` activa la capacidad de demo (Compose local: true; Java aislado: false). Además, cada solicitud debe consentirla; la UI exige marcar una casilla. No se cambia ningún alias, etiqueta, aprobación o versión MLflow. `productionApproved=false` en todas las predicciones. Sin consentimiento devuelve 409; fechas inválidas 400; features ausentes 404; dependencia ML indisponible 503 seguro. Timeouts HTTP connect 2 s/read 15 s; SQL connect 3 s/socket 10 s/statement 5 s. JDBC usa rol fijo `retailops_api`, transacciones read-only, parámetros preparados y rollback; inferencia conserva `trainer` y vistas training. El helper EDA admite el DNS Docker literal `postgres`, sin ampliar identidades ni privilegios.

Pantallas: dashboard, ventas con filtros/paginación y gráfico de página, pronósticos, modelo/métricas y pipelines. Huecos calendarios se muestran como desconocidos, nunca cero. Las cantidades de familias distintas no representan ingresos ni una unidad física homogénea. La fecha objetivo de una predicción puede superar el corte; las observaciones y features de origen no pueden hacerlo.

## Evidencia ejecutada

- Nueve servicios healthy al validar; modelo v1 descargado desde el registro persistido a volumen independiente `ml_inference_cache`.
- Corte 2014-12-31; un lote bootstrap de 1 297 296 filas; 54 tiendas y 33 familias. Tienda 1/GROCERY I, diciembre: 30 observaciones; 25 de diciembre ausente. Consulta hasta enero de 2015 rechazada.
- Predicción real desde Spring: emisión 2014-12-31, tienda 1/GROCERY I, objetivos 2015-01-01…07: **10.53490163, 2343.58832739, 1791.86781423, 931.47117528, 1865.60140568, 2814.96193602, 2814.96193602**.
- Modelo candidato v1, run `55257fc2ce414793b73b9d0df4c95fbb`. Holdout: HGB MAE 125.633166, WAPE 26.192141 %, RMSLE 0.522605; Seasonal Naïve MAE 120.912959, WAPE 25.208067 %, RMSLE 0.573126. **HGB no supera MAE/WAPE**. No se entrenó, registró ni promovió otro modelo.
- Smoke con caída real de FastAPI: 503 `ML_UNAVAILABLE`, recuperación del mismo v1; comparación privada contra secretos locales sin coincidencias en respuestas. Evidencia `.local/application/smoke.json` (ignorada).
- JUnit: cuatro casos relevantes verificados (tres aprobados inicialmente; consentimiento corregido y caso vuelto a ejecutar con éxito). Pytest del contrato de carga/inferencia: uno aprobado. Frontend build y lint correctos; warnings heredados de TailAdmin y aviso de bundle ApexCharts grande. No se repitieron suites de fases previas.

## Parada conservadora

```bash
docker compose -f infra/docker/compose.yaml --profile app --profile mlops --profile airflow stop web api ml-service airflow-dag-processor airflow-scheduler airflow-api mlflow minio postgres
docker compose -f infra/docker/compose.yaml --profile app --profile mlops --profile airflow ps -a
```

No usar `down -v`, prune ni eliminar artefactos. Persisten base de datos, objetos, experimentos, logs y caché del modelo. La aplicación no ofrece ingesta, entrenamiento, promoción ni disparo de DAGs. Quedan pendientes autenticación comercial, autorización multiusuario, ajuste del bundle y despliegues/observabilidad de fases posteriores, sin implementarlos aquí.

Verificación Chromium/Playwright temporal: cinco pantallas con respuestas HTTP reales 200, gráficos, 30 filas históricas, consentimiento obligatorio, siete predicciones y viewport móvil 390 px sin desbordamiento ni errores JavaScript. Evidencia y capturas privadas en `.local/application/{browser.json,dashboard.png,sales.png,forecast.png,mobile.png}`. La primera espera del comprobador se corrigió para opciones HTML nativas ocultas; no era un fallo de la aplicación.

Cierre operativo F3 verificado con `docker compose ps -a`: los nueve servicios (PostgreSQL, MinIO, MLflow, Airflow API/scheduler/dag processor, FastAPI, Spring y web) quedaron exited. Ocho con código 0; Java con 143 (terminación SIGTERM de Compose). Se conservaron contenedores, volúmenes, datos y artefactos; evidencia privada `services-stopped.json`. Cambios F3 sin commit.
