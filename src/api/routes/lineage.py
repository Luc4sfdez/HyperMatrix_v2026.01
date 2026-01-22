"""
HyperMatrix v2026 - Lineage API Routes
Import resolution and dependency graph endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from ..dependencies import get_db
from ...core.lineage import LineageResolver, ImportType

router = APIRouter()


class ResolveImportRequest(BaseModel):
    """Request for import resolution."""
    module: str
    source_file: str
    is_from_import: bool = False


class DependencyGraphRequest(BaseModel):
    """Request for dependency graph."""
    root_path: str
    entry_files: Optional[list[str]] = None


@router.post("/resolve")
async def resolve_import(request: ResolveImportRequest):
    """Resolve an import to its source file."""
    source_path = Path(request.source_file)

    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found")

    # Determine project root (go up until we find a marker or hit root)
    project_root = source_path.parent
    for _ in range(10):
        if (project_root / "setup.py").exists() or \
           (project_root / "pyproject.toml").exists() or \
           (project_root / "package.json").exists() or \
           (project_root / ".git").exists():
            break
        if project_root.parent == project_root:
            break
        project_root = project_root.parent

    resolver = LineageResolver(str(project_root))

    ext = source_path.suffix.lower()
    if ext == ".py":
        result = resolver.resolve_python_import(
            request.module,
            request.source_file,
            request.is_from_import,
        )
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        result = resolver.resolve_js_import(request.module, request.source_file)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    return {
        "module": result.module,
        "names": result.names,
        "import_type": result.import_type.value,
        "resolved_path": result.resolved_path,
        "is_local": result.import_type in (ImportType.LOCAL, ImportType.RELATIVE),
    }


@router.post("/graph")
async def build_dependency_graph(request: DependencyGraphRequest):
    """Build dependency graph for a project."""
    root_path = Path(request.root_path)

    if not root_path.exists():
        raise HTTPException(status_code=404, detail="Root path not found")

    resolver = LineageResolver(str(root_path))

    entry_files = request.entry_files
    if entry_files:
        entry_files = [str(Path(f).resolve()) for f in entry_files]

    graph = resolver.build_dependency_graph(entry_files)

    # Convert to JSON-serializable format
    nodes = []
    edges = []

    for filepath, node in graph.nodes.items():
        nodes.append({
            "id": filepath,
            "depth": node.depth,
            "import_count": len(node.imports),
            "imported_by_count": len(node.imported_by),
        })

        for imp in node.imports:
            if imp.resolved_path and imp.import_type == ImportType.LOCAL:
                edges.append({
                    "source": filepath,
                    "target": imp.resolved_path,
                    "module": imp.module,
                })

    return {
        "root_path": str(root_path),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "root_files": graph.root_files,
        "circular_dependencies": [
            {"file1": c[0], "file2": c[1]}
            for c in graph.circular_deps
        ],
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/dependents")
async def get_dependents(
    filepath: str = Query(..., description="File to find dependents for"),
    project_root: str = Query(..., description="Project root path"),
):
    """Get all files that depend on a given file."""
    file_path = Path(filepath)
    root_path = Path(project_root)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not root_path.exists():
        raise HTTPException(status_code=404, detail="Project root not found")

    resolver = LineageResolver(str(root_path))
    graph = resolver.build_dependency_graph()

    dependents = resolver.get_dependents(graph, str(file_path))

    return {
        "filepath": str(file_path),
        "dependent_count": len(dependents),
        "dependents": dependents,
    }


@router.get("/dependencies")
async def get_dependencies(
    filepath: str = Query(..., description="File to find dependencies for"),
    project_root: str = Query(..., description="Project root path"),
):
    """Get all files that a given file depends on."""
    file_path = Path(filepath)
    root_path = Path(project_root)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not root_path.exists():
        raise HTTPException(status_code=404, detail="Project root not found")

    resolver = LineageResolver(str(root_path))
    graph = resolver.build_dependency_graph()

    dependencies = resolver.get_dependencies(graph, str(file_path))

    return {
        "filepath": str(file_path),
        "dependency_count": len(dependencies),
        "dependencies": dependencies,
    }


@router.get("/chain")
async def get_import_chain(
    from_file: str = Query(..., description="Starting file"),
    to_file: str = Query(..., description="Target file"),
    project_root: str = Query(..., description="Project root path"),
):
    """Find the import chain between two files."""
    from_path = Path(from_file)
    to_path = Path(to_file)
    root_path = Path(project_root)

    if not from_path.exists():
        raise HTTPException(status_code=404, detail="From file not found")

    if not to_path.exists():
        raise HTTPException(status_code=404, detail="To file not found")

    resolver = LineageResolver(str(root_path))
    graph = resolver.build_dependency_graph()

    chain = resolver.get_import_chain(graph, str(from_path), str(to_path))

    return {
        "from_file": str(from_path),
        "to_file": str(to_path),
        "chain_length": len(chain),
        "chain": chain,
        "connected": len(chain) > 0,
    }


@router.get("/project/{project_id}/imports")
async def get_project_import_summary(project_id: int):
    """Get import summary for a project from database."""
    db = get_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()

        # Verify project
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get all imports grouped by module
        cursor.execute("""
            SELECT i.module, i.is_from_import, COUNT(*) as usage_count,
                   GROUP_CONCAT(DISTINCT fi.filepath) as used_in
            FROM imports i
            JOIN files fi ON i.file_id = fi.id
            WHERE fi.project_id = ?
            GROUP BY i.module
            ORDER BY usage_count DESC
        """, (project_id,))

        imports = []
        third_party = []
        local = []

        for row in cursor.fetchall():
            module = row["module"]
            entry = {
                "module": module,
                "usage_count": row["usage_count"],
                "is_from_import": bool(row["is_from_import"]),
                "used_in_files": row["used_in"].split(",") if row["used_in"] else [],
            }

            # Classify import
            if module.startswith(".") or "/" in module:
                local.append(entry)
            elif module.split(".")[0] in LineageResolver.PYTHON_BUILTINS:
                imports.append(entry)
            else:
                third_party.append(entry)

    return {
        "project_id": project_id,
        "project_name": project["name"],
        "total_imports": len(imports) + len(third_party) + len(local),
        "builtin_imports": imports,
        "third_party_imports": third_party,
        "local_imports": local,
    }
