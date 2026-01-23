"""
HyperMatrix v2026 - Project Summary API
Endpoints for generating and retrieving project summaries.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..app import scan_results, active_scans
from ...core.summary import get_summary_generator, ProjectSummary

router = APIRouter(prefix="/api/summary", tags=["summary"])
logger = logging.getLogger(__name__)

# Store generated summaries
summaries: dict[str, ProjectSummary] = {}


class SummaryResponse(BaseModel):
    """Response model for summary."""
    scan_id: str
    project_path: str
    summary_text: str
    file_count: int
    function_count: int
    class_count: int
    technologies: list[str]
    generated_at: str


class QuickSummaryResponse(BaseModel):
    """Response for quick summary (no AI)."""
    scan_id: str
    file_count: int
    file_types: dict[str, int]
    technologies: list[str]
    directories: int


@router.get("/{scan_id}")
async def get_summary(scan_id: str):
    """
    Get the summary for a scan.

    Returns existing summary if available, or quick summary if AI summary
    hasn't been generated yet.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check if we have an AI-generated summary
    if scan_id in summaries:
        summary = summaries[scan_id]
        return {
            "type": "ai_generated",
            "scan_id": summary.scan_id,
            "project_path": summary.project_path,
            "summary_text": summary.summary_text,
            "file_count": summary.file_count,
            "function_count": summary.function_count,
            "class_count": summary.class_count,
            "technologies": summary.technologies,
            "generated_at": summary.generated_at,
        }

    # Return quick summary
    generator = get_summary_generator()
    quick = generator.generate_quick_summary(scan_results[scan_id])

    return {
        "type": "quick",
        "scan_id": scan_id,
        **quick,
        "message": "AI summary not generated yet. Use POST /api/summary/{scan_id}/generate to create one."
    }


@router.post("/{scan_id}/generate")
async def generate_summary(scan_id: str, background_tasks: BackgroundTasks):
    """
    Generate an AI summary for a scan.

    This runs in the background and may take up to 2 minutes depending on
    project size and Ollama performance.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check if already generating or generated
    if scan_id in summaries:
        return {
            "status": "exists",
            "message": "Summary already exists",
            "summary": summaries[scan_id].summary_text[:500] + "..." if len(summaries[scan_id].summary_text) > 500 else summaries[scan_id].summary_text
        }

    # Start background generation
    async def generate_in_background():
        try:
            generator = get_summary_generator()
            result = scan_results[scan_id]

            summary = await generator.generate_summary(
                scan_id=scan_id,
                scan_result=result,
                analysis_result=result.get("analysis")
            )

            if summary:
                summaries[scan_id] = summary
                logger.info(f"Generated summary for scan {scan_id}")
            else:
                logger.warning(f"Failed to generate summary for scan {scan_id}")

        except Exception as e:
            logger.error(f"Error generating summary: {e}")

    background_tasks.add_task(generate_in_background)

    return {
        "status": "generating",
        "message": "Summary generation started. Poll GET /api/summary/{scan_id} to check status.",
        "scan_id": scan_id
    }


@router.get("/{scan_id}/quick")
async def get_quick_summary(scan_id: str):
    """
    Get a quick summary (statistics only, no AI).

    This is instant and doesn't require Ollama.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    generator = get_summary_generator()
    quick = generator.generate_quick_summary(scan_results[scan_id])

    return {
        "scan_id": scan_id,
        **quick
    }


@router.delete("/{scan_id}")
async def delete_summary(scan_id: str):
    """Delete a generated summary."""
    if scan_id in summaries:
        del summaries[scan_id]
        return {"status": "deleted", "scan_id": scan_id}

    return {"status": "not_found", "scan_id": scan_id}


@router.get("")
async def list_summaries():
    """List all generated summaries."""
    return {
        "summaries": [
            {
                "scan_id": s.scan_id,
                "project_path": s.project_path,
                "file_count": s.file_count,
                "technologies": s.technologies,
                "generated_at": s.generated_at,
            }
            for s in summaries.values()
        ],
        "total": len(summaries)
    }
