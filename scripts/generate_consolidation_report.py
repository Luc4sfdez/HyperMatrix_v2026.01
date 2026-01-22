"""
HyperMatrix v2026 - Consolidation Report Generator
Generates a comprehensive HTML report with all consolidation proposals.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def generate_report(db_path: str, output_path: str):
    """Generate comprehensive HTML consolidation report."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get latest project ID
    cursor.execute('SELECT MAX(project_id) FROM consolidation_proposals')
    project_id = cursor.fetchone()[0]

    # Gather all data
    data = gather_data(cursor, project_id)

    # Generate HTML
    html = generate_html(data)

    # Write report
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    conn.close()
    return output_path


def gather_data(cursor, project_id):
    """Gather all consolidation data from database."""

    data = {}

    # Basic stats
    cursor.execute('''
        SELECT
            COUNT(*) as total_groups,
            SUM(sibling_count) as total_siblings,
            AVG(average_affinity) as avg_affinity,
            SUM(CASE WHEN confidence >= 0.9 THEN 1 ELSE 0 END) as high_conf,
            SUM(CASE WHEN average_affinity >= 0.95 THEN sibling_count ELSE 0 END) as identical,
            SUM(CASE WHEN average_affinity >= 0.7 AND average_affinity < 0.95 THEN sibling_count ELSE 0 END) as similar,
            SUM(CASE WHEN average_affinity < 0.7 THEN sibling_count ELSE 0 END) as different
        FROM consolidation_proposals
        WHERE project_id = ?
    ''', (project_id,))
    row = cursor.fetchone()
    data['stats'] = {
        'total_groups': row[0],
        'total_siblings': row[1],
        'avg_affinity': row[2],
        'high_confidence': row[3],
        'identical': row[4] or 0,
        'similar': row[5] or 0,
        'different': row[6] or 0,
    }

    # All proposals
    cursor.execute('''
        SELECT id, filename, master_path, confidence, sibling_count,
               average_affinity, reasons, created_at
        FROM consolidation_proposals
        WHERE project_id = ?
        ORDER BY sibling_count DESC, average_affinity DESC
    ''', (project_id,))
    data['proposals'] = cursor.fetchall()

    # Get siblings for each proposal
    data['siblings'] = {}
    for prop in data['proposals']:
        prop_id = prop[0]
        cursor.execute('''
            SELECT sibling_path, affinity_to_master, affinity_level
            FROM consolidation_siblings
            WHERE proposal_id = ?
            ORDER BY affinity_to_master DESC
        ''', (prop_id,))
        data['siblings'][prop_id] = cursor.fetchall()

    # Categorize proposals
    data['identical_files'] = []  # >95% affinity
    data['similar_files'] = []    # 70-95% affinity
    data['divergent_files'] = []  # <70% affinity

    for prop in data['proposals']:
        prop_id, filename, master, conf, siblings, affinity, reasons, created = prop
        entry = {
            'id': prop_id,
            'filename': filename,
            'master': master,
            'confidence': conf,
            'siblings': siblings,
            'affinity': affinity,
            'reasons': reasons,
            'sibling_list': data['siblings'].get(prop_id, [])
        }

        if affinity and affinity >= 0.95:
            data['identical_files'].append(entry)
        elif affinity and affinity >= 0.70:
            data['similar_files'].append(entry)
        else:
            data['divergent_files'].append(entry)

    # Distribution by affinity ranges
    cursor.execute('''
        SELECT
            CASE
                WHEN average_affinity >= 0.95 THEN '95-100%'
                WHEN average_affinity >= 0.90 THEN '90-95%'
                WHEN average_affinity >= 0.80 THEN '80-90%'
                WHEN average_affinity >= 0.70 THEN '70-80%'
                WHEN average_affinity >= 0.50 THEN '50-70%'
                ELSE '<50%'
            END as range,
            COUNT(*) as count
        FROM consolidation_proposals
        WHERE project_id = ?
        GROUP BY range
        ORDER BY range DESC
    ''', (project_id,))
    data['distribution'] = cursor.fetchall()

    return data


