from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.routers import admin, analytics, graph, health, operators, people, signals, trends

app = FastAPI(title="Vancouver Wellness Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(operators.router)
app.include_router(signals.router)
app.include_router(people.router)
app.include_router(analytics.router)
app.include_router(trends.router)
app.include_router(graph.router)
app.include_router(admin.router)
