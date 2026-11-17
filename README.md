# RetailOps — Retail Sales Forecasting & MLOps Platform

Plataforma full-stack local de análisis y predicción de ventas diarias por tienda y familia a siete días. Demuestra ingeniería de software y datos, ML, MLOps, DevOps y SRE mediante una reproducción histórica de Corporación Favorita. Apoya planificación comercial y estimación de demanda; no optimiza inventario real.

**Estado:** F0/F1/F2/F3 completadas en sus alcances registrados; aplicación React → Spring → FastAPI verificada con datos reales y candidato MLflow v1, sin aprobación de producción. Corte 2014-12-31; cero meses nuevos liberados. F4 incorpora CI validada localmente y despliegue K3s/Helm real con smoke y ensayo de actualización/rollback aprobados. Laboratorio detenido conservando recursos; K3s sigue activo con autoarranque deshabilitado. F5.1 añade métricas, Prometheus y Grafana verificados; F5.2 añade Loki/Alloy y logs HTTP correlacionados verificados; F5.3 añade alertas locales y SLO propuestos; sin autenticación comercial ni F5.4. Ver [progreso](docs/PROGRESS.md), [roadmap](docs/ROADMAP.md) y [despliegue](docs/DEPLOYMENT.md).

## Stack y arquitectura

| Componente | Tecnología | Responsabilidad |
| --- | --- | --- |
| `apps/web` | React, TypeScript, TailAdmin gratuito, Tailwind CSS | Interfaz responsive |
| `apps/api` | Java 21, Spring Boot 4.1.2, Maven Wrapper | Plano de control y API integrada; Flyway en perfil de mantenimiento |
| `apps/ml-service` | Python 3.12, FastAPI, uv | Inferencia explícita del candidato v1 y metadatos |
| Ingeniería de datos | Airflow, PostgreSQL, MinIO, Parquet | SOURCE → RAW → BRONZE → SILVER → GOLD |
| MLOps | MLflow | Experimentos, registro y versiones de modelos |
| Infraestructura | Docker Compose → K3s de un nodo, Helm | Ejecución y despliegues locales |
| Operación | GitHub Actions, Prometheus y Grafana; Loki pendiente | CI declarada; observabilidad fuera de F4 |

El navegador solo se comunica con Spring Boot, que consulta histórico/metadatos, delega inferencia a FastAPI y consulta Airflow como viewer. La aplicación no ejecuta ingestas, entrenamientos ni promociones. Más detalle en [aplicación](docs/APPLICATION.md), [arquitectura](docs/ARCHITECTURE.md) y [decisiones](docs/DECISIONS.md).

## Requisitos e instalación

Entorno verificado: CachyOS, OpenJDK 21.0.13, Maven 3.10.0, Node 26.13.1, npm 12.2.2 y uv 0.13.8. No reinstalar herramientas del sistema. Maven Wrapper descarga Maven si es necesario. Python se gestiona con uv; no usar ni reemplazar Python 3.14 del sistema. Las descargas iniciales requieren red.

Desde la raíz, crear la configuración local:

```bash
cp .env.example .env
```

Este archivo solo contiene configuración pública de Fase 0. Para mantener Python y sus ejecutables dentro del proyecto, ejecutar desde la raíz:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
export UV_PYTHON_BIN_DIR="$PWD/.local/bin"
uv python install 3.12.16
```

En terminales nuevas, volver a exportar esas dos rutas absolutas antes de usar uv. El directorio `.local/` está excluido de Git.

Instalar las dependencias bloqueadas de cada aplicación:

```bash
cd apps/web
npm ci
```

```bash
cd apps/ml-service
uv sync --locked
```

Ejecutar esos bloques desde la raíz en terminales separadas. No se requiere Docker en Fase 0 ni se levanta infraestructura.

## Configuración y ejecución

En cada terminal, desde la raíz, exportar `.env` antes de cambiar de directorio:

```bash
set -a
source .env
set +a
```

En Bash/Zsh `source` carga el ejemplo compatible; no ejecutar archivos de configuración no confiables. En Fish, exportar las variables de forma equivalente. Vite también lee automáticamente el `.env` de la raíz. La API y ML reciben variables de entorno exportadas.

| Servicio | Comando desde su carpeta | Dirección por defecto | Salud |
| --- | --- | --- | --- |
| Web | `npm run dev` | `http://127.0.0.1:5173` | Página principal |
| API | `./mvnw spring-boot:run` | `http://127.0.0.1:8080` | `/actuator/health` |
| ML | `uv run --locked python -m app` | `http://127.0.0.1:8000` | `/health` |

