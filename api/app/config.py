"""Application settings via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration read from environment variables.

    Per ENV_VARS.md — every secret or external URL is read from env.
    Never hardcode values here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ENVIRONMENT: str = "development"

    # Database
    DB_URL: str = "postgresql+asyncpg://iqbalai:iqbalai@localhost:5432/iqbalai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # NATS
    NATS_URL: str = "nats://localhost:4222"
    # When false, lifespan skips eager NATS connect (core-only compose boot — T-236).
    EVENTS_ENABLED: bool = False

    # MinIO / S3-compatible
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minio_admin"
    MINIO_SECRET_KEY: str = "change_me"
    MINIO_BUCKET_PDFS: str = "pdfs"
    MINIO_BUCKET_AUDIO: str = "audio"
    MINIO_BUCKET_ML_MODELS: str = "ml-models"
    MINIO_BUCKET_EXPORTS: str = "exports"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"

    # OIDC / Authentik
    OIDC_ISSUER_URL: str = "http://localhost:9000/application/o/iqbalai/"
    OIDC_CLIENT_ID: str = "iqbalai-api"
    OIDC_CLIENT_SECRET: str = "change_me"
    OIDC_JWKS_URL: str = "http://localhost:9000/application/o/iqbalai/jwks/"
    AUTHENTIK_API_URL: str = "http://localhost:9000/api/v3"
    AUTHENTIK_API_TOKEN: str = ""

    # App URLs + email (T-030 invite flow)
    APP_URL: str = "http://localhost:3000"
    EMAIL_PROVIDER: str = "log"  # log | smtp | brevo (brevo not implemented yet)
    EMAIL_FROM: str = "noreply@iqbalai.local"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USE_SSL: bool = True
    SMTP_USE_TLS: bool = False
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TIMEOUT: int = 30

    # LLM
    LLM_PROVIDER: str = "groq"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.1-70b-versatile"
    LLM_FALLBACK_PROVIDER: str = "openai"
    LLM_FALLBACK_BASE_URL: str = "https://api.openai.com/v1"
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_MODEL: str = "gpt-4o-mini"

    # Task-specific model overrides
    LECTURE_GEN_MODEL: str = ""
    CHATBOT_MODEL: str = ""
    STUDENT_QA_MODEL: str = ""
    VA_MODEL: str = ""
    SCORING_MODEL: str = ""

    # Embeddings — infinity (prod) or local sentence-transformers (dev, low RAM)
    EMBEDDING_PROVIDER: str = "infinity"  # infinity | local
    EMBEDDING_MODEL: str = ""  # empty = provider default (BGE-M3 or MiniLM)
    EMBEDDING_VECTOR_DIM: int = 0  # 0 = provider default (1024 or 384)
    INFINITY_URL: str = "http://localhost:7997"

    # Web search — self-hosted SearXNG (RAG tier-3 fallback + framework research,
    # STACK_LOCK §Web-search; ARCH §7.12/§8.21).
    WEBSEARCH_URL: str = "http://localhost:8888"

    # Exam-framework AI research (T-093, ARCH §3.19/§8.21).
    # Hard USD cost ceiling per research run; agent halts + flags a partial result
    # if the estimated LLM spend crosses it.
    FRAMEWORK_RESEARCH_COST_CEILING_USD: float = 10.0
    # Blended token price used to estimate a run's USD cost from LLM usage. A safety
    # knob for the ceiling above — not billing-grade; tune per provider.
    FRAMEWORK_RESEARCH_USD_PER_1K_TOKENS: float = 0.001
    # How many top search results to fetch + synthesise per run (§8.21: 10-20).
    FRAMEWORK_RESEARCH_MAX_SOURCES: int = 15

    # Browser origins allowed for cross-origin API calls (comma-separated).
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    GRADUATION_GRACE_DAYS: int = 180
    FINAL_GRADE_LEVEL_ORDINAL: int = 12
    GRADUATION_MIGRATION_MAX_ATTEMPTS: int = 5

    # Exam-framework approval SLA (T-094, Flow 4 §3.5.1, ARCH §3.19/§10.6). The
    # Platform-Admin approval target is 72h; a reminder fires after REMINDER_DAYS and
    # an escalation after ESCALATION_DAYS for any plan still in PENDING_APPROVAL.
    FRAMEWORK_APPROVAL_SLA_HOURS: int = 72
    FRAMEWORK_APPROVAL_REMINDER_DAYS: int = 7
    FRAMEWORK_APPROVAL_ESCALATION_DAYS: int = 14
    # Refresh cadence (days) for the quarterly Pattern-A re-research (T-095, ARCH
    # §8.21/§10.6). The beat runs daily and picks PUBLISHED frameworks whose last
    # research run is older than this — cadence is enforced in the task, not the beat.
    FRAMEWORK_REFRESH_DAYS: int = 90

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def require_oidc_values_in_production(self) -> "Settings":
        """Prevent a deployed API from silently trusting local Authentik defaults."""
        if self.ENVIRONMENT.lower() == "production":
            required = {
                "OIDC_ISSUER_URL": self.OIDC_ISSUER_URL,
                "OIDC_CLIENT_ID": self.OIDC_CLIENT_ID,
                "OIDC_CLIENT_SECRET": self.OIDC_CLIENT_SECRET,
                "OIDC_JWKS_URL": self.OIDC_JWKS_URL,
                "APP_URL": self.APP_URL,
            }
            missing = [
                name
                for name, value in required.items()
                if not value or "localhost" in value or value == "change_me"
            ]
            if missing:
                raise ValueError(
                    "Production authentication settings must be explicitly configured: "
                    + ", ".join(missing)
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()
