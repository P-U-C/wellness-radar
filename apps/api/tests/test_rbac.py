from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.api.app import security
from apps.api.app.security import Principal, require_permission

AdminReadPrincipal = Annotated[Principal, Depends(require_permission("admin:read"))]
AdminWritePrincipal = Annotated[Principal, Depends(require_permission("admin:write"))]


def test_rbac_denies_missing_or_insufficient_role(monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "api_viewer_token", "viewer-token")
    monkeypatch.setattr(security.settings, "api_analyst_token", "analyst-token")
    monkeypatch.setattr(security.settings, "api_admin_token", "admin-token")

    app = FastAPI()

    @app.get("/admin-read")
    def admin_read(principal: AdminReadPrincipal) -> dict[str, str]:
        return {"role": principal.role}

    client = TestClient(app)

    assert client.get("/admin-read").status_code == 401
    denied = client.get("/admin-read", headers={"Authorization": "Bearer viewer-token"})
    assert denied.status_code == 403


def test_rbac_allows_analyst_read_and_admin_write(monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "api_viewer_token", "viewer-token")
    monkeypatch.setattr(security.settings, "api_analyst_token", "analyst-token")
    monkeypatch.setattr(security.settings, "api_admin_token", "admin-token")

    app = FastAPI()

    @app.get("/admin-read")
    def admin_read(principal: AdminReadPrincipal) -> dict[str, str]:
        return {"role": principal.role}

    @app.post("/admin-write")
    def admin_write(principal: AdminWritePrincipal) -> dict[str, str]:
        return {"role": principal.role}

    client = TestClient(app)

    assert client.get("/admin-read", headers={"X-API-Key": "analyst-token"}).json() == {
        "role": "analyst"
    }
    assert client.post("/admin-write", headers={"X-API-Key": "analyst-token"}).status_code == 403
    assert client.post("/admin-write", headers={"X-API-Key": "admin-token"}).json() == {
        "role": "admin"
    }
