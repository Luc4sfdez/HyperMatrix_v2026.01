"""
HyperMatrix v2026 - AI Context Builder
Builds rich context from SQLite + ChromaDB before calling Ollama.
Enables AI to answer questions like:
- "Where is function X?"
- "What depends on file Y?"
- "If I delete function Z, what breaks?"
"""

import re
import sqlite3
import os
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# Database path
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DB_PATH = os.path.join(DATA_DIR, "hypermatrix.db")

# Knowledge Base paths (check multiple locations)
# In Docker: /app/data/knowledge/ or /app/config/knowledge/
# Locally: config/knowledge/
KB_PATHS = [
    os.path.join(DATA_DIR, "knowledge", "hypermatrix_kb.md"),  # Docker data dir
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "knowledge", "hypermatrix_kb.md"),  # Project config dir
]

# Cached Knowledge Base (loaded once at module import)
_KNOWLEDGE_BASE_CACHE: Optional[str] = None


def _load_knowledge_base() -> str:
    """
    Load the HyperMatrix knowledge base from file.
    Cached at module level to avoid repeated file reads.
    Checks multiple paths for flexibility in deployment.
    """
    global _KNOWLEDGE_BASE_CACHE

    if _KNOWLEDGE_BASE_CACHE is not None:
        return _KNOWLEDGE_BASE_CACHE

    try:
        # Try each path in order
        for kb_path in KB_PATHS:
            if os.path.exists(kb_path):
                with open(kb_path, 'r', encoding='utf-8') as f:
                    _KNOWLEDGE_BASE_CACHE = f.read()
                break
        else:
            # Fallback minimal knowledge base if file not found
            _KNOWLEDGE_BASE_CACHE = """
Eres el asistente de HyperMatrix, una herramienta de análisis de código.
Guía al usuario con instrucciones específicas sobre pestañas y comandos.
Pestañas principales: Dashboard, Resultados, Comparador, Explorador BD, Código Muerto.
Comandos: /proyecto, /archivos, /funciones, /duplicados, /hermanos, /impacto.
"""
    except Exception as e:
        _KNOWLEDGE_BASE_CACHE = f"[Error loading knowledge base: {e}]"

    return _KNOWLEDGE_BASE_CACHE


def get_knowledge_base() -> str:
    """Get the cached knowledge base content."""
    return _load_knowledge_base()


