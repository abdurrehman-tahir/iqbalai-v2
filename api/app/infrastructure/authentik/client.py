"""Authentik REST API client — single chokepoint for user lifecycle (ARCH §6.12)."""

from __future__ import annotations

import uuid
from typing import Protocol

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class AuthentikClientProtocol(Protocol):
    async def create_user(self, *, email: str, name: str, is_active: bool = False) -> str: ...

    async def activate_user(self, authentik_id: str) -> None: ...

    async def set_password(self, authentik_id: str, password: str) -> None: ...

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None: ...


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

    async def set_password(self, authentik_id: str, password: str) -> None:
        if authentik_id in self._users:
            self._users[authentik_id]["password"] = password
        logger.info("dev_authentik_password_set", pk=authentik_id)

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None:
        logger.info("dev_authentik_group_added", pk=authentik_id, group=group_slug)


class AuthentikClient:
    """Production Authentik REST client."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    async def create_user(self, *, email: str, name: str, is_active: bool = False) -> str:
        payload = {
            "username": email,
            "email": email,
            "name": name,
            "is_active": is_active,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/core/users/",
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["pk"])

    async def activate_user(self, authentik_id: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{self._base_url}/core/users/{authentik_id}/",
                json={"is_active": True},
                headers={"Authorization": f"Bearer {self._token}"},
            )
            resp.raise_for_status()

    async def set_password(self, authentik_id: str, password: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/core/users/{authentik_id}/set_password/",
                json={"password": password},
                headers={"Authorization": f"Bearer {self._token}"},
            )
            resp.raise_for_status()

    async def add_to_group(self, authentik_id: str, group_slug: str) -> None:
        logger.info("authentik_add_to_group", pk=authentik_id, group=group_slug)


_dev_client: DevAuthentikClient | None = None


def get_authentik_client() -> AuthentikClientProtocol:
    """Return the process-wide Authentik client (dev stub when no API token)."""
    global _dev_client
    settings = get_settings()
    if not settings.AUTHENTIK_API_TOKEN:
        if _dev_client is None:
            _dev_client = DevAuthentikClient()
        return _dev_client
    return AuthentikClient(settings.AUTHENTIK_API_URL, settings.AUTHENTIK_API_TOKEN)
