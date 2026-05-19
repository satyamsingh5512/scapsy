import asyncio
from typing import Annotated

import httpx
from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Depends
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db_session
from app.schemas.system import CapabilityCheck, DependencyHealth, SystemHealthResponse, SystemReadinessResponse

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/health", response_model=SystemHealthResponse)
async def system_health(session: DbSession) -> SystemHealthResponse:
    settings = get_settings()
    dependencies = {
        "postgres": await _check_postgres(session),
        "redis": await _check_redis(settings.redis_url),
        "kafka": await _check_kafka(),
        "elasticsearch": await _check_elasticsearch(str(settings.elasticsearch_url)),
        "neo4j": await _check_neo4j(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password),
        "minio": await _check_minio(settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key),
        "extraction": DependencyHealth(status="ok", detail="Regex extractor available; AI tiers are lazy-loaded."),
    }
    status = "ok" if all(item.status == "ok" for item in dependencies.values()) else "degraded"
    return SystemHealthResponse(
        status=status,
        dependencies=dependencies,
        workers={
            "celery_broker": settings.celery_broker_url,
            "raw_pages_topic": settings.kafka_raw_pages_topic,
            "extracted_data_topic": settings.kafka_extracted_data_topic,
        },
    )


@router.get("/readiness", response_model=SystemReadinessResponse)
async def system_readiness(session: DbSession) -> SystemReadinessResponse:
    settings = get_settings()
    checks = [
        _capability("api", "ok", "FastAPI process is serving requests."),
        _dependency_capability(
            "postgres",
            await _check_postgres(session),
            "Start Postgres and run Alembic migrations.",
        ),
        _dependency_capability("redis", await _check_redis(settings.redis_url), "Start Redis or update REDIS_URL."),
        _dependency_capability("kafka", await _check_kafka(), "Start Kafka or update KAFKA_BOOTSTRAP_SERVERS."),
        _dependency_capability(
            "elasticsearch",
            await _check_elasticsearch(str(settings.elasticsearch_url)),
            "Start Elasticsearch and update ELASTICSEARCH_URL.",
        ),
        _capability(
            "regex_extraction",
            "ok",
            "Tier 1 deterministic extractor is importable and covered by tests.",
        ),
        _capability(
            "ai_extraction",
            "ok" if settings.openai_api_key else "degraded",
            "OpenAI tier is configured." if settings.openai_api_key else "OpenAI tier is disabled until OPENAI_API_KEY is set.",
            "Store OPENAI_API_KEY in .env locally or as a Docker/Fly secret.",
        ),
        _capability(
            "private_llm",
            "ok" if settings.ollama_base_url else "degraded",
            "Ollama endpoint is configured for private mode." if settings.ollama_base_url else "Ollama endpoint is not configured.",
            "Set OLLAMA_BASE_URL when enabling private LLM extraction.",
        ),
        _dependency_capability(
            "neo4j",
            await _check_neo4j(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password),
            "Start Neo4j and set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD.",
        ),
        _dependency_capability(
            "minio",
            await _check_minio(settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key),
            "Start MinIO and set MINIO_ENDPOINT, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY.",
        ),
    ]
    working = [check.name for check in checks if check.status == "ok"]
    degraded = [check.name for check in checks if check.status == "degraded"]
    broken = [check.name for check in checks if check.status == "down"]
    status = "ok" if not degraded and not broken else "degraded"
    if broken:
        status = "down"
    return SystemReadinessResponse(status=status, checks=checks, working=working, degraded=degraded, broken=broken)


async def _check_postgres(session: AsyncSession) -> DependencyHealth:
    try:
        await session.execute(text("select 1"))
        return DependencyHealth(status="ok")
    except Exception as exc:
        return DependencyHealth(status="down", detail=str(exc))


async def _check_redis(url: str) -> DependencyHealth:
    try:
        redis = Redis.from_url(url)
        await redis.ping()
        await redis.aclose()
        return DependencyHealth(status="ok")
    except Exception as exc:
        return DependencyHealth(status="down", detail=str(exc))


async def _check_kafka() -> DependencyHealth:
    settings = get_settings()
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id=f"{settings.kafka_client_id}-health",
        security_protocol=settings.kafka_security_protocol,
    )
    try:
        await asyncio.wait_for(producer.start(), timeout=5)
        return DependencyHealth(status="ok")
    except Exception as exc:
        return DependencyHealth(status="down", detail=str(exc))
    finally:
        try:
            await producer.stop()
        except Exception:
            pass


async def _check_elasticsearch(url: str) -> DependencyHealth:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{url}/_cluster/health")
            response.raise_for_status()
        return DependencyHealth(status="ok")
    except Exception as exc:
        return DependencyHealth(status="down", detail=str(exc))


async def _check_minio(endpoint: str | None, access_key: str | None, secret_key: str | None) -> DependencyHealth:
    if not endpoint or not access_key or not secret_key:
        return DependencyHealth(status="down", detail="MINIO_ENDPOINT or access keys are not configured")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{endpoint.rstrip('/')}/minio/health/ready")
            response.raise_for_status()
        return DependencyHealth(status="ok")
    except Exception as exc:
        return DependencyHealth(status="down", detail=str(exc))


async def _check_neo4j(uri: str | None, user: str | None, password: str | None) -> DependencyHealth:
    if not uri or not user or not password:
        return DependencyHealth(status="down", detail="NEO4J connection settings are not configured")
    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        async with driver.session() as session:
            await session.run("RETURN 1")
        await driver.close()
        return DependencyHealth(status="ok")
    except Exception as exc:
        return DependencyHealth(status="down", detail=str(exc))


def _capability(name: str, status: str, detail: str, remediation: str | None = None) -> CapabilityCheck:
    return CapabilityCheck(name=name, status=status, detail=detail, remediation=remediation)


def _dependency_capability(
    name: str,
    dependency: DependencyHealth,
    remediation: str,
) -> CapabilityCheck:
    return _capability(
        name=name,
        status=dependency.status,
        detail=dependency.detail or f"{name} dependency check returned {dependency.status}.",
        remediation=None if dependency.status == "ok" else remediation,
    )
