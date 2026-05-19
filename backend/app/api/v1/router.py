from fastapi import APIRouter

from app.api.v1 import ai_engine, alerts, auth, data, jobs, system

api_router = APIRouter()
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(ai_engine.router, prefix="/ai-engine", tags=["ai-engine"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