Spring publica también `/actuator/health/liveness` y `/actuator/health/readiness`. Estas señales describen el proceso sin dependencias de datos; la salud de ML no significa que exista un modelo cargado. La web muestra un estado inicial sin métricas ficticias.

Variables: `API_HOST`, `API_PORT`, `ML_HOST`, `ML_PORT`, `WEB_HOST`, `WEB_PORT` y `API_PROXY_TARGET`; valores locales por defecto en `.env.example`. ML y Vite validan sus parámetros al iniciar; Spring convierte y valida los parámetros del servidor. No hay credenciales obligatorias en esta fase. No colocar secretos en `VITE_*` porque se publican en el navegador. No versionar `.env` reales ni introducir credenciales en logs o documentación.

## Compilación y pruebas

Desde las carpetas respectivas:

```bash
# apps/web
npm run build
npm run lint
```

```bash
# apps/api
./mvnw verify
# Jar resultante: target/api-0.0.1-SNAPSHOT.jar
```

```bash
# apps/ml-service
uv run --locked pytest -q
```

Con las dependencias instaladas y el JAR compilado, desde la raíz: `python scripts/smoke_foundation.py`. Este script solo usa la biblioteca estándar para iniciar los tres procesos en puertos locales temporales, comprobar HTTP/probes/proxy y detenerlos al finalizar. Puede ejecutarse con Python del sistema como utilidad de verificación; el servicio ML siempre se inicia con su `.venv` Python 3.12. Logs en `.local/verification/`, excluidos de Git. No sube archivos ni procesa datos.

`package-lock.json` conserva resoluciones e integridad de npm; `uv.lock` fija dependencias Python. Maven usa versiones fijas del parent/BOM y Wrapper; no tiene lock equivalente y requiere conservar esos números al actualizar. Resultados y advertencias reales en PROGRESS. Las pruebas que usan sockets/instrumentación pueden necesitar ejecución fuera de un sandbox restringido. No se ha realizado QA visual en navegador en esta sesión.

## Dataset

Los originales de [Kaggle — Store Sales: Time Series Forecasting](https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data) deben estar en `data/source/favorita/`: `train.csv`, `stores.csv`, `holidays_events.csv`, `oil.csv`, `transactions.csv`, `test.csv` y `sample_submission.csv`.

Los siete archivos estaban presentes al inicializar. [Inventario local](docs/DATA_INVENTORY.json) registra tamaños, columnas y SHA-256; no contiene ventas ni datos de filas. No descargar nuevamente, modificar o publicar los originales. `data/source/` y las capas generadas están excluidas de Git. El perfilado estadístico y temporal está implementado en F1-01; ver [informe](docs/DATA_PROFILING.md) y [módulo reproducible](pipelines/ingestion/README.md). El manifiesto mensual solo describe lotes; no libera datos ni avanza el corte.

Bootstrap futuro: 2013–2014, corte 2014-12-31. Desde enero de 2015, liberar un mes por ejecución hasta agosto de 2017, posiblemente incompleto. Nunca utilizar información posterior al corte, incluidas transacciones y promociones desconocidas. Validación temporal, sin particiones aleatorias. La ingesta no dispara entrenamiento ni despliegue automáticamente.

## Continuidad y licencias

