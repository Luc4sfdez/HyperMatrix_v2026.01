"""
HyperMatrix v2026 - Batch Actions Routes
Endpoints for batch operations on sibling groups.
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Query

from ..models import BatchAction, BatchActionRequest, BatchActionResult, DryRunResult
from ..app import scan_results, db_manager, rules_config
from ...core.fusion import IntelligentFusion

router = APIRouter()


def calculate_impact(scan_id: str, actions: List[Dict[str, Any]]) -> DryRunResult:
    """Calculate the impact of batch actions without executing."""
    if scan_id not in scan_results:
        raise ValueError("Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise ValueError("No consolidation data")

    files_to_merge = 0
    files_to_delete = 0
    space_to_recover = 0
    affected_files = set()
    warnings = []

    for action_item in actions:
        filename = action_item.get("filename")
        action = action_item.get("action")

        group = consolidation.groups.get(filename)
        if not group:
            warnings.append(f"Group not found: {filename}")
            continue

        proposal = group.master_proposal
        if not proposal:
            warnings.append(f"No master proposal for: {filename}")
            continue

        if action == BatchAction.MERGE.value:
            files_to_merge += len(group.files)
            for f in group.files:
                affected_files.add(f.filepath)

        elif action == BatchAction.KEEP_MASTER.value:
            files_to_delete += len(proposal.siblings)
            for f in proposal.siblings:
                space_to_recover += f.size
                affected_files.add(f.filepath)

        elif action == BatchAction.DELETE_DUPLICATES.value:
            files_to_delete += len(proposal.siblings)
            for f in proposal.siblings:
                space_to_recover += f.size
                affected_files.add(f.filepath)

    # Calculate imports that would need updating
    imports_to_update = 0
    # This would require analyzing which files import the affected files
    # For now, estimate based on affected files count
    imports_to_update = len(affected_files) * 2  # Rough estimate

    return DryRunResult(
        total_groups=len(actions),
        files_to_merge=files_to_merge,
        files_to_delete=files_to_delete,
        space_to_recover_kb=space_to_recover / 1024,
        imports_to_update=imports_to_update,
        affected_files=list(affected_files),
        warnings=warnings,
    )


@router.post("/dry-run/{scan_id}")
async def dry_run_batch(scan_id: str, request: BatchActionRequest):
    """
    Simulate batch actions without making changes.
    Returns detailed impact analysis.
    """
    try:
        impact = calculate_impact(scan_id, request.actions)
        return {
            "dry_run": True,
            "impact": impact.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/execute/{scan_id}")
async def execute_batch(scan_id: str, request: BatchActionRequest):
    """
    Execute batch actions on sibling groups.
    Set dry_run=false to actually make changes.
    """
    if request.dry_run:
        return await dry_run_batch(scan_id, request)

    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    results = []
    backup_dir = Path("hypermatrix_backup")
    backup_dir.mkdir(exist_ok=True)

    for action_item in request.actions:
        filename = action_item.get("filename")
        action = action_item.get("action")

        group = consolidation.groups.get(filename)
        if not group:
            results.append(BatchActionResult(
                action=action,
                filename=filename,
                success=False,
                message="Group not found",
            ))
            continue

        proposal = group.master_proposal
        if not proposal:
            results.append(BatchActionResult(
                action=action,
                filename=filename,
                success=False,
                message="No master proposal",
            ))
            continue

        try:
            if action == BatchAction.MERGE.value:
                # Merge all files into master
                files = [f.filepath for f in group.files]
                fusion = IntelligentFusion()
                fusion.analyze_versions(files)
                merge_result = fusion.fuse(proposal.proposed_master.filepath)

                if merge_result.success:
                    # Backup original
                    master_path = Path(proposal.proposed_master.filepath)
                    backup_path = backup_dir / f"{filename}.backup"
                    shutil.copy2(master_path, backup_path)

                    # Write merged content
                    master_path.write_text(merge_result.fused_code, encoding="utf-8")

                    results.append(BatchActionResult(
                        action=action,
                        filename=filename,
                        success=True,
                        message=f"Merged {len(files)} files",
                        changes=[
                            f"Added {len(merge_result.functions_added)} functions",
                            f"Added {len(merge_result.classes_added)} classes",
                            f"Backup at: {backup_path}",
                        ],
                    ))
                else:
                    results.append(BatchActionResult(
                        action=action,
                        filename=filename,
                        success=False,
                        message=f"Merge failed: {merge_result.warnings}",
                    ))

            elif action == BatchAction.KEEP_MASTER.value:
                # Move non-master files to backup
                changes = []
                for sibling in proposal.siblings:
                    src = Path(sibling.filepath)
                    if src.exists():
                        dst = backup_dir / src.name
                        counter = 1
                        while dst.exists():
                            dst = backup_dir / f"{src.stem}_{counter}{src.suffix}"
                            counter += 1
                        shutil.move(str(src), str(dst))
                        changes.append(f"Moved {src.name} to backup")

                results.append(BatchActionResult(
                    action=action,
                    filename=filename,
                    success=True,
                    message=f"Kept master, moved {len(proposal.siblings)} files",
                    changes=changes,
                ))

            elif action == BatchAction.DELETE_DUPLICATES.value:
                # Delete non-master files (with backup)
                changes = []
                for sibling in proposal.siblings:
                    src = Path(sibling.filepath)
                    if src.exists():
                        dst = backup_dir / f"deleted_{src.name}"
                        shutil.copy2(str(src), str(dst))
                        os.remove(str(src))
                        changes.append(f"Deleted {src.name} (backed up)")

                results.append(BatchActionResult(
                    action=action,
                    filename=filename,
                    success=True,
                    message=f"Deleted {len(proposal.siblings)} duplicates",
                    changes=changes,
                ))

            elif action == BatchAction.IGNORE.value:
                results.append(BatchActionResult(
                    action=action,
                    filename=filename,
                    success=True,
                    message="Ignored",
                ))

        except Exception as e:
            results.append(BatchActionResult(
                action=action,
                filename=filename,
                success=False,
                message=str(e),
            ))

    # Summary
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    return {
        "executed": True,
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "backup_directory": str(backup_dir),
        "results": [r.model_dump() for r in results],
    }


@router.get("/suggestions/{scan_id}")
async def get_batch_suggestions(
    scan_id: str,
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
):
    """
    Get suggested batch actions based on analysis.
    Returns recommended actions for groups with high confidence.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    if not consolidation:
        raise HTTPException(status_code=400, detail="No consolidation data")

    suggestions = []

    for filename, group in consolidation.groups.items():
        proposal = group.master_proposal
        if not proposal or proposal.confidence < min_confidence:
            continue

        # Calculate average affinity
        avg_affinity = 0.0
        if proposal.affinity_matrix:
            avg_affinity = sum(a.overall_affinity for a in proposal.affinity_matrix) / len(proposal.affinity_matrix)

        # Determine suggested action
        if avg_affinity >= 0.95:
            # Nearly identical - suggest keeping master only
            suggested_action = BatchAction.KEEP_MASTER.value
            reason = "Files are nearly identical (>95% affinity)"
        elif avg_affinity >= 0.7:
            # Similar but with differences - suggest merge
            suggested_action = BatchAction.MERGE.value
            reason = f"Files have {avg_affinity:.0%} affinity - merge recommended"
        else:
            # Lower affinity - just inform
            suggested_action = BatchAction.IGNORE.value
            reason = f"Lower affinity ({avg_affinity:.0%}) - review manually"

        # Apply rules if configured
        if rules_config:
            master_path = proposal.proposed_master.filepath.lower()
            for pattern in rules_config.never_master_from:
                if pattern.lower() in master_path:
                    suggested_action = BatchAction.IGNORE.value
                    reason = f"Master in excluded path: {pattern}"
                    break

        suggestions.append({
            "filename": filename,
            "file_count": len(group.files),
            "suggested_action": suggested_action,
            "reason": reason,
            "confidence": proposal.confidence,
            "average_affinity": round(avg_affinity, 4),
            "master": proposal.proposed_master.filepath,
        })

    # Sort by confidence
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "total_suggestions": len(suggestions),
        "min_confidence_used": min_confidence,
        "suggestions": suggestions,
    }
