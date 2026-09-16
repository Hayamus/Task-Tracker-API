import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUESTS_TOTAL = Counter(
    name="http_requests_total",
    documentation="Общее количество HTTP-запросов",
    labelnames=["method", "endpoint", "status_code"]
)

ERRORS_TOTAL = Counter(
    name="http_errors_total",
    documentation="Количество запросов с ошибками (4xx, 5xx)",
    labelnames=["method", "endpoint", "status_code"]
)

REQUEST_DURATION_SECONDS = Histogram(
    name="http_request_duration_seconds",
    documentation="Длительность выполнения HTTP-запросов в секундах",
    labelnames=["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/metrics", "/health"]:
            return await call_next(request)

        endpoint = request.url.path
        if request.scope.get("route"):
            endpoint = request.scope["route"].path

        method = request.method
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time

            REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)

            REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()

            if status_code.startswith(("4", "5")):
                ERRORS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()

        return response


def get_metrics_exposition() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )