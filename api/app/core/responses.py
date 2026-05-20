"""Response envelope helpers per ARCH §5."""
from __future__ import annotations

from typing import Any


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
