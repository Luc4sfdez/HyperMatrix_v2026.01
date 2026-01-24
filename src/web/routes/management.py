"""
HyperMatrix v2026 - Project Management Routes
Endpoints for managing workspace and analysis data separately.
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/management", tags=["management"])

# Paths
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
WORKSPACE_PATH = Path(DATA_DIR) / "workspace"
VECTORS_PATH = Path(DATA_DIR) / "vectors"


def get_folder_size(path: Path) -> int:
    """Calculate size of a folder in bytes."""
    total = 0
    if path.exists():
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except:
                    pass
    return total


def get_chromadb_count(project_id: int) -> int:
    """Get count of documents in ChromaDB for a project."""
    try:
        from ...embeddings import get_embedding_engine
        engine = get_embedding_engine()
        if engine and engine.collection:
            # Query documents with this project_id
            results = engine.collection.get(
                where={"project_id": project_id},
                include=[]
            )
            return len(results.get("ids", []))
    except Exception as e:
        print(f"[Management] ChromaDB count error: {e}")
    return 0


def get_chromadb_count_by_scan(scan_id: str) -> int:
    """Get count of documents in ChromaDB for a scan."""
    try:
        from ...embeddings import get_embedding_engine
        engine = get_embedding_engine()
        if engine and engine.collection:
            results = engine.collection.get(
                where={"scan_id": scan_id},
                include=[]
            )
            return len(results.get("ids", []))
    except Exception as e:
        print(f"[Management] ChromaDB count error: {e}")
    return 0


@router.get("/projects/status")
async def get_projects_status():
    """
    Get status of all projects with workspace and analysis info.
    Shows what would be affected by delete operations.
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    projects = []

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()

        # Get all projects with file counts
        cursor.execute("""
            SELECT p.id, p.name, p.root_path, p.created_at,
                   COUNT(DISTINCT f.id) as file_count,
                   COUNT(DISTINCT fn.id) as function_count,
                   COUNT(DISTINCT c.id) as class_count,
                   COUNT(DISTINCT v.id) as variable_count,
                   COUNT(DISTINCT i.id) as import_count
            FROM projects p
            LEFT JOIN files f ON f.project_id = p.id
            LEFT JOIN functions fn ON fn.file_id = f.id
            LEFT JOIN classes c ON c.file_id = f.id
            LEFT JOIN variables v ON v.file_id = f.id
            LEFT JOIN imports i ON i.file_id = f.id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)

        for row in cursor.fetchall():
            project_id = row["id"]
            project_name = row["name"]
            root_path = row["root_path"]

            # Check workspace
            workspace_path = Path(root_path) if root_path else None
            workspace_exists = workspace_path and workspace_path.exists()
            workspace_size = get_folder_size(workspace_path) if workspace_exists else 0

            # Get ChromaDB count
            chromadb_docs = get_chromadb_count(project_id)

            # Calculate total SQLite records
            sqlite_records = (
                row["file_count"] +
                row["function_count"] +
                row["class_count"] +
                row["variable_count"] +
                row["import_count"]
            )

            projects.append({
                "id": project_id,
                "name": project_name,
                "root_path": root_path,
                "created_at": row["created_at"],
                "workspace": {
                    "exists": workspace_exists,
                    "size_bytes": workspace_size,
                    "size_human": f"{workspace_size / 1024 / 1024:.2f} MB" if workspace_size else "0 MB"
                },
                "analysis": {
                    "exists": row["file_count"] > 0,
                    "files": row["file_count"],
                    "functions": row["function_count"],
                    "classes": row["class_count"],
                    "variables": row["variable_count"],
                    "imports": row["import_count"],
                    "sqlite_total": sqlite_records,
                    "chromadb_docs": chromadb_docs
                }
            })

    return {
        "total_projects": len(projects),
        "projects": projects
    }


@router.get("/workspace/{project_id}/preview")
async def preview_workspace_delete(project_id: int):
    """
    Preview what will be deleted from workspace.
    Call this before DELETE to show user what will be removed.
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, root_path FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        project_name = row["name"]
        root_path = Path(row["root_path"]) if row["root_path"] else None

        if not root_path or not root_path.exists():
            return {
                "project_id": project_id,
                "project_name": project_name,
                "workspace_exists": False,
                "message": "Workspace already deleted or not found",
                "files_to_delete": [],
                "total_size": 0
            }

        # List files
        files = []
        total_size = 0
        for f in root_path.rglob("*"):
            if f.is_file():
                try:
                    size = f.stat().st_size
                    files.append({
                        "path": str(f.relative_to(root_path)),
                        "size": size
                    })
                    total_size += size
                except:
                    pass

        return {
            "project_id": project_id,
            "project_name": project_name,
            "workspace_exists": True,
            "root_path": str(root_path),
            "files_to_delete": files[:100],  # Limit to first 100
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_human": f"{total_size / 1024 / 1024:.2f} MB",
            "warning": "This will permanently delete workspace files. Analysis data will be preserved."
        }


@router.delete("/workspace/{project_id}")
async def delete_workspace_only(project_id: int, confirm: bool = False):
    """
    Delete workspace files only. Preserves SQLite and ChromaDB analysis data.
    Requires confirm=true query parameter.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Add ?confirm=true to confirm deletion. Use GET /preview first."
        )

    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, root_path FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        project_name = row["name"]
        root_path = Path(row["root_path"]) if row["root_path"] else None

        if not root_path or not root_path.exists():
            return {
                "success": True,
                "message": "Workspace already deleted or not found",
                "project_id": project_id,
                "deleted_files": 0
            }

        # Count files before deletion
        file_count = sum(1 for _ in root_path.rglob("*") if _.is_file())
        total_size = get_folder_size(root_path)

        # Delete workspace
        try:
            shutil.rmtree(root_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete workspace: {e}")

        return {
            "success": True,
            "message": f"Workspace deleted for project '{project_name}'",
            "project_id": project_id,
            "deleted_files": file_count,
            "deleted_size_bytes": total_size,
            "deleted_size_human": f"{total_size / 1024 / 1024:.2f} MB",
            "analysis_preserved": True
        }


@router.get("/analysis/{scan_id}/preview")
async def preview_analysis_delete(scan_id: str):
    """
    Preview what will be deleted from analysis (SQLite + ChromaDB).
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    project_id = int(scan_id)

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()

        # Get project info
        cursor.execute("SELECT name, root_path FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Project/Scan {scan_id} not found")

        # Count records
        counts = {}
        for table in ["files", "functions", "classes", "variables", "imports"]:
            if table == "files":
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (project_id,))
            else:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table} t
                    JOIN files f ON t.file_id = f.id
                    WHERE f.project_id = ?
                """, (project_id,))
            counts[table] = cursor.fetchone()[0]

        # ChromaDB count
        chromadb_docs = get_chromadb_count(project_id)

        return {
            "scan_id": scan_id,
            "project_name": row["name"],
            "sqlite_records": counts,
            "sqlite_total": sum(counts.values()),
            "chromadb_docs": chromadb_docs,
            "workspace_preserved": True,
            "warning": "This will delete all analysis data. Workspace files will be preserved."
        }


@router.delete("/analysis/{scan_id}")
async def delete_analysis_only(scan_id: str, confirm: bool = False):
    """
    Delete analysis data only (SQLite + ChromaDB). Preserves workspace files.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Add ?confirm=true to confirm deletion. Use GET /preview first."
        )

    from ..app import db_manager, active_scans, scan_results

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    project_id = int(scan_id)
    deleted_counts = {}

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()

        # Verify project exists
        cursor.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project/Scan {scan_id} not found")

        project_name = row["name"]

        # Delete from child tables first (foreign key order)
        for table in ["functions", "classes", "variables", "imports"]:
            cursor.execute(f"""
                DELETE FROM {table} WHERE file_id IN (
                    SELECT id FROM files WHERE project_id = ?
                )
            """, (project_id,))
            deleted_counts[table] = cursor.rowcount

        # Delete files
        cursor.execute("DELETE FROM files WHERE project_id = ?", (project_id,))
        deleted_counts["files"] = cursor.rowcount

        # Delete project record
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        deleted_counts["projects"] = cursor.rowcount

        conn.commit()

    # Delete from ChromaDB
    chromadb_deleted = 0
    try:
        from ...embeddings import get_embedding_engine
        engine = get_embedding_engine()
        if engine and engine.collection:
            # Get IDs to delete
            results = engine.collection.get(
                where={"project_id": project_id},
                include=[]
            )
            ids_to_delete = results.get("ids", [])
            if ids_to_delete:
                engine.collection.delete(ids=ids_to_delete)
                chromadb_deleted = len(ids_to_delete)
    except Exception as e:
        print(f"[Management] ChromaDB delete error: {e}")

    # Clean up in-memory state
    if scan_id in active_scans:
        del active_scans[scan_id]
    if scan_id in scan_results:
        del scan_results[scan_id]

    return {
        "success": True,
        "message": f"Analysis deleted for project '{project_name}'",
        "scan_id": scan_id,
        "sqlite_deleted": deleted_counts,
        "sqlite_total": sum(deleted_counts.values()),
        "chromadb_deleted": chromadb_deleted,
        "workspace_preserved": True
    }


@router.get("/project/{project_id}/preview")
async def preview_full_delete(project_id: int):
    """
    Preview what will be deleted (both workspace and analysis).
    """
    workspace_preview = await preview_workspace_delete(project_id)
    analysis_preview = await preview_analysis_delete(str(project_id))

    return {
        "project_id": project_id,
        "workspace": workspace_preview,
        "analysis": analysis_preview,
        "warning": "This will PERMANENTLY delete ALL data for this project (workspace + analysis)."
    }


@router.delete("/project/{project_id}/all")
async def delete_project_all(project_id: int, confirm: bool = False):
    """
    Delete both workspace and analysis data for a project.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Add ?confirm=true to confirm deletion. Use GET /preview first."
        )

    # Delete workspace first
    workspace_result = await delete_workspace_only(project_id, confirm=True)

    # Delete analysis
    analysis_result = await delete_analysis_only(str(project_id), confirm=True)

    return {
        "success": True,
        "message": "Project completely deleted",
        "project_id": project_id,
        "workspace": workspace_result,
        "analysis": analysis_result
    }
