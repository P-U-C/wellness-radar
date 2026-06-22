from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from apps.api.app.routers import (
    admin,
    analytics,
    brief,
    bundles,
    graph,
    health,
    metrics,
    operators,
    people,
    propositions,
    signals,
    trends,
)
from apps.api.app.services.metrics import runtime_metrics

app = FastAPI(title="Vancouver Wellness Radar API", version="0.1.0")
logger = logging.getLogger("wellness_radar.api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        runtime_metrics.observe_request(status_code=status_code, duration_ms=duration_ms)
        logger.info(
            json.dumps(
                {
                    "event": "api_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "role": getattr(getattr(request.state, "principal", None), "role", None),
                },
                sort_keys=True,
            )
        )


app.include_router(health.router)
app.include_router(operators.router)
app.include_router(signals.router)
app.include_router(people.router)
app.include_router(bundles.router)
app.include_router(analytics.router)
app.include_router(brief.router)
app.include_router(propositions.router)
app.include_router(trends.router)
app.include_router(graph.router)
app.include_router(metrics.router)
app.include_router(admin.router)
