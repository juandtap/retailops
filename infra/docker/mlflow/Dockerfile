FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
COPY infra/docker/mlflow/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
COPY infra/docker/mlflow/start.py /app/start.py
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /tmp
ENTRYPOINT ["python", "/app/start.py"]
