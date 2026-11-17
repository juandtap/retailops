# Base local reproducible construida con el lock uv de apps/ml-service.
ARG MLFLOW_BASE=retailops-mlflow:local-v1
FROM ${MLFLOW_BASE}
COPY infra/docker/app/ml-requirements.lock /tmp/ml-requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/ml-requirements.lock
WORKDIR /opt/retailops/apps/ml-service
COPY apps/ml-service/app ./app
COPY notebooks/retailops_eda /opt/retailops/notebooks/retailops_eda
COPY contracts/gold-features-v1.json /opt/retailops/contracts/gold-features-v1.json
RUN mkdir -p /opt/retailops/.local/secrets /opt/retailops/.local/mlops && chown -R 1000:1000 /opt/retailops/.local
ENV ML_HOST=0.0.0.0 ML_PORT=8000 PYTHONUNBUFFERED=1
USER 1000:1000
ENTRYPOINT ["python","-m","app"]