class ContextBuilder:
    """
    Builds comprehensive context for AI queries by searching:
    1. SQLite (functions, classes, variables, imports, files)
    2. ChromaDB (semantic similarity)
    """

    def __init__(self, project_id: Optional[int] = None):
        self.project_id = project_id
        self._chromadb_engine = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection with row factory."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_chromadb(self):
        """Get ChromaDB engine lazily."""
        if self._chromadb_engine is None:
            try:
                from ..embeddings import get_embedding_engine
                self._chromadb_engine = get_embedding_engine()
            except Exception:
                self._chromadb_engine = None
        return self._chromadb_engine

    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract potential code identifiers from user query.
        Looks for function names, class names, file names, etc.
        """
        keywords = []

        # Extract potential identifiers (camelCase, snake_case, etc.)
        # Pattern for code identifiers
        identifier_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(identifier_pattern, query)

        # Filter out common words
        stopwords = {
            'the', 'is', 'in', 'at', 'of', 'and', 'or', 'to', 'a', 'an',
            'this', 'that', 'what', 'where', 'when', 'how', 'why', 'which',
            'function', 'class', 'method', 'variable', 'file', 'import',
            'line', 'code', 'error', 'bug', 'fix', 'change', 'delete',
            'update', 'add', 'remove', 'find', 'search', 'show', 'get',
            'está', 'donde', 'qué', 'cual', 'como', 'para', 'por',
            'función', 'archivo', 'línea', 'si', 'borro', 'elimino',
            'depende', 'rompe', 'usa', 'llama', 'importa'
        }

        for match in matches:
            if len(match) > 2 and match.lower() not in stopwords:
                keywords.append(match)

        # Extract file patterns (*.py, config.py, etc.)
        file_pattern = r'(\w+\.\w+)'
        file_matches = re.findall(file_pattern, query)
        keywords.extend(file_matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_keywords.append(kw)

        return unique_keywords[:10]  # Limit to 10 keywords

    def search_sqlite(self, keywords: List[str], limit: int = 20) -> Dict[str, Any]:
        """
        Search SQLite for functions, classes, variables, imports matching keywords.
        """
        results = {
            "functions": [],
            "classes": [],
            "variables": [],
            "imports": [],
            "files": [],
        }

        if not keywords:
            return results

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build WHERE clause for project filter
            project_filter = ""
            if self.project_id:
                project_filter = f"AND f.project_id = {self.project_id}"

            # Helper to extract filename from path
            def get_filename(filepath):
                return filepath.split('/')[-1].split('\\')[-1] if filepath else 'unknown'

            # Search functions
            for kw in keywords:
                cursor.execute(f"""
                    SELECT fn.name, fn.lineno, fn.args,
                           f.filepath, f.file_type, p.name as project_name
                    FROM functions fn
                    JOIN files f ON fn.file_id = f.id
                    JOIN projects p ON f.project_id = p.id
                    WHERE fn.name LIKE ? {project_filter}
                    LIMIT ?
                """, (f"%{kw}%", limit))

                for row in cursor.fetchall():
                    results["functions"].append({
                        "name": row["name"],
                        "line": row["lineno"],
                        "params": row["args"],
                        "file": row["filepath"],
                        "filename": get_filename(row["filepath"]),
                        "project": row["project_name"]
                    })

            # Search classes
            for kw in keywords:
                cursor.execute(f"""
                    SELECT c.name, c.lineno, c.bases,
                           f.filepath, f.file_type, p.name as project_name
                    FROM classes c
                    JOIN files f ON c.file_id = f.id
                    JOIN projects p ON f.project_id = p.id
                    WHERE c.name LIKE ? {project_filter}
                    LIMIT ?
                """, (f"%{kw}%", limit))

                for row in cursor.fetchall():
                    results["classes"].append({
                        "name": row["name"],
                        "line": row["lineno"],
                        "bases": row["bases"],
                        "file": row["filepath"],
                        "filename": get_filename(row["filepath"]),
                        "project": row["project_name"]
                    })

            # Search imports (to understand dependencies)
            for kw in keywords:
                cursor.execute(f"""
                    SELECT i.module, i.name, i.alias, i.lineno,
                           f.filepath
                    FROM imports i
                    JOIN files f ON i.file_id = f.id
                    WHERE (i.module LIKE ? OR i.name LIKE ?) {project_filter}
                    LIMIT ?
                """, (f"%{kw}%", f"%{kw}%", limit))

                for row in cursor.fetchall():
                    results["imports"].append({
                        "module": row["module"],
                        "name": row["name"],
                        "alias": row["alias"],
                        "line": row["lineno"],
                        "file": row["filepath"],
                        "filename": get_filename(row["filepath"])
                    })

            # Search files by path (contains keyword)
            for kw in keywords:
                cursor.execute(f"""
                    SELECT f.filepath, f.file_type,
                           p.name as project_name
                    FROM files f
                    JOIN projects p ON f.project_id = p.id
                    WHERE f.filepath LIKE ? {project_filter}
                    LIMIT ?
                """, (f"%{kw}%", limit))

                for row in cursor.fetchall():
                    results["files"].append({
                        "filepath": row["filepath"],
                        "filename": get_filename(row["filepath"]),
                        "language": row["file_type"],
                        "project": row["project_name"]
                    })

            conn.close()

        except Exception as e:
            results["error"] = str(e)

        return results

    def search_chromadb(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search ChromaDB for semantically similar content.
        """
        results = []

        try:
            engine = self._get_chromadb()
            if engine and engine.collection:
                # Build where filter for project if specified
                where_filter = None
                if self.project_id:
                    where_filter = {"project_id": self.project_id}

                # Perform semantic search
                search_results = engine.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )

                if search_results and search_results.get("documents"):
                    docs = search_results["documents"][0]
                    metadatas = search_results.get("metadatas", [[]])[0]
                    distances = search_results.get("distances", [[]])[0]

                    for i, doc in enumerate(docs):
                        meta = metadatas[i] if i < len(metadatas) else {}
                        dist = distances[i] if i < len(distances) else 0

                        results.append({
                            "content": doc[:500],  # Limit content size
                            "metadata": meta,
                            "relevance": round(1 - dist, 3) if dist else 1.0,
                            "file": meta.get("filepath", meta.get("filename", "unknown")),
                        })

        except Exception as e:
            results.append({"error": str(e)})

        return results

    def find_dependents(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Find what files/functions depend on (call) a given function.
        This helps answer "If I delete X, what breaks?"
        """
        dependents = []

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Search for imports that might use this function
            cursor.execute("""
                SELECT DISTINCT f.filepath, f.filename, i.module, i.name
                FROM imports i
                JOIN files f ON i.file_id = f.id
                WHERE i.name = ? OR i.module LIKE ?
            """, (function_name, f"%{function_name}%"))

            for row in cursor.fetchall():
                dependents.append({
                    "file": row["filepath"],
                    "filename": row["filename"],
                    "imports": f"{row['module']}.{row['name']}" if row['name'] else row['module']
                })

            conn.close()

        except Exception as e:
            dependents.append({"error": str(e)})

        return dependents

    def get_project_stats(self) -> Dict[str, Any]:
        """Get overall project statistics for context."""
        stats = {
            "total_files": 0,
            "total_functions": 0,
            "total_classes": 0,
            "total_variables": 0,
            "total_imports": 0,
            "projects": []
        }

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            project_filter = ""
            if self.project_id:
                project_filter = f"WHERE f.project_id = {self.project_id}"

            # Get counts
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) as files,
                       COUNT(DISTINCT fn.id) as functions,
                       COUNT(DISTINCT c.id) as classes,
                       COUNT(DISTINCT v.id) as variables,
                       COUNT(DISTINCT i.id) as imports
                FROM files f
                LEFT JOIN functions fn ON fn.file_id = f.id
                LEFT JOIN classes c ON c.file_id = f.id
                LEFT JOIN variables v ON v.file_id = f.id
                LEFT JOIN imports i ON i.file_id = f.id
                {project_filter}
            """)

            row = cursor.fetchone()
            if row:
                stats["total_files"] = row["files"]
                stats["total_functions"] = row["functions"]
                stats["total_classes"] = row["classes"]
                stats["total_variables"] = row["variables"]
                stats["total_imports"] = row["imports"]

            # Get project list
            cursor.execute("SELECT id, name, root_path FROM projects ORDER BY name")
            for row in cursor.fetchall():
                stats["projects"].append({
                    "id": row["id"],
                    "name": row["name"],
                    "path": row["root_path"]
                })

            conn.close()

        except Exception as e:
            stats["error"] = str(e)

        return stats

    def build_context(self, query: str) -> str:
        """
        Build comprehensive context for AI from query.
        Returns a formatted string ready to prepend to Ollama prompt.
        Includes: Knowledge Base + Project Context + DB Results
        """
        # Extract keywords
        keywords = self.extract_keywords(query)

        # Get project stats
        stats = self.get_project_stats()

        # Search SQLite
        sqlite_results = self.search_sqlite(keywords)

        # Search ChromaDB
        chromadb_results = self.search_chromadb(query)

        # Check for dependency questions
        dependents = []
        delete_patterns = ['borr', 'elimin', 'delete', 'remove', 'rompe', 'break', 'depende']
        if any(p in query.lower() for p in delete_patterns):
            for kw in keywords[:3]:  # Check first 3 keywords
                deps = self.find_dependents(kw)
                if deps and not any(d.get('error') for d in deps):
                    dependents.extend(deps)

        # Build context string - START WITH KNOWLEDGE BASE
        context_parts = []

        # Add Knowledge Base first (always present)
        knowledge_base = get_knowledge_base()
        if knowledge_base:
            context_parts.append(knowledge_base)
            context_parts.append("")
            context_parts.append("---")
            context_parts.append("")

        context_parts.append("=== CONTEXTO DE LA BASE DE DATOS ===")
        context_parts.append(f"Proyectos cargados: {len(stats['projects'])}")
        context_parts.append(f"Total archivos: {stats['total_files']}")
        context_parts.append(f"Total funciones: {stats['total_functions']}")
        context_parts.append(f"Total clases: {stats['total_classes']}")
        context_parts.append(f"Total imports: {stats['total_imports']}")
        context_parts.append("")

        # Add found functions
        if sqlite_results["functions"]:
            context_parts.append("FUNCIONES ENCONTRADAS:")
            for fn in sqlite_results["functions"][:10]:
                context_parts.append(
                    f"  - {fn['name']}({fn['params'] or ''}) en línea {fn['line']} de {fn['filename']}"
                )
                context_parts.append(f"    Ruta: {fn['file']}")
            context_parts.append("")

        # Add found classes
        if sqlite_results["classes"]:
            context_parts.append("CLASES ENCONTRADAS:")
            for cls in sqlite_results["classes"][:10]:
                bases = f"({cls['bases']})" if cls['bases'] else ""
                context_parts.append(
                    f"  - class {cls['name']}{bases} en línea {cls['line']} de {cls['filename']}"
                )
                context_parts.append(f"    Ruta: {cls['file']}")
            context_parts.append("")

        # Add found imports
        if sqlite_results["imports"]:
            context_parts.append("IMPORTS RELEVANTES:")
            for imp in sqlite_results["imports"][:10]:
                import_str = f"from {imp['module']} import {imp['name']}" if imp['name'] else f"import {imp['module']}"
                context_parts.append(f"  - {import_str} (línea {imp['line']} en {imp['filename']})")
            context_parts.append("")

        # Add found files
        if sqlite_results["files"]:
            context_parts.append("ARCHIVOS RELEVANTES:")
            for f in sqlite_results["files"][:10]:
                context_parts.append(f"  - {f['filename']} ({f.get('language', 'unknown')})")
                context_parts.append(f"    Ruta: {f['filepath']}")
            context_parts.append("")

        # Add dependents if found
        if dependents:
            context_parts.append("DEPENDENCIAS (archivos que usan estos elementos):")
            for dep in dependents[:10]:
                context_parts.append(f"  - {dep['filename']} importa {dep.get('imports', 'unknown')}")
                context_parts.append(f"    Ruta: {dep['file']}")
            context_parts.append("")

        # Add ChromaDB semantic results
        if chromadb_results and not any(r.get('error') for r in chromadb_results):
            context_parts.append("CONTENIDO RELACIONADO (búsqueda semántica):")
            for r in chromadb_results[:5]:
                context_parts.append(f"  Archivo: {r.get('file', 'unknown')} (relevancia: {r.get('relevance', 0)})")
                if r.get('content'):
                    # Show first 200 chars
                    preview = r['content'][:200].replace('\n', ' ')
                    context_parts.append(f"    Preview: {preview}...")
            context_parts.append("")

        context_parts.append("=== FIN CONTEXTO ===")
        context_parts.append("")
        context_parts.append("Usa esta información para responder la pregunta del usuario.")
        context_parts.append("Si el usuario pregunta 'dónde está X', indica archivo y línea exacta.")
        context_parts.append("Si pregunta 'qué se rompe si borro X', lista los archivos dependientes.")
        context_parts.append("")

        return "\n".join(context_parts)


def build_ai_context(query: str, project_id: Optional[int] = None) -> str:
    """
    Convenience function to build context for a query.
    Called from /api/ai/chat endpoint.
    """
    builder = ContextBuilder(project_id=project_id)
    return builder.build_context(query)


def get_context_builder(project_id: Optional[int] = None) -> ContextBuilder:
    """Get a ContextBuilder instance."""
    return ContextBuilder(project_id=project_id)
