"""
HyperMatrix v2026 - API Server
FastAPI-based REST API for code analysis.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routes import projects, search, analysis, lineage
from .dependencies import set_db, get_db
from ..core.db_manager import DBManager

# Database path - use DATA_DIR env var for persistence in Docker volume
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "hypermatrix.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    db_path = app.state.db_path if hasattr(app.state, 'db_path') else DEFAULT_DB_PATH
    set_db(DBManager(db_path))
    yield
    # Cleanup if needed


def create_app(
    db_path: str = None,
    debug: bool = False,
) -> FastAPI:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="HyperMatrix API",
        description="Code Analysis & DNA Extraction Engine API",
        version="2026.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.db_path = db_path
    app.state.debug = debug

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
    app.include_router(search.router, prefix="/api/search", tags=["Search"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
    app.include_router(lineage.router, prefix="/api/lineage", tags=["Lineage"])

    @app.get("/", tags=["Health"])
    async def root():
        """API root endpoint."""
        return {
            "name": "HyperMatrix API",
            "version": "2026.1.0",
            "status": "running",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Default app instance
app = create_app()
