"""
HyperMatrix v2026 - Advanced Analysis Routes (BLOQUE D)
Endpoints for natural search, dead code, refactoring, webhooks, cross-project, and ML.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from ...core.natural_search import NaturalSearch, QueryParser
from ...core.dead_code_detector import DeadCodeDetector
from ...core.refactoring_suggester import RefactoringSuggester
from ...core.webhooks import WebhookManager, WebhookConfig, WebhookEvent
from ...core.project_comparator import ProjectComparator
from ...core.ml_learning import get_learning_system

router = APIRouter()


# Lazy initialization
_natural_search: Optional[NaturalSearch] = None
_dead_code_detector: Optional[DeadCodeDetector] = None
_refactoring_suggester: Optional[RefactoringSuggester] = None
_webhook_manager: Optional[WebhookManager] = None
_project_comparator: Optional[ProjectComparator] = None


def get_natural_search() -> NaturalSearch:
    global _natural_search
    if _natural_search is None:
        _natural_search = NaturalSearch()
    return _natural_search


def get_dead_code_detector() -> DeadCodeDetector:
    global _dead_code_detector
    if _dead_code_detector is None:
        _dead_code_detector = DeadCodeDetector()
    return _dead_code_detector


def get_refactoring_suggester() -> RefactoringSuggester:
    global _refactoring_suggester
    if _refactoring_suggester is None:
        _refactoring_suggester = RefactoringSuggester()
    return _refactoring_suggester


def get_webhook_manager() -> WebhookManager:
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


def get_project_comparator() -> ProjectComparator:
    global _project_comparator
    if _project_comparator is None:
        _project_comparator = ProjectComparator()
    return _project_comparator


# ============ D.1: NATURAL LANGUAGE SEARCH ============

@router.post("/search/index")
async def index_directory(
    directory: str = Query(..., description="Directory to index"),
    extensions: List[str] = Query([".py"], description="File extensions to index"),
):
    """
    Index a directory for natural language search.
    """
    if not Path(directory).exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    search = get_natural_search()
    indexed = search.index_directory(directory, extensions)

    return {
        "directory": directory,
        "files_indexed": indexed,
        "extensions": extensions,
    }


@router.get("/search")
async def natural_search(
    q: str = Query(..., description="Natural language query"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search code using natural language.

    Examples:
    - "functions that handle authentication"
    - "classes with more than 10 methods"
    - "files importing pandas"
    - "async functions in the api folder"
    """
    search = get_natural_search()
    results = search.search(q, limit=limit)

    # Parse query for additional info
    parser = QueryParser()
    parsed = parser.parse(q)

    return {
        "query": q,
        "parsed_query": {
            "element_types": parsed.element_types,
            "keywords": parsed.keywords,
            "filters": parsed.filters,
        },
        "results_count": len(results),
        "results": [
            {
                "file": r.filepath,
                "name": r.name,
                "type": r.element_type,
                "line": r.line_number,
                "score": round(r.score, 4),
                "snippet": r.snippet[:200] if r.snippet else None,
                "match_reasons": r.match_reasons,
            }
            for r in results
        ],
    }


# ============ D.2: DEAD CODE DETECTION ============

@router.post("/dead-code/analyze")
async def analyze_dead_code(
    files: List[str] = Query(..., description="Files to analyze"),
):
    """
    Detect dead (unused) code in files.

    Detects:
    - Unused functions
    - Unused classes
    - Unused imports
    - Unused variables
    """
    valid_files = [f for f in files if Path(f).exists() and f.endswith(".py")]

    if not valid_files:
        raise HTTPException(status_code=400, detail="No valid Python files")

    detector = get_dead_code_detector()
    report = detector.analyze_project(valid_files)

    return {
        "files_analyzed": len(valid_files),
        "total_definitions": report.total_definitions,
        "summary": report.summary,
        "potential_savings_lines": report.potential_savings_lines,
        "dead_functions": [
            {
                "file": item.filepath,
                "name": item.name,
                "line": item.line_number,
                "confidence": item.confidence,
                "reason": item.reason,
                "suggestion": item.suggestion,
            }
            for item in report.dead_functions[:50]
        ],
        "dead_classes": [
            {
                "file": item.filepath,
                "name": item.name,
                "line": item.line_number,
                "confidence": item.confidence,
                "suggestion": item.suggestion,
            }
            for item in report.dead_classes[:50]
        ],
        "dead_imports": [
            {
                "file": item.filepath,
                "name": item.name,
                "line": item.line_number,
                "confidence": item.confidence,
                "suggestion": item.suggestion,
            }
            for item in report.dead_imports[:100]
        ],
        "dead_variables": [
            {
                "file": item.filepath,
                "name": item.name,
                "line": item.line_number,
                "suggestion": item.suggestion,
            }
            for item in report.dead_variables[:50]
        ],
    }


