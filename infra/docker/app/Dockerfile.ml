# Base local reproducible construida con el lock uv de apps/ml-service.
FROM retailops-mlflow:local-v1
WORKDIR /opt/retailops/apps/ml-service
COPY apps/ml-service/app ./app
COPY notebooks/retailops_eda /opt/retailops/notebooks/retailops_eda
COPY contracts/gold-features-v1.json /opt/retailops/contracts/gold-features-v1.json
RUN mkdir -p /opt/retailops/.local/secrets /opt/retailops/.local/mlops && chown -R 1000:1000 /opt/retailops/.local
ENV ML_HOST=0.0.0.0 ML_PORT=8000 PYTHONUNBUFFERED=1
USER 1000:1000
ENTRYPOINT ["python","-m","app"]
