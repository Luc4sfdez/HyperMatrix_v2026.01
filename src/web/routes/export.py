"""
HyperMatrix v2026 - Export Routes
Endpoints for exporting reports in various formats.
"""

import json
import csv
import io
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse

from ..models import ExportFormat, ExportRequest
from ..app import scan_results, db_manager

router = APIRouter()


def generate_json_report(scan_id: str, include_details: bool = True) -> dict:
    """Generate JSON report."""
    if scan_id not in scan_results:
        raise ValueError("Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    report = {
        "generated_at": datetime.now().isoformat(),
        "scan_id": scan_id,
        "project_name": result.get("project_name"),
        "summary": {
            "total_files": result.get("total_files", 0),
            "analyzed_files": result.get("analyzed_files", 0),
            "duplicate_groups": result.get("duplicate_groups", 0),
            "sibling_groups": result.get("sibling_groups", 0),
        },
    }

    if include_details and consolidation:
        groups_data = []
        for filename, group in consolidation.groups.items():
            proposal = group.master_proposal
            if not proposal:
                continue

            avg_affinity = 0.0
            if proposal.affinity_matrix:
                avg_affinity = sum(a.overall_affinity for a in proposal.affinity_matrix) / len(proposal.affinity_matrix)

            group_data = {
                "filename": filename,
                "file_count": len(group.files),
                "average_affinity": round(avg_affinity, 4),
                "proposed_master": proposal.proposed_master.filepath,
                "confidence": proposal.confidence,
                "files": [
                    {
                        "path": f.filepath,
                        "size": f.size,
                        "functions": f.function_count,
                        "classes": f.class_count,
                    }
                    for f in group.files
                ],
            }

            if include_details:
                group_data["affinity_matrix"] = [
                    {
                        "file1": a.file1,
                        "file2": a.file2,
                        "overall": a.overall_affinity,
                        "content": a.content_similarity,
                        "structure": a.structure_similarity,
                        "dna": a.dna_similarity,
                    }
                    for a in proposal.affinity_matrix
                ]

            groups_data.append(group_data)

        report["sibling_groups"] = groups_data

    return report


def generate_csv_report(scan_id: str) -> str:
    """Generate CSV report."""
    if scan_id not in scan_results:
        raise ValueError("Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Filename",
        "File Count",
        "Average Affinity",
        "Proposed Master",
        "Master Directory",
        "Confidence",
        "All Paths",
    ])

    if consolidation:
        for filename, group in consolidation.groups.items():
            proposal = group.master_proposal
            if not proposal:
                continue

            avg_affinity = 0.0
            if proposal.affinity_matrix:
                avg_affinity = sum(a.overall_affinity for a in proposal.affinity_matrix) / len(proposal.affinity_matrix)

            all_paths = "; ".join(f.filepath for f in group.files)

            writer.writerow([
                filename,
                len(group.files),
                f"{avg_affinity:.4f}",
                proposal.proposed_master.filepath,
                proposal.proposed_master.directory,
                f"{proposal.confidence:.2f}",
                all_paths,
            ])

    return output.getvalue()


def generate_markdown_report(scan_id: str, include_details: bool = True) -> str:
    """Generate Markdown report."""
    if scan_id not in scan_results:
        raise ValueError("Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    lines = []
    lines.append(f"# HyperMatrix Analysis Report")
    lines.append(f"")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Project:** {result.get('project_name', 'Unknown')}")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Files | {result.get('total_files', 0)} |")
    lines.append(f"| Analyzed Files | {result.get('analyzed_files', 0)} |")
    lines.append(f"| Duplicate Groups | {result.get('duplicate_groups', 0)} |")
    lines.append(f"| Sibling Groups | {result.get('sibling_groups', 0)} |")
    lines.append(f"")

    if consolidation:
        lines.append(f"## Sibling Groups")
        lines.append(f"")

        # Sort by average affinity
        sorted_groups = []
        for filename, group in consolidation.groups.items():
            proposal = group.master_proposal
            if not proposal:
                continue
            avg_affinity = 0.0
            if proposal.affinity_matrix:
                avg_affinity = sum(a.overall_affinity for a in proposal.affinity_matrix) / len(proposal.affinity_matrix)
            sorted_groups.append((filename, group, avg_affinity))

        sorted_groups.sort(key=lambda x: x[2], reverse=True)

        for filename, group, avg_affinity in sorted_groups:
            proposal = group.master_proposal
            lines.append(f"### {filename}")
            lines.append(f"")
            lines.append(f"- **Files:** {len(group.files)}")
            lines.append(f"- **Average Affinity:** {avg_affinity:.1%}")
            lines.append(f"- **Proposed Master:** `{proposal.proposed_master.filepath}`")
            lines.append(f"- **Confidence:** {proposal.confidence:.0%}")
            lines.append(f"")

            if include_details:
                lines.append(f"**Files:**")
                lines.append(f"")
                for f in group.files:
                    marker = " **(MASTER)**" if f.filepath == proposal.proposed_master.filepath else ""
                    lines.append(f"- `{f.filepath}`{marker}")
                    lines.append(f"  - Size: {f.size:,} bytes")
                    lines.append(f"  - Functions: {f.function_count}, Classes: {f.class_count}")
                lines.append(f"")

    lines.append(f"---")
    lines.append(f"*Generated by HyperMatrix v2026*")

    return "\n".join(lines)


@router.get("/{scan_id}/json")
async def export_json(
    scan_id: str,
    include_details: bool = Query(True, description="Include detailed affinity data"),
):
    """Export report as JSON."""
    try:
        report = generate_json_report(scan_id, include_details)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{scan_id}/csv")
async def export_csv(scan_id: str):
    """Export report as CSV."""
    try:
        csv_content = generate_csv_report(scan_id)
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=hypermatrix_report_{scan_id}.csv"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{scan_id}/markdown")
async def export_markdown(
    scan_id: str,
    include_details: bool = Query(True),
):
    """Export report as Markdown."""
    try:
        md_content = generate_markdown_report(scan_id, include_details)
        return StreamingResponse(
            io.StringIO(md_content),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=hypermatrix_report_{scan_id}.md"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{scan_id}/download")
async def download_report(
    scan_id: str,
    format: ExportFormat = Query(ExportFormat.JSON),
    include_details: bool = Query(True),
):
    """Download report in specified format."""
    try:
        if format == ExportFormat.JSON:
            content = json.dumps(generate_json_report(scan_id, include_details), indent=2)
            media_type = "application/json"
            ext = "json"
        elif format == ExportFormat.CSV:
            content = generate_csv_report(scan_id)
            media_type = "text/csv"
            ext = "csv"
        elif format == ExportFormat.MARKDOWN:
            content = generate_markdown_report(scan_id, include_details)
            media_type = "text/markdown"
            ext = "md"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

        filename = f"hypermatrix_report_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        return StreamingResponse(
            io.StringIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/formats")
async def list_formats():
    """List available export formats."""
    return {
        "formats": [
            {"id": "json", "name": "JSON", "description": "Full data export in JSON format"},
            {"id": "csv", "name": "CSV", "description": "Spreadsheet-compatible format"},
            {"id": "markdown", "name": "Markdown", "description": "Documentation-friendly format"},
        ]
    }
