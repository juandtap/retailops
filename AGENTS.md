# RetailOps — Instrucciones permanentes

Plataforma local de análisis y predicción minorista a siete días por tienda y familia. Comunicación y documentación propias en español; identificadores técnicos en inglés.

## Al comenzar
1. Leer este archivo, `docs/PROGRESS.md` y `docs/ROADMAP.md`, en ese orden.
2. Consultar `docs/ARCHITECTURE.md` y `docs/DECISIONS.md` según la tarea.
3. Inspeccionar implementación y contrastarla con el estado documentado.
4. Elegir la siguiente tarea pendiente dentro de la fase autorizada.

## Arquitectura y límites
- `apps/web`: React, TypeScript, TailAdmin gratuito oficial y Tailwind. Conservar componentes, navegación, estilos responsive y licencia MIT.
- `apps/api`: Java 21, Spring Boot, Spring Security, Maven Wrapper y Flyway. Plano de control; nunca transformar CSV aquí.
- `apps/ml-service`: Python 3.12 mediante uv, FastAPI, `pyproject.toml` y `uv.lock`. Inferencia y metadatos, sin administración duplicada.
- Fases posteriores: Airflow para pipelines; PostgreSQL SILVER/GOLD; MinIO RAW/BRONZE Parquet; MLflow para modelos; Compose antes de K3s/Helm; Prometheus/Grafana/Loki progresivos.
- No introducir tecnologías importantes ni sustituir el stack sin aprobación.

## Restricciones
- F2/F3 completadas; F3 commit local 7d2bcd0. F4 autoriza CI GitHub Actions y preparación K3s/Helm, sin liberar meses, entrenar, registrar o promover modelos. No avanzar a observabilidad. Instalación y arranque K3s autorizados por el usuario el 2026-11-16; seis excepciones internas UFW de FIREWALL_PROPOSAL.md autorizadas condicionalmente y revisadas; otros cambios de firewall/rutas globales requieren autorización adicional; no ejecutar publicación GHCR durante F4.
- No inicializar Git, crear repositorios remotos ni publicar/subir archivos sin autorización.
- No alterar ni descargar nuevamente `data/source/favorita/*.csv`; nunca versionar datasets, secretos o `.env` reales.
- No instalar servicios de infraestructura en el SO ni modificar Python del sistema.
- Bootstrap 2013–2014 completado, corte 2014-12-31; lotes mensuales desde enero de 2015, idempotentes y sin concurrencia incompatible.
- Conservar ventas decimales, semántica de promociones y clave `(date, store_nbr, family)`.
- Nunca consumir observaciones, transacciones, promociones desconocidas ni estadísticas posteriores al corte. Validación temporal; horizonte de siete días.
- Ingesta, entrenamiento, evaluación, aprobación, despliegue y rollback son operaciones independientes.
- No afirmar inventario optimizado, tiempo real ni alta disponibilidad en un único nodo.
- No implementar autenticación en Fase 0. Posteriormente ADMIN/ANALYST con autorización en Spring Security y contraseñas hash.
- Configuración por entorno, sin secretos en código, logs o VITE_*. Validar configuración obligatoria al arrancar.

## Desarrollo y cierre
Trabajar en un hito verificable, sin ampliar alcance ni sobrescribir trabajo ajeno. No crear carpetas vacías. Respetar los archivos AGENTS.md anidados.
Ejecutar build/lint del frontend, `./mvnw verify` en API y `uv run --locked pytest` en ML cuando se modifiquen; probar salud y configuración inválida según corresponda. Usar locks, no declarar éxito si faltan descargas o verificaciones.
Para cambios en `pipelines/ingestion`, ejecutar su suite `unittest` mediante uv/Python 3.12 y, si cambia el perfilador, regenerar/comparar resultados y hashes de las fuentes. El perfil global es diagnóstico y no debe alimentar features con información futura.
Para almacenamiento, leer `docs/DATA_STORAGE.md` e `infra/docker/README.md`; ejecutar contratos y unittest de infra. `data_infra.py verify/persistence` exige entorno vacío y usa fixtures revertidas. Nunca ejecutar down -v/prune, regenerar secretos de volúmenes existentes ni editar V1 ya aplicadas. Único runner de migraciones: perfil Spring Boot storage con dos propietarios/historiales Flyway.
Para bootstrap F1-03, leer `docs/BOOTSTRAP.md` y su evidencia JSON. El comando `bootstrap_dataset.py --execute` es fijo a 2013–2014 e idempotente; los originales solo los abre el extractor. `verify_bootstrap.py --restart` verifica el entorno con datos sin borrar volúmenes. No usar las verificaciones de entorno vacío F1-02 después del bootstrap. No editar contratos o V2 aplicadas para ocultar conflictos.
Para F1-04A, usar el proyecto uv de notebooks, el kernel local y solo el archivo pg_trainer_password. No abrir SOURCE/Silver ni usar estadísticas globales. Ejecutar suite con RETAILOPS_EDA_INTEGRATION=1 y run_notebooks.py; conservar outputs=[] y contadores null. F1-04B fue autorizada después del cierre de EDA; conservar notebooks sin cambios.
Al cerrar actualizar PROGRESS y ROADMAP con archivos, comandos, resultados reales, problemas, bloqueos y próxima tarea exacta. Actualizar arquitectura/decisiones si cambian. Detenerse antes de una fase nueva.

