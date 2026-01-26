"""
HyperMatrix v2026 - Deep Analyzer
Analyzes components across multiple project versions.
Provides rich context for AI assistant.
"""

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from glob import glob

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DB_PATH = os.path.join(DATA_DIR, "hypermatrix.db")
PROJECTS_DIR = "/projects"


class DeepAnalyzer:
    """
    Analyzes components (parsers, modules, classes) across project versions.
    Extracts docstrings, comments, structure, and compares versions.
    """

    def __init__(self):
        self.db_path = DB_PATH
        self.projects_dir = PROJECTS_DIR

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_component_files(self, component_name: str) -> List[Dict[str, Any]]:
        """
        Find all files related to a component across all project versions.
        """
        files = []

        # Search in filesystem
        patterns = [
            f"**/*{component_name}*.py",
            f"**/*{component_name.replace('_', '')}*.py",
        ]

        for pattern in patterns:
            search_path = os.path.join(self.projects_dir, pattern)
            for filepath in glob(search_path, recursive=True):
                if '__pycache__' in filepath or '.pyc' in filepath:
                    continue

                # Extract version from path
                version = self._extract_version(filepath)

                files.append({
                    "path": filepath,
                    "filename": os.path.basename(filepath),
                    "version": version,
                    "relative_path": filepath.replace(self.projects_dir, ""),
                })

        # Sort by version
        files.sort(key=lambda x: x.get("version", ""))
        return files

    def _extract_version(self, filepath: str) -> str:
        """Extract version from filepath like v11.30, v10.2, etc."""
        # Common patterns
        patterns = [
            r'v(\d+\.\d+)',           # v11.30, v10.2
            r'-v(\d+\.\d+)',          # -v11.1
            r'v(\d+)',                # v11
            r'_v(\d+\.\d+)',          # _v11.20
        ]

        for pattern in patterns:
            match = re.search(pattern, filepath, re.IGNORECASE)
            if match:
                return f"v{match.group(1)}"

        # Try to extract from folder names
        parts = filepath.split(os.sep)
        for part in parts:
            if 'v11' in part.lower() or 'v10' in part.lower():
                return part

        return "unknown"

    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """
        Deep analyze a single file: docstring, classes, methods, comments.
        """
        result = {
            "path": filepath,
            "filename": os.path.basename(filepath),
            "exists": False,
            "lines": 0,
            "docstring": "",
            "classes": [],
            "functions": [],
            "key_comments": [],
            "imports": [],
            "supports_gen1": False,
            "supports_gen2": False,
        }

        if not os.path.exists(filepath):
            return result

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            result["error"] = str(e)
            return result

        result["exists"] = True
        result["lines"] = len(lines)

        # Extract module docstring
        docstring_match = re.search(r'^"""(.*?)"""', content, re.DOTALL)
        if docstring_match:
            result["docstring"] = docstring_match.group(1).strip()[:500]

        # Extract classes
        class_matches = re.findall(r'class\s+(\w+)\s*(?:\(([^)]*)\))?:', content)
        for name, bases in class_matches:
            result["classes"].append({
                "name": name,
                "bases": bases.strip() if bases else "",
            })

        # Extract functions/methods
        func_matches = re.findall(r'def\s+(\w+)\s*\(([^)]*)\)', content)
        for name, params in func_matches:
            result["functions"].append({
                "name": name,
                "params": params.strip()[:100],
            })

        # Extract key comments (structure comments like BLOQUE A, Offset, etc.)
        key_patterns = [
            r'#\s*(BLOQUE\s+\w+.*)',
            r'#\s*(Offset\s+\d+.*)',
            r'#\s*(\d+\s*bytes?.*)',
            r'#\s*(Gen\d+.*)',
        ]
        for pattern in key_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            result["key_comments"].extend(matches[:10])

        # Extract imports
        import_matches = re.findall(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', content, re.MULTILINE)
        for from_module, imports in import_matches[:20]:
            result["imports"].append(f"from {from_module} import {imports}" if from_module else f"import {imports}")

        # Check Gen1/Gen2 support
        content_lower = content.lower()
        result["supports_gen1"] = 'gen1' in content_lower or '_parse_gen1' in content_lower or 'generation 1' in content_lower
        result["supports_gen2"] = 'gen2' in content_lower or '_parse_gen2' in content_lower or 'generation 2' in content_lower

        return result

    def analyze_component(self, component_name: str) -> Dict[str, Any]:
        """
        Full analysis of a component across all versions.
        Returns structured data ready for AI to format.
        """
        result = {
            "component": component_name,
            "files_found": 0,
            "versions": [],
            "summary": "",
            "structure": [],
            "comparison": [],
        }

        # Find all related files
        files = self.find_component_files(component_name)
        result["files_found"] = len(files)

        if not files:
            result["summary"] = f"No se encontraron archivos para '{component_name}'"
            return result

        # Analyze each file
        analyzed_files = []
        for file_info in files:
            analysis = self.analyze_file(file_info["path"])
            analysis["version"] = file_info["version"]
            analysis["relative_path"] = file_info["relative_path"]
            analyzed_files.append(analysis)

        # Build versions table
        for af in analyzed_files:
            if af["exists"]:
                result["versions"].append({
                    "version": af["version"],
                    "path": af["relative_path"],
                    "lines": af["lines"],
                    "classes": len(af["classes"]),
                    "functions": len(af["functions"]),
                    "gen1": "✅" if af["supports_gen1"] else "❌",
                    "gen2": "✅" if af["supports_gen2"] else "❌",
                })

        # Extract common docstring (from most complete version)
        best_file = max(analyzed_files, key=lambda x: x["lines"]) if analyzed_files else None
        if best_file and best_file.get("docstring"):
            result["summary"] = best_file["docstring"]

        # Extract structure from key comments
        if best_file and best_file.get("key_comments"):
            result["structure"] = best_file["key_comments"][:15]

        # Build comparison (functions across versions)
        all_functions = set()
        for af in analyzed_files:
            for func in af.get("functions", []):
                all_functions.add(func["name"])

        for func_name in sorted(all_functions):
            func_versions = []
            for af in analyzed_files:
                has_func = any(f["name"] == func_name for f in af.get("functions", []))
                if has_func:
                    func_versions.append(af["version"])

            if len(func_versions) < len(analyzed_files):  # Not in all versions
                result["comparison"].append({
                    "function": func_name,
                    "in_versions": func_versions,
                })

        return result

    def format_analysis_for_ai(self, analysis: Dict[str, Any]) -> str:
        """
        Format the analysis as a markdown string for AI context.
        """
        lines = []

        component = analysis.get("component", "Unknown")
        lines.append(f"## Análisis del componente: {component}")
        lines.append("")

        # Summary
        if analysis.get("summary"):
            lines.append("### Descripción")
            lines.append(analysis["summary"])
            lines.append("")

        # Versions table
        versions = analysis.get("versions", [])
        if versions:
            lines.append(f"### Versiones encontradas ({len(versions)})")
            lines.append("")
            lines.append("| Versión | Líneas | Clases | Funciones | Gen1 | Gen2 |")
            lines.append("|---------|--------|--------|-----------|------|------|")
            for v in versions:
                lines.append(f"| {v['version']} | {v['lines']} | {v['classes']} | {v['functions']} | {v['gen1']} | {v['gen2']} |")
            lines.append("")

        # Structure
        structure = analysis.get("structure", [])
        if structure:
            lines.append("### Estructura del componente")
            for comment in structure:
                lines.append(f"- {comment}")
            lines.append("")

        # Comparison (functions that differ)
        comparison = analysis.get("comparison", [])
        if comparison:
            lines.append("### Diferencias entre versiones")
            lines.append("Funciones que NO están en todas las versiones:")
            for comp in comparison[:10]:
                lines.append(f"- `{comp['function']}`: solo en {', '.join(comp['in_versions'])}")
            lines.append("")

        # File paths
        if versions:
            lines.append("### Rutas de archivos")
            for v in versions[:5]:
                lines.append(f"- **{v['version']}**: `{v['path']}`")

        return "\n".join(lines)


def analyze_component(component_name: str) -> str:
    """
    Convenience function for analyzing a component.
    Returns formatted markdown ready for AI.
    """
    analyzer = DeepAnalyzer()
    analysis = analyzer.analyze_component(component_name)
    return analyzer.format_analysis_for_ai(analysis)


def get_deep_analyzer() -> DeepAnalyzer:
    """Get a DeepAnalyzer instance."""
    return DeepAnalyzer()
