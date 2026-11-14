FROM apache/airflow:3.3.2-python3.12@sha256:9df9c8be4096b9cc626bd7cb1f2b8c712eef66c59c615f8c7e6200871ca10bd1
USER root
RUN mkdir -p /opt/retailops/.local/secrets /opt/retailops/.local/airflow /opt/retailops/.local/mlops && chown -R airflow:root /opt/retailops
COPY --chown=airflow:root pipelines/ingestion/pyproject.toml pipelines/ingestion/uv.lock /opt/locks/ingestion/
COPY --chown=airflow:root apps/ml-service/pyproject.toml apps/ml-service/uv.lock /opt/locks/ml/
USER airflow
RUN UV_PROJECT_ENVIRONMENT=/opt/retailops/ingestion-venv uv sync --project /opt/locks/ingestion --frozen --no-dev --python /usr/local/bin/python && UV_PROJECT_ENVIRONMENT=/opt/retailops/ml-venv uv sync --project /opt/locks/ml --frozen --no-dev --python /usr/local/bin/python
COPY --chown=airflow:root pipelines /opt/retailops/pipelines
COPY --chown=airflow:root apps/ml-service/app /opt/retailops/apps/ml-service/app
COPY --chown=airflow:root apps/ml-service/uv.lock /opt/retailops/apps/ml-service/uv.lock
COPY --chown=airflow:root notebooks/retailops_eda /opt/retailops/notebooks/retailops_eda
COPY --chown=airflow:root notebooks/retailops_baselines.py /opt/retailops/notebooks/
COPY --chown=airflow:root contracts /opt/retailops/contracts
COPY --chown=airflow:root docs/DATA_BATCH_MANIFEST.json docs/DATA_INVENTORY.json /opt/retailops/docs/
COPY --chown=airflow:root infra/airflow/dags /opt/airflow/dags
COPY --chown=airflow:root infra/docker/airflow/start.py /opt/retailops/start.py
ENV PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
ENTRYPOINT ["/usr/bin/dumb-init", "--", "python", "/opt/retailops/start.py"]
