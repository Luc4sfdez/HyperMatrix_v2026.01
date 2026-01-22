"""
HyperMatrix v2026 - Analysis Routes
Endpoints for dependency analysis, quality metrics, and version tracking.
"""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ...core.impact_analyzer import ImpactAnalyzer
from ...core.quality_analyzer import QualityAnalyzer
from ...core.version_tracker import VersionTracker
from ...core.merge_validator import MergeValidator
from ..app import scan_results

router = APIRouter()


# Initialize analyzers lazily
_impact_analyzer: Optional[ImpactAnalyzer] = None
_quality_analyzer: Optional[QualityAnalyzer] = None
_version_tracker: Optional[VersionTracker] = None
_merge_validator: Optional[MergeValidator] = None


def get_impact_analyzer(project_root: str) -> ImpactAnalyzer:
    global _impact_analyzer
    if _impact_analyzer is None or str(_impact_analyzer.project_root) != project_root:
        _impact_analyzer = ImpactAnalyzer(project_root)
    return _impact_analyzer


def get_quality_analyzer() -> QualityAnalyzer:
    global _quality_analyzer
    if _quality_analyzer is None:
        _quality_analyzer = QualityAnalyzer()
    return _quality_analyzer


def get_version_tracker(project_root: str) -> VersionTracker:
    global _version_tracker
    if _version_tracker is None or str(_version_tracker.project_root) != project_root:
        _version_tracker = VersionTracker(project_root)
    return _version_tracker


def get_merge_validator(project_root: str) -> MergeValidator:
    global _merge_validator
    if _merge_validator is None or str(_merge_validator.project_root) != project_root:
        _merge_validator = MergeValidator(project_root)
    return _merge_validator


# ============ DEPENDENCY ANALYSIS (B.5) ============

@router.get("/dependencies/{scan_id}/{filename}")
async def get_file_dependencies(scan_id: str, filename: str):
    """
    Get dependency information for a specific file.

    Shows what this file imports and what imports this file.
    """
    # Try memory-based consolidation first
    if scan_id in scan_results:
        result = scan_results[scan_id]
        consolidation = result.get("consolidation")

        if consolidation:
            # Find file in sibling groups
            target_file = None
            for fname, group in consolidation.groups.items():
                if fname == filename:
                    if group.master_proposal:
                        target_file = group.master_proposal.proposed_master.filepath
                    break

            if target_file:
                # Get dependency report from analyzer
                analyzer = get_impact_analyzer(str(Path(target_file).parent.parent))
                report = analyzer.get_dependency_report(target_file)

                return {
                    "filepath": report.filepath,
                    "imports": report.imports,
                    "imported_by": report.imported_by,
                    "circular_dependencies": report.circular_dependencies,
                    "external_dependencies": report.external_dependencies,
                    "depth_from_root": report.depth_from_root,
                    "coupling_score": report.coupling_score,
                }

    # Fallback: try database
    try:
        from ..app import db_manager
        if db_manager:
            project_id = int(scan_id)
            with db_manager._get_connection() as conn:
                cursor = conn.cursor()

                # Find files matching the filename
                cursor.execute("""
                    SELECT f.id, f.filepath
                    FROM files f
                    WHERE f.project_id = ? AND f.filepath LIKE ?
                    LIMIT 1
                """, (project_id, f"%{filename}%"))

                file_row = cursor.fetchone()
                if file_row:
                    file_id = file_row["id"]
                    filepath = file_row["filepath"]
                    # Extract module name from filepath
                    module = filename.replace(".py", "")

                    # Get imports
                    cursor.execute("""
                        SELECT i.module, i.names, i.lineno
                        FROM imports i WHERE i.file_id = ?
                    """, (file_id,))
                    imports = [row["module"] for row in cursor.fetchall()]

                    # Find files that import this module
                    cursor.execute("""
                        SELECT DISTINCT f.filepath
                        FROM imports i
                        JOIN files f ON f.id = i.file_id
                        WHERE f.project_id = ? AND (
                            i.module LIKE ? OR i.names LIKE ?
                        )
                    """, (project_id, f"%{module}%", f"%{filename.replace('.py', '')}%"))
                    imported_by = [row["filepath"] for row in cursor.fetchall() if row["filepath"] != filepath]

                    return {
                        "filepath": filepath,
                        "imports": imports,
                        "imported_by": imported_by,
                        "circular_dependencies": [],
                        "external_dependencies": [i for i in imports if not i.startswith(".")],
                        "depth_from_root": 0,
                        "coupling_score": min(1.0, (len(imports) + len(imported_by)) / 20),
                    }
    except Exception as e:
        print(f"DB fallback error: {e}")

    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@router.post("/impact/deletion")
