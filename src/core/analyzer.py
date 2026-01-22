"""
HyperMatrix v2026 - Code Analyzer
Orchestrates all parsers to analyze source code files.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from enum import Enum

from ..parsers import (
    PythonParser,
    JavaScriptParser,
    MarkdownParser,
    JSONParser,
    ParseResult,
    JSParseResult,
    MDParseResult,
    JSONParseResult,
)


class FileType(Enum):
    """Supported file types."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    MARKDOWN = "markdown"
    JSON = "json"
    UNKNOWN = "unknown"


@dataclass
class AnalysisResult:
    """Result of analyzing a file."""
    filepath: str
    file_type: FileType
    python_result: Optional[ParseResult] = None
    js_result: Optional[JSParseResult] = None
    md_result: Optional[MDParseResult] = None
    json_result: Optional[JSONParseResult] = None
    error: Optional[str] = None


@dataclass
class ProjectAnalysis:
    """Result of analyzing an entire project."""
    root_path: str
    files: list[AnalysisResult] = field(default_factory=list)
    total_files: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_imports: int = 0
    errors: list[str] = field(default_factory=list)


class Analyzer:
    """Orchestrator that uses all parsers to analyze code."""

    EXTENSION_MAP = {
        ".py": FileType.PYTHON,
        ".js": FileType.JAVASCRIPT,
        ".jsx": FileType.JAVASCRIPT,
        ".ts": FileType.TYPESCRIPT,
        ".tsx": FileType.TYPESCRIPT,
        ".md": FileType.MARKDOWN,
        ".markdown": FileType.MARKDOWN,
        ".json": FileType.JSON,
    }

    IGNORE_DIRS = {
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }

    def __init__(self):
        self.python_parser = PythonParser()
        self.js_parser = JavaScriptParser()
        self.md_parser = MarkdownParser()
        self.json_parser = JSONParser()

    def detect_file_type(self, filepath: str) -> FileType:
        """Detect file type from extension."""
        ext = Path(filepath).suffix.lower()
        return self.EXTENSION_MAP.get(ext, FileType.UNKNOWN)

    def analyze_file(self, filepath: str) -> AnalysisResult:
        """Analyze a single file."""
        file_type = self.detect_file_type(filepath)

        result = AnalysisResult(
            filepath=filepath,
            file_type=file_type,
        )

        try:
            if file_type == FileType.PYTHON:
                result.python_result = self.python_parser.parse_file(filepath)

            elif file_type in (FileType.JAVASCRIPT, FileType.TYPESCRIPT):
                result.js_result = self.js_parser.parse_file(filepath)

            elif file_type == FileType.MARKDOWN:
                result.md_result = self.md_parser.parse_file(filepath)

            elif file_type == FileType.JSON:
                result.json_result = self.json_parser.parse_file(filepath)

        except Exception as e:
            result.error = str(e)

        return result

    def analyze_directory(
        self,
        directory: str,
        recursive: bool = True,
        extensions: Optional[list[str]] = None,
    ) -> ProjectAnalysis:
        """Analyze all files in a directory."""
        project = ProjectAnalysis(root_path=directory)
        directory = Path(directory)

        if not directory.exists():
            project.errors.append(f"Directory not found: {directory}")
            return project

        files_to_analyze = self._collect_files(directory, recursive, extensions)
        project.total_files = len(files_to_analyze)

        for filepath in files_to_analyze:
            result = self.analyze_file(str(filepath))
            project.files.append(result)

            if result.error:
                project.errors.append(f"{filepath}: {result.error}")
            else:
                self._update_totals(project, result)

        return project

    def _collect_files(
        self,
        directory: Path,
        recursive: bool,
        extensions: Optional[list[str]],
    ) -> list[Path]:
        """Collect files to analyze."""
        files = []

        if recursive:
            for root, dirs, filenames in os.walk(directory):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

                for filename in filenames:
                    filepath = Path(root) / filename
                    if self._should_include(filepath, extensions):
                        files.append(filepath)
        else:
            for filepath in directory.iterdir():
                if filepath.is_file() and self._should_include(filepath, extensions):
                    files.append(filepath)

        return sorted(files)

    def _should_include(
        self,
        filepath: Path,
        extensions: Optional[list[str]],
    ) -> bool:
        """Check if file should be included in analysis."""
        ext = filepath.suffix.lower()

        if extensions:
            return ext in extensions

        return ext in self.EXTENSION_MAP

    def _update_totals(self, project: ProjectAnalysis, result: AnalysisResult):
        """Update project totals from analysis result."""
        if result.python_result:
            project.total_functions += len(result.python_result.functions)
            project.total_classes += len(result.python_result.classes)
            project.total_imports += len(result.python_result.imports)

        elif result.js_result:
            project.total_functions += len(result.js_result.functions)
            project.total_classes += len(result.js_result.classes)
            project.total_imports += len(result.js_result.imports)

    def get_summary(self, project: ProjectAnalysis) -> dict:
        """Get analysis summary."""
        return {
            "root_path": project.root_path,
            "total_files": project.total_files,
            "total_functions": project.total_functions,
            "total_classes": project.total_classes,
            "total_imports": project.total_imports,
            "errors": len(project.errors),
            "files_by_type": self._count_by_type(project),
        }

    def _count_by_type(self, project: ProjectAnalysis) -> dict:
        """Count files by type."""
        counts = {}
        for result in project.files:
            type_name = result.file_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts
