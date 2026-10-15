import json, os, sys, time, uuid
from collections import deque

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

START = time.time()
EMAIL = os.environ.get("EMAIL", "you@example.com")  # set this in Render

# Exposes the metric as `http_requests_total`
REQUESTS = Counter("http_requests", "Total HTTP requests to any endpoint")
LOGS = deque(maxlen=1000)

app = FastAPI()


@app.middleware("http")
async def instrument(request: Request, call_next):
    REQUESTS.inc()  # counts every endpoint, including /metrics and /healthz
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    t0 = time.time()
    status, level = 500, "ERROR"
    try:
        response = await call_next(request)
        status = response.status_code
        level = "INFO" if status < 400 else "WARNING"
        response.headers["x-request-id"] = request_id
        return response
    finally:
        entry = {
            "level": level,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "path": request.url.path,
            "request_id": request_id,
            "method": request.method,
            "status": status,
            "duration_ms": round((time.time() - t0) * 1000, 2),
        }
        LOGS.append(entry)
        print(json.dumps(entry), file=sys.stdout, flush=True)


@app.get("/work")
def work(n: int = 1):
    n = max(0, min(n, 1000))
    acc = 0
    for i in range(n):
        acc += sum(j * j for j in range(1000))  # one "unit" of work
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "uptime_s": float(time.time() - START)}


@app.get("/logs/tail")
def logs_tail(limit: int = 50):
    limit = max(0, limit)
    return list(LOGS)[-limit:] if limit else []
