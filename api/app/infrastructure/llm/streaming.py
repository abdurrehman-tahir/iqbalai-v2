"""SSE / async generator helpers for streaming LLM responses."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi.responses import StreamingResponse


async def sse_stream(generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
    """Convert a text generator to SSE-formatted bytes stream."""
    async for chunk in generator:
        yield f"data: {chunk}\n\n".encode()
    yield b"data: [DONE]\n\n"


def stream_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    """Wrap a text generator as a FastAPI StreamingResponse (SSE)."""
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
