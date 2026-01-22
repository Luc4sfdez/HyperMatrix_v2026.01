"""
HyperMatrix v2026 - Search API Routes
Search functions, classes, and code elements.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import json

from ..dependencies import get_db

router = APIRouter()


class FunctionResult(BaseModel):
    """Function search result."""
    id: int
    name: str
    filepath: str
    lineno: int
    args: list[str]
    returns: Optional[str]
    is_async: bool
    docstring: Optional[str]


class ClassResult(BaseModel):
    """Class search result."""
    id: int
    name: str
    filepath: str
    lineno: int
    bases: list[str]
    methods: list[str]
    docstring: Optional[str]


class ImportResult(BaseModel):
    """Import search result."""
    id: int
    module: str
    filepath: str
    lineno: int
    names: list[str]
    is_from_import: bool


class VariableResult(BaseModel):
    """Variable search result."""
    id: int
    name: str
    filepath: str
    lineno: int
    type_annotation: Optional[str]
    scope: str


@router.get("/functions")
async def search_functions(
    q: str = Query(..., min_length=1, description="Search query"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Search functions by name."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        if project_id:
            cursor.execute("""
                SELECT f.*, fi.filepath
                FROM functions f
                JOIN files fi ON f.file_id = fi.id
                WHERE f.name LIKE ? AND fi.project_id = ?
                ORDER BY f.name
                LIMIT ? OFFSET ?
            """, (f"%{q}%", project_id, limit, offset))
        else:
            cursor.execute("""
                SELECT f.*, fi.filepath
                FROM functions f
                JOIN files fi ON f.file_id = fi.id
                WHERE f.name LIKE ?
                ORDER BY f.name
                LIMIT ? OFFSET ?
            """, (f"%{q}%", limit, offset))

        rows = cursor.fetchall()

    results = []
    for row in rows:
        args = json.loads(row["args"]) if row["args"] else []
        results.append({
            "id": row["id"],
            "name": row["name"],
            "filepath": row["filepath"],
            "lineno": row["lineno"],
            "args": args,
            "returns": row["returns"],
            "is_async": bool(row["is_async"]),
            "docstring": row["docstring"],
        })

    return {"query": q, "count": len(results), "results": results}


@router.get("/classes")
async def search_classes(
    q: str = Query(..., min_length=1, description="Search query"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Search classes by name."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        if project_id:
            cursor.execute("""
                SELECT c.*, fi.filepath
                FROM classes c
                JOIN files fi ON c.file_id = fi.id
                WHERE c.name LIKE ? AND fi.project_id = ?
                ORDER BY c.name
                LIMIT ? OFFSET ?
            """, (f"%{q}%", project_id, limit, offset))
        else:
            cursor.execute("""
                SELECT c.*, fi.filepath
                FROM classes c
                JOIN files fi ON c.file_id = fi.id
                WHERE c.name LIKE ?
                ORDER BY c.name
                LIMIT ? OFFSET ?
            """, (f"%{q}%", limit, offset))

        rows = cursor.fetchall()

    results = []
    for row in rows:
        bases = json.loads(row["bases"]) if row["bases"] else []
        methods = json.loads(row["methods"]) if row["methods"] else []
        results.append({
            "id": row["id"],
            "name": row["name"],
            "filepath": row["filepath"],
            "lineno": row["lineno"],
            "bases": bases,
            "methods": methods,
            "docstring": row["docstring"],
        })

    return {"query": q, "count": len(results), "results": results}


@router.get("/imports")
async def search_imports(
    module: str = Query(..., min_length=1, description="Module name"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    limit: int = Query(50, ge=1, le=200),
):
    """Search imports by module name."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        if project_id:
            cursor.execute("""
                SELECT i.*, fi.filepath
                FROM imports i
                JOIN files fi ON i.file_id = fi.id
                WHERE i.module LIKE ? AND fi.project_id = ?
                ORDER BY i.module
                LIMIT ?
            """, (f"%{module}%", project_id, limit))
        else:
            cursor.execute("""
                SELECT i.*, fi.filepath
                FROM imports i
                JOIN files fi ON i.file_id = fi.id
                WHERE i.module LIKE ?
                ORDER BY i.module
                LIMIT ?
            """, (f"%{module}%", limit))

        rows = cursor.fetchall()

    results = []
    for row in rows:
        names = json.loads(row["names"]) if row["names"] else []
        results.append({
            "id": row["id"],
            "module": row["module"],
            "filepath": row["filepath"],
            "lineno": row["lineno"],
            "names": names,
            "is_from_import": bool(row["is_from_import"]),
        })

    return {"module": module, "count": len(results), "results": results}


