FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Generous timeout + retries so slow/flaky networks resume downloads instead of aborting.
RUN pip install --timeout 300 --retries 15 uv

COPY pyproject.toml uv.lock ./

# Install into system Python so the volume mount doesn't overwrite site-packages.
# UV_HTTP_TIMEOUT widens uv's per-request timeout for the same slow-network resilience.
ENV UV_HTTP_TIMEOUT=300
RUN uv pip install --system . \
    && uv pip install --system "numpy>=1.26.0,<2" "fastapi>=0.111.0,<0.137" --force-reinstall

# Non-root user for API, Celery worker, and beat (avoids Celery superuser warning)
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home --home-dir /home/app app \
    && mkdir -p /home/app/celerybeat \
    && chown -R app:app /app /home/app

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
