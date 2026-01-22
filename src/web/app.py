"""
HyperMatrix v2026 - Web Application
FastAPI-based web interface for code analysis and consolidation.
"""

import asyncio
import uuid
from pathlib import Path
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from .models import (
    ScanRequest, ScanProgress, ScanStatus,
    BatchActionRequest, DryRunResult, ExportRequest, RulesConfig
)
from ..core.db_manager import DBManager
from ..core.consolidation import ConsolidationEngine, SiblingGroup
from ..core.fusion import IntelligentFusion
from ..phases.phase1_discovery import Phase1Discovery
from ..phases.phase1_5_deduplication import Phase1_5Deduplication
from ..phases.phase2_analysis import Phase2Analysis
from ..phases.phase3_consolidation import Phase3Consolidation


# Global state for scans
active_scans: Dict[str, ScanProgress] = {}
scan_results: Dict[str, dict] = {}
db_manager: Optional[DBManager] = None
rules_config: Optional[RulesConfig] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_manager, rules_config
    db_path = getattr(app.state, 'db_path', 'hypermatrix.db')
    db_manager = DBManager(db_path)
    rules_config = load_rules_config()

    # Load persisted projects/scans from database on startup
    print("[HyperMatrix] Starting up...")
    try:
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # Get recent projects with file counts
            cursor.execute("""
                SELECT p.id, p.name, p.root_path, p.created_at,
                       COUNT(f.id) as file_count
                FROM projects p
                LEFT JOIN files f ON f.project_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                LIMIT 20
            """)

            projects = cursor.fetchall()

            for proj in projects:
                scan_id = str(proj["id"])
                # Create a completed scan progress entry
                active_scans[scan_id] = ScanProgress(
                    scan_id=scan_id,
                    status=ScanStatus.COMPLETED,
                    phase="completed",
                    phase_progress=1.0,
                    total_files=proj["file_count"] or 0,
                    processed_files=proj["file_count"] or 0,
                    current_file=None,
                )
                # Create minimal scan results entry
                scan_results[scan_id] = {
                    "project_name": proj["name"],
                    "total_files": proj["file_count"] or 0,
                    "analyzed_files": proj["file_count"] or 0,
                    "root_path": proj["root_path"],
                    "created_at": proj["created_at"],
                }

            print(f"[HyperMatrix] Loaded {len(projects)} projects from database")
    except Exception as e:
        print(f"[HyperMatrix] Warning: Could not load projects from DB: {e}")

    yield
    # Cleanup
    print("[HyperMatrix] Shutting down...")


def load_rules_config() -> RulesConfig:
    """Load rules from YAML config if exists."""
    import yaml
    config_path = Path("hypermatrix_rules.yaml")
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)
                return RulesConfig(**data) if data else RulesConfig()
        except Exception:
            pass
    return RulesConfig()