@router.get("/variables")
async def search_variables(
    q: str = Query(..., min_length=1, description="Variable name"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    limit: int = Query(50, ge=1, le=200),
):
    """Search variables by name."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT v.*, fi.filepath
            FROM variables v
            JOIN files fi ON v.file_id = fi.id
            WHERE v.name LIKE ?
        """
        params = [f"%{q}%"]

        if project_id:
            query += " AND fi.project_id = ?"
            params.append(project_id)

        if scope:
            query += " AND v.scope LIKE ?"
            params.append(f"%{scope}%")

        query += " ORDER BY v.name LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "name": row["name"],
            "filepath": row["filepath"],
            "lineno": row["lineno"],
            "type_annotation": row["type_annotation"],
            "scope": row["scope"],
        })

    return {"query": q, "count": len(results), "results": results}


@router.get("/all")
async def search_all(
    q: str = Query(..., min_length=1, description="Search query"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    limit: int = Query(20, ge=1, le=50),
):
    """Search across all code elements."""
    db = get_db()

    results = {
        "query": q,
        "functions": [],
        "classes": [],
        "variables": [],
        "imports": [],
    }

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # Search functions
        if project_id:
            cursor.execute("""
                SELECT f.name, fi.filepath, f.lineno
                FROM functions f
                JOIN files fi ON f.file_id = fi.id
                WHERE f.name LIKE ? AND fi.project_id = ?
                LIMIT ?
            """, (f"%{q}%", project_id, limit))
        else:
            cursor.execute("""
                SELECT f.name, fi.filepath, f.lineno
                FROM functions f
                JOIN files fi ON f.file_id = fi.id
                WHERE f.name LIKE ?
                LIMIT ?
            """, (f"%{q}%", limit))

        results["functions"] = [
            {"name": r["name"], "filepath": r["filepath"], "lineno": r["lineno"]}
            for r in cursor.fetchall()
        ]

        # Search classes
        if project_id:
            cursor.execute("""
                SELECT c.name, fi.filepath, c.lineno
                FROM classes c
                JOIN files fi ON c.file_id = fi.id
                WHERE c.name LIKE ? AND fi.project_id = ?
                LIMIT ?
            """, (f"%{q}%", project_id, limit))
        else:
            cursor.execute("""
                SELECT c.name, fi.filepath, c.lineno
                FROM classes c
                JOIN files fi ON c.file_id = fi.id
                WHERE c.name LIKE ?
                LIMIT ?
            """, (f"%{q}%", limit))

        results["classes"] = [
            {"name": r["name"], "filepath": r["filepath"], "lineno": r["lineno"]}
            for r in cursor.fetchall()
        ]

        # Search variables
        if project_id:
            cursor.execute("""
                SELECT v.name, fi.filepath, v.lineno, v.scope
                FROM variables v
                JOIN files fi ON v.file_id = fi.id
                WHERE v.name LIKE ? AND fi.project_id = ?
                LIMIT ?
            """, (f"%{q}%", project_id, limit))
        else:
            cursor.execute("""
                SELECT v.name, fi.filepath, v.lineno, v.scope
                FROM variables v
                JOIN files fi ON v.file_id = fi.id
                WHERE v.name LIKE ?
                LIMIT ?
            """, (f"%{q}%", limit))

        results["variables"] = [
            {"name": r["name"], "filepath": r["filepath"], "lineno": r["lineno"], "scope": r["scope"]}
            for r in cursor.fetchall()
        ]

    results["total"] = (
        len(results["functions"]) +
        len(results["classes"]) +
        len(results["variables"])
    )

    return results