@router.get("/dead-code/file/{filepath:path}")
async def analyze_file_dead_code(filepath: str):
    """
    Analyze a single file for dead code.
    """
    if not Path(filepath).exists():
        raise HTTPException(status_code=404, detail="File not found")

    detector = get_dead_code_detector()
    items = detector.find_dead_in_file(filepath)

    return {
        "file": filepath,
        "dead_code_items": len(items),
        "items": [
            {
                "name": item.name,
                "type": item.item_type,
                "line": item.line_number,
                "confidence": item.confidence,
                "reason": item.reason,
                "suggestion": item.suggestion,
            }
            for item in items
        ],
    }


# ============ D.3: REFACTORING SUGGESTIONS ============

@router.post("/refactoring/analyze")
async def analyze_refactoring(
    files: List[str] = Query(..., description="Files to analyze"),
):
    """
    Get refactoring suggestions for files.

    Detects:
    - Long functions (extract method)
    - High complexity (simplify)
    - Deep nesting (flatten)
    - Duplicate code (extract common)
    - Naming issues
    """
    valid_files = [f for f in files if Path(f).exists() and f.endswith(".py")]

    if not valid_files:
        raise HTTPException(status_code=400, detail="No valid Python files")

    suggester = get_refactoring_suggester()
    reports = suggester.analyze_files(valid_files)

    all_suggestions = []
    for filepath, report in reports.items():
        all_suggestions.extend(report.suggestions)

    # Group by severity
    by_severity = {"high": [], "medium": [], "low": []}
    for s in all_suggestions:
        by_severity[s.severity].append({
            "file": s.filepath,
            "line": s.line_number,
            "type": s.suggestion_type,
            "title": s.title,
            "description": s.description,
            "effort": s.effort,
            "impact": s.impact,
            "category": s.category,
        })

    return {
        "files_analyzed": len(valid_files),
        "total_suggestions": len(all_suggestions),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "high_priority": by_severity["high"][:20],
        "medium_priority": by_severity["medium"][:20],
        "low_priority": by_severity["low"][:20],
    }


@router.get("/refactoring/file/{filepath:path}")
async def get_file_refactoring(filepath: str):
    """
    Get refactoring suggestions for a single file.
    """
    if not Path(filepath).exists():
        raise HTTPException(status_code=404, detail="File not found")

    suggester = get_refactoring_suggester()
    report = suggester.analyze_file(filepath)

    return {
        "file": filepath,
        "overall_score": round(report.overall_score, 2),
        "total_suggestions": report.total_suggestions,
        "by_type": report.suggestions_by_type,
        "by_severity": report.suggestions_by_severity,
        "priority_suggestions": [
            {
                "line": s.line_number,
                "type": s.suggestion_type,
                "severity": s.severity,
                "title": s.title,
                "description": s.description,
                "code_snippet": s.code_snippet[:300] if s.code_snippet else None,
                "suggested_code": s.suggested_code[:300] if s.suggested_code else None,
            }
            for s in report.priority_suggestions
        ],
    }


@router.get("/refactoring/quick-wins")
async def get_quick_wins(
    files: List[str] = Query(..., description="Files to analyze"),
):
    """
    Get quick win refactorings (low effort, high impact).
    """
    valid_files = [f for f in files if Path(f).exists() and f.endswith(".py")]

    suggester = get_refactoring_suggester()
    quick_wins = []

    for filepath in valid_files:
        report = suggester.analyze_file(filepath)
        wins = suggester.get_quick_wins(report)
        quick_wins.extend(wins)

    return {
        "quick_wins_count": len(quick_wins),
        "quick_wins": [
            {
                "file": s.filepath,
                "line": s.line_number,
                "title": s.title,
                "description": s.description,
                "impact": s.impact,
            }
            for s in quick_wins[:30]
        ],
    }