Leer `AGENTS.md`, PROGRESS y ROADMAP antes de continuar. El alcance autorizado llega al EDA F1-04A; detenerse antes de F1-04B/GOLD y no liberar meses incrementales y no inicializar Git todavía. TailAdmin procede del [repositorio oficial](https://github.com/TailAdmin/free-react-tailwind-admin-dashboard), commit `df1e9f37e56e0bf83030e8063f5353da2e0ecf18`; licencia MIT original en [apps/web/LICENSE.md](apps/web/LICENSE.md). No se utilizan componentes Pro. Las páginas de ejemplo conservadas en el código no son funcionalidades de RetailOps.

## Repetir el perfilado de F1-01

Desde la raíz, con Python 3.12 gestionado por uv ya instalado:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv run --project pipelines/ingestion --locked python pipelines/ingestion/profile_dataset.py --source data/source/favorita --output docs
uv run --project pipelines/ingestion --locked python -m unittest discover -s pipelines/ingestion/tests -v
```

El módulo utiliza solo la biblioteca estándar, lectura por bloques y almacenamiento temporal para las comprobaciones exactas. No altera los originales ni crea infraestructura. Consulte el README del módulo para límites y opciones.

## Almacenamiento de F1-02

PostgreSQL 18.7 y MinIO se ejecutan localmente con Compose, volúmenes persistentes, secretos generados y puertos de loopback. No montan los CSV. El proceso web de Spring Boot sigue arrancando sin base de datos; un perfil de mantenimiento optativo ejecuta Flyway con propietarios/historiales separados para control y datos.

Leer el [manual de operación](infra/docker/README.md) para preparar secretos, compilar MinIO desde fuentes oficiales fijadas, iniciar, migrar, verificar, detener y conservar volúmenes. El [diseño de almacenamiento](docs/DATA_STORAGE.md) y [contrato v1](contracts/data-storage-v1.json) explican esquemas, ausencia vs cero y la separación efectiva de credenciales/vistas/buckets. MinIO comunitario está archivado; se documentan sus límites de mantenimiento. F1-03 ejecutó el bootstrap 2013–2014; los lotes mensuales posteriores siguen sin liberar.

## Bootstrap histórico de F1-03

El [contrato y protocolo](docs/BOOTSTRAP.md) acepta explícitamente las ausencias de Navidad sin generar ventas cero. Los [resultados verificables](docs/BOOTSTRAP_EVIDENCE.json) registran 1 297 296 ventas, 54 tiendas, 33 familias, 195 objetos en cuarentena y 98 publicados. Los auxiliares sin evidencia temporal permanecen restringidos y con known_from NULL.

Desde la raíz:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv run --project pipelines/ingestion --locked python scripts/data_infra.py up
uv run --project pipelines/ingestion --locked python pipelines/ingestion/bootstrap_dataset.py --execute
uv run --project pipelines/ingestion --locked python scripts/verify_bootstrap.py --restart
```

El primer comando, con el lote ya completado, verifica idempotencia sin recargar observaciones. El segundo prueba persistencia reiniciando los servicios: no ejecutarlo mientras otro trabajo dependa de ellos. No usar `data_infra.py verify/persistence` de F1-02 para el entorno cargado; esos controles exigen tablas vacías y se rechazan deliberadamente. El manifiesto original sigue siendo planificación sin liberación; consultar las tablas control para estado operativo.

## EDA con Jupyter — F1-04A

Los [notebooks](notebooks/README.md) ejecutan análisis exploratorio y temporal sobre training con credenciales restringidas y datos hasta 2014-12-31. No leen SOURCE/Silver ni auxiliares restringidos; no crean GOLD o modelos. El proyecto uv separado tiene dependencias bloqueadas y un kernel local Python 3.12. Los notebooks se guardan sin outputs; las figuras agregadas y [hallazgos](docs/EDA_FINDINGS.md) se generan tras ejecución completa. [Evidencia de ejecución](docs/EDA_EXECUTION.json).

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv sync --project notebooks --locked
docker compose --env-file .env.example -f infra/docker/compose.yaml up -d --wait postgres
uv run --project notebooks --locked python notebooks/lab.py
# Alternativa automática: uv run --project notebooks --locked python notebooks/run_notebooks.py
```

F1-04B requiere autorización posterior.

GOLD point-in-time F1-04B: [contrato, ejecución y resultados](docs/FEATURE_ENGINEERING.md), con siete horizontes y etiquetas separadas al corte 2014-12-31. No hay modelos entrenados.

Aplicación integrada F3: [inicio, endpoints y smoke real](docs/APPLICATION.md).

CI y despliegue F4: [DEPLOYMENT.md](docs/DEPLOYMENT.md). Workflows/imágenes validados localmente; K3s/Helm y ensayo real de rollout/rollback aprobados. Actions remota y publicación no ejecutadas. Compose conserva infraestructura y datos; sin publicación automática ni observabilidad.

F5.1: [observabilidad con Prometheus y Grafana](docs/OBSERVABILITY.md), dashboards provisionados y cuatro targets UP verificados. Laboratorio detenido conservando métricas/PVC/credenciales; procedimiento de reactivación documentado. F5.2: [Loki/Alloy y correlación](docs/LOGGING.md); cobertura de logs HTTP propios, persistencia real y cierre conservador. Sin F5.3.

F5.3: [Alertmanager local, SLI/SLO y cierre planificado](docs/SRE.md); [runbooks operativos](docs/RUNBOOKS.md). Notificaciones solo al receptor local, sin destinatarios externos; presupuestos condicionados a cobertura suficiente. No avanzar a F5.4.

F5.4: [backups cifrados y restauración aislada](docs/BACKUP_RECOVERY.md). Dos restauraciones del plano de datos/artefacto comprobadas (~95s cada una), con VersionId, hashes completos y candidato v1 conservados. Copias privadas fuera de Git, clave separada, sin offsite ni RTO integral de aplicaciones. Cierre conserva originales/PVC; sin F5.5.
