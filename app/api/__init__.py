"""API router registry."""

from fastapi import APIRouter
from app.api.datasources import router as datasources_router
from app.api.golden import router as golden_router
from app.api.telemetry import router as telemetry_router
from app.api.query import router as query_router

api_router = APIRouter()
api_router.include_router(datasources_router, prefix="/datasources", tags=["Data Sources"])
api_router.include_router(golden_router, prefix="/golden-queries", tags=["Golden Queries"])
api_router.include_router(query_router, prefix="/query", tags=["Query Execution"])
api_router.include_router(telemetry_router, prefix="/metrics", tags=["Telemetry"])
