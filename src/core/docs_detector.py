"""
HyperMatrix v2026 - Documentation Detector
Automatically detects and categorizes documentation files in projects.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Documentation patterns to detect
DOCS_PATTERNS = [
    "*.md", "*.txt", "*.rst", "*.adoc",
    "README*", "CHANGELOG*", "HISTORY*", "NEWS*",
    "LICENSE*", "CONTRIBUTING*", "AUTHORS*",
    "docs/**/*", "doc/**/*", "documentation/**/*",
    "notes/**/*", "bitacora*", "bitácora*",
    "*.pdf", "*.doc", "*.docx", "*.odt",
    "INSTALL*", "UPGRADE*", "TODO*", "ROADMAP*",
]

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", ".svn", ".hg", "__pycache__",
    "venv", ".venv", "env", ".env", "dist", "build",
    ".next", ".nuxt", "coverage", ".pytest_cache",
    "vendor", "packages", ".idea", ".vscode",
}

# File patterns to always skip
SKIP_PATTERNS = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "composer.lock",
}


@dataclass
class DocumentInfo:
    """Information about a detected document."""
    filepath: str
    filename: str
    doc_type: str
    size_bytes: int
    modified_at: str
    title: Optional[str] = None
    preview: Optional[str] = None
    linked: bool = False


@dataclass
class DocsDetectionResult:
    """Result of documentation detection."""
    project_path: str
    documents: List[DocumentInfo] = field(default_factory=list)
    by_type: Dict[str, List[DocumentInfo]] = field(default_factory=dict)
    total_count: int = 0
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())


# Document type classification
DOC_TYPE_PATTERNS = {
    "readme": [r"^readme", r"^léeme", r"^leeme"],
    "changelog": [r"^changelog", r"^history", r"^news", r"^changes"],
    "license": [r"^license", r"^licence", r"^copying"],
    "contributing": [r"^contributing", r"^contribute"],
    "install": [r"^install", r"^setup", r"^getting.?started"],
    "api_doc": [r"^api", r"api\.md$", r"api\.rst$"],
    "bitacora": [r"bitacora", r"bitácora", r"logbook", r"journal"],
    "notes": [r"^notes?", r"^notas?", r"^apuntes?"],
    "todo": [r"^todo", r"^tareas?", r"^tasks?"],
    "roadmap": [r"^roadmap", r"^plan", r"^hoja.?de.?ruta"],
    "spec": [r"^spec", r"^requirement", r"^requisito", r"^design"],
    "manual": [r"^manual", r"^guide", r"^guía", r"^tutorial"],
}


def classify_document(filename: str) -> str:
    """Classify a document by its filename."""
    filename_lower = filename.lower()

    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower):
                return doc_type

    # Default classification by extension
    ext = Path(filename).suffix.lower()
    if ext in ('.md', '.rst', '.adoc'):
        return "documentation"
    elif ext in ('.pdf', '.doc', '.docx', '.odt'):
        return "document"
    elif ext == '.txt':
        return "text"

    return "other"


def extract_title_from_md(filepath: str) -> Optional[str]:
    """Extract title from a markdown file (first H1)."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith('# '):
                    return line[2:].strip()
                # Also check for underline style headers
                if line and not line.startswith('#'):
                    next_line = f.readline().strip()
                    if next_line and all(c == '=' for c in next_line):
                        return line
    except Exception:
        pass
    return None


def extract_preview(filepath: str, max_chars: int = 200) -> Optional[str]:
    """Extract a preview of the document content."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(max_chars + 100)  # Read a bit more to find good cut point

            # Clean up the content
            content = content.strip()

            # Skip title line if markdown
            if content.startswith('#'):
                lines = content.split('\n', 1)
                if len(lines) > 1:
                    content = lines[1].strip()

            # Truncate at word boundary
            if len(content) > max_chars:
                content = content[:max_chars]
                last_space = content.rfind(' ')
                if last_space > max_chars // 2:
                    content = content[:last_space]
                content += '...'

            return content if content else None
    except Exception:
        return None


def should_skip_path(path: Path) -> bool:
    """Check if a path should be skipped."""
    parts = path.parts

    # Skip if any part is in skip dirs
    for part in parts:
        if part in SKIP_DIRS:
            return True
        # Skip hidden directories
        if part.startswith('.') and part not in ('.', '..'):
            return True

    # Skip lock files and other patterns
    if path.name in SKIP_PATTERNS:
        return True

    return False


def detect_documentation(project_path: str, max_files: int = 500) -> DocsDetectionResult:
    """
    Detect documentation files in a project.

    Args:
        project_path: Root path of the project
        max_files: Maximum number of files to scan

    Returns:
        DocsDetectionResult with all detected documents
    """
    result = DocsDetectionResult(project_path=project_path)
    root = Path(project_path)

    if not root.exists() or not root.is_dir():
        logger.warning(f"Project path does not exist or is not a directory: {project_path}")
        return result

    documents: List[DocumentInfo] = []
    seen_paths: Set[str] = set()
    files_scanned = 0

    # Extensions to look for
    doc_extensions = {'.md', '.txt', '.rst', '.adoc', '.pdf', '.doc', '.docx', '.odt'}

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Remove skip directories from dirnames to prevent walking into them
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]

            rel_dir = Path(dirpath).relative_to(root)

            for filename in filenames:
                if files_scanned >= max_files:
                    break

                filepath = Path(dirpath) / filename

                # Skip if already seen
                str_path = str(filepath)
                if str_path in seen_paths:
                    continue
                seen_paths.add(str_path)

                # Check if this is a documentation file
                is_doc = False

                # Check by extension
                ext = filepath.suffix.lower()
                if ext in doc_extensions:
                    is_doc = True

                # Check by name patterns
                name_lower = filename.lower()
                for pattern in ['readme', 'changelog', 'license', 'contributing',
                               'install', 'authors', 'history', 'news', 'todo',
                               'roadmap', 'bitacora', 'notes', 'manual', 'guide']:
                    if pattern in name_lower:
                        is_doc = True
                        break

                # Check if in docs directory
                if str(rel_dir).startswith(('docs', 'doc', 'documentation', 'notes')):
                    if ext in doc_extensions or ext == '':
                        is_doc = True

                if not is_doc:
                    continue

                files_scanned += 1

                try:
                    stat = filepath.stat()

                    # Get title and preview for markdown files
                    title = None
                    preview = None
                    if ext in ('.md', '.txt', '.rst'):
                        title = extract_title_from_md(str(filepath))
                        preview = extract_preview(str(filepath))

                    doc_info = DocumentInfo(
                        filepath=str(filepath.relative_to(root)),
                        filename=filename,
                        doc_type=classify_document(filename),
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        title=title,
                        preview=preview,
                    )

                    documents.append(doc_info)

                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not stat file {filepath}: {e}")
                    continue

            if files_scanned >= max_files:
                break

    except Exception as e:
        logger.error(f"Error detecting documentation: {e}")

    # Organize by type
    by_type: Dict[str, List[DocumentInfo]] = {}
    for doc in documents:
        if doc.doc_type not in by_type:
            by_type[doc.doc_type] = []
        by_type[doc.doc_type].append(doc)

    # Sort documents: readme first, then by type, then by name
    type_priority = ['readme', 'changelog', 'license', 'contributing', 'install',
                    'api_doc', 'manual', 'spec', 'roadmap', 'bitacora', 'notes',
                    'todo', 'documentation', 'document', 'text', 'other']

    def sort_key(doc: DocumentInfo) -> tuple:
        try:
            priority = type_priority.index(doc.doc_type)
        except ValueError:
            priority = len(type_priority)
        return (priority, doc.filename.lower())

    documents.sort(key=sort_key)

    result.documents = documents
    result.by_type = by_type
    result.total_count = len(documents)

    logger.info(f"Detected {len(documents)} documentation files in {project_path}")

    return result


def get_docs_summary(result: DocsDetectionResult) -> Dict:
    """Get a summary of detected documentation."""
    return {
        "project_path": result.project_path,
        "total_documents": result.total_count,
        "by_type": {
            doc_type: len(docs)
            for doc_type, docs in result.by_type.items()
        },
        "has_readme": any(d.doc_type == "readme" for d in result.documents),
        "has_changelog": any(d.doc_type == "changelog" for d in result.documents),
        "has_license": any(d.doc_type == "license" for d in result.documents),
        "detected_at": result.detected_at,
    }
