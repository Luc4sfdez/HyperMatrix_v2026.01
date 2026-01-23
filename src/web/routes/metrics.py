"""
HyperMatrix v2026 - Code Metrics API
Endpoints for code quality metrics and technical debt analysis.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..app import scan_results
from ...core.code_metrics import (
    analyze_project_metrics,
    analyze_file_metrics,
    ProjectMetrics,
    FileMetrics,
)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])
logger = logging.getLogger(__name__)

# Cache for project metrics (can be expensive to compute)
metrics_cache: dict[str, ProjectMetrics] = {}


class FileMetricsResponse(BaseModel):
    """Response for file metrics."""
    filepath: str
    lines_total: int
    lines_code: int
    lines_comment: int
    avg_complexity: float
    max_complexity: int
    doc_coverage: float
    tech_debt_score: float
    functions_count: int
    classes_count: int


class ProjectMetricsResponse(BaseModel):
    """Response for project metrics."""
    total_files: int
    total_lines: int
    total_functions: int
    total_classes: int
    avg_complexity: float
    max_complexity: int
    max_complexity_file: str
    doc_coverage: float
    tech_debt_score: float
    hotspots: list
    circular_deps: list
    files_by_complexity: list


@router.get("/{scan_id}")
async def get_project_metrics(scan_id: str, refresh: bool = False):
    """
    Get code quality metrics for a scanned project.

    Calculates:
    - Cyclomatic complexity per file
    - Documentation coverage
    - Technical debt score
    - Hotspots (high complexity areas)
    - Circular dependencies

    Use refresh=true to force recalculation.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check cache
    if scan_id in metrics_cache and not refresh:
        cached = metrics_cache[scan_id]
        return {
            "scan_id": scan_id,
            "cached": True,
            **_project_metrics_to_dict(cached)
        }

    scan = scan_results[scan_id]

    # Get project path
    project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="Project path not found in scan")

    # Get file list from scan if available
    filepaths = None
    discovery = scan.get("discovery", {})
    if discovery.get("files"):
        filepaths = [
            f.get("filepath") or f.get("path")
            for f in discovery["files"]
            if (f.get("filepath") or f.get("path", "")).endswith(".py")
        ]

    try:
        metrics = analyze_project_metrics(
            root_path=project_path,
            filepaths=filepaths,
            max_files=500
        )

        # Cache the result
        metrics_cache[scan_id] = metrics

        return {
            "scan_id": scan_id,
            "cached": False,
            **_project_metrics_to_dict(metrics)
        }

    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scan_id}/file")
async def get_file_metrics(scan_id: str, filepath: str):
    """
    Get detailed metrics for a specific file.

    Returns complexity, documentation coverage, and function-level details.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        metrics = analyze_file_metrics(filepath)

        if not metrics:
            raise HTTPException(status_code=400, detail="Could not analyze file (not Python or syntax error)")

        return {
            "filepath": metrics.filepath,
            "lines": {
                "total": metrics.lines_total,
                "code": metrics.lines_code,
                "comment": metrics.lines_comment,
                "blank": metrics.lines_blank,
            },
            "complexity": {
                "average": metrics.avg_complexity,
                "max": metrics.max_complexity,
            },
            "doc_coverage": metrics.doc_coverage,
            "tech_debt_score": metrics.tech_debt_score,
            "counts": {
                "functions": len(metrics.functions),
                "classes": metrics.classes,
                "imports": metrics.imports,
            },
            "functions": [
                {
                    "name": f.name,
                    "line": f.lineno,
                    "lines": f.lines,
                    "complexity": f.complexity,
                    "has_docstring": f.has_docstring,
                    "parameters": f.parameters,
                    "nested_depth": f.nested_depth,
                }
                for f in metrics.functions
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing file metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scan_id}/hotspots")
async def get_complexity_hotspots(scan_id: str, limit: int = 10):
    """
    Get files with highest complexity (hotspots).

    These are files that may need refactoring attention.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Try to use cached metrics
    if scan_id in metrics_cache:
        metrics = metrics_cache[scan_id]
    else:
        scan = scan_results[scan_id]
        project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")

        if not project_path:
            raise HTTPException(status_code=400, detail="Project path not found")

        metrics = analyze_project_metrics(project_path, max_files=500)
        metrics_cache[scan_id] = metrics

    return {
        "scan_id": scan_id,
        "hotspots": metrics.hotspots[:limit],
        "total_hotspots": len(metrics.hotspots),
        "threshold": {
            "avg_complexity": 5,
            "max_complexity": 10,
        },
    }