def generate_html(data):
    """Generate complete HTML report."""

    stats = data['stats']
    total_files = stats['total_siblings'] + stats['total_groups']

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HyperMatrix - Reporte de Consolidacion</title>
    <style>
        :root {{
            --primary: #2563eb;
            --success: #16a34a;
            --warning: #d97706;
            --danger: #dc2626;
            --dark: #1f2937;
            --light: #f3f4f6;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--light);
            color: var(--dark);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary), #1e40af);
            color: white;
            padding: 40px 20px;
            margin-bottom: 30px;
            border-radius: 12px;
        }}

        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}

        header p {{
            opacity: 0.9;
            font-size: 1.1rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        }}

        .stat-card .value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .stat-card .label {{
            color: #6b7280;
            font-size: 0.9rem;
            margin-top: 5px;
        }}

        .stat-card.success .value {{ color: var(--success); }}
        .stat-card.warning .value {{ color: var(--warning); }}
        .stat-card.danger .value {{ color: var(--danger); }}

        .section {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .section h2 {{
            color: var(--dark);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--light);
        }}

        .section h3 {{
            color: var(--dark);
            margin: 20px 0 15px 0;
            font-size: 1.1rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}

        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}

        th {{
            background: var(--light);
            font-weight: 600;
            color: var(--dark);
        }}

        tr:hover {{
            background: #f9fafb;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .badge-success {{ background: #dcfce7; color: var(--success); }}
        .badge-warning {{ background: #fef3c7; color: var(--warning); }}
        .badge-danger {{ background: #fee2e2; color: var(--danger); }}
        .badge-info {{ background: #dbeafe; color: var(--primary); }}

        .progress-bar {{
            height: 24px;
            background: var(--light);
            border-radius: 12px;
            overflow: hidden;
            margin: 10px 0;
        }}

        .progress-bar .fill {{
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .fill-success {{ background: var(--success); }}
        .fill-warning {{ background: var(--warning); }}
        .fill-danger {{ background: var(--danger); }}

        .action-box {{
            background: #f0f9ff;
            border-left: 4px solid var(--primary);
            padding: 15px 20px;
            margin: 15px 0;
            border-radius: 0 8px 8px 0;
        }}

        .action-box.success {{ background: #f0fdf4; border-color: var(--success); }}
        .action-box.warning {{ background: #fffbeb; border-color: var(--warning); }}
        .action-box.danger {{ background: #fef2f2; border-color: var(--danger); }}

        .file-path {{
            font-family: 'Consolas', monospace;
            font-size: 0.8rem;
            color: #6b7280;
            word-break: break-all;
        }}

        .collapsible {{
            cursor: pointer;
            user-select: none;
        }}

        .collapsible:hover {{
            background: #f3f4f6;
        }}

        .details {{
            display: none;
            padding: 15px;
            background: #f9fafb;
            border-radius: 8px;
            margin: 10px 0;
        }}

        .details.show {{
            display: block;
        }}

        .chart-bar {{
            display: flex;
            align-items: center;
            margin: 8px 0;
        }}

        .chart-bar .label {{
            width: 80px;
            font-size: 0.85rem;
        }}

        .chart-bar .bar {{
            flex: 1;
            height: 28px;
            background: var(--light);
            border-radius: 4px;
            overflow: hidden;
            margin: 0 10px;
        }}

        .chart-bar .bar .fill {{
            height: 100%;
            display: flex;
            align-items: center;
            padding-left: 10px;
            color: white;
            font-size: 0.8rem;
        }}

        .chart-bar .count {{
            width: 50px;
            text-align: right;
            font-weight: 600;
        }}

        footer {{
            text-align: center;
            padding: 30px;
            color: #6b7280;
            font-size: 0.9rem;
        }}

        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            table {{
                font-size: 0.8rem;
            }}

            th, td {{
                padding: 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Reporte de Consolidacion</h1>
            <p>Analisis de similitudes y propuestas de unificacion - HyperMatrix v2026</p>
            <p style="margin-top: 10px; opacity: 0.8;">Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>

        <!-- Resumen Ejecutivo -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="value">{stats['total_groups']}</div>
                <div class="label">Grupos de Archivos</div>
            </div>
            <div class="stat-card">
                <div class="value">{total_files}</div>
                <div class="label">Total Archivos Analizados</div>
            </div>
            <div class="stat-card success">
                <div class="value">{stats['identical']}</div>
                <div class="label">Duplicados Identicos</div>
            </div>
            <div class="stat-card warning">
                <div class="value">{stats['similar']}</div>
                <div class="label">Versiones Similares</div>
            </div>
            <div class="stat-card danger">
                <div class="value">{stats['different']}</div>
                <div class="label">Archivos Divergentes</div>
            </div>
            <div class="stat-card">
                <div class="value">{stats['avg_affinity']:.0%}</div>
                <div class="label">Afinidad Promedio</div>
            </div>
        </div>

        <!-- Ahorro Potencial -->
        <div class="section">
            <h2>Ahorro Potencial</h2>

            <div class="progress-bar">
                <div class="fill fill-success" style="width: {(stats['identical']/total_files)*100:.1f}%">
                    Identicos ({stats['identical']})
                </div>
                <div class="fill fill-warning" style="width: {(stats['similar']/total_files)*100:.1f}%">
                    Similares ({stats['similar']})
                </div>
                <div class="fill fill-danger" style="width: {(stats['different']/total_files)*100:.1f}%">
                    Diferentes ({stats['different']})
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px;">
                <div class="action-box success">
                    <strong>Eliminar sin revisar:</strong> {stats['identical']} archivos<br>
                    <small>Son copias identicas (>95% similitud)</small>
                </div>
                <div class="action-box warning">
                    <strong>Revisar y fusionar:</strong> {stats['similar']} archivos<br>
                    <small>Versiones similares (70-95% similitud)</small>
                </div>
                <div class="action-box danger">
                    <strong>Mantener separados:</strong> {stats['different']} archivos<br>
                    <small>Muy diferentes (<70% similitud)</small>
                </div>
            </div>

            <div class="action-box" style="margin-top: 20px;">
                <strong>Resultado esperado:</strong> Reducir de <strong>{total_files}</strong> archivos a <strong>{stats['total_groups']}</strong> archivos unicos.<br>
                <small>Reduccion del {((total_files - stats['total_groups'])/total_files)*100:.0f}% en archivos duplicados.</small>
            </div>
        </div>

        <!-- Distribucion por Afinidad -->
        <div class="section">
            <h2>Distribucion por Nivel de Similitud</h2>
            {generate_distribution_chart(data['distribution'], stats['total_groups'])}
        </div>

        <!-- Archivos Mas Fragmentados -->
        <div class="section">
            <h2>Top 20 Archivos Mas Fragmentados</h2>
            <p style="color: #6b7280; margin-bottom: 15px;">Archivos con mas versiones duplicadas en el proyecto</p>

            <table>
                <thead>
                    <tr>
                        <th>Archivo</th>
                        <th>Versiones</th>
                        <th>Afinidad</th>
                        <th>Estado</th>
                        <th>Accion Recomendada</th>
                    </tr>
                </thead>
                <tbody>
                    {generate_top_fragmented_rows(data['proposals'][:20])}
                </tbody>
            </table>
        </div>

        <!-- Duplicados Identicos -->
        <div class="section">
            <h2>Duplicados Identicos (Eliminar)</h2>
            <p style="color: #6b7280; margin-bottom: 15px;">
                Estos {len(data['identical_files'])} grupos contienen archivos practicamente identicos.
                Se recomienda mantener solo el archivo master.
            </p>

            {generate_identical_section(data['identical_files'][:30])}
        </div>

        <!-- Versiones Similares -->
        <div class="section">
            <h2>Versiones Similares (Revisar y Fusionar)</h2>
            <p style="color: #6b7280; margin-bottom: 15px;">
                Estos {len(data['similar_files'])} grupos tienen versiones con diferencias menores.
                Revisar cual tiene las mejores caracteristicas.
            </p>

            {generate_similar_section(data['similar_files'][:30])}
        </div>

        <!-- Versiones Divergentes -->
        <div class="section">
            <h2>Versiones Divergentes (Mantener Separadas)</h2>
            <p style="color: #6b7280; margin-bottom: 15px;">
                Estos {len(data['divergent_files'])} grupos tienen archivos muy diferentes aunque compartan nombre.
                Probablemente sirven propositos distintos.
            </p>

            {generate_divergent_section(data['divergent_files'][:20])}
        </div>

        <!-- Detalle Completo -->
        <div class="section">
            <h2>Catalogo Completo de Propuestas</h2>
            <p style="color: #6b7280; margin-bottom: 15px;">
                Lista completa de los {stats['total_groups']} grupos detectados con sus archivos relacionados.
            </p>

            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Archivo</th>
                        <th>Versiones</th>
                        <th>Afinidad</th>
                        <th>Confianza</th>
                        <th>Master Propuesto</th>
                    </tr>
                </thead>
                <tbody>
                    {generate_full_catalog(data['proposals'])}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Generado por <strong>HyperMatrix v2026</strong> - Motor de Analisis de Codigo</p>
            <p>Consolidation Engine con optimizaciones de rendimiento</p>
        </footer>
    </div>

    <script>
        // Toggle details
        document.querySelectorAll('.collapsible').forEach(el => {{
            el.addEventListener('click', () => {{
                const details = el.nextElementSibling;
                if (details && details.classList.contains('details')) {{
                    details.classList.toggle('show');
                }}
            }});
        }});
    </script>
</body>
</html>'''

    return html


def generate_distribution_chart(distribution, total):
    """Generate distribution bar chart."""
    colors = {
        '95-100%': '#16a34a',
        '90-95%': '#22c55e',
        '80-90%': '#84cc16',
        '70-80%': '#eab308',
        '50-70%': '#f97316',
        '<50%': '#ef4444'
    }

    html = ''
    for range_name, count in distribution:
        pct = (count / total) * 100 if total > 0 else 0
        color = colors.get(range_name, '#6b7280')
        html += f'''
        <div class="chart-bar">
            <span class="label">{range_name}</span>
            <div class="bar">
                <div class="fill" style="width: {pct}%; background: {color};">{count}</div>
            </div>
            <span class="count">{pct:.0f}%</span>
        </div>'''

    return html


def generate_top_fragmented_rows(proposals):
    """Generate rows for top fragmented files."""
    html = ''
    for prop in proposals:
        prop_id, filename, master, conf, siblings, affinity, reasons, created = prop
        total = siblings + 1

        if affinity and affinity >= 0.95:
            badge = '<span class="badge badge-success">Identico</span>'
            action = 'Eliminar duplicados'
        elif affinity and affinity >= 0.70:
            badge = '<span class="badge badge-warning">Similar</span>'
            action = 'Revisar diferencias'
        else:
            badge = '<span class="badge badge-danger">Divergente</span>'
            action = 'Mantener separados'

        html += f'''
        <tr>
            <td><strong>{filename}</strong></td>
            <td>{total}</td>
            <td>{affinity:.0%}</td>
            <td>{badge}</td>
            <td>{action}</td>
        </tr>'''

    return html


def generate_identical_section(files):
    """Generate section for identical files."""
    if not files:
        return '<p>No se encontraron archivos identicos.</p>'

    html = '<div style="display: grid; gap: 15px;">'

    for f in files:
        siblings_html = ''
        for sib in f['sibling_list'][:5]:
            path, aff, level = sib
            short_path = '...' + path[-70:] if len(path) > 70 else path
            siblings_html += f'<div class="file-path">- {short_path} ({aff:.0%})</div>'

        if len(f['sibling_list']) > 5:
            siblings_html += f'<div style="color: #6b7280; font-size: 0.85rem;">... y {len(f["sibling_list"]) - 5} mas</div>'

        html += f'''
        <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>{f['filename']}</strong>
                <span class="badge badge-success">{f['siblings'] + 1} versiones - {f['affinity']:.0%}</span>
            </div>
            <div class="file-path" style="margin: 10px 0;">Master: {f['master']}</div>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e7eb;">
                <small style="color: #6b7280;">Duplicados a eliminar:</small>
                {siblings_html}
            </div>
        </div>'''

    html += '</div>'
    return html


def generate_similar_section(files):
    """Generate section for similar files."""
    if not files:
        return '<p>No se encontraron archivos similares.</p>'

    html = '<table><thead><tr><th>Archivo</th><th>Versiones</th><th>Afinidad</th><th>Master Propuesto</th><th>Diferencias</th></tr></thead><tbody>'

    for f in files:
        master_short = '...' + f['master'][-50:] if len(f['master']) > 50 else f['master']
        reasons = f['reasons'] or 'Sin detalles'
        reasons_short = reasons[:40] + '...' if len(reasons) > 40 else reasons

        html += f'''
        <tr>
            <td><strong>{f['filename']}</strong></td>
            <td>{f['siblings'] + 1}</td>
            <td>{f['affinity']:.0%}</td>
            <td class="file-path">{master_short}</td>
            <td><small>{reasons_short}</small></td>
        </tr>'''

    html += '</tbody></table>'
    return html


def generate_divergent_section(files):
    """Generate section for divergent files."""
    if not files:
        return '<p>No se encontraron archivos divergentes.</p>'

    html = '<table><thead><tr><th>Archivo</th><th>Versiones</th><th>Afinidad</th><th>Nota</th></tr></thead><tbody>'

    for f in files:
        html += f'''
        <tr>
            <td><strong>{f['filename']}</strong></td>
            <td>{f['siblings'] + 1}</td>
            <td>{f['affinity']:.0%}</td>
            <td><small>Archivos muy diferentes, revisar individualmente</small></td>
        </tr>'''

    html += '</tbody></table>'
    return html


def generate_full_catalog(proposals):
    """Generate full catalog rows."""
    html = ''
    for i, prop in enumerate(proposals, 1):
        prop_id, filename, master, conf, siblings, affinity, reasons, created = prop
        master_short = '...' + master[-45:] if len(master) > 45 else master

        html += f'''
        <tr>
            <td>{i}</td>
            <td><strong>{filename}</strong></td>
            <td>{siblings + 1}</td>
            <td>{affinity:.0%}</td>
            <td>{conf:.0%}</td>
            <td class="file-path">{master_short}</td>
        </tr>'''

    return html


if __name__ == '__main__':
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else 'hypermatrix.db'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'consolidation_report.html'

    print(f'Generating consolidation report...')
    print(f'  Database: {db_path}')
    print(f'  Output: {output_path}')

    result = generate_report(db_path, output_path)
    print(f'  Done! Report saved to: {result}')