# ============ D.4: WEBHOOKS ============

class WebhookRegisterRequest(BaseModel):
    id: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    enabled: bool = True


@router.post("/webhooks/register")
async def register_webhook(request: WebhookRegisterRequest):
    """
    Register a new webhook endpoint.
    """
    manager = get_webhook_manager()

    try:
        events = [WebhookEvent(e) for e in request.events]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")

    config = WebhookConfig(
        id=request.id,
        url=request.url,
        events=events,
        secret=request.secret,
        enabled=request.enabled,
    )

    success = manager.register_webhook(config)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to register webhook")

    return {"status": "registered", "webhook_id": request.id}


@router.delete("/webhooks/{webhook_id}")
async def unregister_webhook(webhook_id: str):
    """
    Remove a webhook endpoint.
    """
    manager = get_webhook_manager()
    success = manager.unregister_webhook(webhook_id)

    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {"status": "unregistered", "webhook_id": webhook_id}


@router.get("/webhooks")
async def list_webhooks():
    """
    List all registered webhooks.
    """
    manager = get_webhook_manager()
    return {"webhooks": manager.list_webhooks()}


@router.get("/webhooks/{webhook_id}/history")
async def get_webhook_history(webhook_id: str, limit: int = Query(50, ge=1, le=200)):
    """
    Get delivery history for a webhook.
    """
    manager = get_webhook_manager()
    history = manager.get_delivery_history(webhook_id=webhook_id, limit=limit)

    return {
        "webhook_id": webhook_id,
        "deliveries": [
            {
                "id": d.id,
                "event": d.event.value,
                "timestamp": d.timestamp.isoformat(),
                "success": d.success,
                "status_code": d.status_code,
                "attempts": d.attempts,
                "duration_ms": d.duration_ms,
                "error": d.error,
            }
            for d in history
        ],
    }


@router.get("/webhooks/events")
async def list_webhook_events():
    """
    List all available webhook event types.
    """
    return {
        "events": [
            {"name": e.value, "description": _get_event_description(e)}
            for e in WebhookEvent
        ]
    }


def _get_event_description(event: WebhookEvent) -> str:
    descriptions = {
        WebhookEvent.SCAN_STARTED: "Fired when a scan begins",
        WebhookEvent.SCAN_PROGRESS: "Fired during scan progress updates",
        WebhookEvent.SCAN_COMPLETED: "Fired when a scan completes successfully",
        WebhookEvent.SCAN_FAILED: "Fired when a scan fails",
        WebhookEvent.MERGE_REQUESTED: "Fired when a merge is requested",
        WebhookEvent.MERGE_COMPLETED: "Fired when a merge completes",
        WebhookEvent.MERGE_FAILED: "Fired when a merge fails",
        WebhookEvent.BATCH_STARTED: "Fired when batch operations begin",
        WebhookEvent.BATCH_COMPLETED: "Fired when batch operations complete",
        WebhookEvent.DEAD_CODE_DETECTED: "Fired when dead code is found",
        WebhookEvent.CLONES_DETECTED: "Fired when code clones are detected",
        WebhookEvent.HIGH_SIMILARITY: "Fired when high similarity is detected",
    }
    return descriptions.get(event, "")


# ============ D.5: CROSS-PROJECT COMPARISON ============

