"""
HyperMatrix v2026 - Web Models (Pydantic schemas)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanRequest(BaseModel):
    """Request to start a new scan."""
    path: str = Field(..., description="Path to scan")
    project_name: Optional[str] = Field(None, description="Project name")
    include_archives: bool = Field(True, description="Include ZIP/TAR files")
    detect_duplicates: bool = Field(True, description="Detect duplicate files")
    calculate_similarities: bool = Field(True, description="Calculate file similarities")


class ScanProgress(BaseModel):
    """Progress of a running scan."""
    scan_id: str
    status: ScanStatus
    phase: str
    phase_progress: float
    total_files: int
    processed_files: int
    current_file: Optional[str]
    errors: List[str] = []


class SiblingGroupResponse(BaseModel):
    """Response for a sibling group."""
    filename: str
    file_count: int
    average_affinity: float
    proposed_master: str
    master_confidence: float
    files: List[Dict[str, Any]]


class AffinityResponse(BaseModel):
    """Affinity between two files."""
    file1: str
    file2: str
    overall_affinity: float
    level: str
    content_similarity: float
    structure_similarity: float
    dna_similarity: float
    hash_match: bool


class BatchAction(str, Enum):
    MERGE = "merge"
    KEEP_MASTER = "keep_master"
    IGNORE = "ignore"
    DELETE_DUPLICATES = "delete_duplicates"


class BatchActionRequest(BaseModel):
    """Request to perform batch action on sibling groups."""
    actions: List[Dict[str, Any]] = Field(..., description="List of actions")
    dry_run: bool = Field(True, description="Simulate without making changes")


class BatchActionResult(BaseModel):
    """Result of a batch action."""
    action: str
    filename: str
    success: bool
    message: str
    changes: List[str] = []


class DryRunResult(BaseModel):
    """Result of a dry run simulation."""
    total_groups: int
    files_to_merge: int
    files_to_delete: int
    space_to_recover_kb: float
    imports_to_update: int
    affected_files: List[str]
    warnings: List[str]


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"


class ExportRequest(BaseModel):
    """Request to export report."""
    format: ExportFormat
    include_details: bool = True
    project_id: Optional[int] = None


class RulesConfig(BaseModel):
    """YAML-based rules configuration."""
    prefer_paths: List[str] = Field(default_factory=list)
    never_master_from: List[str] = Field(default_factory=list)
    ignore_patterns: List[str] = Field(default_factory=list)
    min_affinity_threshold: float = 0.3
    conflict_resolution: str = "keep_largest"
    auto_commit: bool = False


class QualityMetrics(BaseModel):
    """Quality metrics for a file."""
    filepath: str
    has_tests: bool
    has_docstrings: bool
    has_type_hints: bool
    complexity_score: float
    maintainability_index: float
    code_smells: List[str]
    quality_score: float


class DependencyInfo(BaseModel):
    """Dependency information for impact analysis."""
    filepath: str
    imports: List[str]
    imported_by: List[str]
    would_break: List[str]


class MergePreview(BaseModel):
    """Preview of a merge operation."""
    base_file: str
    files_to_merge: List[str]
    functions_to_add: List[str]
    classes_to_add: List[str]
    conflicts: List[Dict[str, Any]]
    estimated_lines: int
    preview_code: str
