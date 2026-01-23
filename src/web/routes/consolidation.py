"""
HyperMatrix v2026 - Consolidation Routes
Endpoints for viewing siblings, affinity, and merge operations.
"""

from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from ..models import SiblingGroupResponse, AffinityResponse, MergePreview
from .. import app as web_app  # Import module to access globals dynamically
from ..app import scan_results, rules_config
from ...core.consolidation import ConsolidationEngine, AffinityLevel
from ...core.fusion import IntelligentFusion, ConflictResolution

router = APIRouter()


@router.get("/siblings/{scan_id}")
async def get_sibling_groups(
    scan_id: str,
    min_affinity: float = Query(0.0, ge=0.0, le=1.0, description="Minimum affinity filter"),
    file_type: Optional[str] = Query(None, description="Filter by file extension"),
    search: Optional[str] = Query(None, description="Search by filename"),
    sort_by: str = Query("affinity", description="Sort by: affinity, files, name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get sibling groups from a completed scan."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    # Return empty data if no consolidation available (not an error)
    if not consolidation or not hasattr(consolidation, "groups"):
        return {
            "groups": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "message": "No sibling groups found (scan may not have detected duplicates)"
        }

    groups = []
    for filename, group in consolidation.groups.items():
        # Apply filters
        if file_type and not filename.endswith(file_type):
            continue
        if search and search.lower() not in filename.lower():
            continue

        proposal = group.master_proposal
        if not proposal:
            continue

        # Calculate average affinity
        avg_affinity = 0.0
        if proposal.affinity_matrix:
            avg_affinity = sum(a.overall_affinity for a in proposal.affinity_matrix) / len(proposal.affinity_matrix)

        if avg_affinity < min_affinity:
            continue

        groups.append({
            "filename": filename,
            "file_count": len(group.files),
            "average_affinity": round(avg_affinity, 4),
            "proposed_master": proposal.proposed_master.filepath,
            "master_directory": proposal.proposed_master.directory,
            "master_confidence": proposal.confidence,
            "reasons": proposal.reasons,
            "files": [
                {
                    "filepath": f.filepath,
                    "directory": f.directory,
                    "size": f.size,
                    "function_count": f.function_count,
                    "class_count": f.class_count,
                    "complexity": f.complexity,
                    "is_master": f.filepath == proposal.proposed_master.filepath,
                }
                for f in group.files
            ],
        })

    # Sort
    if sort_by == "affinity":
        groups.sort(key=lambda x: x["average_affinity"], reverse=True)
    elif sort_by == "files":
        groups.sort(key=lambda x: x["file_count"], reverse=True)
    elif sort_by == "name":
        groups.sort(key=lambda x: x["filename"])

    # Paginate
    total = len(groups)
    groups = groups[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "groups": groups,
    }


@router.get("/siblings/{scan_id}/{filename}")
async def get_sibling_group_detail(scan_id: str, filename: str):
    """Get detailed info for a specific sibling group."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    group = consolidation.groups.get(filename)
    if not group:
        raise HTTPException(status_code=404, detail=f"Sibling group not found: {filename}")

    proposal = group.master_proposal
    if not proposal:
        raise HTTPException(status_code=400, detail="No master proposal for this group")

    # Build affinity matrix for display
    affinity_data = []
    for aff in proposal.affinity_matrix:
        affinity_data.append({
            "file1": Path(aff.file1).name,
            "file1_path": aff.file1,
            "file2": Path(aff.file2).name,
            "file2_path": aff.file2,
            "overall": aff.overall_affinity,
            "level": aff.level.value,
            "content": aff.content_similarity,
            "structure": aff.structure_similarity,
            "dna": aff.dna_similarity,
            "hash_match": aff.hash_match,
        })

    return {
        "filename": filename,
        "files": [
            {
                "filepath": f.filepath,
                "directory": f.directory,
                "size": f.size,
                "hash": f.hash_sha256,
                "function_count": f.function_count,
                "class_count": f.class_count,
                "complexity": f.complexity,
                "is_master": f.filepath == proposal.proposed_master.filepath,
            }
            for f in group.files
        ],
        "master": {
            "filepath": proposal.proposed_master.filepath,
            "confidence": proposal.confidence,
            "reasons": proposal.reasons,
        },
        "affinity_matrix": affinity_data,
    }


@router.get("/compare")
async def compare_files(
    file1: str = Query(..., description="First file path"),
    file2: str = Query(..., description="Second file path"),
):
    """Compare two files and return affinity."""
    path1 = Path(file1)
    path2 = Path(file2)

    if not path1.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file1}")
    if not path2.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file2}")

    # Create sibling objects for comparison
    from ...core.consolidation import SiblingFile
    import hashlib

    def make_sibling(path: Path) -> SiblingFile:
        content = path.read_bytes()
        return SiblingFile(
            filepath=str(path),
            filename=path.name,
            directory=str(path.parent),
            size=len(content),
            hash_sha256=hashlib.sha256(content).hexdigest(),
        )

    s1 = make_sibling(path1)
    s2 = make_sibling(path2)

    engine = ConsolidationEngine()
    affinity = engine.calculate_affinity(s1, s2)

    # Read file contents for diff
    try:
        content1 = path1.read_text(encoding="utf-8", errors="ignore")
        content2 = path2.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        content1, content2 = "", ""

    return {
        "file1": file1,
        "file2": file2,
        "affinity": {
            "overall": affinity.overall_affinity,
            "level": affinity.level.value,
            "content": affinity.content_similarity,
            "structure": affinity.structure_similarity,
            "dna": affinity.dna_similarity,
            "hash_match": affinity.hash_match,
        },
        "file1_lines": len(content1.splitlines()),
        "file2_lines": len(content2.splitlines()),
    }


@router.post("/merge/preview")
async def preview_merge(
    files: List[str] = Query(..., description="Files to merge"),
    base_file: Optional[str] = Query(None, description="Base file (auto-select if not provided)"),
):
    """Preview a merge operation without executing."""
    # Validate files
    valid_files = []
    for f in files:
        p = Path(f)
        if p.exists() and p.suffix == ".py":
            valid_files.append(f)

    if len(valid_files) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 valid Python files")

    # Analyze versions
    fusion = IntelligentFusion()
    fusion.analyze_versions(valid_files)

    # Find unique elements
    unique = fusion.find_unique_elements()

    # Detect conflicts
    conflicts = fusion.detect_conflicts()

    # Select base
    if base_file and base_file in valid_files:
        selected_base = base_file
    else:
        selected_base = fusion.select_base_version()

    base_analysis = fusion.versions[selected_base]

    # Preview fused code
    result = fusion.fuse(selected_base)

    return {
        "base_file": selected_base,
        "files_to_merge": valid_files,
        "unique_functions": unique.get("unique_functions", {}),
        "unique_classes": unique.get("unique_classes", {}),
        "common_functions": list(unique.get("common_functions", {}).keys()),
        "common_classes": list(unique.get("common_classes", {}).keys()),
        "conflicts": [
            {
                "type": c.element_type,
                "name": c.element_name,
                "versions": c.versions,
                "differences": c.differences,
            }
            for c in conflicts
        ],
        "stats": result.stats,
        "preview_lines": len(result.fused_code.splitlines()),
        "preview_code": result.fused_code[:5000] if len(result.fused_code) > 5000 else result.fused_code,
        "truncated": len(result.fused_code) > 5000,
    }


@router.post("/merge/execute")
async def execute_merge(
    files: List[str] = Query(..., description="Files to merge"),
    output_path: str = Query(..., description="Output file path"),
    base_file: Optional[str] = Query(None, description="Base file"),
    conflict_resolution: str = Query("keep_largest", description="Conflict resolution strategy"),
):
    """Execute a merge operation."""
    # Validate
    for f in files:
        if not Path(f).exists():
            raise HTTPException(status_code=404, detail=f"File not found: {f}")

    output = Path(output_path)
    if output.exists():
        raise HTTPException(status_code=400, detail="Output file already exists")

    # Map conflict resolution
    resolution_map = {
        "keep_largest": ConflictResolution.KEEP_LARGEST,
        "keep_complex": ConflictResolution.KEEP_MOST_COMPLEX,
        "keep_newest": ConflictResolution.KEEP_NEWEST,
        "keep_all": ConflictResolution.KEEP_ALL,
        "manual": ConflictResolution.MANUAL,
    }
    resolution = resolution_map.get(conflict_resolution, ConflictResolution.KEEP_LARGEST)

    # Execute fusion
    fusion = IntelligentFusion(conflict_resolution=resolution)
    fusion.analyze_versions(files)
    result = fusion.fuse(base_file)

    if not result.success:
        raise HTTPException(status_code=500, detail=f"Merge failed: {result.warnings}")

    # Write output
    output.write_text(result.fused_code, encoding="utf-8")

    return {
        "success": True,
        "output_path": str(output),
        "stats": result.stats,
        "functions_added": result.functions_added,
        "classes_added": result.classes_added,
        "conflicts_resolved": len(result.conflicts_resolved),
        "conflicts_pending": len(result.conflicts_pending),
    }


@router.get("/cross-project/different")
async def get_different_files_across_projects(
    project_filter: Optional[str] = Query(None, description="Filter by project name pattern (e.g., 'tgd-v')"),
    directory_filter: Optional[str] = Query(None, description="Filter by directory"),
    min_versions: int = Query(2, ge=2, description="Minimum number of different versions"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get files that exist in multiple projects with DIFFERENT hashes.
    Useful for identifying files that need merge/consolidation.
    """
    from collections import defaultdict

    if not web_app.db_manager:
        raise HTTPException(status_code=500, detail="Database not available")

    try:
        with web_app.db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # Get projects matching filter
            if project_filter:
                cursor.execute("""
                    SELECT id, name, root_path FROM projects
                    WHERE name LIKE ?
                    ORDER BY name
                """, (f"%{project_filter}%",))
            else:
                cursor.execute("SELECT id, name, root_path FROM projects ORDER BY name")

            projects = cursor.fetchall()

            if len(projects) < 2:
                return {"error": "Need at least 2 projects to compare", "projects_found": len(projects)}

            # Get all files with hashes
            file_data = {}
            for proj_id, proj_name, proj_path in projects:
                cursor.execute("""
                    SELECT filepath, hash FROM files
                    WHERE project_id = ? AND file_type = 'python' AND hash IS NOT NULL
                """, (proj_id,))

                for fpath, fhash in cursor.fetchall():
                    try:
                        rel = str(Path(fpath).relative_to(proj_path))
                    except:
                        rel = Path(fpath).name

                    if rel not in file_data:
                        file_data[rel] = {}
                    file_data[rel][proj_name] = {'hash': fhash, 'path': fpath}

            # Find files with different hashes
            different_files = []
            for rel_path, project_hashes in sorted(file_data.items()):
                if len(project_hashes) < 2:
                    continue

                # Apply directory filter
                if directory_filter and directory_filter.lower() not in rel_path.lower():
                    continue

                unique_hashes = set(v['hash'] for v in project_hashes.values())
                if len(unique_hashes) >= min_versions:
                    different_files.append({
                        'relative_path': rel_path,
                        'versions': len(unique_hashes),
                        'in_projects': len(project_hashes),
                        'projects': {
                            proj: {
                                'hash': data['hash'][:12] + '...',
                                'full_path': data['path']
                            }
                            for proj, data in project_hashes.items()
                        }
                    })

            # Sort by number of versions (most divergent first)
            different_files.sort(key=lambda x: (-x['versions'], -x['in_projects']))

            total = len(different_files)
            paginated = different_files[offset:offset + limit]

            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "projects_compared": [p[1] for p in projects],
                "files": paginated
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cross-project/diff/{relative_path:path}")
async def get_file_diff_across_projects(
    relative_path: str,
    project_filter: Optional[str] = Query(None, description="Filter by project name pattern"),
):
    """
    Get detailed diff information for a specific file across all projects.
    Shows the actual content differences between versions.
    """
    import difflib

    if not web_app.db_manager:
        raise HTTPException(status_code=500, detail="Database not available")

    try:
        with web_app.db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # Get projects
            if project_filter:
                cursor.execute("""
                    SELECT id, name, root_path FROM projects
                    WHERE name LIKE ?
                    ORDER BY name
                """, (f"%{project_filter}%",))
            else:
                cursor.execute("SELECT id, name, root_path FROM projects ORDER BY name")

            projects = cursor.fetchall()

            # Find matching files - normalize path separators
            versions = []
            # Convert forward slashes to backslashes for Windows paths in DB
            search_path = relative_path.replace('/', '\\')
            for proj_id, proj_name, proj_path in projects:
                cursor.execute("""
                    SELECT filepath, hash FROM files
                    WHERE project_id = ? AND (filepath LIKE ? OR filepath LIKE ?)
                """, (proj_id, f"%{search_path}", f"%{relative_path}"))

                for fpath, fhash in cursor.fetchall():
                    file_path = Path(fpath)
                    if file_path.exists():
                        try:
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            lines = content.splitlines()
                            versions.append({
                                'project': proj_name,
                                'path': fpath,
                                'hash': fhash,
                                'lines': len(lines),
                                'content': content[:10000] if len(content) > 10000 else content,
                                'truncated': len(content) > 10000
                            })
                        except Exception as e:
                            versions.append({
                                'project': proj_name,
                                'path': fpath,
                                'hash': fhash,
                                'error': str(e)
                            })

            if len(versions) < 2:
                return {"error": "File not found in multiple projects", "found_in": len(versions)}

            # Generate unified diff between first two versions
            diff_output = None
            if len(versions) >= 2 and 'content' in versions[0] and 'content' in versions[1]:
                diff = list(difflib.unified_diff(
                    versions[0]['content'].splitlines(keepends=True),
                    versions[1]['content'].splitlines(keepends=True),
                    fromfile=f"{versions[0]['project']}/{relative_path}",
                    tofile=f"{versions[1]['project']}/{relative_path}",
                    lineterm=''
                ))
                diff_output = ''.join(diff[:500])  # Limit diff output

            return {
                "relative_path": relative_path,
                "versions_found": len(versions),
                "unique_hashes": len(set(v.get('hash', '') for v in versions)),
                "versions": versions,
                "diff_sample": diff_output
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
