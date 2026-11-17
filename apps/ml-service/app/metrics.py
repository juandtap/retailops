"""Métricas por proceso con etiquetas acotadas; nunca exponen features o secretos."""
import time
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, ProcessCollector, GCCollector, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response


def instrument(app):
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    GCCollector(registry=registry)
    requests = Counter('retailops_ml_http_requests_total', 'Solicitudes HTTP completadas', ['method', 'route', 'status'], registry=registry)
    latency = Histogram('retailops_ml_http_request_duration_seconds', 'Duración HTTP del servicio', ['method', 'route'],
                        buckets=(.01, .05, .1, .25, .5, 1, 2, 5), registry=registry)
    loaded = Gauge('retailops_ml_model_loaded', 'Uno si el runtime cargó un modelo; no expresa aprobación', registry=registry)
    loaded.set_function(lambda: int(getattr(app.state, 'model', None) is not None))
    info = Gauge('retailops_ml_model_info', 'Identidad del modelo cargado, sin run ni artefactos',
                 ['name', 'version', 'feature_version', 'purpose'], registry=registry)
    app.state.model_metric = info

    @app.middleware('http')
    async def observe(request, call_next):
        if request.url.path == '/metrics':
            return await call_next(request)
        started = time.perf_counter()
        status = 500
        method = request.method if request.method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'} else 'OTHER'
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get('route'), 'path', 'unmatched')
            requests.labels(method, route, str(status)).inc()
            latency.labels(method, route).observe(time.perf_counter() - started)

    @app.get('/metrics', include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), headers={'Content-Type': CONTENT_TYPE_LATEST})
