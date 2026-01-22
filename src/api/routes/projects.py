"""
HyperMatrix v2026 - Projects API Routes
CRUD operations for projects.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from ..dependencies import get_db
from ...phases import Phase1Discovery, Phase1_5Deduplication, Phase2Analysis

router = APIRouter()


# Pydantic models
class ProjectCreate(BaseModel):
    """Request model for creating a project."""
    name: str = Field(..., min_length=1, max_length=100)
    root_path: str = Field(..., min_length=1)


class ProjectResponse(BaseModel):
    """Response model for project."""
    id: int
    name: str
    root_path: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectStats(BaseModel):
    """Project statistics."""
    project_id: int
    total_files: int
    total_functions: int
    total_classes: int
    total_imports: int


class AnalyzeRequest(BaseModel):
    """Request model for analysis."""
    project_name: str = "default"
    target_path: str
    skip_duplicates: bool = True
    extract_archives: bool = True


class AnalyzeResponse(BaseModel):
    """Response model for analysis."""
    project_id: int
    status: str
    total_files: int
    analyzed_files: int
    functions_found: int
    classes_found: int
    duration_seconds: float


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    """Create a new project."""
    db = get_db()
    project_id = db.create_project(project.name, project.root_path)

    return ProjectResponse(
        id=project_id,
        name=project.name,
        root_path=project.root_path,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int):
    """Get project by ID."""
    db = get_db()
    project = db.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project["id"],
        name=project["name"],
        root_path=project["root_path"],
        created_at=str(project.get("created_at", "")),
        updated_at=str(project.get("updated_at", "")),
    )


@router.get("/{project_id}/stats", response_model=ProjectStats)
async def get_project_stats(project_id: int):
    """Get project statistics."""
    db = get_db()

    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stats = db.get_statistics(project_id)

    return ProjectStats(
        project_id=project_id,
        total_files=stats.get("total_files", 0),
        total_functions=stats.get("total_functions", 0),
        total_classes=stats.get("total_classes", 0),
        total_imports=stats.get("total_imports", 0),
    )


@router.delete("/{project_id}")
async def delete_project(project_id: int):
    """Delete a project and all its data."""
    db = get_db()

    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.clear_project(project_id)

    return {"status": "deleted", "project_id": project_id}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_directory(request: AnalyzeRequest):
    """
    Analyze a directory and store results.
    Runs Phase 1, 1.5, and 2.
    """
    import time
    start_time = time.time()

    db = get_db()

    # Phase 1: Discovery
    phase1 = Phase1Discovery(compute_hash=True, extract_archives=request.extract_archives)
    discovery_result = phase1.scan_directory(request.target_path)

    # Phase 1.5: Deduplication
    phase1_5 = Phase1_5Deduplication()
    dedup_result = phase1_5.process(discovery_result)

    # Phase 2: Analysis
    phase2 = Phase2Analysis(
        db_manager=db,
        skip_duplicates=request.skip_duplicates,
        extract_dna=True,
    )

    # Create project
    project_id = db.create_project(request.project_name, request.target_path)

    analysis_result = phase2.analyze_all_files(
        discovery_result,
        dedup_result if request.skip_duplicates else None,
        request.project_name,
    )

    # Cleanup
    phase1.cleanup()

    duration = time.time() - start_time
    summary = phase2.get_summary()

    return AnalyzeResponse(
        project_id=project_id,
        status="completed",
        total_files=summary["total_files"],
        analyzed_files=summary["analyzed_files"],
        functions_found=summary["total_functions"],
        classes_found=summary["total_classes"],
        duration_seconds=round(duration, 2),
    )


@router.get("/")
async def list_projects():
    """List all projects."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, root_path, created_at FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()

    return {
        "projects": [
            {
                "id": row["id"],
                "name": row["name"],
                "root_path": row["root_path"],
                "created_at": str(row["created_at"]) if row["created_at"] else None,
            }
            for row in rows
        ]
    }
