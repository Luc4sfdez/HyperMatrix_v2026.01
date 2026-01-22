"""
HyperMatrix v2026 - Analysis API Routes
File analysis and data flow endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import json

from ..dependencies import get_db
from ...parsers import PythonParser, JavaScriptParser, MarkdownParser, JSONParser

router = APIRouter()


class FileAnalysisRequest(BaseModel):
    """Request for single file analysis."""
    filepath: str
    extract_dna: bool = True


class DataFlowResult(BaseModel):
    """Data flow analysis result."""
    variable: str
    lineno: int
    flow_type: str
    scope: str


@router.get("/file/{file_id}")
async def get_file_analysis(file_id: int):
    """Get complete analysis for a file."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # Get file info
        cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        file_row = cursor.fetchone()

        if not file_row:
            raise HTTPException(status_code=404, detail="File not found")

        # Get functions
        cursor.execute("SELECT * FROM functions WHERE file_id = ?", (file_id,))
        functions = []
        for row in cursor.fetchall():
            functions.append({
                "name": row["name"],
                "lineno": row["lineno"],
                "args": json.loads(row["args"]) if row["args"] else [],
                "returns": row["returns"],
                "is_async": bool(row["is_async"]),
                "docstring": row["docstring"],
            })

        # Get classes
        cursor.execute("SELECT * FROM classes WHERE file_id = ?", (file_id,))
        classes = []
        for row in cursor.fetchall():
            classes.append({
                "name": row["name"],
                "lineno": row["lineno"],
                "bases": json.loads(row["bases"]) if row["bases"] else [],
                "methods": json.loads(row["methods"]) if row["methods"] else [],
                "docstring": row["docstring"],
            })

        # Get imports
        cursor.execute("SELECT * FROM imports WHERE file_id = ?", (file_id,))
        imports = []
        for row in cursor.fetchall():
            imports.append({
                "module": row["module"],
                "lineno": row["lineno"],
                "names": json.loads(row["names"]) if row["names"] else [],
                "is_from_import": bool(row["is_from_import"]),
            })

        # Get variables
        cursor.execute("SELECT * FROM variables WHERE file_id = ?", (file_id,))
        variables = []
        for row in cursor.fetchall():
            variables.append({
                "name": row["name"],
                "lineno": row["lineno"],
                "type_annotation": row["type_annotation"],
                "scope": row["scope"],
            })

    return {
        "file_id": file_id,
        "filepath": file_row["filepath"],
        "file_type": file_row["file_type"],
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "variables": variables,
        "summary": {
            "function_count": len(functions),
            "class_count": len(classes),
            "import_count": len(imports),
            "variable_count": len(variables),
        }
    }


