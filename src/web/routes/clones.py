"""
HyperMatrix v2026 - Clone Detection Routes
Endpoints for fragment detection and semantic similarity analysis.
"""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ...core.clone_detector import CloneDetector
from ...core.semantic_analyzer import SemanticAnalyzer
from ..app import scan_results

router = APIRouter()


# Lazy initialization
_clone_detector: Optional[CloneDetector] = None
_semantic_analyzer: Optional[SemanticAnalyzer] = None


def get_clone_detector() -> CloneDetector:
    global _clone_detector
    if _clone_detector is None:
        _clone_detector = CloneDetector()
    return _clone_detector


def get_semantic_analyzer() -> SemanticAnalyzer:
    global _semantic_analyzer
    if _semantic_analyzer is None:
        _semantic_analyzer = SemanticAnalyzer()
    return _semantic_analyzer


# ============ CLONE DETECTION (C.3) ============

@router.post("/detect")
async def detect_clones(
    files: List[str] = Query(..., description="List of files to analyze"),
    min_lines: int = Query(5, ge=3, le=100),
    similarity_threshold: float = Query(0.7, ge=0.5, le=1.0),
):
    """
    Detect code clones (duplicated fragments) across files.

    Clone Types:
    - Type 1: Exact clones
    - Type 2: Renamed clones (variables renamed)
    - Type 3: Modified clones (statements added/removed)
    """
    # Validate files
    valid_files = []
    for f in files:
        if Path(f).exists() and f.endswith(".py"):
            valid_files.append(f)

    if len(valid_files) < 1:
        raise HTTPException(status_code=400, detail="No valid Python files provided")

    detector = CloneDetector(
        min_lines=min_lines,
        similarity_threshold=similarity_threshold
    )
    report = detector.detect_clones(valid_files)

    return {
        "total_fragments": report.total_fragments,
        "clone_summary": report.summary,
        "duplicated_lines": report.duplicated_lines,
        "duplication_ratio": round(report.duplication_ratio, 4),
        "clone_pairs": [
            {
                "fragment1": {
                    "file": cp.fragment1.filepath,
                    "name": cp.fragment1.name,
                    "type": cp.fragment1.fragment_type,
                    "lines": f"{cp.fragment1.start_line}-{cp.fragment1.end_line}",
                },
                "fragment2": {
                    "file": cp.fragment2.filepath,
                    "name": cp.fragment2.name,
                    "type": cp.fragment2.fragment_type,
                    "lines": f"{cp.fragment2.start_line}-{cp.fragment2.end_line}",
                },
                "clone_type": cp.clone_type,
                "similarity": round(cp.similarity, 4),
            }
            for cp in report.clone_pairs[:100]  # Limit to first 100
        ],
        "clone_groups": [
            {
                "representative": {
                    "file": g.representative.filepath,
                    "name": g.representative.name,
                },
                "clone_count": len(g.clones) + 1,
                "clone_type": g.clone_type,
                "group_similarity": round(g.group_similarity, 4),
                "total_lines": g.total_lines,
                "files_involved": g.files_involved,
            }
            for g in report.clone_groups
        ],
    }