@router.get("/{scan_id}/circular-deps")
async def get_circular_dependencies(scan_id: str):
    """
    Get detected circular import dependencies.

    Circular imports can cause runtime issues and indicate architectural problems.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Try to use cached metrics
    if scan_id in metrics_cache:
        metrics = metrics_cache[scan_id]
    else:
        scan = scan_results[scan_id]
        project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")

        if not project_path:
            raise HTTPException(status_code=400, detail="Project path not found")

        metrics = analyze_project_metrics(project_path, max_files=500)
        metrics_cache[scan_id] = metrics

    return {
        "scan_id": scan_id,
        "circular_dependencies": [
            {"module_a": pair[0], "module_b": pair[1]}
            for pair in metrics.circular_deps
        ],
        "total": len(metrics.circular_deps),
    }


@router.get("/{scan_id}/tech-debt")
async def get_tech_debt_summary(scan_id: str):
    """
    Get technical debt summary for the project.

    The score is 0-100, with higher values indicating more technical debt.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Try to use cached metrics
    if scan_id in metrics_cache:
        metrics = metrics_cache[scan_id]
    else:
        scan = scan_results[scan_id]
        project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")

        if not project_path:
            raise HTTPException(status_code=400, detail="Project path not found")

        metrics = analyze_project_metrics(project_path, max_files=500)
        metrics_cache[scan_id] = metrics

    # Categorize debt level
    score = metrics.tech_debt_score
    if score < 20:
        level = "low"
        message = "Good code quality"
    elif score < 40:
        level = "moderate"
        message = "Some areas need attention"
    elif score < 60:
        level = "high"
        message = "Significant refactoring recommended"
    else:
        level = "critical"
        message = "Major technical debt issues"

    return {
        "scan_id": scan_id,
        "tech_debt_score": score,
        "level": level,
        "message": message,
        "factors": {
            "avg_complexity": metrics.avg_complexity,
            "max_complexity": metrics.max_complexity,
            "doc_coverage": metrics.doc_coverage,
        },
        "recommendations": _get_recommendations(metrics),
    }


@router.delete("/{scan_id}/cache")
async def clear_metrics_cache(scan_id: str):
    """Clear cached metrics for a scan."""
    if scan_id in metrics_cache:
        del metrics_cache[scan_id]
        return {"status": "cleared", "scan_id": scan_id}
    return {"status": "not_cached", "scan_id": scan_id}


def _project_metrics_to_dict(metrics: ProjectMetrics) -> dict:
    """Convert ProjectMetrics to dictionary."""
    return {
        "total_files": metrics.total_files,
        "total_lines": metrics.total_lines,
        "total_functions": metrics.total_functions,
        "total_classes": metrics.total_classes,
        "complexity": {
            "average": metrics.avg_complexity,
            "max": metrics.max_complexity,
            "max_file": metrics.max_complexity_file,
        },
        "doc_coverage": metrics.doc_coverage,
        "tech_debt_score": metrics.tech_debt_score,
        "hotspots": metrics.hotspots,
        "circular_dependencies": [
            {"module_a": p[0], "module_b": p[1]}
            for p in metrics.circular_deps
        ],
        "files_by_complexity": metrics.files_by_complexity,
    }


def _get_recommendations(metrics: ProjectMetrics) -> list:
    """Generate recommendations based on metrics."""
    recommendations = []

    if metrics.avg_complexity > 10:
        recommendations.append({
            "type": "complexity",
            "priority": "high",
            "message": "Average complexity is high. Consider breaking down complex functions.",
        })
    elif metrics.avg_complexity > 5:
        recommendations.append({
            "type": "complexity",
            "priority": "medium",
            "message": "Some functions have moderate complexity. Review hotspots.",
        })

    if metrics.doc_coverage < 0.3:
        recommendations.append({
            "type": "documentation",
            "priority": "high",
            "message": f"Only {metrics.doc_coverage*100:.0f}% of functions have docstrings. Add documentation.",
        })
    elif metrics.doc_coverage < 0.6:
        recommendations.append({
            "type": "documentation",
            "priority": "medium",
            "message": "Documentation coverage could be improved.",
        })

    if metrics.circular_deps:
        recommendations.append({
            "type": "architecture",
            "priority": "high",
            "message": f"Found {len(metrics.circular_deps)} circular import(s). Refactor to remove cycles.",
        })

    if len(metrics.hotspots) > 5:
        recommendations.append({
            "type": "refactoring",
            "priority": "medium",
            "message": f"{len(metrics.hotspots)} files have high complexity. Plan refactoring sessions.",
        })

    if not recommendations:
        recommendations.append({
            "type": "general",
            "priority": "low",
            "message": "Code quality metrics look good. Keep up the good work!",
        })

    return recommendations