@router.post("/compare/projects")
async def compare_projects(
    project1_path: str = Query(...),
    project1_name: str = Query(...),
    project2_path: str = Query(...),
    project2_name: str = Query(...),
    deep_compare: bool = Query(True),
):
    """
    Compare two projects for shared/duplicated code.
    """
    for path in [project1_path, project2_path]:
        if not Path(path).exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    comparator = get_project_comparator()

    # Create snapshots
    comparator.create_snapshot(project1_path, project1_name)
    comparator.create_snapshot(project2_path, project2_name)

    # Compare
    report = comparator.compare_projects(project1_name, project2_name, deep_compare)

    return {
        "projects": report.project_names,
        "total_files": report.total_files,
        "summary": report.summary,
        "shared_code_ratio": {k: round(v, 4) for k, v in report.shared_code_ratio.items()},
        "exact_matches": [
            {
                "project1_file": m.project1_file,
                "project2_file": m.project2_file,
                "common_lines": m.common_lines,
            }
            for m in report.exact_matches[:50]
        ],
        "similar_matches": [
            {
                "project1_file": m.project1_file,
                "project2_file": m.project2_file,
                "similarity": round(m.similarity, 4),
                "match_type": m.match_type,
            }
            for m in report.similar_matches[:50]
        ],
        "common_patterns": report.common_patterns,
        "unique_files": {
            k: v[:20] for k, v in report.unique_files.items()
        },
    }


@router.post("/compare/find-origin")
async def find_code_origin(
    file_path: str = Query(..., description="File to trace"),
    search_projects: List[str] = Query(..., description="Project names to search"),
):
    """
    Find where code might have originated from.
    """
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    comparator = get_project_comparator()
    origins = comparator.find_code_origin(file_path, search_projects)

    return {
        "file": file_path,
        "potential_origins": origins[:20],
    }


# ============ D.6: ML LEARNING ============

class DecisionRecord(BaseModel):
    decision_type: str
    files: List[str]
    choice: str
    similarity_scores: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/ml/record-decision")
async def record_decision(decision: DecisionRecord):
    """
    Record a user decision for ML learning.
    """
    learning = get_learning_system()

    recorded = learning.record_decision(
        decision_type=decision.decision_type,
        files=decision.files,
        choice=decision.choice,
        similarity_scores=decision.similarity_scores,
        metadata=decision.metadata,
    )

    return {
        "status": "recorded",
        "decision_id": recorded.id,
        "timestamp": recorded.timestamp,
    }


@router.post("/ml/recommend")
async def get_recommendation(
    decision_type: str = Query(...),
    files: List[str] = Query(...),
    similarity_scores: Optional[Dict[str, float]] = Body(None),
):
    """
    Get ML recommendation for a decision.
    """
    learning = get_learning_system()

    recommendation = learning.get_recommendation(
        decision_type=decision_type,
        files=files,
        similarity_scores=similarity_scores,
    )

    if not recommendation:
        return {
            "has_recommendation": False,
            "reason": "Not enough data to make recommendation",
        }

    return {
        "has_recommendation": True,
        "recommended_action": recommendation.action,
        "confidence": round(recommendation.confidence, 4),
        "reasoning": recommendation.reasoning,
        "similar_decisions": recommendation.similar_decisions,
    }


@router.get("/ml/stats")
async def get_ml_stats():
    """
    Get ML learning system statistics.
    """
    learning = get_learning_system()
    stats = learning.get_stats()

    return {
        "total_decisions": stats.total_decisions,
        "decisions_by_type": stats.decisions_by_type,
        "accuracy_estimate": round(stats.accuracy_estimate, 4),
        "most_common_patterns": stats.most_common_patterns,
        "last_updated": stats.last_updated,
    }


@router.post("/ml/export")
async def export_ml_data(filepath: str = Query(...)):
    """
    Export ML learning data.
    """
    learning = get_learning_system()
    success = learning.export_data(filepath)

    if not success:
        raise HTTPException(status_code=500, detail="Export failed")

    return {"status": "exported", "filepath": filepath}


@router.post("/ml/import")
async def import_ml_data(filepath: str = Query(...)):
    """
    Import ML learning data.
    """
    if not Path(filepath).exists():
        raise HTTPException(status_code=404, detail="File not found")

    learning = get_learning_system()
    imported = learning.import_data(filepath)

    return {"status": "imported", "decisions_imported": imported}


@router.delete("/ml/clear")
async def clear_ml_data():
    """
    Clear all ML learning data.
    """
    learning = get_learning_system()
    success = learning.clear_data()

    return {"status": "cleared" if success else "failed"}
