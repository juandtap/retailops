# Registro de decisiones

Fecha: 2026-11-13. El stack y la simulación histórica están aprobados por el prompt maestro. «Prevista» indica que la decisión está establecida pero la tecnología aún no está instalada/integrada. No se incorporan plataformas adicionales.

| ID | Decisión y estado | Razón / ventajas | Coste o limitación | Alternativa considerada |
| --- | --- | --- | --- | --- |
| ADR-001 | Spring Boot, Java 21; base presente | Plano de control tipado y ecosistema de seguridad/transacciones | JVM y configuración; no usarlo para ETL | Backend Python único simplifica procesos, pero mezcla administración e inferencia y contradice el stack |
| ADR-002 | FastAPI, Python 3.12; base presente | Separación de inferencia y bibliotecas ML | Otro proceso/contratos HTTP | Inferencia dentro de Java dificulta reutilizar modelos Python |
| ADR-003 | TailAdmin React gratuito; presente | Componentes, navegación, tablas y estilos reutilizables reales | Mantener dependencia upstream, ejemplos y licencia | Dashboard propio aumenta trabajo y no cumple la base solicitada |
| ADR-004 | PostgreSQL; infraestructura presente, sin datos | Integridad, transacciones, claves naturales y consultas analíticas | Operar volúmenes y backups | SQLite reduce operación pero limita el stack objetivo y concurrencia futura |
| ADR-005 | MinIO; infraestructura local presente, sin datos | Objetos compatibles S3, particiones y artefactos locales | Servicio/volúmenes adicionales | Sistema de archivos directo es simple pero menos representativo del acceso por objetos |
| ADR-006 | Airflow; prevista | DAGs, historial y reintentos visibles | Peso operativo; proteger idempotencia fuera del scheduler | Cron/scripts carecen del historial y control de ejecuciones solicitado |
| ADR-007 | MLflow y Model Registry; previstos | Experimentos y versiones trazables | Requiere configurar backend, objetos y acceso | Registro manual en archivos dispersa trazabilidad |
| ADR-008 | Docker Compose presente; K3s posterior | Entorno reproducible sin instalar servicios en el SO | Un solo equipo, sin alta disponibilidad | Servicios nativos complican aislamiento y contradicen las restricciones |
| ADR-009 | K3s de un nodo; previsto | Práctica local de despliegues/probes/recuperación | Más operación sin redundancia física | Solo Compose no cubre el objetivo Kubernetes; clúster multinodo queda fuera del alcance |
| ADR-010 | Helm; previsto | Despliegues parametrizados/versionados | Complejidad de plantillas | Manifiestos planos duplican configuración por entorno |
| ADR-011 | Prometheus, Grafana, Loki; previstos | Métricas, paneles y logs correlacionados | Consumo y mantenimiento progresivos | Logs locales bastan inicialmente, pero no cubren la observabilidad final |
| ADR-012 | Maven + Wrapper; presentes | Versiones fijas, ecosistema Java y ejecución reproducible | Descarga inicial; Maven no genera lock transitivo | Gradle excluido expresamente |
| ADR-013 | uv, Python 3.12, pyproject y uv.lock; presentes | Gestión aislada y resolución bloqueada sin tocar Python 3.14 | Requiere descargar runtime/dependencias | pip/requirements y Python del SO incumplen las reglas o dispersan configuración |
| ADR-014 | Simulación histórica mensual; prevista | Liberación reproducible, sin fingir una fuente en tiempo real | Granularidad mensual y último mes parcial | Liberar todo el dataset produce fuga temporal; streaming no corresponde a la fuente |
| ADR-015 | GitHub Actions; prevista tras autorización de Git/GitHub | Automatizar pruebas y artefactos | Runners externos no acceden siempre al equipo apagable | Despliegue remoto continuo no es apropiado para K3s local |

## Concreciones de Fase 0

- TailAdmin 2.5.0 desde commit `df1e9f37e56e0bf83030e8063f5353da2e0ecf18`, archivo del repositorio oficial, sin Git. Mantener LICENSE.md original MIT. Conservar componentes y demos en código, pero presentar solo una portada de Foundation en español; no exponer ventas ni autenticación ficticias. Las librerías auxiliares ya proceden de la plantilla.
- Mantener Node 26/npm 12: instalación bloqueada y build verifican compatibilidad operativa. No se cambia el runtime del equipo. Se fija la familia de versiones en `engines` y npm en `packageManager`.
- Spring Initializr indicó 4.1.2.RELEASE, pero Maven Central solo publica 4.1.2. Se corrigió el parent a la versión oficial publicada; Maven Wrapper fija Maven 3.10.0. Las dependencias siguen el BOM de Spring Boot y plugins versionados por el parent.
- Actuator expone solo salud pública sin detalles sensibles y probes del proceso. Spring Security y Flyway se incorporarán en sus fases para evitar autenticación o una base de datos prematuras.
- FastAPI expone salud del proceso; no declarar disponibilidad de inferencia sin modelo. uv instala Python en `.local/python` del proyecto. No forzar ni reemplazar ejecutables existentes del usuario.
- Valores por defecto de loopback y puertos locales; no se necesitan secretos ni URLs de infraestructura todavía. El proxy de desarrollo es configurable, sin CORS global permisivo.

