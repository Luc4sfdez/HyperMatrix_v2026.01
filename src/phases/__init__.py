"""HyperMatrix v2026 - Analysis Phases"""

from .phase1_discovery import (
    Phase1Discovery,
    FileMetadata,
    ArchiveInfo,
    DiscoveryResult,
)

from .phase1_5_deduplication import (
    Phase1_5Deduplication,
    DuplicateGroup,
    DeduplicationResult,
)

from .phase2_analysis import (
    Phase2Analysis,
    Phase2Result,
    AnalysisResult,
    FileDNA,
    DataFlowDNA,
    LogicSequenceDNA,
    DNAType,
)

from .phase3_consolidation import (
    Phase3Consolidation,
    Phase3Result,
)

__all__ = [
    # Phase 1
    "Phase1Discovery",
    "FileMetadata",
    "ArchiveInfo",
    "DiscoveryResult",
    # Phase 1.5
    "Phase1_5Deduplication",
    "DuplicateGroup",
    "DeduplicationResult",
    # Phase 2
    "Phase2Analysis",
    "Phase2Result",
    "AnalysisResult",
    "FileDNA",
    "DataFlowDNA",
    "LogicSequenceDNA",
    "DNAType",
    # Phase 3
    "Phase3Consolidation",
    "Phase3Result",
]
