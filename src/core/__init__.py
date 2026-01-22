"""HyperMatrix v2026 - Core Module"""

from .analyzer import (
    Analyzer,
    AnalysisResult,
    ProjectAnalysis,
    FileType,
)

from .db_manager import DBManager

from .lineage import (
    LineageResolver,
    DependencyGraph,
    DependencyNode,
    ResolvedImport,
    ImportType,
)

from .consolidation import (
    ConsolidationEngine,
    SiblingGroup,
    SiblingFile,
    MasterProposal,
    AffinityResult,
    AffinityLevel,
)

from .metrics import (
    MetricsCalculator,
    CouplingAnalyzer,
    ComplexityMetrics,
    FileMetrics,
    ProjectMetrics,
    CouplingMetrics,
    calculate_file_metrics,
    calculate_project_metrics,
)

from .watcher import (
    FileWatcher,
    IncrementalAnalyzer,
    FileChange,
    WatcherConfig,
    FileHashCache,
    watch_project,
)