## Pendientes de aprobación/diseño

La sesión con cookie de Spring Security es una propuesta para Fase 2, no una decisión implementada. Antes de incorporarla, revisar CSRF, duración de sesión, almacenamiento de usuarios, hash de contraseñas y política de origen. Diseñar en la fase correspondiente esquemas, transacciones de corte histórico, contratos internos, baseline y criterios de promoción.

Fuentes: [TailAdmin oficial](https://github.com/TailAdmin/free-react-tailwind-admin-dashboard), [Spring Initializr](https://start.spring.io/), [Maven Central — parent Spring Boot](https://repo.maven.apache.org/maven2/org/springframework/boot/spring-boot-starter-parent/), [proyectos uv](https://docs.astral.sh/uv/guides/projects/).

## ADR-016 — Perfilado de F1-01 con biblioteca estándar

Estado: implementada en el alcance autorizado de F1-01. Python 3.12 y uv con lock propio en `pipelines/ingestion`. Lectura CSV por bloques y agregados incrementales; SQLite de `sqlite3` conserva temporalmente claves/valores para duplicados, percentiles y relaciones exactas sin retener millones de objetos Python. No se incorpora un servidor, dependencia externa ni almacenamiento de aplicación.

Ventaja: reproducible sin descargas de librerías ni carga completa en RAM. Coste: requiere espacio temporal y múltiples recorridos/índices; el sistema puede usar tmpfs y su caché de archivos no está incluida en el RSS del proceso. Alternativas: conjuntos/listas completos en Python elevan memoria; pandas/otras librerías añadirían una dependencia innecesaria para este hito.

La completitud de calendario se distingue de la cuadrícula observada. Los 25 de diciembre ausentes y el último mes parcial se registran sin imputación ni rechazo automático. El manifiesto es PLAN_ONLY, no libera datos ni avanza el corte. Los resultados globales nunca se usan como parámetros de entrenamiento.

## ADR-017 — Almacenamiento y límites de F1-02

La solicitud posterior amplió expresamente F1-02 desde Compose básico a modelo, contratos, migraciones y control de acceso. PostgreSQL 18.7 fijado por digest, volúmenes persistentes y MinIO desde fuentes oficiales con commits/checksums/base fijados. MinIO comunitario está archivado y los tags históricos consultados en Quay devolvieron 401; no se incorporó una alternativa ni edición comercial sin autorización. Go se usa solo dentro del builder Docker, no como servicio o herramienta instalada en el SO. La imagen conserva licencias AGPL originales. Riesgo aceptado dentro del alcance local solicitado: no hay mantenimiento upstream de MinIO; no recomendar este despliegue para producción.

`control` pertenece a retailops_control_migrator; `data_meta/silver/gold/training` a retailops_data_migrator. Un runner Spring Boot/Flyway optativo con dos historiales separados aplica ambos grupos, en orden; no hay DDL competidor en pipelines ni inicialización SQL alternativa. El proceso web no recibe credenciales migradoras ni requiere base de datos para su salud actual.

Acceso mínimo: entrenador solo SELECT sobre vistas de seguridad con corte y estado de lote verificados en el servidor; sin tablas base, modificación de corte, escalada de rol o tablas temporales. MinIO separa físicamente cuarentena de released; escritor de ingesta no puede publicar, entrenador no puede leer futuro ni escribir. Alternativa descartada: un bucket único y filtros voluntarios de fecha no protegen contra una consulta o clave incorrecta. No se afirma protección frente a administradores/usuario local con acceso a SOURCE. El runtime de entrenamiento deberá restringir montajes/credenciales en su fase.

NUMERIC sin truncamiento para ventas, promociones enteras, NULL/ausencias diferenciados de cero y feriados agregados por ámbito antes del join. known_from y evidencia explícita para auxiliares; sin evidencia se excluyen de vistas de entrenamiento. Preservar los hallazgos de F1-01 sin rellenar Navidad/mes parcial automáticamente.

No hay atomicidad distribuida S3/PostgreSQL: el publicador futuro deberá autorizar en SQL antes de copiar a released, gestionar indisponibilidad parcial/reintentos e impedir ingestas concurrentes incompatibles. Esa operación no se implementa en F1-02. Versionado S3 no equivale a WORM; registrar versión+SHA-256 y evitar sobrescrituras mediante el contrato de contenido en F1-03.

Operación local: secretos en archivos 0600 ignorados, sin claves hardcodeadas; Compose secrets no es un gestor cifrado. Red bridge con puertos 127.0.0.1, no `internal:true` porque impedía publicar puertos en este Docker. HTTP local sin TLS, un solo nodo y sin alta disponibilidad. Probar persistencia con marcadores administrativos y fixtures revertidas, nunca con una ingesta ficticia.

## ADR-018 — Bootstrap y publicación recuperable de F1-03

Contrato bootstrap-v1: 2013–2014, 1 297 296 ventas, cuadrícula completa de días observados y ausencias de Navidad 2013/2014 aceptadas explícitamente. Distinguir calendario incompleto de lote contractualmente completo; no imputar ceros. El corte final es el último día autorizado 2014-12-31.

Clientes bloqueados en uv.lock: PyArrow 24.0.0 para Parquet/Decimal128(38,18), Psycopg 3.3.9 para COPY y transacciones, SDK MinIO 7.2.20 para S3/versiones. Son bibliotecas para tecnologías ya aprobadas, no nuevas plataformas. Extracción con bloques globales acotados y bytes RAW preservados; ninguna estadística futura ni feature se calcula.

V2 compatibles, sin editar V1: publications/inventario con fases STAGING/AUTHORIZED/COMPLETE; vistas condicionadas a COMPLETE; ordinal nullable en huecos derivados para no inventar procedencia. Se serializa por advisory lock de sesión y se refuerzan períodos incompatibles mediante índice/trigger. Silver se carga en una transacción única; la reejecución compara contratos, contenido, conteos y versiones y no sobreescribe conflictos.

SQL autoriza antes de copiar a released, conforme a F1-02. El corte permanece anterior hasta verificación completa y finalización SQL. Una copia existente sin confirmación se recupera por su hash/versión; el historial conserva intentos fallidos y no declara éxito prematuro. No hay atomicidad distribuida ni garantía de que todos los objetos aparezcan a la vez. Alternativa descartada: copiar futuro primero y confiar en filtros voluntarios o marcar éxito antes del inventario completo.

Se cargan auxiliares del período, pero tiendas/familias/feriados/petróleo quedan con known_from/evidencia NULL y sus objetos permanecen privados en cuarentena. No se infieren fechas de disponibilidad de snapshots o calendarios sin anuncios históricos. Las familias se obtienen de identificadores del histórico seleccionado, sin vocabularios futuros. Esta política es conservadora y limita features futuros hasta una decisión explícita con evidencia.

Integración real previa en bases temporales y objetos con UUID, incluyendo fallo tras autorización, publicación parcial, copia sin confirmación, conflictos e idempotencia/reinicio. El bootstrap real se cargó una vez y luego se verificó con una reejecución sin duplicados/versiones nuevas y un reinicio real. El manifiesto de planificación se conserva intacto; solo control almacena el estado operativo.

## ADR-019 — EDA aislado y reproducible de F1-04A

La solicitud divide la antigua F1-04 en EDA/Jupyter (A, autorizada) y GOLD/controles (B, pendiente). Proyecto uv/Python 3.12 propio en notebooks con lock: JupyterLab/ipykernel, nbformat/nbclient para ejecución automatizada, pandas/NumPy para agregados y correlaciones, matplotlib para figuras y Psycopg para consultas. No se añade plataforma de datos ni se instala globalmente.

Solo rol retailops_trainer, archivo de secreto específico y vistas training, ventana fija 2013–2014 y batch bootstrap. Consultas parametrizadas en registro cerrado; readonly, timeout 30 s y máximo 5000 filas aceptadas. No se usan helpers de administración ni datos/estadísticas de SOURCE/Silver/2015–2017. Las dimensiones/auxiliares ocultos se documentan en lugar de buscar otra fuente o elevar privilegios.

Se agrega en servidor y solo se descargan resúmenes/series acotadas. Cero y ausencia se separan, se conserva calendario con NaN y Pearson por pares de días de calendario explicita el tratamiento de faltantes. Se evita una librería de modelado/ACF adicional innecesaria; no se estiman bandas o causalidad. Medias móviles y cuantiles son descriptivos, no features persistidas ni estadísticas autorizadas para folds anteriores.

Notebooks canónicos sin outputs; NBClient ejecuta en memoria con kernel uv local y persiste solo evidencia/figuras agregadas. El launcher JupyterLab usa loopback/token automático y limpia outputs al guardar mediante hook. Configuración y kernel se mantienen en .local/eda, sin registro global o montajes privilegiados. No es una sandbox frente al usuario propietario de la PC ni un servicio multiusuario remoto.

## ADR-020 — GOLD diario point-in-time y etiquetas separadas

F1-04B autorizada explícitamente tras EDA; roadmap ya contemplaba la subdivisión y no se alteran fases completadas. Materializar todos los días de emisión 2013–2014 y siete horizontes: 9 106 020 ejemplos, incluidas emisiones en fechas ausentes, sin generar ventas. Ventanas de calendario terminan al emitir, lag respecto al objetivo, NULL/flags conservados; stddev muestral. Asumir ventas disponibles al cierre es una hipótesis documentada porque faltan timestamps históricos de llegada.

Se reutiliza ingestor como identidad confiable de transformación, separado de trainer, sin nuevas credenciales/plataformas. Trainer sigue limitado a vistas training; etiquetas en superficie distinta y nunca en MODEL_INPUTS. V3 control bloquea snapshot mediante función SECURITY DEFINER de propósito fijo; V3 data crea tablas/vistas. Runner único Flyway, V1/V2 inmutables.

Bloques mensuales en transacción, advisory lock compartido con bootstrap y comparación bidireccional EXCEPT en reintentos; no sobrescribir conflictos. Mantener NUMERIC y código hash. Alternativa de materializar semanalmente reduciría volumen pero limitaría emisiones diarias; 401 GiB disponibles y cobertura completa viable, sin cambiar diseño. No se persisten parámetros globales, imputaciones, auxiliares desconocidos o predicciones. Snapshot v1 fijo: incorporar otro corte requerirá contrato/versionado explícito.

## ADR-021 — F1-05 sin MLflow, baselines sin ajuste

La solicitud actual reemplaza el alcance previo de F1-05 (baseline+MLflow) por tres referencias fijas: lag semanal y medias retrospectivas 7/28 de GOLD. MLflow y modelos supervisados quedan diferidos. Evaluar emisiones de julio, septiembre y noviembre 2014; etiquetas solo para puntuar, intersección común para clasificación directa y cobertura individual. WAPE indefinido con volumen cero, NULL sin imputación, RMSLE sin clipping porque las features son no negativas. Cursor por bloques, conexión trainer reutilizada, notebook como verificación principal y solo tres pruebas mínimas; sin nuevos servicios/dependencias. Resultados en BASELINE_RESULTS.md.

## ADR-022 — HGB global, MLflow separado e inferencia desde GOLD

F1-06 autoriza un único HGB Poisson sklearn y MLflow/FastAPI. Categorías nativas mediante encoder de entrenamiento, NaN preservado, sin optimización extensa. Ajuste con emisiones semanales y etiquetas ≤2014-10-31; validación noviembre y holdout diciembre 8..24 posterior a objetivos F1-05. Sin refit posterior al holdout ni cambio de métricas/población al perder contra baseline.

MLflow posee base/bucket/identidades propios; modelo y registros persisten en volúmenes existentes. Runner MLflow administra su base independiente, sin DDL en negocio ni migraciones Flyway editadas. Artefactos vía proxy: trainer/API no requieren secretos S3 o administrativos. Se usan locks uv y base Docker por digest; entorno ML existente ampliado, sin plataforma adicional.

FastAPI fija versión registrada, valida contrato y obtiene features de training con trainer; JSON no admite features arbitrarias. Rechaza emisiones anteriores al ajuste o posteriores al corte. Modelo servido como candidato explícito para comprobación funcional, no promoción automática; aprobación/rollback siguen pendientes. Carga de artefactos solo desde origen propio confiable, con lista explícita de tipos skops y habilitación de ejecución de modelo. Límites y resultado negativo en métricas principales se conservan en MLOPS.md.

## ADR-023 — Git local anticipado, sin publicación

Autorización explícita después del cierre F1-06 para preparar el repositorio antes de Airflow: auditoría adaptada de .gitignore e inicialización en main. Sin staging, primer commit, remotos o push; no equivale a ejecutar GitHub Actions ni completar F5-01. Versionar código/locks/contratos/configuración segura/notebooks fuente e informes agregados revisados; excluir datasets completos, secretos, modelos serializados y runtime. Revisión básica de candidatos sin coincidencias con secretos reales conocidos; futuras adiciones requieren la misma revisión.
