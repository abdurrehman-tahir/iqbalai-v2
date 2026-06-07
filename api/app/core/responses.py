"""Response envelope helpers + typed envelope models per ARCH §5.

The `success()` / `paginated()` helpers build the runtime dict payloads. The
`SuccessEnvelope[T]` / `PaginatedEnvelope[T]` Pydantic generics are what routes
declare as `response_model=` so the OpenAPI (and therefore the generated frontend
client — A-002) carries the real `data` shape instead of a bare `dict`. T-225
wires every `success()`-returning route onto these generics.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessEnvelope(BaseModel, Generic[T]):
    """Typed form of the `success()` payload: `{"data": <T>, "message": str}`."""

    data: T
    message: str = "ok"


class PaginatedEnvelope(BaseModel, Generic[T]):
    """Typed form of the `paginated()` payload."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class DeletedResponse(BaseModel):
    """Payload for soft-delete endpoints — `data` of a `SuccessEnvelope`."""

    deleted: bool = True


def success(data: Any, message: str = "ok") -> dict[str, Any]:  # noqa: ANN401
    """Standard success envelope."""
    return {"data": data, "message": message}


def paginated(
    items: list[Any],  # noqa: ANN401
    total: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:  # noqa: ANN401
    """Standard paginated response envelope."""
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
