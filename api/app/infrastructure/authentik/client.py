"""Authentik REST API client — single chokepoint for user lifecycle (ARCH §6.12)."""

from __future__ import annotations

import uuid
from typing import Protocol

import httpx
import structlog

from app.config import get_settings
from app.core.exceptions import AuthentikApiError

logger = structlog.get_logger(__name__)


class AuthentikClientProtocol(Protocol):
    async def create_user(self, *, email: str, name: str, is_active: bool = False) -> str: ...

    async def activate_user(self, authentik_id: str) -> None: ...

    async def deactivate_user(self, authentik_id: str) -> None: ...

    async def set_password(self, authentik_id: str, password: str) -> None: ...

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None: ...

    async def set_tenant_type(self, authentik_id: str, tenant_type: str) -> None: ...


class DevAuthentikClient:
    """In-memory stub used when AUTHENTIK_API_TOKEN is unset (local dev + tests)."""

    def __init__(self) -> None:
        self._users: dict[str, dict[str, object]] = {}

    async def create_user(self, *, email: str, name: str, is_active: bool = False) -> str:
        pk = str(uuid.uuid4())
        self._users[pk] = {"email": email, "name": name, "is_active": is_active, "password": None}
        logger.info("dev_authentik_user_created", pk=pk, email=email, is_active=is_active)
        return pk

    async def activate_user(self, authentik_id: str) -> None:
        if authentik_id in self._users:
            self._users[authentik_id]["is_active"] = True
        logger.info("dev_authentik_user_activated", pk=authentik_id)

    async def deactivate_user(self, authentik_id: str) -> None:
        if authentik_id in self._users:
            self._users[authentik_id]["is_active"] = False
        logger.info("dev_authentik_user_deactivated", pk=authentik_id)

    async def set_password(self, authentik_id: str, password: str) -> None:
        if authentik_id in self._users:
            self._users[authentik_id]["password"] = password
        logger.warning(
            "dev_authentik_password_set_stub_only",
            pk=authentik_id,
            hint="Set AUTHENTIK_API_TOKEN so invites update real Authentik users",
        )

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None:
        logger.info("dev_authentik_group_added", pk=authentik_id, group=group_slug)

    async def set_tenant_type(self, authentik_id: str, tenant_type: str) -> None:
        logger.info("dev_authentik_tenant_type_set", pk=authentik_id, tenant_type=tenant_type)


class AuthentikClient:
    """Production Authentik REST client."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _raise_for_response(self, resp: httpx.Response, *, path: str) -> None:
        if resp.is_success:
            return

        detail = resp.text
        try:
            payload = resp.json()
            detail = str(payload.get("detail", payload))
        except ValueError:
            pass

        logger.error(
            "authentik_api_error",
            status_code=resp.status_code,
            path=path,
            detail=detail[:200],
        )

        if resp.status_code in (401, 403) and "invalid" in detail.lower():
            raise AuthentikApiError(
                "Authentik API token is invalid or expired. Create a new token in "
                "Authentik Admin → Directory → Tokens (Intent: API, user: akadmin) "
                "and set AUTHENTIK_API_TOKEN in .env, then restart the api container."
            )

        raise AuthentikApiError(f"Authentik request failed ({resp.status_code}): {detail}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method,
                f"{self._base_url}{path}",
                json=json,
                headers=self._auth_headers(),
            )
        self._raise_for_response(resp, path=path)
        return resp

    async def create_user(self, *, email: str, name: str, is_active: bool = False) -> str:
        payload = {
            "username": email,
            "email": email,
            "name": name,
            "is_active": is_active,
        }
        resp = await self._request("POST", "/core/users/", json=payload)
        data = resp.json()
        return str(data["pk"])

    async def activate_user(self, authentik_id: str) -> None:
        await self._request(
            "PATCH",
            f"/core/users/{authentik_id}/",
            json={"is_active": True},
        )

    async def deactivate_user(self, authentik_id: str) -> None:
        await self._request(
            "PATCH",
            f"/core/users/{authentik_id}/",
            json={"is_active": False},
        )

    async def set_password(self, authentik_id: str, password: str) -> None:
        await self._request(
            "POST",
            f"/core/users/{authentik_id}/set_password/",
            json={"password": password},
        )

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None:
        logger.info("authentik_add_to_group", pk=authentik_id, group=group_slug)

    async def set_tenant_type(self, authentik_id: str, tenant_type: str) -> None:
        logger.info("authentik_set_tenant_type", pk=authentik_id, tenant_type=tenant_type)


_dev_client: DevAuthentikClient | None = None


def get_authentik_client() -> AuthentikClientProtocol:
    """Return the process-wide Authentik client (dev stub when no API token)."""
    global _dev_client
    settings = get_settings()
    if not settings.AUTHENTIK_API_TOKEN:
        if _dev_client is None:
            logger.warning(
                "authentik_dev_stub_active",
                hint="Invites/passwords are NOT synced to Authentik — set AUTHENTIK_API_TOKEN",
            )
            _dev_client = DevAuthentikClient()
        return _dev_client
    return AuthentikClient(settings.AUTHENTIK_API_URL, settings.AUTHENTIK_API_TOKEN)
