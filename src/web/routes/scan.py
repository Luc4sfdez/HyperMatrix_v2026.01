"""
HyperMatrix v2026 - Scan Routes
Endpoints for starting and monitoring scans.
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..models import ScanRequest, ScanProgress, ScanStatus
from .. import app as web_app  # Import module to access globals dynamically
from ..app import active_scans, scan_results
from ...phases.phase1_discovery import Phase1Discovery
from ...phases.phase1_5_deduplication import Phase1_5Deduplication
from ...phases.phase2_analysis import Phase2Analysis
from ...phases.phase3_consolidation import Phase3Consolidation

router = APIRouter()


async def run_scan(scan_id: str, request: ScanRequest):
    """Background task to run the full scan pipeline."""
    progress = active_scans[scan_id]

    try:
        path = Path(request.path)
        if not path.exists():
            progress.status = ScanStatus.FAILED
            progress.errors.append(f"Path not found: {request.path}")
            return

        project_name = request.project_name or path.name

        # Phase 1: Discovery
        progress.phase = "discovery"
        progress.status = ScanStatus.RUNNING

        discovery = Phase1Discovery(extract_archives=request.include_archives)
        discovery_result = discovery.scan_directory(str(path))

        progress.total_files = len(discovery_result.files)
        progress.phase_progress = 1.0

        # Phase 1.5: Deduplication
        if request.detect_duplicates:
            progress.phase = "deduplication"
            progress.phase_progress = 0.0

            dedup = Phase1_5Deduplication()
            dedup_result = dedup.process(discovery_result)
            progress.phase_progress = 1.0
        else:
            dedup_result = None

        # Phase 2: Analysis
        progress.phase = "analysis"
        progress.phase_progress = 0.0

        analysis = Phase2Analysis(web_app.db_manager)
        analysis_result = analysis.analyze_all_files(
            discovery_result,
            dedup_result=dedup_result,
            project_name=project_name
        )

        progress.processed_files = analysis_result.analyzed_files
        progress.phase_progress = 1.0

        # Phase 3: Consolidation
        consolidation_result = None
        if request.calculate_similarities:
            progress.phase = "consolidation"
            progress.phase_progress = 0.0
            progress.current_file = None

            consolidation = Phase3Consolidation(web_app.db_manager)
            consolidation_result = consolidation.consolidate(discovery_result, analysis_result)
            progress.phase_progress = 1.0

        # Store results
        scan_results[scan_id] = {
            "project_name": project_name,
            "total_files": progress.total_files,
            "analyzed_files": progress.processed_files,
            "duplicate_groups": dedup_result.total_duplicate_count if dedup_result else 0,
            "sibling_groups": consolidation_result.sibling_groups if consolidation_result else 0,
            "consolidation": consolidation_result,
            "analysis": analysis_result,
        }

        progress.status = ScanStatus.COMPLETED
        progress.phase = "completed"

    except Exception as e:
        progress.status = ScanStatus.FAILED
        progress.errors.append(str(e))


@router.post("/start", response_model=ScanProgress)
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Start a new scan."""
    # Validate path
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Path not found: {request.path}")

    # Create scan
    scan_id = str(uuid.uuid4())[:8]
    progress = ScanProgress(
        scan_id=scan_id,
        status=ScanStatus.PENDING,
        phase="initializing",
        phase_progress=0.0,
        total_files=0,
        processed_files=0,
        current_file=None,
    )

    active_scans[scan_id] = progress

    # Start background task
    background_tasks.add_task(run_scan, scan_id, request)

    return progress


@router.get("/status/{scan_id}", response_model=ScanProgress)
async def get_scan_status(scan_id: str):
    """Get scan progress."""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    return active_scans[scan_id]


