from __future__ import annotations

import json
from typing import Any

from neo4j import AsyncGraphDatabase

from app.config import get_settings


async def write_graph(
    *,
    job_id: str,
    page_id: str | None,
    url: str,
    schema_name: str,
    record_id: str,
    data: dict[str, Any],
) -> None:
    settings = get_settings()
    if not settings.neo4j_uri or not settings.neo4j_user or not settings.neo4j_password:
        return

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    database = settings.neo4j_database
    query = (
        "MERGE (j:Job {id: $job_id}) "
        "MERGE (p:Page {id: $page_id}) "
        "ON CREATE SET p.url = $url "
        "MERGE (r:Record {id: $record_id}) "
        "SET r.schema_name = $schema_name, r.data = $data "
        "MERGE (j)-[:HAS_PAGE]->(p) "
        "MERGE (p)-[:HAS_RECORD]->(r)"
    )
    payload = {
        "job_id": job_id,
        "page_id": page_id or f"page:{job_id}:{url}",
        "url": url,
        "record_id": record_id,
        "schema_name": schema_name,
        "data": json.dumps(data, ensure_ascii=True),
    }

    async with driver.session(database=database) as session:
        await session.run(query, payload)
    await driver.close()
