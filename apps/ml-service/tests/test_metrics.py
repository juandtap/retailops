"""Contrato Prometheus: estados reales y cardinalidad acotada, sin modelo/SQL reales."""
from fastapi.testclient import TestClient
from app.main import create_app


def test_metrics_record_http_and_missing_model_without_raw_urls():
    with TestClient(create_app()) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/model').status_code == 503
        for name in ['untrusted-first', 'untrusted-second']:
            assert client.get('/'+name).status_code == 404
        text = client.get('/metrics').text
        assert 'retailops_ml_model_loaded 0.0' in text
        assert 'route="/model",status="503"' in text
        assert 'route="unmatched",status="404"' in text
        assert 'untrusted-first' not in text and 'untrusted-second' not in text
        assert 'retailops_ml_http_request_duration_seconds_bucket' in text
        assert 'process_resident_memory_bytes' in text
        assert 'route="/metrics"' not in text


def test_loaded_model_metric_reflects_runtime_not_approval():
    class Runtime:
        def information(self):
            return {'name':'retailops-sales-global','version':'1','feature_version':'sales-pit-v1','purpose':'candidate_local_preview'}
    with TestClient(create_app(loader=Runtime)) as client:
        text = client.get('/metrics').text
        assert 'retailops_ml_model_loaded 1.0' in text
        assert 'purpose="candidate_local_preview"' in text
        assert 'production_approved' not in text
