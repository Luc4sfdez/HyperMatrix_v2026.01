"""
HyperMatrix v2026 - Phase 2: Analysis
Analyzes all files using parsers, extracts DNA, and populates database.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from enum import Enum

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from .phase1_discovery import FileMetadata, DiscoveryResult
from .phase1_5_deduplication import DeduplicationResult
from ..parsers import (
    PythonParser,
    JavaScriptParser,
    MarkdownParser,
    JSONParser,
    HTMLParser,
    CSSParser,
    ParseResult,
    JSParseResult,
    MDParseResult,
    JSONParseResult,
    HTMLParseResult,
    CSSParseResult,
    DataFlowType,
)
from ..core.db_manager import DBManager

# Embedding engine for semantic search (lazy loaded)
_embedding_engine = None

def get_embedding_engine():
    """Get the embedding engine (lazy initialization)."""
    global _embedding_engine
    if _embedding_engine is None:
        try:
            from ..embeddings import get_embedding_engine as _get_engine
            _embedding_engine = _get_engine()
        except ImportError as e:
            logger.warning(f"Embeddings not available: {e}")
            _embedding_engine = None
        except Exception as e:
            logger.warning(f"Failed to initialize embedding engine: {e}")
            _embedding_engine = None
    return _embedding_engine

# Configure logging
logger = logging.getLogger(__name__)


class DNAType(Enum):
    """Type of code DNA element."""
    DATA_FLOW = "data_flow"
    LOGIC_SEQUENCE = "logic_sequence"
    CALL_GRAPH = "call_graph"
    IMPORT_CHAIN = "import_chain"


@dataclass
class DataFlowDNA:
    """Data flow DNA - tracks variable lifecycle."""
    variable: str
    operations: list[tuple[int, str]]  # (lineno, READ/WRITE)
    scope: str
    first_write: Optional[int] = None
    last_read: Optional[int] = None


@dataclass
class LogicSequenceDNA:
    """Logic sequence DNA - function call order and control flow."""
    function_calls: list[tuple[int, str]]  # (lineno, function_name)
    control_structures: list[tuple[int, str]]  # (lineno, if/for/while/try)
    return_points: list[int]


@dataclass
class FileDNA:
    """Complete DNA profile for a file."""
    filepath: str
    data_flows: list[DataFlowDNA] = field(default_factory=list)
    logic_sequence: Optional[LogicSequenceDNA] = None
    complexity_score: float = 0.0
    fingerprint: str = ""


@dataclass
class AnalysisResult:
    """Result of analyzing a single file."""
    filepath: str
    file_type: str
    success: bool = True
    error: Optional[str] = None
    parse_result: Any = None
    dna: Optional[FileDNA] = None
    analysis_time: float = 0.0


@dataclass
class Phase2Result:
    """Result of the complete analysis phase."""
    total_files: int = 0
    analyzed_files: int = 0
    failed_files: int = 0
    skipped_duplicates: int = 0
    results: list[AnalysisResult] = field(default_factory=list)
    dna_profiles: list[FileDNA] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_functions: int = 0
    total_classes: int = 0
    total_imports: int = 0
    analysis_duration: float = 0.0


class Phase2Analysis:
    """Phase 2: Code analysis and DNA extraction."""

    EXTENSION_TO_TYPE = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".md": "markdown",
        ".markdown": "markdown",
        ".json": "json",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "css",
        ".sass": "css",
        ".less": "css",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".txt": "text",
        ".rst": "text",
        ".log": "text",
        ".pdf": "pdf",
    }

    def __init__(
        self,
        db_manager: Optional[DBManager] = None,
        skip_duplicates: bool = True,
        extract_dna: bool = True,
        index_embeddings: bool = True,
    ):
        self.db_manager = db_manager
        self.skip_duplicates = skip_duplicates
        self.extract_dna_flag = extract_dna
        self.index_embeddings = index_embeddings

        # Initialize parsers
        self.python_parser = PythonParser()
        self.js_parser = JavaScriptParser()
        self.md_parser = MarkdownParser()
        self.json_parser = JSONParser()
        self.html_parser = HTMLParser()
        self.css_parser = CSSParser()

        self.result = Phase2Result()
        self._dedup_result: Optional[DeduplicationResult] = None
        self._project_id: Optional[int] = None
        self._indexed_count = 0  # Track embedding indexing

        logger.info("Phase2Analysis initialized (embeddings=%s)", index_embeddings)

    def analyze_all_files(
        self,
        discovery_result: DiscoveryResult,
        dedup_result: Optional[DeduplicationResult] = None,
        project_name: str = "default",
    ) -> Phase2Result:
        """
        Analyze all discovered files.

        Args:
            discovery_result: Result from Phase1Discovery
            dedup_result: Optional result from Phase1_5Deduplication
            project_name: Name for the project in database

        Returns:
            Phase2Result with all analysis results
        """
        start_time = datetime.now()
        self.result = Phase2Result()
        self._dedup_result = dedup_result

        logger.info(f"Starting analysis of {len(discovery_result.files)} files")

        # Create project in database if db_manager exists
        if self.db_manager:
            self._project_id = self.db_manager.create_project(
                project_name,
                discovery_result.root_path
            )
            logger.info(f"Created project in database: ID={self._project_id}")

        # Filter files to analyze
        files_to_analyze = self._filter_files(discovery_result.files)
        self.result.total_files = len(discovery_result.files)
        self.result.skipped_duplicates = len(discovery_result.files) - len(files_to_analyze)

        logger.info(f"Analyzing {len(files_to_analyze)} files "
                   f"(skipped {self.result.skipped_duplicates} duplicates)")

        # Process files with progress bar
        iterator = tqdm(files_to_analyze, desc="Analyzing files", unit="file") if TQDM_AVAILABLE else files_to_analyze

        for file_meta in iterator:
            try:
                analysis_result = self._analyze_file(file_meta)
                self.result.results.append(analysis_result)

                if analysis_result.success:
                    self.result.analyzed_files += 1
                    self._update_totals(analysis_result)

                    if analysis_result.dna:
                        self.result.dna_profiles.append(analysis_result.dna)
                else:
                    self.result.failed_files += 1
                    if analysis_result.error:
                        self.result.errors.append(f"{file_meta.filepath}: {analysis_result.error}")

            except Exception as e:
                error = f"Unexpected error analyzing {file_meta.filepath}: {e}"
                logger.error(error)
                self.result.errors.append(error)
                self.result.failed_files += 1

        self.result.analysis_duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Analysis complete: {self.result.analyzed_files} succeeded, "
                   f"{self.result.failed_files} failed, "
                   f"{self._indexed_count} indexed to embeddings, "
                   f"{self.result.analysis_duration:.2f}s")

        return self.result

    def _filter_files(self, files: list[FileMetadata]) -> list[FileMetadata]:
        """Filter files based on deduplication result and supported types."""
        filtered = []

        for file_meta in files:
            # Skip unsupported file types silently
            file_type = self._get_file_type(file_meta.extension)
            if file_type == "unknown":
                logger.debug(f"Skipping unsupported type: {file_meta.filepath}")
                continue

            # Skip duplicates if enabled
            if self.skip_duplicates and self._dedup_result:
                if file_meta.filepath in self._dedup_result.original_map:
                    logger.debug(f"Skipping duplicate: {file_meta.filepath}")
                    continue

            filtered.append(file_meta)

        return filtered

    def _analyze_file(self, file_meta: FileMetadata) -> AnalysisResult:
        """Analyze a single file."""
        start_time = datetime.now()
        file_type = self._get_file_type(file_meta.extension)

        result = AnalysisResult(
            filepath=file_meta.filepath,
            file_type=file_type,
        )

        try:
            # Parse based on file type
            if file_type == "python":
                parse_result = self.python_parser.parse_file(file_meta.filepath)
                result.parse_result = parse_result
                logger.debug(f"Parsed Python: {file_meta.filename} - "
                           f"{len(parse_result.functions)} functions, "
                           f"{len(parse_result.classes)} classes")

            elif file_type in ("javascript", "typescript"):
                parse_result = self.js_parser.parse_file(file_meta.filepath)
                result.parse_result = parse_result
                logger.debug(f"Parsed JS/TS: {file_meta.filename} - "
                           f"{len(parse_result.functions)} functions")

            elif file_type == "markdown":
                parse_result = self.md_parser.parse_file(file_meta.filepath)
                result.parse_result = parse_result
                logger.debug(f"Parsed Markdown: {file_meta.filename} - "
                           f"{len(parse_result.headings)} headings")

            elif file_type == "json":
                parse_result = self.json_parser.parse_file(file_meta.filepath)
                result.parse_result = parse_result
                logger.debug(f"Parsed JSON: {file_meta.filename} - "
                           f"{len(parse_result.keys)} keys")

            elif file_type == "html":
                parse_result = self.html_parser.parse_file(file_meta.filepath)
                result.parse_result = parse_result
                logger.debug(f"Parsed HTML: {file_meta.filename} - "
                           f"{parse_result.tag_count} tags, "
                           f"{len(parse_result.scripts)} scripts")

            elif file_type == "css":
                parse_result = self.css_parser.parse_file(file_meta.filepath)
                result.parse_result = parse_result
                logger.debug(f"Parsed CSS: {file_meta.filename} - "
                           f"{parse_result.selector_count} selectors, "
                           f"{parse_result.property_count} properties")

            elif file_type == "yaml":
                # YAML files are read as text for now, no specific parser
                result.parse_result = None
                logger.debug(f"Scanned YAML: {file_meta.filename}")

            elif file_type == "text":
                # Text files (txt, rst, log) - read content for embedding
                result.parse_result = None
                logger.debug(f"Scanned text: {file_meta.filename}")

            elif file_type == "pdf":
                # PDF files - extract text for embedding
                result.parse_result = None
                logger.debug(f"Scanned PDF: {file_meta.filename}")

            else:
                result.success = False
                result.error = f"Unsupported file type: {file_type}"
                return result

            # Extract DNA
            if self.extract_dna_flag and result.parse_result:
                result.dna = self.extract_dna(file_meta.filepath, result.parse_result)

            # Populate database
            if self.db_manager and result.success:
                self.populate_db(file_meta, result)

            # Index to embedding engine for semantic search
            if self.index_embeddings and result.success:
                self._index_to_embeddings(file_meta, result)

            result.analysis_time = (datetime.now() - start_time).total_seconds()

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.warning(f"Failed to analyze {file_meta.filepath}: {e}")

        return result

    def _get_file_type(self, extension: str) -> str:
        """Get file type from extension."""
        return self.EXTENSION_TO_TYPE.get(extension.lower(), "unknown")

    def extract_dna(self, filepath: str, parse_result: Any) -> Optional[FileDNA]:
        """
        Extract DNA profile from parse result.

        DNA includes:
        - Data flow patterns (READ/WRITE sequences)
        - Logic sequence (function calls, control flow)

        Args:
            filepath: Path to the analyzed file
            parse_result: Result from parser

        Returns:
            FileDNA profile
        """
        dna = FileDNA(filepath=filepath)

        try:
            if isinstance(parse_result, ParseResult):
                # Python DNA extraction
                dna.data_flows = self._extract_python_data_flow(parse_result)
                dna.logic_sequence = self._extract_python_logic_sequence(parse_result)
                dna.complexity_score = self._calculate_complexity(parse_result)

            elif isinstance(parse_result, JSParseResult):
                # JavaScript DNA extraction
                dna.data_flows = self._extract_js_data_flow(parse_result)
                dna.complexity_score = self._calculate_js_complexity(parse_result)

            # Generate fingerprint
            dna.fingerprint = self._generate_fingerprint(dna)

            logger.debug(f"Extracted DNA for {Path(filepath).name}: "
                        f"{len(dna.data_flows)} data flows, "
                        f"complexity={dna.complexity_score:.2f}")

        except Exception as e:
            logger.warning(f"Failed to extract DNA for {filepath}: {e}")

        return dna

    def _extract_python_data_flow(self, parse_result: ParseResult) -> list[DataFlowDNA]:
        """Extract data flow DNA from Python parse result."""
        flows_by_var: dict[str, DataFlowDNA] = {}

        for flow in parse_result.data_flow:
            var_key = f"{flow.scope}:{flow.variable}"

            if var_key not in flows_by_var:
                flows_by_var[var_key] = DataFlowDNA(
                    variable=flow.variable,
                    operations=[],
                    scope=flow.scope,
                )

            dna = flows_by_var[var_key]
            dna.operations.append((flow.lineno, flow.flow_type.value))

            if flow.flow_type == DataFlowType.WRITE:
                if dna.first_write is None:
                    dna.first_write = flow.lineno
            else:
                dna.last_read = flow.lineno

        return list(flows_by_var.values())

    def _extract_js_data_flow(self, parse_result: JSParseResult) -> list[DataFlowDNA]:
        """Extract data flow DNA from JavaScript parse result."""
        flows_by_var: dict[str, DataFlowDNA] = {}

        for flow in parse_result.data_flow:
            var_key = f"{flow.scope}:{flow.variable}"

            if var_key not in flows_by_var:
                flows_by_var[var_key] = DataFlowDNA(
                    variable=flow.variable,
                    operations=[],
                    scope=flow.scope,
                )

            dna = flows_by_var[var_key]
            dna.operations.append((flow.lineno, flow.flow_type.value))

        return list(flows_by_var.values())

    def _extract_python_logic_sequence(self, parse_result: ParseResult) -> LogicSequenceDNA:
        """Extract logic sequence DNA from Python parse result."""
        # This is a simplified version - full implementation would use AST
        function_calls = []
        control_structures = []
        return_points = []

        # Track function definitions as potential call targets
        for func in parse_result.functions:
            function_calls.append((func.lineno, f"def:{func.name}"))

        return LogicSequenceDNA(
            function_calls=function_calls,
            control_structures=control_structures,
            return_points=return_points,
        )

    def _calculate_complexity(self, parse_result: ParseResult) -> float:
        """Calculate complexity score for Python code."""
        score = 0.0

        # Functions contribute to complexity
        score += len(parse_result.functions) * 1.0

        # Classes add complexity
        score += len(parse_result.classes) * 2.0

        # Data flow complexity
        score += len(parse_result.data_flow) * 0.1

        # Import complexity
        score += len(parse_result.imports) * 0.5

        return round(score, 2)

    def _calculate_js_complexity(self, parse_result: JSParseResult) -> float:
        """Calculate complexity score for JavaScript code."""
        score = 0.0

        score += len(parse_result.functions) * 1.0
        score += len(parse_result.classes) * 2.0
        score += len(parse_result.data_flow) * 0.1
        score += len(parse_result.imports) * 0.5

        return round(score, 2)

    def _generate_fingerprint(self, dna: FileDNA) -> str:
        """Generate a fingerprint hash for the DNA profile."""
        import hashlib

        # Create string representation of DNA
        parts = []

        for flow in dna.data_flows:
            ops = ",".join(f"{op[1]}" for op in flow.operations[:10])
            parts.append(f"{flow.variable}:{ops}")

        parts.append(f"complexity:{dna.complexity_score}")

        content = "|".join(sorted(parts))
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def populate_db(self, file_meta: FileMetadata, analysis_result: AnalysisResult):
        """
        Populate database with analysis results.

        Args:
            file_meta: File metadata from discovery
            analysis_result: Result from analysis
        """
        if not self.db_manager or not self._project_id:
            return

        try:
            # Save file record
            file_id = self.db_manager.save_file(
                self._project_id,
                file_meta.filepath,
                analysis_result.file_type,
                file_meta.hash_sha256,
            )

            # Save parse results
            if isinstance(analysis_result.parse_result, ParseResult):
                self.db_manager.save_python_result(file_id, analysis_result.parse_result)
                logger.debug(f"Saved to DB: {file_meta.filename} (ID={file_id})")

        except Exception as e:
            logger.error(f"Failed to save to database: {file_meta.filepath}: {e}")

    def _index_to_embeddings(self, file_meta: FileMetadata, analysis_result: AnalysisResult):
        """
        Index file content to embedding engine for semantic search.

        Indexes:
        - Full file content
        - Individual functions (for code files)
        - Individual classes (for code files)
        - Headings/sections (for markdown)

        Args:
            file_meta: File metadata from discovery
            analysis_result: Result from analysis
        """
        engine = get_embedding_engine()
        if not engine or not engine.is_available:
            return

        try:
            # Read file content
            content = self._read_file_content(file_meta.filepath)
            if not content:
                return

            # Prepare metadata
            base_metadata = {
                "filename": file_meta.filename,
                "extension": file_meta.extension,
                "file_type": analysis_result.file_type,
                "size": file_meta.size,
            }

            # Index full file
            if engine.index_file(file_meta.filepath, content, base_metadata):
                self._indexed_count += 1
                logger.debug(f"Indexed file: {file_meta.filename}")

            # Index individual code elements for more granular search
            pr = analysis_result.parse_result

            if isinstance(pr, ParseResult):
                # Index Python functions
                for func in pr.functions:
                    func_content = self._extract_function_content(content, func)
                    if func_content:
                        element_id = f"{file_meta.filepath}:function:{func.name}"
                        # Build metadata safely
                        func_meta = {"has_docstring": bool(getattr(func, 'docstring', None))}
                        if hasattr(func, 'params') and func.params:
                            func_meta["params"] = [getattr(p, 'name', str(p)) for p in func.params]
                        if hasattr(func, 'decorators'):
                            func_meta["decorators"] = func.decorators
                        engine.index_code_element(
                            element_id=element_id,
                            element_type="function",
                            name=func.name,
                            content=func_content,
                            file_path=file_meta.filepath,
                            lineno=func.lineno,
                            metadata=func_meta
                        )

                # Index Python classes
                for cls in pr.classes:
                    cls_content = self._extract_class_content(content, cls)
                    if cls_content:
                        element_id = f"{file_meta.filepath}:class:{cls.name}"
                        # Build metadata safely
                        cls_meta = {"has_docstring": bool(getattr(cls, 'docstring', None))}
                        if hasattr(cls, 'bases'):
                            cls_meta["bases"] = cls.bases
                        if hasattr(cls, 'methods'):
                            cls_meta["method_count"] = len(cls.methods)
                        engine.index_code_element(
                            element_id=element_id,
                            element_type="class",
                            name=cls.name,
                            content=cls_content,
                            file_path=file_meta.filepath,
                            lineno=cls.lineno,
                            metadata=cls_meta
                        )

            elif isinstance(pr, JSParseResult):
                # Index JavaScript functions
                for func in pr.functions:
                    func_content = self._extract_function_content(content, func)
                    if func_content:
                        element_id = f"{file_meta.filepath}:function:{func.name}"
                        # Build metadata safely
                        func_meta = {}
                        if hasattr(func, 'is_async'):
                            func_meta["is_async"] = func.is_async
                        if hasattr(func, 'is_arrow'):
                            func_meta["is_arrow"] = func.is_arrow
                        engine.index_code_element(
                            element_id=element_id,
                            element_type="function",
                            name=func.name,
                            content=func_content,
                            file_path=file_meta.filepath,
                            lineno=func.lineno,
                            metadata=func_meta
                        )

            elif isinstance(pr, MDParseResult):
                # Index Markdown sections by heading
                for heading in pr.headings:
                    section_content = self._extract_section_content(content, heading, pr.headings)
                    if section_content and len(section_content) > 50:
                        element_id = f"{file_meta.filepath}:section:{heading.text[:50]}"
                        engine.index_code_element(
                            element_id=element_id,
                            element_type="section",
                            name=heading.text,
                            content=section_content,
                            file_path=file_meta.filepath,
                            lineno=heading.lineno,
                            metadata={
                                "level": heading.level,
                            }
                        )

        except Exception as e:
            logger.warning(f"Failed to index {file_meta.filepath} to embeddings: {e}")

    def _read_file_content(self, filepath: str, max_size: int = 500000) -> Optional[str]:
        """Read file content for embedding, with size limit."""
        try:
            path = Path(filepath)
            file_size = path.stat().st_size
            if file_size > max_size:
                logger.debug(f"File too large for embedding: {filepath}")
                return None

            # Handle PDF files specially
            if path.suffix.lower() == '.pdf':
                return self._extract_pdf_text(filepath)

            # Regular text files
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            logger.debug(f"Could not read file for embedding: {filepath}: {e}")
            return None

    def _extract_pdf_text(self, filepath: str) -> Optional[str]:
        """Extract text content from a PDF file."""
        try:
            # Try PyMuPDF (fitz) first - faster and more reliable
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(filepath)
                text_parts = []
                for page_num in range(min(doc.page_count, 50)):  # Limit to 50 pages
                    page = doc[page_num]
                    text_parts.append(page.get_text())
                doc.close()
                text = "\n".join(text_parts)
                logger.debug(f"Extracted {len(text)} chars from PDF using PyMuPDF: {filepath}")
                return text[:50000] if text else None  # Limit to 50k chars
            except ImportError:
                pass

            # Fallback to pypdf
            try:
                from pypdf import PdfReader
                reader = PdfReader(filepath)
                text_parts = []
                for page_num, page in enumerate(reader.pages[:50]):  # Limit to 50 pages
                    text_parts.append(page.extract_text() or "")
                text = "\n".join(text_parts)
                logger.debug(f"Extracted {len(text)} chars from PDF using pypdf: {filepath}")
                return text[:50000] if text else None
            except ImportError:
                logger.debug("No PDF library available (install PyMuPDF or pypdf)")
                return None

        except Exception as e:
            logger.debug(f"Could not extract PDF text from {filepath}: {e}")
            return None

    def _extract_function_content(self, content: str, func) -> Optional[str]:
        """Extract function source code from file content."""
        try:
            lines = content.split('\n')
            start = func.lineno - 1
            end = getattr(func, 'end_lineno', start + 20)
            if end is None:
                end = min(start + 50, len(lines))
            return '\n'.join(lines[start:end])
        except Exception:
            return None

    def _extract_class_content(self, content: str, cls) -> Optional[str]:
        """Extract class source code from file content."""
        try:
            lines = content.split('\n')
            start = cls.lineno - 1
            end = getattr(cls, 'end_lineno', start + 50)
            if end is None:
                end = min(start + 100, len(lines))
            return '\n'.join(lines[start:end])
        except Exception:
            return None

    def _extract_section_content(self, content: str, heading, all_headings) -> Optional[str]:
        """Extract markdown section content (from heading to next heading of same or higher level)."""
        try:
            lines = content.split('\n')
            start = heading.lineno - 1

            # Find next heading of same or higher level
            end = len(lines)
            for h in all_headings:
                if h.lineno > heading.lineno and h.level <= heading.level:
                    end = h.lineno - 1
                    break

            section = '\n'.join(lines[start:end])
            return section[:5000]  # Limit section size
        except Exception:
            return None

    def _update_totals(self, result: AnalysisResult):
        """Update running totals from analysis result."""
        pr = result.parse_result

        if isinstance(pr, ParseResult):
            self.result.total_functions += len(pr.functions)
            self.result.total_classes += len(pr.classes)
            self.result.total_imports += len(pr.imports)

        elif isinstance(pr, JSParseResult):
            self.result.total_functions += len(pr.functions)
            self.result.total_classes += len(pr.classes)
            self.result.total_imports += len(pr.imports)

    def get_summary(self) -> dict:
        """Get analysis summary."""
        return {
            "total_files": self.result.total_files,
            "analyzed_files": self.result.analyzed_files,
            "failed_files": self.result.failed_files,
            "skipped_duplicates": self.result.skipped_duplicates,
            "success_rate": round(
                self.result.analyzed_files / self.result.total_files * 100, 2
            ) if self.result.total_files > 0 else 0,
            "total_functions": self.result.total_functions,
            "total_classes": self.result.total_classes,
            "total_imports": self.result.total_imports,
            "dna_profiles": len(self.result.dna_profiles),
            "indexed_to_embeddings": self._indexed_count,
            "errors": len(self.result.errors),
            "analysis_duration_seconds": round(self.result.analysis_duration, 2),
        }

    def get_dna_by_complexity(self, top_n: int = 10) -> list[FileDNA]:
        """Get top N files by complexity score."""
        return sorted(
            self.result.dna_profiles,
            key=lambda d: d.complexity_score,
            reverse=True
        )[:top_n]

    def get_files_by_type(self) -> dict[str, int]:
        """Get count of analyzed files by type."""
        by_type: dict[str, int] = {}
        for result in self.result.results:
            if result.success:
                ft = result.file_type
                by_type[ft] = by_type.get(ft, 0) + 1
        return by_type
