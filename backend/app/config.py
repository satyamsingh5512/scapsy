from functools import lru_cache
import json
from typing import Annotated, Any

from pydantic import AnyHttpUrl, BeforeValidator, Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_origins(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            return [str(origin).strip() for origin in json.loads(stripped)]
        return [origin.strip() for origin in stripped.split(",") if origin.strip()]
    if isinstance(value, list):
        return [str(origin) for origin in value]
    raise ValueError("CORS_ORIGINS must be a JSON list or comma-separated string")


CorsOrigins = Annotated[list[str], BeforeValidator(_parse_cors_origins)]


def _parse_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            return [str(item).strip() for item in json.loads(stripped)]
        return [item.strip() for item in stripped.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("Value must be a JSON list or comma-separated string")


StringList = Annotated[list[str], BeforeValidator(_parse_string_list)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "WebIntel AI"
    app_env: str = "local"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "webintel"
    postgres_user: str = "webintel"
    postgres_password: str = "webintel_dev_password"

    database_url: PostgresDsn | None = None
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_raw_pages_topic: str = "raw-pages"
    kafka_extracted_data_topic: str = "extracted-data"
    kafka_extraction_group_id: str = "webintel-extraction-workers"
    kafka_client_id: str = "webintel-backend"
    kafka_security_protocol: str = "PLAINTEXT"
    elasticsearch_url: AnyHttpUrl = Field(default="http://localhost:9200")
    elasticsearch_index: str = "webintel-records"

    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None
    neo4j_database: str | None = None

    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_secure: bool = False
    minio_raw_bucket: str = "webintel-raw"
    minio_record_bucket: str = "webintel-records"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_timezone: str = "UTC"
    redbeat_redis_url: str = "redis://localhost:6379/3"

    crawler_user_agent: str = "WebIntelAI/0.1 (+https://local.webintel.ai)"
    crawler_request_timeout_seconds: int = 30
    crawler_max_concurrency: int = 8
    playwright_headless: bool = True
    playwright_navigation_timeout_ms: int = 30_000
    playwright_block_resource_types: StringList = Field(default_factory=lambda: ["image", "media", "font"])

    spacy_model: str = "en_core_web_sm"
    hf_qa_model: str = "distilbert-base-cased-distilled-squad"
    extraction_confidence_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    extraction_max_text_chars: int = 24_000
    openai_api_key: str | None = None
    openai_extraction_model: str = "gpt-4.1-mini"

    ollama_base_url: str | None = None

    jwt_private_key_pem: str | None = None
    jwt_public_key_pem: str | None = None
    jwt_issuer: str = "webintel-ai"
    jwt_audience: str = "webintel-ai-users"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 7
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    cors_origins: CorsOrigins = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url is not None:
            return str(self.database_url)
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