async def analyze_deletion_impact(filepath: str = Query(...)):
    """
    Analyze what would break if a file is deleted.
    """
    path = Path(filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    analyzer = get_impact_analyzer(str(path.parent.parent))
    impact = analyzer.analyze_deletion_impact(filepath)

    return {
        "target_file": impact.target_file,
        "action": impact.action,
        "safe_to_proceed": impact.safe_to_proceed,
        "directly_affected": impact.directly_affected,
        "transitively_affected": impact.transitively_affected,
        "import_updates_required": impact.import_updates_required,
        "breaking_changes": impact.breaking_changes,
        "warnings": impact.warnings,
    }


@router.post("/impact/merge")
async def analyze_merge_impact(
    files: List[str] = Query(...),
    target: str = Query(...)
):
    """
    Analyze impact of merging multiple files into one.
    """
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 files")

    for f in files:
        if not Path(f).exists():
            raise HTTPException(status_code=404, detail=f"File not found: {f}")

    analyzer = get_impact_analyzer(str(Path(files[0]).parent.parent))
    impact = analyzer.analyze_merge_impact(files, target)

    return {
        "target_file": impact.target_file,
        "action": impact.action,
        "safe_to_proceed": impact.safe_to_proceed,
        "directly_affected": impact.directly_affected,
        "import_updates_required": impact.import_updates_required,
        "warnings": impact.warnings,
    }


@router.get("/impact/group/{scan_id}/{filename}")
async def get_group_impact(scan_id: str, filename: str):
    """
    Get impact analysis for consolidating a sibling group.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    group = consolidation.groups.get(filename)
    if not group or not group.master_proposal:
        raise HTTPException(status_code=404, detail="Group not found")

    files = [f.filepath for f in group.files]
    master = group.master_proposal.proposed_master.filepath

    analyzer = get_impact_analyzer(str(Path(master).parent.parent))
    impact = analyzer.get_affected_files_for_group(files, master)

    return impact


# ============ QUALITY ANALYSIS (B.4) ============

@router.get("/quality/file")
async def get_file_quality(filepath: str = Query(...)):
    """
    Get quality metrics for a single file.
    """
    path = Path(filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    analyzer = get_quality_analyzer()
    metrics = analyzer.analyze_file(filepath)

    return {
        "filepath": metrics.filepath,
        "quality_score": metrics.quality_score,
        "maintainability_index": metrics.maintainability_index,
        "documentation": {
            "has_module_docstring": metrics.has_module_docstring,
            "docstring_coverage": metrics.docstring_coverage,
            "comment_ratio": metrics.comment_ratio,
        },
        "type_safety": {
            "has_type_hints": metrics.has_type_hints,
            "type_hint_coverage": metrics.type_hint_coverage,
            "uses_typing_module": metrics.uses_typing_module,
        },
        "structure": {
            "function_count": metrics.function_count,
            "class_count": metrics.class_count,
            "avg_function_length": metrics.avg_function_length,
            "max_function_length": metrics.max_function_length,
            "avg_complexity": metrics.avg_complexity,
            "max_complexity": metrics.max_complexity,
        },
        "testing": {
            "has_tests": metrics.has_tests,
            "testable_functions": metrics.testable_functions,
        },
        "code_smells": metrics.code_smells,
        "long_functions": metrics.long_functions,
        "complex_functions": metrics.complex_functions,
    }


@router.post("/quality/compare")
async def compare_file_quality(files: List[str] = Query(...)):
    """
    Compare quality metrics across multiple files.

    Returns ranking and recommendation for master selection.
    """
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 files")

    for f in files:
        if not Path(f).exists():
            raise HTTPException(status_code=404, detail=f"File not found: {f}")

    analyzer = get_quality_analyzer()
    comparison = analyzer.compare_files(files)

    return {
        "best_quality_file": comparison.best_quality_file,
        "confidence": comparison.confidence,
        "recommendation": comparison.recommendation,
        "rankings": comparison.quality_rankings,
    }


@router.get("/quality/group/{scan_id}/{filename}")
async def get_group_quality(scan_id: str, filename: str):
    """
    Get quality comparison for all files in a sibling group.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    group = consolidation.groups.get(filename)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    files = [f.filepath for f in group.files]
    analyzer = get_quality_analyzer()
    comparison = analyzer.compare_files(files)

    return {
        "filename": filename,
        "file_count": len(files),
        "best_quality_file": comparison.best_quality_file,
        "confidence": comparison.confidence,
        "recommendation": comparison.recommendation,
        "rankings": comparison.quality_rankings,
    }


# ============ VERSION TRACKING (B.2) ============

@router.get("/history/file")
async def get_file_history(filepath: str = Query(...)):
    """
    Get version history for a single file.

    Includes git history if available.
    """
    path = Path(filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    tracker = get_version_tracker(str(path.parent.parent))
    version = tracker.get_file_version(filepath)
    git_history = tracker.get_git_history(filepath)

    return {
        "filepath": version.filepath,
        "current_version": {
            "hash": version.hash_sha256,
            "size": version.size,
            "modified": version.modified_time.isoformat(),
            "created": version.created_time.isoformat() if version.created_time else None,
            "lines": version.line_count,
        },
        "git": {
            "commit": version.git_commit,
            "author": version.git_author,
            "date": version.git_date.isoformat() if version.git_date else None,
            "message": version.git_message,
        } if version.git_commit else None,
        "git_history": git_history,
    }


@router.get("/history/group/{scan_id}/{filename}")
async def get_group_history(scan_id: str, filename: str):
    """
    Get version history for all files in a sibling group.

    Helps determine which file is the original.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    group = consolidation.groups.get(filename)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    files = [f.filepath for f in group.files]
    tracker = get_version_tracker(str(Path(files[0]).parent.parent))

    history = tracker.build_version_history(files)
    timeline = tracker.get_modification_timeline(files)

    return {
        "filename": filename,
        "oldest_version": history.oldest_version,
        "newest_version": history.newest_version,
        "likely_original": history.likely_original,
        "evolution_chain": history.evolution_chain,
        "timeline": timeline,
    }


@router.get("/evolution/{scan_id}/{filename}")
async def analyze_evolution(scan_id: str, filename: str):
    """
    Analyze how sibling files evolved from each other.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    group = consolidation.groups.get(filename)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    files = [f.filepath for f in group.files]
    tracker = get_version_tracker(str(Path(files[0]).parent.parent))

    analysis = tracker.analyze_evolution(files)

    return {
        "filename": filename,
        "likely_original": analysis.likely_original,
        "confidence": analysis.confidence,
        "evolution_tree": analysis.evolution_tree,
        "evidence": analysis.evidence,
    }


# ============ MERGE VALIDATION (B.6) ============

@router.post("/validate/merge")
async def validate_merge(
    code: str,
    run_tests: bool = Query(True),
    run_lint: bool = Query(True),
):
    """
    Validate merged code before committing.

    Runs syntax check, import validation, optional tests and lint.
    """
    if not code.strip():
        raise HTTPException(status_code=400, detail="No code provided")

    validator = get_merge_validator(".")
    validation = validator.validate_merge(
        code,
        original_files=[],
        run_tests=run_tests,
        run_lint=run_lint,
    )

    return {
        "success": validation.success,
        "syntax_valid": validation.syntax_valid,
        "imports_valid": validation.imports_valid,
        "tests_passed": validation.tests_passed,
        "lint_passed": validation.lint_passed,
        "tests_summary": {
            "run": validation.tests_run,
            "passed": validation.tests_passed_count,
            "failed": validation.tests_failed_count,
        },
        "lint_issues_count": len(validation.lint_issues),
        "errors": validation.errors,
        "warnings": validation.warnings,
        "validation_steps": [
            {"step": r.step, "passed": r.passed, "message": r.message}
            for r in validation.validation_results
        ],
    }


@router.post("/validate/quick")
async def quick_validate(code: str):
    """
    Quick validation - syntax and imports only.
    """
    if not code.strip():
        raise HTTPException(status_code=400, detail="No code provided")

    validator = get_merge_validator(".")
    is_valid, issues = validator.quick_validate(code)

    return {
        "valid": is_valid,
        "issues": issues,
    }
