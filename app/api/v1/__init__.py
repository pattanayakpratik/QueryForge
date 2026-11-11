"""API v1 router registry."""

from fastapi import APIRouter
from app.api.v1.datasources import router as datasources_router
from app.api.v1.golden import router as golden_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.query import router as query_router

api_v1_router = APIRouter()
api_v1_router.include_router(datasources_router, prefix="/datasources", tags=["Data Sources"])
api_v1_router.include_router(golden_router, prefix="/golden-queries", tags=["Golden Queries"])
api_v1_router.include_router(query_router, prefix="/query", tags=["Query Execution"])
api_v1_router.include_router(telemetry_router, prefix="/metrics", tags=["Telemetry"])
