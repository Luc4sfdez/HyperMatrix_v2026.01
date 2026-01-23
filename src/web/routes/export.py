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
            {"id": "html", "name": "HTML", "description": "Standalone HTML report with styling"},
        ]
    }


def generate_html_report(scan_id: str, include_details: bool = True) -> str:
    """Generate a standalone HTML report with embedded CSS."""
    if scan_id not in scan_results:
        raise ValueError("Scan results not found")

    result = scan_results[scan_id]
    consolidation = result.get("consolidation")

    # Try to get metrics if available
    metrics_data = None
    try:
        from ...core.code_metrics import analyze_project_metrics
        project_path = result.get("root_path") or result.get("discovery", {}).get("root_path")
        if project_path:
            metrics = analyze_project_metrics(project_path, max_files=200)
            metrics_data = {
                "total_files": metrics.total_files,
                "total_lines": metrics.total_lines,
                "avg_complexity": metrics.avg_complexity,
                "doc_coverage": metrics.doc_coverage,
                "tech_debt": metrics.tech_debt_score,
                "hotspots": metrics.hotspots[:5],
            }
    except Exception:
        pass

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HyperMatrix Report - {result.get('project_name', 'Unknown')}</title>
    <style>
        :root {{
            --primary: #6366f1;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
            --bg: #0f172a;
            --bg-secondary: #1e293b;
            --fg: #f8fafc;
            --fg-secondary: #94a3b8;
            --border: #334155;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--fg);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: var(--primary); margin-bottom: 0.5rem; }}
        h2 {{ color: var(--fg); margin: 2rem 0 1rem; border-bottom: 2px solid var(--border); padding-bottom: 0.5rem; }}
        h3 {{ color: var(--fg-secondary); margin: 1.5rem 0 0.75rem; }}
        .meta {{ color: var(--fg-secondary); font-size: 0.9rem; margin-bottom: 2rem; }}
        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        .stat {{
            text-align: center;
            padding: 1rem;
            background: var(--bg);
            border-radius: 8px;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: var(--primary); }}
        .stat-label {{ color: var(--fg-secondary); font-size: 0.85rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--fg-secondary); font-weight: 600; }}
        code {{
            background: var(--bg);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'Fira Code', 'Monaco', monospace;
            font-size: 0.85rem;
        }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-success {{ background: var(--success); color: #000; }}
        .badge-warning {{ background: var(--warning); color: #000; }}
        .badge-error {{ background: var(--error); color: #fff; }}
        .progress {{
            height: 8px;
            background: var(--bg);
            border-radius: 4px;
            overflow: hidden;
        }}
        .progress-bar {{
            height: 100%;
            background: var(--primary);
            transition: width 0.3s;
        }}
        footer {{
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--fg-secondary);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>HyperMatrix Analysis Report</h1>
        <p class="meta">
            <strong>Project:</strong> {result.get('project_name', 'Unknown')} |
            <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
            <strong>Scan ID:</strong> {scan_id}
        </p>

        <h2>Summary</h2>
        <div class="grid">
            <div class="stat">
                <div class="stat-value">{result.get('total_files', 0):,}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat">
                <div class="stat-value">{result.get('analyzed_files', 0):,}</div>
                <div class="stat-label">Analyzed</div>
            </div>
            <div class="stat">
                <div class="stat-value">{result.get('duplicate_groups', 0)}</div>
                <div class="stat-label">Duplicates</div>
            </div>
            <div class="stat">
                <div class="stat-value">{result.get('sibling_groups', 0)}</div>
                <div class="stat-label">Sibling Groups</div>
            </div>
        </div>
"""

    # Add metrics section if available
    if metrics_data:
        debt_color = "success" if metrics_data["tech_debt"] < 30 else "warning" if metrics_data["tech_debt"] < 60 else "error"
        html += f"""
        <h2>Code Quality Metrics</h2>
        <div class="card">
            <div class="grid">
                <div class="stat">
                    <div class="stat-value">{metrics_data['total_lines']:,}</div>
                    <div class="stat-label">Lines of Code</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics_data['avg_complexity']:.1f}</div>
                    <div class="stat-label">Avg Complexity</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics_data['doc_coverage']*100:.0f}%</div>
                    <div class="stat-label">Doc Coverage</div>
                </div>
                <div class="stat">
                    <div class="stat-value"><span class="badge badge-{debt_color}">{metrics_data['tech_debt']:.0f}</span></div>
                    <div class="stat-label">Tech Debt Score</div>
                </div>
            </div>
        </div>
"""

        if metrics_data["hotspots"]:
            html += """
            <h3>Complexity Hotspots</h3>
            <table>
                <tr><th>File</th><th>Complexity</th><th>Functions</th><th>Debt</th></tr>
"""
            for hs in metrics_data["hotspots"]:
                filepath = hs.get("filepath", "")
                if len(filepath) > 60:
                    filepath = "..." + filepath[-57:]
                html += f"""
                <tr>
                    <td><code>{filepath}</code></td>
                    <td>{hs.get('max_complexity', 0)}</td>
                    <td>{hs.get('functions', 0)}</td>
                    <td>{hs.get('tech_debt', 0):.1f}</td>
                </tr>
"""
            html += "</table>"

    # Sibling groups section
    if consolidation and include_details:
        html += """
        <h2>Sibling Groups</h2>
"""
        sorted_groups = []
        for filename, group in consolidation.groups.items():
            proposal = group.master_proposal
            if not proposal:
                continue
            avg_affinity = 0.0
            if proposal.affinity_matrix:
                avg_affinity = sum(a.overall_affinity for a in proposal.affinity_matrix) / len(proposal.affinity_matrix)
            sorted_groups.append((filename, group, avg_affinity, proposal))

        sorted_groups.sort(key=lambda x: x[2], reverse=True)

        for filename, group, avg_affinity, proposal in sorted_groups[:20]:
            confidence_class = "success" if proposal.confidence > 0.7 else "warning" if proposal.confidence > 0.4 else "error"
            html += f"""
        <div class="card">
            <h3>{filename}</h3>
            <p>
                <strong>Files:</strong> {len(group.files)} |
                <strong>Affinity:</strong> {avg_affinity:.1%} |
                <strong>Confidence:</strong> <span class="badge badge-{confidence_class}">{proposal.confidence:.0%}</span>
            </p>
            <p><strong>Proposed Master:</strong> <code>{proposal.proposed_master.filepath}</code></p>
            <details>
                <summary style="cursor:pointer; color:var(--primary);">View all files</summary>
                <ul style="margin-top:0.5rem;">
"""
            for f in group.files:
                is_master = " (MASTER)" if f.filepath == proposal.proposed_master.filepath else ""
                html += f'                    <li><code>{f.filepath}</code>{is_master}</li>\n'
            html += """
                </ul>
            </details>
        </div>
"""

    html += f"""
        <footer>
            Generated by HyperMatrix v2026 | {datetime.now().year}
        </footer>
    </div>
</body>
</html>
"""
    return html


@router.get("/{scan_id}/html")
async def export_html(
    scan_id: str,
    include_details: bool = Query(True),
):
    """Export report as standalone HTML."""
    try:
        html_content = generate_html_report(scan_id, include_details)
        return StreamingResponse(
            io.StringIO(html_content),
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename=hypermatrix_report_{scan_id}.html"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