@router.get("/detect/{scan_id}")
async def detect_clones_in_scan(
    scan_id: str,
    min_lines: int = Query(5, ge=3, le=100),
):
    """
    Detect clones in files from a completed scan.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    # Collect all files from sibling groups
    all_files = set()
    for group in consolidation.groups.values():
        for f in group.files:
            if f.filepath.endswith(".py"):
                all_files.add(f.filepath)

    if not all_files:
        raise HTTPException(status_code=400, detail="No Python files in scan results")

    detector = CloneDetector(min_lines=min_lines)
    report = detector.detect_clones(list(all_files))

    return {
        "scan_id": scan_id,
        "files_analyzed": len(all_files),
        "clone_summary": report.summary,
        "duplication_ratio": round(report.duplication_ratio, 4),
        "clone_groups_count": len(report.clone_groups),
    }


@router.post("/suggestions")
async def get_deduplication_suggestions(
    files: List[str] = Query(...),
):
    """
    Get suggestions for deduplicating code based on clone detection.
    """
    valid_files = [f for f in files if Path(f).exists() and f.endswith(".py")]

    if len(valid_files) < 1:
        raise HTTPException(status_code=400, detail="No valid files")

    detector = get_clone_detector()
    report = detector.detect_clones(valid_files)
    suggestions = detector.suggest_deduplication(report)

    return {
        "total_suggestions": len(suggestions),
        "suggestions": suggestions[:20],  # Top 20
    }


@router.get("/file/{filepath:path}")
async def find_clones_of_file(
    filepath: str,
    search_in: List[str] = Query(None, description="Files to search in"),
):
    """
    Find clones of code from a specific file.
    """
    if not Path(filepath).exists():
        raise HTTPException(status_code=404, detail="File not found")

    # If no search paths provided, use parent directory
    if not search_in:
        parent = Path(filepath).parent
        search_in = [str(f) for f in parent.rglob("*.py") if str(f) != filepath]

    valid_search = [f for f in search_in if Path(f).exists() and f != filepath]

    if not valid_search:
        return {"clones": [], "message": "No files to search"}

    detector = get_clone_detector()
    clones = detector.find_clones_in_file(filepath, valid_search)

    return {
        "target_file": filepath,
        "searched_files": len(valid_search),
        "clones_found": len(clones),
        "clones": [
            {
                "fragment1": {
                    "file": cp.fragment1.filepath,
                    "name": cp.fragment1.name,
                    "lines": f"{cp.fragment1.start_line}-{cp.fragment1.end_line}",
                },
                "fragment2": {
                    "file": cp.fragment2.filepath,
                    "name": cp.fragment2.name,
                    "lines": f"{cp.fragment2.start_line}-{cp.fragment2.end_line}",
                },
                "clone_type": cp.clone_type,
                "similarity": round(cp.similarity, 4),
            }
            for cp in clones
        ],
    }


# ============ SEMANTIC SIMILARITY (C.1) ============

@router.post("/semantic")
async def analyze_semantic_similarity(
    files: List[str] = Query(...),
    threshold: float = Query(0.5, ge=0.3, le=1.0),
):
    """
    Analyze semantic similarity between code elements.

    Finds functions/classes that do the same thing even with different names.
    """
    valid_files = [f for f in files if Path(f).exists() and f.endswith(".py")]

    if len(valid_files) < 1:
        raise HTTPException(status_code=400, detail="No valid files")

    analyzer = get_semantic_analyzer()
    report = analyzer.analyze_files(valid_files)

    # Filter by threshold
    filtered_matches = [
        m for m in report.semantic_matches
        if m.overall_similarity >= threshold
    ]

    return {
        "total_elements": report.total_elements,
        "summary": report.summary,
        "semantic_matches": [
            {
                "element1": {
                    "file": m.element1.filepath,
                    "name": m.element1.name,
                    "type": m.element1.element_type,
                },
                "element2": {
                    "file": m.element2.filepath,
                    "name": m.element2.name,
                    "type": m.element2.element_type,
                },
                "semantic_similarity": m.semantic_similarity,
                "structural_similarity": m.structural_similarity,
                "behavioral_similarity": m.behavioral_similarity,
                "match_type": m.match_type,
                "evidence": m.evidence,
            }
            for m in filtered_matches[:50]
        ],
        "semantic_groups": report.semantic_groups,
    }


@router.get("/semantic/{scan_id}")
async def analyze_semantic_in_scan(scan_id: str):
    """
    Analyze semantic similarity in files from a completed scan.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    # Collect all Python files
    all_files = set()
    for group in consolidation.groups.values():
        for f in group.files:
            if f.filepath.endswith(".py"):
                all_files.add(f.filepath)

    if not all_files:
        raise HTTPException(status_code=400, detail="No Python files")

    analyzer = get_semantic_analyzer()
    report = analyzer.analyze_files(list(all_files))

    return {
        "scan_id": scan_id,
        "files_analyzed": len(all_files),
        "summary": report.summary,
        "cross_file_matches": len(report.cross_file_matches),
        "semantic_groups_count": len(report.semantic_groups),
    }


@router.post("/semantic/duplicates")
async def find_semantic_duplicates(
    target_file: str = Query(...),
    search_in: List[str] = Query(...),
    threshold: float = Query(0.7, ge=0.5, le=1.0),
):
    """
    Find semantic duplicates of functions from one file in others.

    This is the key feature for detecting "same function, different name".
    """
    if not Path(target_file).exists():
        raise HTTPException(status_code=404, detail="Target file not found")

    valid_search = [f for f in search_in if Path(f).exists() and f != target_file]

    if not valid_search:
        raise HTTPException(status_code=400, detail="No valid search files")

    analyzer = get_semantic_analyzer()
    duplicates = analyzer.find_semantic_duplicates(target_file, valid_search, threshold)

    return {
        "target_file": target_file,
        "searched_files": len(valid_search),
        "duplicates_found": len(duplicates),
        "duplicates": [
            {
                "source": {
                    "file": d.element1.filepath if d.element1.filepath == target_file else d.element2.filepath,
                    "name": d.element1.name if d.element1.filepath == target_file else d.element2.name,
                },
                "duplicate": {
                    "file": d.element2.filepath if d.element1.filepath == target_file else d.element1.filepath,
                    "name": d.element2.name if d.element1.filepath == target_file else d.element1.name,
                },
                "similarity": d.overall_similarity,
                "match_type": d.match_type,
                "evidence": d.evidence,
            }
            for d in duplicates
        ],
    }


@router.get("/semantic/group/{scan_id}/{filename}")
async def get_semantic_group_analysis(scan_id: str, filename: str):
    """
    Analyze semantic similarity within a sibling group.

    Helps identify if files with the same name are semantically equivalent.
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

    files = [f.filepath for f in group.files if f.filepath.endswith(".py")]

    if len(files) < 2:
        return {"message": "Not enough Python files in group for comparison"}

    analyzer = get_semantic_analyzer()
    report = analyzer.analyze_files(files)

    return {
        "filename": filename,
        "files_analyzed": len(files),
        "summary": report.summary,
        "semantic_matches": [
            {
                "element1": {"file": m.element1.filepath, "name": m.element1.name},
                "element2": {"file": m.element2.filepath, "name": m.element2.name},
                "similarity": m.overall_similarity,
                "match_type": m.match_type,
                "evidence": m.evidence,
            }
            for m in report.semantic_matches
        ],
        "semantic_groups": report.semantic_groups,
    }
