from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from apps.api.app.config import settings

ROLE_ORDER = {"viewer": 1, "analyst": 2, "admin": 3}
ROLE_PERMISSIONS = {
    "viewer": {"public:read"},
    "analyst": {
        "public:read",
        "admin:read",
        "export:read",
        "subscription:write",
        "correction:write",
    },
    "admin": {
        "public:read",
        "admin:read",
        "admin:write",
        "export:read",
        "snapshot:write",
        "subscription:write",
        "correction:write",
    },
}


@dataclass(frozen=True)
class Principal:
    role: str
    token_name: str

    @property
    def actor_id(self) -> str:
        return f"api-token:{self.token_name}"


def configured_tokens() -> dict[str, tuple[str, str]]:
    tokens: dict[str, tuple[str, str]] = {}
    for role, token in [
        ("viewer", settings.api_viewer_token),
        ("analyst", settings.api_analyst_token),
        ("admin", settings.api_admin_token),
    ]:
        if token:
            tokens[token] = (role, f"{role}_token")
    return tokens


def principal_from_token(token: str | None) -> Principal | None:
    if not token:
        return None
    match = configured_tokens().get(token)
    if not match:
        return None
    role, token_name = match
    return Principal(role=role, token_name=token_name)


def bearer_or_key(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return x_api_key.strip() if x_api_key else None


def require_permission(permission: str) -> Callable[..., Principal]:
    def dependency(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> Principal:
        principal = principal_from_token(bearer_or_key(authorization, x_api_key))
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="valid API token required",
            )
        request.state.principal = principal
        if permission not in ROLE_PERMISSIONS[principal.role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{principal.role} cannot perform {permission}",
            )
        return principal

    return dependency


def require_role(minimum_role: str) -> Callable[..., Principal]:
    def dependency(
        principal: Annotated[Principal, Depends(require_permission("public:read"))],
    ) -> Principal:
        if ROLE_ORDER[principal.role] < ROLE_ORDER[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{minimum_role} role required",
            )
        return principal

    return dependency