@router.get("/result/{scan_id}/summary")
async def get_scan_result_summary(scan_id: str):
    """Get lightweight scan results summary (no heavy objects)."""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")

    progress = active_scans[scan_id]
    if progress.status != ScanStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Scan not completed. Status: {progress.status}")

    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Results not found")

    result = scan_results[scan_id]

    # Return only lightweight summary data
    summary = {
        "scan_id": scan_id,
        "project_name": result.get("project_name"),
        "total_files": result.get("total_files", 0),
        "analyzed_files": result.get("analyzed_files", 0),
        "duplicate_groups": result.get("duplicate_groups", 0),
        "sibling_groups": result.get("sibling_groups", 0),
    }

    # Add consolidation summary if available
    consolidation = result.get("consolidation")
    if consolidation:
        summary["consolidation_summary"] = {
            "total_groups": getattr(consolidation, "sibling_groups", 0),
            "total_similarities": getattr(consolidation, "total_similarities", 0),
        }
        # Add sibling_groups as list with filenames for Lineage page
        if hasattr(consolidation, 'groups') and consolidation.groups:
            summary["sibling_groups"] = [
                {"filename": fname, "count": len(getattr(group, 'files', [])) if hasattr(group, 'files') else 1}
                for fname, group in consolidation.groups.items()
            ]

    # Add analysis summary if available
    analysis = result.get("analysis")
    if analysis:
        summary["analysis_summary"] = {
            "analyzed_files": getattr(analysis, "analyzed_files", 0),
            "failed_files": getattr(analysis, "failed_files", 0),
            "total_functions": getattr(analysis, "total_functions", 0),
            "total_classes": getattr(analysis, "total_classes", 0),
            "errors": getattr(analysis, "errors", []),
        }

    # For DB-loaded projects without consolidation, load files from database
    if not consolidation and web_app.db_manager:
        try:
            with web_app.db_manager._get_connection() as conn:
                cursor = conn.cursor()
                # Get files for this project
                cursor.execute("""
                    SELECT DISTINCT f.filepath
                    FROM files f
                    WHERE f.project_id = ?
                    ORDER BY f.filepath
                    LIMIT 200
                """, (int(scan_id),))
                files = cursor.fetchall()
                if files:
                    # Group files by filename (basename)
                    from pathlib import Path
                    file_groups = {}
                    for row in files:
                        basename = Path(row["filepath"]).name
                        if basename not in file_groups:
                            file_groups[basename] = []
                        file_groups[basename].append(row["filepath"])
                    summary["sibling_groups"] = [
                        {"filename": fname, "count": len(paths)}
                        for fname, paths in file_groups.items()
                    ]
        except Exception as e:
            print(f"[Scan] Warning: Error loading files from DB: {e}")

    return summary


@router.get("/result/{scan_id}")
async def get_scan_result(scan_id: str):
    """Get full scan results (warning: can be large)."""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")

    progress = active_scans[scan_id]
    if progress.status != ScanStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Scan not completed. Status: {progress.status}")

    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Results not found")

    return scan_results[scan_id]


@router.get("/list")
async def list_scans():
    """List all scans with summary info."""
    scans = []
    for scan_id, progress in active_scans.items():
        scan_info = {
            "scan_id": scan_id,
            "status": progress.status,
            "phase": progress.phase,
            "progress": progress.phase_progress,
            "files": progress.total_files,
        }

        # Add project name and stats from results if available
        if scan_id in scan_results:
            result = scan_results[scan_id]
            scan_info["project"] = result.get("project_name", "")
            scan_info["analyzed"] = result.get("analyzed_files", 0)
            scan_info["duplicates"] = result.get("duplicate_groups", 0)
            scan_info["siblings"] = result.get("sibling_groups", 0)

        scans.append(scan_info)

    return {"scans": scans}


@router.delete("/{scan_id}")
async def delete_scan(scan_id: str):
    """Delete a scan from memory."""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")

    progress = active_scans[scan_id]
    if progress.status == ScanStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete running scan")

    del active_scans[scan_id]
    if scan_id in scan_results:
        del scan_results[scan_id]

    return {"message": "Scan deleted"}
