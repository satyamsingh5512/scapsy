from __future__ import annotations

from typing import Any
from uuid import UUID

import strawberry


@strawberry.type
class JobNode:
    id: strawberry.ID
    name: str
    status: str
    seed_urls: list[str]
    pages_discovered: int
    pages_processed: int


@strawberry.type
class RecordNode:
    id: strawberry.ID
    job_id: strawberry.ID
    page_id: strawberry.ID
    url: str
    extractor_name: str
    schema_name: str
    confidence: float
    data: strawberry.scalars.JSON


@strawberry.type
class AlertNode:
    id: strawberry.ID
    severity: str
    title: str
    status: str
    context: strawberry.scalars.JSON


@strawberry.type
class Query:
    @strawberry.field
    async def jobs(self, limit: int = 50, offset: int = 0) -> list[JobNode]:
        return []

    @strawberry.field
    async def job(self, id: UUID) -> JobNode | None:
        return None

    @strawberry.field
    async def records(self, job_id: UUID | None = None, query: str | None = None, limit: int = 50) -> list[RecordNode]:
        return []

    @strawberry.field
    async def alerts(self, status: str | None = None) -> list[AlertNode]:
        return []


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_job(self, name: str, instruction: str, seed_urls: list[str]) -> JobNode:
        return JobNode(
            id=strawberry.ID("00000000-0000-0000-0000-000000000000"),
            name=name,
            status="pending",
            seed_urls=seed_urls,
            pages_discovered=len(seed_urls),
            pages_processed=0,
        )


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def job_events(self, job_id: UUID) -> Any:
        yield {"job_id": str(job_id), "event": "placeholder"}


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