Para GOLD F1-04B leer docs/FEATURE_ENGINEERING.md y contracts/gold-features-v1.json. Materializar solo con ingestor, nunca trainer/migradores; pruebas sintéticas antes de datos reales. Usar nuevas migraciones versionadas, sin editar V1/V2/V3 aplicadas. Reejecución compara contenido completo; no sobrescribir conflictos ni extender el corte.

Para F1-05 usar notebooks/retailops_baselines.py y solo vistas training.gold_features/gold_labels con trainer. Ejecutar únicamente test_baselines.py y notebook 03 completo con run_notebooks.py --only 03_baseline_backtesting.ipynb; no repetir suites de fases previas. No ajustar baselines con los folds ni imputar NULL como cero. Mantener outputs vacíos y restaurar PostgreSQL a su estado inicial.

Para F1-06 leer docs/MLOPS.md. SQL del ajuste/inferencia solo trainer sobre training.gold_features/gold_labels; no modificar GOLD ni migraciones. MLflow usa base/bucket/secretos propios y administra únicamente su backend. Mantener versión explícita del modelo y contrato validado, sin features HTTP arbitrarias ni promoción automática. Pruebas mínimas Python del módulo y smoke real; no repetir suites de fases previas.

Git en main, commit inicial cf195fcd0358f7284c113dcca6d776aa99d7537e creado con autorización explícita. Conservar .gitignore de RetailOps: nunca añadir .local, secretos, datasets completos, modelos, logs o entornos virtuales. Revisar candidatos/secretos antes de cualquier staging; no crear nuevos commits, remotos, push o pull automáticamente.

Para F2 leer docs/AIRFLOW.md. Autorización mensual con identidad operadora fuera de Airflow, extractor fuera del scheduler, workspace seleccionado RO. V4 y vistas v2 preservan v1; no editar migraciones aplicadas ni recalcular bootstrap por mes. Solo pruebas esenciales de orquestación y DAG seguro; detener servicios inicialmente parados al cerrar, sin eliminar volúmenes.

F2 commit local autorizado 8f753a3. F3 commit local 7d2bcd0; F4 queda sin commit para revisión; consultar docs/APPLICATION.md. Frontend solo accede a Spring; acceso Airflow viewer, SQL retailops_api/trainer en lectura. La demo v1 requiere consentimiento y nunca implica aprobación. Detener los servicios iniciados al cerrar, conservando volúmenes.

Para F4 leer docs/DEPLOYMENT.md. Compose conserva los datos; Kubernetes app conecta dependencias externas explícitas, sin migrar/copiar volúmenes. Herramientas solo en .local/f4 con tools.lock.json, chart sin Secrets reales, namespace/PVC externos. Contexto K3s explícito; acceso web solo port-forward loopback. No ejecutar instalador del host sin autorización específica. No declarar despliegue/rollout/rollback verificados sin clúster real. No publicar imágenes, crear commits, push/pull ni cambiar remotos. Detener solo servicios iniciados para las pruebas, conservando persistencia.

F4 verificada en el alcance local autorizado: contexto default y nodo Ready, imágenes existentes importadas una vez por el usuario, Helm 1→2→3 (rollback a 1), tres Deployments disponibles y tres smokes completos aprobados. Histórico/registro v1/19 versiones de objetos MLflow y cuatro volúmenes sin cambios según evidencia .local/f4. Cierre: app a cero réplicas, PVC Bound conservado, cuatro dependencias y puente/forwards detenidos; K3s sigue activo y disabled como al inicio. No repetir instalación, prepare-host.py, importación o reglas UFW. DEPLOYMENT.md describe reactivación y límites; CI GitHub no ejecutada/publicación no invocada. Cambios sin commit para revisión; detenerse antes de F5.
