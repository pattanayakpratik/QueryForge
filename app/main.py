"""FastAPI application entrypoint, lifespan configuration, and routing."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_metadata_db, close_target_engines
from app.api import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing database startup and shutdown."""
    # Startup: Ensure metadata tables exist
    await init_metadata_db()
    yield
    # Shutdown: Clean up external database connections
    await close_target_engines()


app = FastAPI(
    title=settings.app_name,
    description="Autonomous Text-to-SQL & Natural Language BI Engine with AST Firewall & Self-Healing Loop",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware for Next.js 16 frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router
app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    """Root healthcheck and service status."""
    return {
        "service": settings.app_name,
        "status": "healthy",
        "version": "0.1.0",
        "env": settings.app_env,
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health probe endpoint."""
    return {"status": "ok"}
