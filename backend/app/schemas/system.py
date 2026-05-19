from pydantic import BaseModel


class DependencyHealth(BaseModel):
    status: str
    detail: str | None = None


class CapabilityCheck(BaseModel):
    name: str
    status: str
    detail: str
    remediation: str | None = None


class SystemHealthResponse(BaseModel):
    status: str
    dependencies: dict[str, DependencyHealth]
    workers: dict[str, str]


class SystemReadinessResponse(BaseModel):
    status: str
    checks: list[CapabilityCheck]
    working: list[str]
    degraded: list[str]
    broken: list[str]
