"""
HyperMatrix v2026 - HTML Report Generator
Generates comprehensive HTML analysis reports.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.db_manager import DBManager
from .graph_generator import GraphGenerator, GraphFormat


class HTMLReportGenerator:
    """Generate HTML reports for code analysis."""

    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    def generate_project_report(
        self,
        project_id: int,
        output_path: str,
        include_graph: bool = True,
    ) -> str:
        """Generate comprehensive HTML report for a project."""
        # Get project info
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        stats = self.db.get_statistics(project_id)

        # Get detailed data
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Files by type
            cursor.execute("""
                SELECT file_type, COUNT(*) as count
                FROM files WHERE project_id = ?
                GROUP BY file_type ORDER BY count DESC
            """, (project_id,))
            files_by_type = {row["file_type"]: row["count"] for row in cursor.fetchall()}

            # Top functions
            cursor.execute("""
                SELECT f.name, f.lineno, fi.filepath, f.is_async, f.docstring
                FROM functions f
                JOIN files fi ON f.file_id = fi.id
                WHERE fi.project_id = ?
                ORDER BY f.name LIMIT 50
            """, (project_id,))
            functions = [dict(row) for row in cursor.fetchall()]

            # Top classes
            cursor.execute("""
                SELECT c.name, c.lineno, fi.filepath, c.bases, c.methods, c.docstring
                FROM classes c
                JOIN files fi ON c.file_id = fi.id
                WHERE fi.project_id = ?
                ORDER BY c.name LIMIT 50
            """, (project_id,))
            classes = [dict(row) for row in cursor.fetchall()]

            # Top imports
            cursor.execute("""
                SELECT module, COUNT(*) as count
                FROM imports i
                JOIN files fi ON i.file_id = fi.id
                WHERE fi.project_id = ?
                GROUP BY module ORDER BY count DESC LIMIT 20
            """, (project_id,))
            top_imports = [dict(row) for row in cursor.fetchall()]

        # Generate graph data
        graph_json = ""
        if include_graph:
            try:
                graph_gen = GraphGenerator(project["root_path"])
                graph_gen.build_from_database(self.db, project_id)
                graph_json = graph_gen.to_json()
            except Exception:
                graph_json = '{"nodes": [], "links": []}'

        # Build HTML
        html = self._build_html(
            project=project,
            stats=stats,
            files_by_type=files_by_type,
            functions=functions,
            classes=classes,
            top_imports=top_imports,
            graph_json=graph_json,
        )

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path

    def _build_html(
        self,
        project: dict,
        stats: dict,
        files_by_type: dict,
        functions: list,
        classes: list,
        top_imports: list,
        graph_json: str,
    ) -> str:
        """Build the HTML content."""
        # Parse classes JSON fields
        for cls in classes:
            if cls.get("bases"):
                try:
                    cls["bases"] = json.loads(cls["bases"])
                except:
                    cls["bases"] = []
            if cls.get("methods"):
                try:
                    cls["methods"] = json.loads(cls["methods"])
                except:
                    cls["methods"] = []

        # Build table rows before the template to avoid nested f-strings
        function_rows = ""
        for f in functions[:30]:
            async_badge = "async" if f.get("is_async") else "sync"
            function_rows += f'''
                        <tr>
                            <td><code>{f["name"]}</code></td>
                            <td class="filepath">{Path(f["filepath"]).name}</td>
                            <td>{f["lineno"]}</td>
                            <td><span class="badge">{async_badge}</span></td>
                        </tr>'''

        class_rows = ""
        for c in classes[:30]:
            bases = ", ".join(c.get("bases", []) or []) or "-"
            methods_count = len(c.get("methods", []) or [])
            class_rows += f'''
                        <tr>
                            <td><code>{c["name"]}</code></td>
                            <td class="filepath">{Path(c["filepath"]).name}</td>
                            <td>{bases}</td>
                            <td>{methods_count}</td>
                        </tr>'''

        import_rows = ""
        for i in top_imports:
            import_rows += f'''
                        <tr>
                            <td><code>{i["module"]}</code></td>
                            <td>{i["count"]}</td>
                        </tr>'''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HyperMatrix Report - {project["name"]}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eaeaea;
            --text-secondary: #a0a0a0;
            --accent: #e94560;
            --accent-secondary: #0f4c75;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        header {{
            background: var(--bg-secondary);
            padding: 30px 0;
            margin-bottom: 30px;
            border-bottom: 3px solid var(--accent);
        }}
        header h1 {{ font-size: 2.5rem; margin-bottom: 10px; }}
        header .subtitle {{ color: var(--text-secondary); }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .card h3 {{
            color: var(--accent);
            margin-bottom: 15px;
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .stat-value {{ font-size: 2.5rem; font-weight: bold; }}
        .stat-label {{ color: var(--text-secondary); font-size: 0.9rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--bg-secondary); }}
        th {{ color: var(--accent); font-weight: 600; }}
        tr:hover {{ background: var(--bg-secondary); }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            background: var(--accent-secondary);
        }}
        .section {{ margin-bottom: 40px; }}
        .section-title {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--accent);
        }}
        #graph-container {{
            width: 100%;
            height: 500px;
            background: var(--bg-secondary);
            border-radius: 12px;
        }}
        .chart-container {{ height: 300px; }}
        code {{
            background: var(--bg-secondary);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Fira Code', monospace;
        }}
        .filepath {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>HyperMatrix Analysis Report</h1>
            <p class="subtitle">
                Project: <strong>{project["name"]}</strong> |
                Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
            </p>
        </div>
    </header>

    <div class="container">
        <!-- Stats Overview -->
        <div class="grid">
            <div class="card">
                <h3>Total Files</h3>
                <div class="stat-value">{stats.get("total_files", 0)}</div>
                <div class="stat-label">analyzed files</div>
            </div>
            <div class="card">
                <h3>Functions</h3>
                <div class="stat-value">{stats.get("total_functions", 0)}</div>
                <div class="stat-label">extracted</div>
            </div>
            <div class="card">
                <h3>Classes</h3>
                <div class="stat-value">{stats.get("total_classes", 0)}</div>
                <div class="stat-label">detected</div>
            </div>
            <div class="card">
                <h3>Imports</h3>
                <div class="stat-value">{stats.get("total_imports", 0)}</div>
                <div class="stat-label">dependencies</div>
            </div>
        </div>

        <!-- Files by Type Chart -->
        <div class="section">
            <h2 class="section-title">Files by Type</h2>
            <div class="card">
                <div class="chart-container">
                    <canvas id="filesChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Dependency Graph -->
        <div class="section">
            <h2 class="section-title">Dependency Graph</h2>
            <div class="card">
                <div id="graph-container"></div>
            </div>
        </div>

        <!-- Functions Table -->
        <div class="section">
            <h2 class="section-title">Functions ({len(functions)})</h2>
            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>File</th>
                            <th>Line</th>
                            <th>Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {function_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Classes Table -->
        <div class="section">
            <h2 class="section-title">Classes ({len(classes)})</h2>
            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>File</th>
                            <th>Bases</th>
                            <th>Methods</th>
                        </tr>
                    </thead>
                    <tbody>
                        {class_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Top Imports -->
        <div class="section">
            <h2 class="section-title">Top Imports</h2>
            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Module</th>
                            <th>Usage Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        {import_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Files by type chart
        const filesData = {json.dumps(files_by_type)};
        new Chart(document.getElementById('filesChart'), {{
            type: 'doughnut',
            data: {{
                labels: Object.keys(filesData),
                datasets: [{{
                    data: Object.values(filesData),
                    backgroundColor: ['#e94560', '#0f4c75', '#3282b8', '#bbe1fa', '#1b262c', '#0f3460'],
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right',
                        labels: {{ color: '#eaeaea' }}
                    }}
                }}
            }}
        }});

        // D3 Force Graph
        const graphData = {graph_json};
        if (graphData.nodes && graphData.nodes.length > 0) {{
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = 500;

            const svg = d3.select('#graph-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);

            const simulation = d3.forceSimulation(graphData.nodes)
                .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2));

            const link = svg.append('g')
                .selectAll('line')
                .data(graphData.links)
                .join('line')
                .attr('stroke', '#444')
                .attr('stroke-width', 1);

            const node = svg.append('g')
                .selectAll('circle')
                .data(graphData.nodes)
                .join('circle')
                .attr('r', 8)
                .attr('fill', d => d.color || '#e94560')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            node.append('title').text(d => d.label);

            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);
            }});

            function dragstarted(event) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }}

            function dragged(event) {{
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }}

            function dragended(event) {{
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }}
        }}
    </script>
</body>
</html>'''

    def generate_summary_report(
        self,
        project_ids: list[int],
        output_path: str,
    ) -> str:
        """Generate summary report for multiple projects."""
        projects_data = []

        for pid in project_ids:
            project = self.db.get_project(pid)
            if project:
                stats = self.db.get_statistics(pid)
                projects_data.append({
                    "project": project,
                    "stats": stats,
                })

        html = self._build_summary_html(projects_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path

    def _build_summary_html(self, projects_data: list) -> str:
        """Build summary HTML for multiple projects."""
        rows = ""
        for pd in projects_data:
            p = pd["project"]
            s = pd["stats"]
            rows += f'''
            <tr>
                <td>{p["name"]}</td>
                <td>{s.get("total_files", 0)}</td>
                <td>{s.get("total_functions", 0)}</td>
                <td>{s.get("total_classes", 0)}</td>
                <td>{s.get("total_imports", 0)}</td>
            </tr>'''

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>HyperMatrix Summary Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #1a1a2e; color: #eaeaea; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #e94560; }}
        h1 {{ color: #e94560; }}
    </style>
</head>
<body>
    <h1>HyperMatrix Summary Report</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    <table>
        <tr>
            <th>Project</th>
            <th>Files</th>
            <th>Functions</th>
            <th>Classes</th>
            <th>Imports</th>
        </tr>
        {rows}
    </table>
</body>
</html>'''
