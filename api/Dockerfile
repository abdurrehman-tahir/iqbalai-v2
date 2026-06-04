FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock ./

# Install into system Python so the volume mount doesn't overwrite site-packages
RUN uv pip install --system .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