@router.get("/file/{file_id}/dataflow")
async def get_file_dataflow(
    file_id: int,
    variable: Optional[str] = Query(None, description="Filter by variable name"),
):
    """Get data flow analysis for a file."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # Verify file exists
        cursor.execute("SELECT filepath FROM files WHERE id = ?", (file_id,))
        file_row = cursor.fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="File not found")

        # Get data flow
        if variable:
            cursor.execute("""
                SELECT * FROM data_flow
                WHERE file_id = ? AND variable = ?
                ORDER BY lineno
            """, (file_id, variable))
        else:
            cursor.execute("""
                SELECT * FROM data_flow
                WHERE file_id = ?
                ORDER BY lineno
            """, (file_id,))

        data_flow = []
        for row in cursor.fetchall():
            data_flow.append({
                "variable": row["variable"],
                "lineno": row["lineno"],
                "col_offset": row["col_offset"],
                "flow_type": row["flow_type"],
                "scope": row["scope"],
            })

    # Group by variable
    by_variable = {}
    for df in data_flow:
        var = df["variable"]
        if var not in by_variable:
            by_variable[var] = {"reads": [], "writes": []}

        if df["flow_type"] == "READ":
            by_variable[var]["reads"].append(df["lineno"])
        else:
            by_variable[var]["writes"].append(df["lineno"])

    return {
        "file_id": file_id,
        "filepath": file_row["filepath"],
        "total_operations": len(data_flow),
        "data_flow": data_flow,
        "by_variable": by_variable,
    }


@router.post("/parse")
async def parse_code(request: FileAnalysisRequest):
    """Parse a file and return analysis without storing."""
    filepath = Path(request.filepath)

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    ext = filepath.suffix.lower()

    try:
        if ext == ".py":
            parser = PythonParser()
            result = parser.parse_file(str(filepath))
            return {
                "filepath": str(filepath),
                "type": "python",
                "functions": [
                    {"name": f.name, "lineno": f.lineno, "args": f.args, "returns": f.returns}
                    for f in result.functions
                ],
                "classes": [
                    {"name": c.name, "lineno": c.lineno, "bases": c.bases, "methods": c.methods}
                    for c in result.classes
                ],
                "imports": [
                    {"module": i.module, "names": i.names, "is_from": i.is_from_import}
                    for i in result.imports
                ],
                "data_flow_count": len(result.data_flow),
            }

        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            parser = JavaScriptParser()
            result = parser.parse_file(str(filepath))
            return {
                "filepath": str(filepath),
                "type": "javascript",
                "functions": [
                    {"name": f.name, "lineno": f.lineno, "params": f.params, "is_async": f.is_async}
                    for f in result.functions
                ],
                "classes": [
                    {"name": c.name, "lineno": c.lineno, "extends": c.extends, "methods": c.methods}
                    for c in result.classes
                ],
                "imports": [
                    {"module": i.module, "names": i.names}
                    for i in result.imports
                ],
            }

        elif ext in (".md", ".markdown"):
            parser = MarkdownParser()
            result = parser.parse_file(str(filepath))
            return {
                "filepath": str(filepath),
                "type": "markdown",
                "headings": [
                    {"text": h.text, "level": h.level, "lineno": h.lineno}
                    for h in result.headings
                ],
                "links": [
                    {"text": l.text, "url": l.url, "is_image": l.is_image}
                    for l in result.links
                ],
                "code_blocks": len(result.code_blocks),
                "word_count": result.word_count,
            }

        elif ext == ".json":
            parser = JSONParser()
            result = parser.parse_file(str(filepath))
            return {
                "filepath": str(filepath),
                "type": "json",
                "is_valid": result.is_valid,
                "root_type": result.root_type.value if result.root_type else None,
                "total_keys": result.total_keys,
                "max_depth": result.max_depth,
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/files")
async def get_project_files(
    project_id: int,
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get all files in a project."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # Verify project exists
        cursor.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Project not found")

        # Get files
        query = "SELECT * FROM files WHERE project_id = ?"
        params = [project_id]

        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)

        query += " ORDER BY filepath LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

    return {
        "project_id": project_id,
        "count": len(rows),
        "files": [
            {
                "id": row["id"],
                "filepath": row["filepath"],
                "file_type": row["file_type"],
                "analyzed_at": str(row["analyzed_at"]) if row["analyzed_at"] else None,
            }
            for row in rows
        ]
    }


@router.get("/summary/{project_id}")
async def get_analysis_summary(project_id: int):
    """Get comprehensive analysis summary for a project."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # Verify project
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # File count by type
        cursor.execute("""
            SELECT file_type, COUNT(*) as count
            FROM files WHERE project_id = ?
            GROUP BY file_type
        """, (project_id,))
        files_by_type = {row["file_type"]: row["count"] for row in cursor.fetchall()}

        # Top functions by usage (simplified)
        cursor.execute("""
            SELECT f.name, COUNT(*) as count, fi.filepath
            FROM functions f
            JOIN files fi ON f.file_id = fi.id
            WHERE fi.project_id = ?
            GROUP BY f.name
            ORDER BY count DESC
            LIMIT 10
        """, (project_id,))
        top_functions = [
            {"name": row["name"], "count": row["count"]}
            for row in cursor.fetchall()
        ]

        # Top imported modules
        cursor.execute("""
            SELECT i.module, COUNT(*) as count
            FROM imports i
            JOIN files fi ON i.file_id = fi.id
            WHERE fi.project_id = ?
            GROUP BY i.module
            ORDER BY count DESC
            LIMIT 10
        """, (project_id,))
        top_imports = [
            {"module": row["module"], "count": row["count"]}
            for row in cursor.fetchall()
        ]

        # Overall stats
        stats = db.get_statistics(project_id)

    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "root_path": project["root_path"],
        },
        "statistics": stats,
        "files_by_type": files_by_type,
        "top_functions": top_functions,
        "top_imports": top_imports,
    }
