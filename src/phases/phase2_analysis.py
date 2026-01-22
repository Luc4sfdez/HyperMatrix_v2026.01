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
    ParseResult,
    JSParseResult,
    MDParseResult,
    JSONParseResult,
    DataFlowType,
)
from ..core.db_manager import DBManager

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
    }

    def __init__(
        self,
        db_manager: Optional[DBManager] = None,
        skip_duplicates: bool = True,
        extract_dna: bool = True,
    ):
        self.db_manager = db_manager
        self.skip_duplicates = skip_duplicates
        self.extract_dna_flag = extract_dna

        # Initialize parsers
        self.python_parser = PythonParser()
        self.js_parser = JavaScriptParser()
        self.md_parser = MarkdownParser()
        self.json_parser = JSONParser()

        self.result = Phase2Result()
        self._dedup_result: Optional[DeduplicationResult] = None
        self._project_id: Optional[int] = None

        logger.info("Phase2Analysis initialized")

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