def create_web_app(
    db_path: str = "hypermatrix.db",
    debug: bool = False,
) -> FastAPI:
    """Create and configure the web application."""

    app = FastAPI(
        title="HyperMatrix Web",
        description="Code Analysis & Consolidation Web Interface",
        version="2026.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.state.db_path = db_path
    app.state.debug = debug

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files (legacy)
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Frontend build (served at /app)
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend-assets")

    # Import and include routers
    from .routes import scan, consolidation, export, batch, rules, analysis, clones, advanced, ai, browse, workspace
    app.include_router(browse.router)  # Has its own prefix /api/browse
    app.include_router(workspace.router)  # Has its own prefix /api/workspace
    app.include_router(scan.router, prefix="/api/scan", tags=["Scan"])
    app.include_router(consolidation.router, prefix="/api/consolidation", tags=["Consolidation"])
    app.include_router(export.router, prefix="/api/export", tags=["Export"])
    app.include_router(batch.router, prefix="/api/batch", tags=["Batch Actions"])
    app.include_router(rules.router, prefix="/api/rules", tags=["Rules"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
    app.include_router(clones.router, prefix="/api/clones", tags=["Clones & Semantic"])
    app.include_router(advanced.router, prefix="/api/advanced", tags=["Advanced (BLOQUE D)"])
    app.include_router(ai.router, prefix="/api/ai", tags=["AI (Ollama)"])

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve main web interface (React frontend)."""
        frontend_index = Path(__file__).parent.parent.parent / "frontend" / "dist" / "index.html"
        if frontend_index.exists():
            return frontend_index.read_text(encoding="utf-8")
        # Fallback to legacy template
        template_path = Path(__file__).parent / "templates" / "index.html"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return """
        <html>
            <head><title>HyperMatrix Web</title></head>
            <body>
                <h1>HyperMatrix Web</h1>
                <p>Template not found. Please create templates/index.html</p>
                <p><a href="/api/docs">API Documentation</a></p>
            </body>
        </html>
        """

    @app.get("/health")
    @app.get("/api/health")
    async def health():
        """Health check."""
        return {
            "status": "healthy",
            "version": "2026.01",
            "active_scans": len(active_scans),
        }

    @app.get("/api/status")
    async def api_status():
        """Get overall API status."""
        return {
            "scans_active": len([s for s in active_scans.values() if s.status == ScanStatus.RUNNING]),
            "scans_completed": len([s for s in active_scans.values() if s.status == ScanStatus.COMPLETED]),
            "database_connected": db_manager is not None,
            "rules_loaded": rules_config is not None,
        }

    # ============ PROJECT HISTORY ENDPOINTS ============

    @app.get("/api/history/projects")
    async def get_project_history(limit: int = 10):
        """Get recent and favorite projects."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        recent = db_manager.get_recent_projects(limit)
        favorites = db_manager.get_favorite_projects()

        return {
            "recent": recent,
            "favorites": favorites,
        }

    @app.post("/api/history/projects")
    async def add_project_to_history(path: str, name: str = None):
        """Add a project to history."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        result = db_manager.add_to_history(path, name)
        return result

    @app.post("/api/history/projects/favorite")
    async def toggle_project_favorite(path: str):
        """Toggle favorite status for a project."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        result = db_manager.toggle_favorite(path)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @app.delete("/api/history/projects")
    async def remove_project_from_history(path: str):
        """Remove a project from history."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        result = db_manager.remove_from_history(path)
        return result

    @app.get("/api/db/stats")
    async def get_database_stats():
        """Get global database statistics."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total projects
            cursor.execute("SELECT COUNT(*) FROM projects")
            stats["total_projects"] = cursor.fetchone()[0]

            # Total files
            cursor.execute("SELECT COUNT(*) FROM files")
            stats["total_files"] = cursor.fetchone()[0]

            # Total functions
            cursor.execute("SELECT COUNT(*) FROM functions")
            stats["total_functions"] = cursor.fetchone()[0]

            # Total classes
            cursor.execute("SELECT COUNT(*) FROM classes")
            stats["total_classes"] = cursor.fetchone()[0]

            # Total variables
            cursor.execute("SELECT COUNT(*) FROM variables")
            stats["total_variables"] = cursor.fetchone()[0]

            # Total imports
            cursor.execute("SELECT COUNT(*) FROM imports")
            stats["total_imports"] = cursor.fetchone()[0]

            # Recent projects
            cursor.execute("""
                SELECT name, root_path, created_at
                FROM projects
                ORDER BY created_at DESC
                LIMIT 5
            """)
            stats["recent_projects"] = [
                {"name": row["name"], "path": row["root_path"], "created_at": row["created_at"]}
                for row in cursor.fetchall()
            ]

            return stats

    @app.get("/api/db/files")
    async def get_analyzed_files(project_id: int = None, limit: int = 100):
        """Get list of analyzed files from database."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            if project_id:
                cursor.execute("""
                    SELECT f.id, f.filepath, f.file_type, p.name as project_name
                    FROM files f
                    JOIN projects p ON f.project_id = p.id
                    WHERE f.project_id = ?
                    ORDER BY f.filepath
                    LIMIT ?
                """, (project_id, limit))
            else:
                cursor.execute("""
                    SELECT f.id, f.filepath, f.file_type, p.name as project_name
                    FROM files f
                    JOIN projects p ON f.project_id = p.id
                    ORDER BY p.name, f.filepath
                    LIMIT ?
                """, (limit,))

            return {
                "files": [
                    {
                        "id": row["id"],
                        "filepath": row["filepath"],
                        "file_type": row["file_type"],
                        "project": row["project_name"],
                    }
                    for row in cursor.fetchall()
                ]
            }

    # ============ DATABASE SEARCH ENDPOINTS ============

    @app.get("/api/db/search")
    async def search_database(
        q: str,
        type: str = "all",  # all, functions, classes, variables, imports
        project_id: int = None,
        limit: int = 50
    ):
        """Search functions, classes, variables, imports in the database."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            results = {"functions": [], "classes": [], "variables": [], "imports": []}
            search_term = f"%{q}%"

            project_filter = "AND f.project_id = ?" if project_id else ""
            params_base = (search_term, project_id, limit) if project_id else (search_term, limit)

            if type in ("all", "functions"):
                cursor.execute(f"""
                    SELECT fn.name, fn.lineno, f.filepath, p.name as project_name
                    FROM functions fn
                    JOIN files f ON fn.file_id = f.id
                    JOIN projects p ON f.project_id = p.id
                    WHERE fn.name LIKE ? {project_filter}
                    ORDER BY fn.name
                    LIMIT ?
                """, params_base)
                results["functions"] = [
                    {"name": r["name"], "line": r["lineno"], "file": r["filepath"], "project": r["project_name"]}
                    for r in cursor.fetchall()
                ]

            if type in ("all", "classes"):
                cursor.execute(f"""
                    SELECT c.name, c.lineno, f.filepath, p.name as project_name
                    FROM classes c
                    JOIN files f ON c.file_id = f.id
                    JOIN projects p ON f.project_id = p.id
                    WHERE c.name LIKE ? {project_filter}
                    ORDER BY c.name
                    LIMIT ?
                """, params_base)
                results["classes"] = [
                    {"name": r["name"], "line": r["lineno"], "file": r["filepath"], "project": r["project_name"]}
                    for r in cursor.fetchall()
                ]

            if type in ("all", "variables"):
                cursor.execute(f"""
                    SELECT v.name, v.lineno, f.filepath, p.name as project_name
                    FROM variables v
                    JOIN files f ON v.file_id = f.id
                    JOIN projects p ON f.project_id = p.id
                    WHERE v.name LIKE ? {project_filter}
                    ORDER BY v.name
                    LIMIT ?
                """, params_base)
                results["variables"] = [
                    {"name": r["name"], "line": r["lineno"], "file": r["filepath"], "project": r["project_name"]}
                    for r in cursor.fetchall()
                ]

            if type in ("all", "imports"):
                cursor.execute(f"""
                    SELECT i.module as name, i.lineno, f.filepath, p.name as project_name
                    FROM imports i
                    JOIN files f ON i.file_id = f.id
                    JOIN projects p ON f.project_id = p.id
                    WHERE i.module LIKE ? {project_filter}
                    ORDER BY i.module
                    LIMIT ?
                """, params_base)
                results["imports"] = [
                    {"name": r["name"], "line": r["lineno"], "file": r["filepath"], "project": r["project_name"]}
                    for r in cursor.fetchall()
                ]

            total = sum(len(v) for v in results.values())
            return {"query": q, "total": total, "results": results}

    @app.get("/api/db/siblings/{project_id}")
    async def get_sibling_groups_from_db(project_id: int, limit: int = 100):
        """Get sibling groups (files with same name) from database."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # Find files with same basename that appear multiple times
            cursor.execute("""
                SELECT filepath FROM files WHERE project_id = ?
            """, (project_id,))

            files = cursor.fetchall()
            if not files:
                return {"total": 0, "groups": []}

            # Group by filename
            from collections import defaultdict
            groups = defaultdict(list)
            for row in files:
                filepath = row["filepath"]
                basename = Path(filepath).name
                groups[basename].append(filepath)

            # Filter to only groups with 2+ files
            sibling_groups = [
                {
                    "filename": fname,
                    "file_count": len(paths),
                    "files": [{"filepath": p, "directory": str(Path(p).parent)} for p in paths[:20]]
                }
                for fname, paths in groups.items()
                if len(paths) > 1
            ]

            # Sort by file count descending
            sibling_groups.sort(key=lambda x: x["file_count"], reverse=True)

            return {
                "total": len(sibling_groups),
                "groups": sibling_groups[:limit]
            }

    @app.get("/api/db/files/{project_id}/python")
    async def get_python_files(project_id: int, limit: int = 500):
        """Get Python files from a project for dead code analysis."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT filepath FROM files
                WHERE project_id = ? AND file_type = 'python'
                ORDER BY filepath
                LIMIT ?
            """, (project_id, limit))

            return {
                "files": [row["filepath"] for row in cursor.fetchall()]
            }

    @app.get("/api/db/projects")
    async def list_projects():
        """List all projects with file counts."""
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database not initialized")

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.name, p.root_path, p.created_at, COUNT(f.id) as file_count
                FROM projects p
                LEFT JOIN files f ON f.project_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """)

            return {
                "projects": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "path": row["root_path"],
                        "created_at": row["created_at"],
                        "file_count": row["file_count"]
                    }
                    for row in cursor.fetchall()
                ]
            }

    @app.get("/api/manual")
    async def get_api_manual():
        """Get API manual in markdown format."""
        manual_path = Path(__file__).parent.parent.parent / "docs" / "API_MANUAL.md"
        if manual_path.exists():
            content = manual_path.read_text(encoding="utf-8")
            return {"content": content, "format": "markdown"}
        raise HTTPException(status_code=404, detail="Manual not found")

    @app.get("/api/browse")
    async def browse_directory(path: str = "C:/"):
        """
        Browse filesystem directory.
        Returns list of files and directories.
        """
        import os
        dir_path = Path(path)

        if not dir_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")

        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        try:
            for entry in os.scandir(dir_path):
                try:
                    stat = entry.stat()
                    items.append({
                        "name": entry.name,
                        "path": str(Path(entry.path).resolve()),
                        "is_dir": entry.is_dir(),
                        "size": stat.st_size if not entry.is_dir() else None,
                        "modified": stat.st_mtime,
                    })
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

        return {
            "path": str(dir_path.resolve()),
            "items": items,
        }

    # SPA catch-all routes for frontend navigation
    frontend_routes = [
        "/explorer", "/lineage", "/dead-code", "/compare",
        "/batch", "/impact", "/merge", "/results", "/refactoring",
        "/analysis", "/ml-dashboard", "/project-compare"
    ]

    @app.get("/{path:path}", response_class=HTMLResponse)
    async def spa_catch_all(path: str):
        """Serve React frontend for all non-API routes."""
        # Skip API routes
        if path.startswith("api/") or path.startswith("assets/") or path.startswith("static/"):
            raise HTTPException(status_code=404, detail="Not found")

        frontend_index = Path(__file__).parent.parent.parent / "frontend" / "dist" / "index.html"
        if frontend_index.exists():
            return frontend_index.read_text(encoding="utf-8")
        raise HTTPException(status_code=404, detail="Frontend not built")

    return app


# Default app instance
app = create_web_app()
