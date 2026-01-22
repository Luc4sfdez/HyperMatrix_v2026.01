"""
HyperMatrix v2026 - Phase 3: Consolidation
Groups siblings, calculates affinity, and stores proposals in database.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from .phase1_discovery import FileMetadata, DiscoveryResult
from .phase2_analysis import Phase2Result, AnalysisResult, FileDNA
from ..core.consolidation import (
    ConsolidationEngine,
    SiblingGroup,
    SiblingFile,
    MasterProposal,
    AffinityResult,
    AffinityLevel,
)
from ..core.db_manager import DBManager

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Phase3Result:
    """Result of the consolidation phase."""
    total_files: int = 0
    sibling_groups: int = 0
    files_with_siblings: int = 0
    proposals_generated: int = 0
    high_confidence_proposals: int = 0
    groups: dict[str, SiblingGroup] = field(default_factory=dict)
    consolidation_report: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    consolidation_duration: float = 0.0


class Phase3Consolidation:
    """Phase 3: File consolidation and sibling detection."""

    def __init__(
        self,
        db_manager: Optional[DBManager] = None,
        min_affinity_threshold: float = 0.3,
        content_weight: float = 0.4,
        structure_weight: float = 0.3,
        dna_weight: float = 0.3,
    ):
        self.db_manager = db_manager
        self.engine = ConsolidationEngine(
            min_affinity_threshold=min_affinity_threshold,
            content_weight=content_weight,
            structure_weight=structure_weight,
            dna_weight=dna_weight,
        )
        self.result = Phase3Result()
        self._project_id: Optional[int] = None

        logger.info("Phase3Consolidation initialized")

    def consolidate(
        self,
        discovery_result: DiscoveryResult,
        analysis_result: Phase2Result,
        project_id: Optional[int] = None,
    ) -> Phase3Result:
        """
        Run consolidation phase.

        Args:
            discovery_result: Result from Phase 1
            analysis_result: Result from Phase 2
            project_id: Database project ID

        Returns:
            Phase3Result with consolidation analysis
        """
        start_time = datetime.now()
        self.result = Phase3Result()
        self._project_id = project_id

        logger.info("Starting Phase 3: Consolidation")

        # Build file info list with all metadata
        file_infos = self._build_file_infos(discovery_result, analysis_result)
        self.result.total_files = len(file_infos)

        logger.info(f"Processing {len(file_infos)} files for sibling detection")

        # Step 1: Detect siblings (same name, different path)
        print("  Detecting sibling files...")
        sibling_groups = self.engine.detect_siblings(file_infos)
        self.result.sibling_groups = len(sibling_groups)
        self.result.files_with_siblings = sum(
            len(g.files) for g in sibling_groups.values()
        )

        if not sibling_groups:
            logger.info("No sibling files detected")
            self.result.consolidation_duration = (
                datetime.now() - start_time
            ).total_seconds()
            return self.result

        # Step 2: Calculate affinity and propose masters
        print(f"  Analyzing {len(sibling_groups)} sibling groups...")

        iterator = (
            tqdm(sibling_groups.items(), desc="Consolidating", unit="group")
            if TQDM_AVAILABLE
            else sibling_groups.items()
        )

        for filename, group in iterator:
            try:
                proposal = self.engine.consolidate_group(group)
                self.result.proposals_generated += 1

                if proposal.confidence >= 0.7:
                    self.result.high_confidence_proposals += 1

                # Save to database if available
                if self.db_manager and self._project_id:
                    self._save_proposal_to_db(group, proposal)

            except Exception as e:
                error = f"Error consolidating {filename}: {e}"
                logger.warning(error)
                self.result.errors.append(error)

        self.result.groups = sibling_groups

        # Step 3: Generate report
        self.result.consolidation_report = self.engine.get_consolidation_report(
            sibling_groups
        )

        self.result.consolidation_duration = (
            datetime.now() - start_time
        ).total_seconds()

        logger.info(
            f"Consolidation complete: {self.result.sibling_groups} groups, "
            f"{self.result.proposals_generated} proposals, "
            f"{self.result.consolidation_duration:.2f}s"
        )

        return self.result

    def _build_file_infos(
        self,
        discovery_result: DiscoveryResult,
        analysis_result: Phase2Result,
    ) -> list[dict]:
        """Build file info list combining discovery and analysis data."""
        # Create lookup from filepath to analysis result
        analysis_lookup: dict[str, AnalysisResult] = {}
        dna_lookup: dict[str, FileDNA] = {}

        for ar in analysis_result.results:
            analysis_lookup[ar.filepath] = ar

        for dna in analysis_result.dna_profiles:
            dna_lookup[dna.filepath] = dna

        # Build combined file infos
        file_infos = []
        for file_meta in discovery_result.files:
            ar = analysis_lookup.get(file_meta.filepath)
            dna = dna_lookup.get(file_meta.filepath)

            info = {
                "filepath": file_meta.filepath,
                "filename": file_meta.filename,
                "size": file_meta.size,
                "hash_sha256": file_meta.hash_sha256,
                "parse_result": ar.parse_result if ar else None,
                "dna": dna,
                "function_count": 0,
                "class_count": 0,
                "complexity": dna.complexity_score if dna else 0.0,
            }

            # Extract counts from parse result
            if ar and ar.parse_result:
                pr = ar.parse_result
                if hasattr(pr, 'functions'):
                    info["function_count"] = len(pr.functions)
                if hasattr(pr, 'classes'):
                    info["class_count"] = len(pr.classes)

            file_infos.append(info)

        return file_infos

    def _save_proposal_to_db(
        self,
        group: SiblingGroup,
        proposal: MasterProposal,
    ):
        """Save consolidation proposal to database."""
        if not self.db_manager:
            return

        try:
            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                # Ensure consolidation table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS consolidation_proposals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        master_path TEXT NOT NULL,
                        confidence REAL,
                        reasons TEXT,
                        sibling_count INTEGER,
                        average_affinity REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects(id)
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS consolidation_siblings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        proposal_id INTEGER NOT NULL,
                        sibling_path TEXT NOT NULL,
                        affinity_to_master REAL,
                        affinity_level TEXT,
                        FOREIGN KEY (proposal_id) REFERENCES consolidation_proposals(id)
                    )
                """)

                # Calculate average affinity
                avg_affinity = (
                    sum(a.overall_affinity for a in proposal.affinity_matrix)
                    / len(proposal.affinity_matrix)
                    if proposal.affinity_matrix else 0.0
                )

                # Insert proposal
                cursor.execute(
                    """INSERT INTO consolidation_proposals
                       (project_id, filename, master_path, confidence, reasons,
                        sibling_count, average_affinity)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        self._project_id,
                        group.filename,
                        proposal.proposed_master.filepath,
                        proposal.confidence,
                        ", ".join(proposal.reasons),
                        len(proposal.siblings),
                        avg_affinity,
                    )
                )

                proposal_id = cursor.lastrowid

                # Insert siblings with affinity info
                for sibling in proposal.siblings:
                    # Find affinity result for this sibling
                    affinity_to_master = 0.0
                    affinity_level = AffinityLevel.MINIMAL.value

                    for ar in proposal.affinity_matrix:
                        if (ar.file1 == sibling.filepath and
                            ar.file2 == proposal.proposed_master.filepath) or \
                           (ar.file2 == sibling.filepath and
                            ar.file1 == proposal.proposed_master.filepath):
                            affinity_to_master = ar.overall_affinity
                            affinity_level = ar.level.value
                            break

                    cursor.execute(
                        """INSERT INTO consolidation_siblings
                           (proposal_id, sibling_path, affinity_to_master, affinity_level)
                           VALUES (?, ?, ?, ?)""",
                        (proposal_id, sibling.filepath, affinity_to_master, affinity_level)
                    )

                logger.debug(f"Saved proposal for {group.filename} to database")

        except Exception as e:
            logger.error(f"Failed to save proposal to database: {e}")

    def get_summary(self) -> dict:
        """Get consolidation summary."""
        return {
            "total_files": self.result.total_files,
            "sibling_groups": self.result.sibling_groups,
            "files_with_siblings": self.result.files_with_siblings,
            "proposals_generated": self.result.proposals_generated,
            "high_confidence_proposals": self.result.high_confidence_proposals,
            "errors": len(self.result.errors),
            "consolidation_duration_seconds": round(
                self.result.consolidation_duration, 2
            ),
        }

    def get_proposals_by_confidence(
        self,
        min_confidence: float = 0.0,
    ) -> list[dict]:
        """Get proposals filtered by minimum confidence."""
        return [
            p for p in self.result.consolidation_report
            if p["confidence"] >= min_confidence
        ]

    def get_high_affinity_pairs(
        self,
        min_affinity: float = 0.9,
    ) -> list[dict]:
        """Get file pairs with high affinity (potential duplicates)."""
        pairs = []
        for group in self.result.groups.values():
            if group.master_proposal:
                for ar in group.master_proposal.affinity_matrix:
                    if ar.overall_affinity >= min_affinity:
                        pairs.append({
                            "file1": ar.file1,
                            "file2": ar.file2,
                            "affinity": ar.overall_affinity,
                            "level": ar.level.value,
                            "hash_match": ar.hash_match,
                        })
        return sorted(pairs, key=lambda x: x["affinity"], reverse=True)

    def print_report(self):
        """Print consolidation report to console."""
        print("\n" + "=" * 60)
        print("CONSOLIDATION REPORT")
        print("=" * 60)

        if not self.result.consolidation_report:
            print("No sibling files detected.")
            return

        for proposal in self.result.consolidation_report:
            print(f"\n[{proposal['filename']}] - {proposal['sibling_count']} versions")
            print(f"  Master: {proposal['master_directory']}")
            print(f"  Confidence: {proposal['confidence']:.0%}")
            print(f"  Average Affinity: {proposal['average_affinity']:.0%}")
            print(f"  Reasons: {', '.join(proposal['reasons'])}")
            print("  Siblings:")
            for sibling in proposal["siblings"]:
                print(f"    - {sibling['directory']}")
