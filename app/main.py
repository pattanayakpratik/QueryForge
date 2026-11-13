"""FastAPI application entrypoint, lifespan configuration, and routing."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.config import get_settings
from app.database import init_metadata_db, close_target_engines, get_metadata_session_maker, encrypt_connection_uri
from app.models.metadata import DataSource
from app.api import api_router

logger = logging.getLogger(__name__)
settings = get_settings()


async def auto_provision_default_datasource() -> None:
    """Auto-provision default demo datasource and seed target demo DB on initial launch."""
    try:
        session_maker = get_metadata_session_maker()
        async with session_maker() as session:
            result = await session.execute(
                select(DataSource).where(DataSource.id == "default-demo-db")
            )
            ds = result.scalars().first()
            if not ds:
                dialect = "postgresql" if "postgres" in settings.target_database_url else "sqlite"
                ds = DataSource(
                    id="default-demo-db",
                    name="Demo SaaS & E-Commerce DB",
                    dialect=dialect,
                    connection_uri_encrypted=encrypt_connection_uri(settings.target_database_url),
                    tables_indexed=5,
                )
                session.add(ds)
                await session.commit()
                logger.info("Auto-provisioned 'default-demo-db' metadata record.")
    except Exception as exc:
        logger.warning(f"Could not provision default-demo-db metadata record ({exc}); continuing.")

    # Seed demo ecommerce database if not already populated
    try:
        from scripts.seed_demo_ecommerce_db import seed_ecommerce_database
        await seed_ecommerce_database(target_url=settings.target_database_url, drop_if_exists=False)
    except Exception as exc:
        logger.warning(f"Demo ecommerce DB auto-seed skipped or failed: {exc}")

    # Index schema cards into SchemaIndexer
    try:
        from app.api.query import agent_loop
        dialect = "postgresql" if "postgres" in settings.target_database_url else "sqlite"
        await agent_loop.schema_indexer.index_datasource(
            datasource_id="default-demo-db",
            connection_uri=settings.target_database_url,
            dialect=dialect,
        )
        logger.info("Indexed demo database schema cards into vector store.")
    except Exception as exc:
        logger.warning(f"Demo schema indexer initial run skipped or failed: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing database startup and shutdown."""
    # Startup: Ensure metadata tables exist
    await init_metadata_db()
    # Auto-provision default demo datasource and seed demo DB if empty
    await auto_provision_default_datasource()
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
