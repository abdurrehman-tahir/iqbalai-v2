# Forbidden imports — quick reference

This is a quick lookup. The authoritative list is `docs/STACK_LOCK.md` §9.

## Categorical forbiddens

### LLM provider SDKs

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import openai`, `from openai import ...` | `app/infrastructure/llm/providers/openai_compat.py` only | `from app.infrastructure.llm import llm_client` |
| `import anthropic` | `app/infrastructure/llm/providers/anthropic_native.py` only | `from app.infrastructure.llm import llm_client` |
| `import groq` | NEVER (Groq is OpenAI-shape; use the OpenAI SDK) | `from app.infrastructure.llm import llm_client` |
| `import mistralai`, `import cohere` | NEVER | `from app.infrastructure.llm import llm_client` |
| `import ollama` | NEVER (use Ollama via env-var routing through the standard client) | `from app.infrastructure.llm import llm_client` |

### LLM orchestration

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `from langchain.* import ...` | `app/infrastructure/ingestion/chunker.py` ONLY (`langchain.text_splitter`) | LangGraph for state machines, Pydantic AI for typed agents |
| `from langchain_community.* import ...` | NEVER | Same |
| `from langchain_openai import ...` | NEVER | `from app.infrastructure.llm import llm_client` |
| `from llama_index import ...` | NEVER | LangGraph + Pydantic AI |

### Vector stores

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import pinecone`, `from pinecone import ...` | NEVER | `from app.infrastructure.rag.retriever import QdrantRetriever` |
| `import weaviate`, `import chromadb`, `import lancedb`, `import milvus` | NEVER | Qdrant via the retriever |
| `qdrant_client` (raw) | `app/infrastructure/rag/retriever.py`, `app/infrastructure/rag/embedder.py` | The QdrantRetriever class |

### Voice (TTS/STT)

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import whisper`, `import faster_whisper`, `import openai_whisper` | `app/infrastructure/voice/stt.py` only | `from app.infrastructure.voice import stt` |
| `import piper`, `import pyttsx3`, `import gTTS` | `app/infrastructure/voice/tts/` only | `from app.infrastructure.voice import tts` |
| `import elevenlabs`, `import deepgram` | NEVER | Voice abstraction (not approved providers) |

### HTTP clients

| Forbidden import | Use instead |
|---|---|
| `import requests` | `import httpx` (already in stack; async-native) |
| `import aiohttp` | `import httpx` (we standardized on httpx) |
| `import urllib.request` | `import httpx` |

### Database / cache

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import psycopg2`, `import psycopg` (raw) | NEVER | SQLAlchemy 2.0 async |
| `import asyncpg` (raw, outside SQLAlchemy) | NEVER | SQLAlchemy 2.0 async with asyncpg driver (configured in `db/engine.py`) |
| `import redis` (raw, sync) | NEVER | `redis.asyncio` |
| `redis.asyncio` (raw) | `app/infrastructure/cache/`, `app/infrastructure/events/dedup.py`, `app/tasks/celery_app.py` | `from app.infrastructure.cache import redis_client` |

### File / object storage

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import boto3` | NEVER (we use MinIO, S3-compatible via `minio` package) | `from app.infrastructure.storage import storage` |
| `import minio` (raw) | `app/infrastructure/storage/client.py` only | `from app.infrastructure.storage import storage` |

### Messaging / events

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import pika`, `import kombu` (RabbitMQ) | NEVER (we use NATS + Celery on Redis) | `from app.infrastructure.events import event_publisher` |
| `import confluent_kafka` (Kafka) | NEVER | `from app.infrastructure.events import event_publisher` |
| `nats.aio` (raw) | `app/infrastructure/events/*.py` only | `from app.infrastructure.events import event_publisher` |

### PDF / OCR / chunking

| Forbidden import | Where it's allowed | Use instead |
|---|---|---|
| `import PyPDF2`, `import fitz`, `import pdfminer` | NEVER (we use MinerU + pdfplumber fallback) | `from app.infrastructure.ingestion import pdf_parser` |
| `import tesserocr`, `import pytesseract` (raw) | `app/infrastructure/ingestion/ocr.py` only | `from app.infrastructure.ingestion import ocr` |
| `import paddleocr` (raw) | `app/infrastructure/ingestion/ocr.py` only | Same |
| `from langchain.text_splitter import ...` | `app/infrastructure/ingestion/chunker.py` only | Same |

### Auth / crypto

| Forbidden import | Use instead |
|---|---|
| `import jwt` (PyJWT) | Allowed in `app/core/security.py` only |
| `import bcrypt`, `import argon2` | We never hash passwords ourselves — Authentik does it |
| `import cryptography` (raw, for app crypto) | Authentik handles tokens; if app-level encryption is needed (Phase 2), get approval |

### Observability

| Forbidden import | Use instead |
|---|---|
| `import logging` (stdlib) | `import structlog` (configured in `app/core/logging.py`) |
| `import sentry_sdk` | At launch: use the custom `/api/v1/frontend-errors` flow + structlog. Sentry is Phase 2. |

### Web frameworks (other than FastAPI)

| Forbidden | Use instead |
|---|---|
| `import flask`, `import django`, `import quart`, `import starlette` (raw) | `fastapi` (which uses Starlette internally) |

### "Helpful" libraries we don't need

These pollute the codebase with patterns that fight ours:

| Forbidden | Use instead |
|---|---|
| `import retry`, `from tenacity import retry` (raw) | The retry helper in `infrastructure/llm/retries.py` (LLM-specific); or write explicit retry logic |
| `import schedule` (in-process cron) | Celery beat |
| `import apscheduler` | Celery beat |
| `import dotenv` (loading env files outside Pydantic Settings) | `from app.config import get_settings` |

## How to check

When you see an import statement in proposed code:

1. Is it in the Python standard library? → OK.
2. Is it in `pyproject.toml`'s dependencies AND not on this list? → OK.
3. Is it on this list but in an allowed location? → OK if the file path matches.
4. Otherwise → STOP. Raise a violation.

If you're not sure whether a library is in `pyproject.toml`, ask. Don't guess.
