FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .

# Install into system Python so the volume mount doesn't overwrite the venv
RUN uv pip install --system -r pyproject.toml --extra-index-url https://pypi.org/simple 2>/dev/null || \
    pip install fastapi uvicorn[standard] pydantic>=2 pydantic-settings sqlalchemy>=2 alembic \
    asyncpg httpx structlog openai qdrant-client boto3 celery[redis] nats-py \
    python-jose[cryptography] prometheus-fastapi-instrumentator

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
