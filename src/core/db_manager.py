"""
HyperMatrix v2026 - Database Manager
SQLite database for storing analysis results.
"""

import os
import sqlite3
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager

from ..parsers import (
    ParseResult,
    JSParseResult,
    MDParseResult,
    JSONParseResult,
)

# Default database path - uses DATA_DIR for Docker persistence
_DATA_DIR = os.getenv("DATA_DIR", "/app/data")
_DEFAULT_DB_PATH = os.path.join(_DATA_DIR, "hypermatrix.db")


class DBManager:
    """SQLite database manager for analysis results."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = _DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_database()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    filepath TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    hash TEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)

            # Functions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    lineno INTEGER,
                    col_offset INTEGER,
                    args TEXT,
                    returns TEXT,
                    is_async BOOLEAN DEFAULT FALSE,
                    docstring TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """)

            # Classes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    lineno INTEGER,
                    col_offset INTEGER,
                    bases TEXT,
                    methods TEXT,
                    docstring TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """)

            # Variables table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS variables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    lineno INTEGER,
                    col_offset INTEGER,
                    type_annotation TEXT,
                    scope TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """)

            # Imports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    module TEXT NOT NULL,
                    lineno INTEGER,
                    names TEXT,
                    is_from_import BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """)

            # Data flow table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    variable TEXT NOT NULL,
                    lineno INTEGER,
                    col_offset INTEGER,
                    flow_type TEXT NOT NULL,
                    scope TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_file ON functions(file_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_file ON classes(file_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_flow_file ON data_flow(file_id)")

            # Project history table (for UI recent/favorites)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    is_favorite BOOLEAN DEFAULT FALSE,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    use_count INTEGER DEFAULT 1
                )
            """)

    def create_project(self, name: str, root_path: str) -> int:
        """Create a new project and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO projects (name, root_path) VALUES (?, ?)",
                (name, root_path)
            )
            return cursor.lastrowid

    def get_project(self, project_id: int) -> Optional[dict]:
        """Get project by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_file(self, project_id: int, filepath: str, file_type: str, file_hash: str = None) -> int:
        """Save a file record and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO files (project_id, filepath, file_type, hash) VALUES (?, ?, ?, ?)",
                (project_id, filepath, file_type, file_hash)
            )
            return cursor.lastrowid

    def save_python_result(self, file_id: int, result: ParseResult):
        """Save Python parse result to database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Save functions
            for func in result.functions:
                cursor.execute(
                    """INSERT INTO functions
                       (file_id, name, lineno, col_offset, args, returns, is_async, docstring)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, func.name, func.lineno, func.col_offset,
                     json.dumps(func.args), func.returns, func.is_async, func.docstring)
                )

            # Save classes
            for cls in result.classes:
                cursor.execute(
                    """INSERT INTO classes
                       (file_id, name, lineno, col_offset, bases, methods, docstring)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, cls.name, cls.lineno, cls.col_offset,
                     json.dumps(cls.bases), json.dumps(cls.methods), cls.docstring)
                )

            # Save variables
            for var in result.variables:
                cursor.execute(
                    """INSERT INTO variables
                       (file_id, name, lineno, col_offset, type_annotation, scope)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (file_id, var.name, var.lineno, var.col_offset,
                     var.type_annotation, var.scope)
                )

            # Save imports
            for imp in result.imports:
                cursor.execute(
                    """INSERT INTO imports
                       (file_id, module, lineno, names, is_from_import)
                       VALUES (?, ?, ?, ?, ?)""",
                    (file_id, imp.module, imp.lineno, json.dumps(imp.names), imp.is_from_import)
                )

            # Save data flow
            for flow in result.data_flow:
                cursor.execute(
                    """INSERT INTO data_flow
                       (file_id, variable, lineno, col_offset, flow_type, scope)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (file_id, flow.variable, flow.lineno, flow.col_offset,
                     flow.flow_type.value, flow.scope)
                )

    def get_functions(self, file_id: int) -> list[dict]:
        """Get all functions for a file."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM functions WHERE file_id = ?", (file_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_classes(self, file_id: int) -> list[dict]:
        """Get all classes for a file."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM classes WHERE file_id = ?", (file_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_imports(self, file_id: int) -> list[dict]:
        """Get all imports for a file."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM imports WHERE file_id = ?", (file_id,))
            return [dict(row) for row in cursor.fetchall()]

    def search_functions(self, name_pattern: str) -> list[dict]:
        """Search functions by name pattern."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT f.*, fi.filepath
                   FROM functions f
                   JOIN files fi ON f.file_id = fi.id
                   WHERE f.name LIKE ?""",
                (f"%{name_pattern}%",)
            )
            return [dict(row) for row in cursor.fetchall()]

    def search_classes(self, name_pattern: str) -> list[dict]:
        """Search classes by name pattern."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT c.*, fi.filepath
                   FROM classes c
                   JOIN files fi ON c.file_id = fi.id
                   WHERE c.name LIKE ?""",
                (f"%{name_pattern}%",)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_data_flow(self, file_id: int, variable: str = None) -> list[dict]:
        """Get data flow for a file, optionally filtered by variable."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if variable:
                cursor.execute(
                    "SELECT * FROM data_flow WHERE file_id = ? AND variable = ? ORDER BY lineno",
                    (file_id, variable)
                )
            else:
                cursor.execute(
                    "SELECT * FROM data_flow WHERE file_id = ? ORDER BY lineno",
                    (file_id,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def clear_project(self, project_id: int):
        """Clear all data for a project."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get file IDs
            cursor.execute("SELECT id FROM files WHERE project_id = ?", (project_id,))
            file_ids = [row[0] for row in cursor.fetchall()]

            # Delete related data
            for file_id in file_ids:
                cursor.execute("DELETE FROM functions WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM classes WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM variables WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM imports WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM data_flow WHERE file_id = ?", (file_id,))

            # Delete files
            cursor.execute("DELETE FROM files WHERE project_id = ?", (project_id,))

    def get_statistics(self, project_id: int) -> dict:
        """Get statistics for a project."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {"project_id": project_id}

            cursor.execute(
                "SELECT COUNT(*) FROM files WHERE project_id = ?",
                (project_id,)
            )
            stats["total_files"] = cursor.fetchone()[0]

            cursor.execute(
                """SELECT COUNT(*) FROM functions f
                   JOIN files fi ON f.file_id = fi.id
                   WHERE fi.project_id = ?""",
                (project_id,)
            )
            stats["total_functions"] = cursor.fetchone()[0]

            cursor.execute(
                """SELECT COUNT(*) FROM classes c
                   JOIN files fi ON c.file_id = fi.id
                   WHERE fi.project_id = ?""",
                (project_id,)
            )
            stats["total_classes"] = cursor.fetchone()[0]

            cursor.execute(
                """SELECT COUNT(*) FROM imports i
                   JOIN files fi ON i.file_id = fi.id
                   WHERE fi.project_id = ?""",
                (project_id,)
            )
            stats["total_imports"] = cursor.fetchone()[0]

            return stats

    # ============ PROJECT HISTORY METHODS ============

    def add_to_history(self, path: str, name: str = None) -> dict:
        """Add or update a project in history."""
        if not name:
            name = Path(path).name or path

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute("SELECT id, use_count FROM project_history WHERE path = ?", (path,))
            row = cursor.fetchone()

            if row:
                # Update existing
                cursor.execute("""
                    UPDATE project_history
                    SET name = ?, last_used = CURRENT_TIMESTAMP, use_count = use_count + 1
                    WHERE path = ?
                """, (name, path))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO project_history (path, name, last_used)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (path, name))

            return {"path": path, "name": name, "status": "updated" if row else "created"}

    def get_recent_projects(self, limit: int = 10) -> list:
        """Get recent projects ordered by last_used."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT path, name, is_favorite, last_used, use_count
                FROM project_history
                ORDER BY last_used DESC
                LIMIT ?
            """, (limit,))

            return [
                {
                    "path": row["path"],
                    "name": row["name"],
                    "is_favorite": bool(row["is_favorite"]),
                    "last_used": row["last_used"],
                    "use_count": row["use_count"],
                }
                for row in cursor.fetchall()
            ]

    def get_favorite_projects(self) -> list:
        """Get favorite projects."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT path, name, last_used, use_count
                FROM project_history
                WHERE is_favorite = TRUE
                ORDER BY name
            """)

            return [
                {
                    "path": row["path"],
                    "name": row["name"],
                    "is_favorite": True,
                    "last_used": row["last_used"],
                    "use_count": row["use_count"],
                }
                for row in cursor.fetchall()
            ]

    def toggle_favorite(self, path: str) -> dict:
        """Toggle favorite status for a project."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT is_favorite FROM project_history WHERE path = ?", (path,))
            row = cursor.fetchone()

            if not row:
                return {"error": "Project not found in history"}

            new_status = not row["is_favorite"]
            cursor.execute(
                "UPDATE project_history SET is_favorite = ? WHERE path = ?",
                (new_status, path)
            )

            return {"path": path, "is_favorite": new_status}

    def remove_from_history(self, path: str) -> dict:
        """Remove a project from history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM project_history WHERE path = ?", (path,))

            return {"path": path, "removed": cursor.rowcount > 0}
