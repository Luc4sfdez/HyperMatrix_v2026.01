"""
HyperMatrix v2026 - Consolidation Engine
Detects sibling versions, calculates affinity, and proposes master files.
"""

import difflib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING
from collections import defaultdict
from enum import Enum

# Performance limits to prevent hanging on large files/groups
MAX_CONTENT_SIZE = 100_000  # Max characters to compare (100KB)
MAX_COMPARISONS_PER_GROUP = 500  # Max pairwise comparisons per group
COMPARISON_TIMEOUT_SECONDS = 5.0  # Max time per comparison

from ..parsers import (
    ParseResult,
    JSParseResult,
    FunctionInfo,
    ClassInfo,
)

if TYPE_CHECKING:
    from ..phases.phase2_analysis import FileDNA

# Configure logging
logger = logging.getLogger(__name__)


class AffinityLevel(Enum):
    """Level of affinity between files."""
    IDENTICAL = "identical"      # 100% - exact copies
    VERY_HIGH = "very_high"      # 90-99% - minor differences
    HIGH = "high"                # 70-89% - significant overlap
    MEDIUM = "medium"            # 50-69% - partial overlap
    LOW = "low"                  # 30-49% - some similarities
    MINIMAL = "minimal"          # <30% - mostly different


@dataclass
class SiblingFile:
    """A file that is a potential sibling (same name, different path)."""
    filepath: str
    filename: str
    directory: str
    size: int
    hash_sha256: Optional[str] = None
    parse_result: Optional[any] = None
    dna: Optional["FileDNA"] = None
    function_count: int = 0
    class_count: int = 0
    complexity: float = 0.0


@dataclass
class AffinityResult:
    """Result of affinity calculation between two files."""
    file1: str
    file2: str
    overall_affinity: float  # 0.0 to 1.0
    level: AffinityLevel
    content_similarity: float
    structure_similarity: float
    dna_similarity: float
    hash_match: bool
    details: dict = field(default_factory=dict)


@dataclass
class MasterProposal:
    """Proposal for master file in a sibling group."""
    proposed_master: SiblingFile
    siblings: list[SiblingFile]
    confidence: float  # 0.0 to 1.0
    reasons: list[str]
    affinity_matrix: list[AffinityResult] = field(default_factory=list)


@dataclass
class SiblingGroup:
    """Group of sibling files with same name."""
    filename: str
    files: list[SiblingFile] = field(default_factory=list)
    master_proposal: Optional[MasterProposal] = None


class ConsolidationEngine:
    """Engine for detecting siblings and calculating affinity."""

    def __init__(
        self,
        min_affinity_threshold: float = 0.3,
        content_weight: float = 0.4,
        structure_weight: float = 0.3,
        dna_weight: float = 0.3,
    ):
        self.min_affinity_threshold = min_affinity_threshold
        self.content_weight = content_weight
        self.structure_weight = structure_weight
        self.dna_weight = dna_weight

        logger.info(f"ConsolidationEngine initialized with threshold: {min_affinity_threshold}")

    def detect_siblings(
        self,
        files: list[dict],
    ) -> dict[str, SiblingGroup]:
        """
        Detect sibling files (same name, different path).

        Args:
            files: List of file info dicts with filepath, size, hash, etc.

        Returns:
            Dictionary mapping filename to SiblingGroup
        """
        logger.info(f"Detecting siblings among {len(files)} files")

        # Group by filename
        by_name: dict[str, list[dict]] = defaultdict(list)
        for file_info in files:
            filepath = Path(file_info.get("filepath", ""))
            filename = filepath.name
            by_name[filename].append(file_info)

        # Create sibling groups (only files with multiple instances)
        sibling_groups = {}
        for filename, file_list in by_name.items():
            if len(file_list) > 1:
                group = SiblingGroup(filename=filename)

                for file_info in file_list:
                    filepath = file_info.get("filepath", "")
                    sibling = SiblingFile(
                        filepath=filepath,
                        filename=filename,
                        directory=str(Path(filepath).parent),
                        size=file_info.get("size", 0),
                        hash_sha256=file_info.get("hash_sha256"),
                        parse_result=file_info.get("parse_result"),
                        dna=file_info.get("dna"),
                        function_count=file_info.get("function_count", 0),
                        class_count=file_info.get("class_count", 0),
                        complexity=file_info.get("complexity", 0.0),
                    )
                    group.files.append(sibling)

                sibling_groups[filename] = group
                logger.debug(f"Found sibling group: {filename} ({len(file_list)} files)")

        logger.info(f"Detected {len(sibling_groups)} sibling groups")
        return sibling_groups

    def calculate_affinity(
        self,
        file1: SiblingFile,
        file2: SiblingFile,
    ) -> AffinityResult:
        """
        Calculate affinity (similarity) between two files.

        Args:
            file1: First file
            file2: Second file

        Returns:
            AffinityResult with similarity metrics
        """
        # Check hash match first (fast path)
        hash_match = (
            file1.hash_sha256 is not None
            and file1.hash_sha256 == file2.hash_sha256
        )

        if hash_match:
            return AffinityResult(
                file1=file1.filepath,
                file2=file2.filepath,
                overall_affinity=1.0,
                level=AffinityLevel.IDENTICAL,
                content_similarity=1.0,
                structure_similarity=1.0,
                dna_similarity=1.0,
                hash_match=True,
                details={"reason": "Identical hash"},
            )

        # Calculate individual similarities
        content_sim = self._calculate_content_similarity(file1, file2)
        structure_sim = self._calculate_structure_similarity(file1, file2)
        dna_sim = self._calculate_dna_similarity(file1, file2)

        # Weighted average
        overall = (
            content_sim * self.content_weight
            + structure_sim * self.structure_weight
            + dna_sim * self.dna_weight
        )

        # Determine level
        level = self._get_affinity_level(overall)

        result = AffinityResult(
            file1=file1.filepath,
            file2=file2.filepath,
            overall_affinity=round(overall, 4),
            level=level,
            content_similarity=round(content_sim, 4),
            structure_similarity=round(structure_sim, 4),
            dna_similarity=round(dna_sim, 4),
            hash_match=hash_match,
            details={
                "content_weight": self.content_weight,
                "structure_weight": self.structure_weight,
                "dna_weight": self.dna_weight,
            },
        )

        logger.debug(f"Affinity {file1.filename}: {overall:.2%} ({level.value})")
        return result

    def _calculate_content_similarity(
        self,
        file1: SiblingFile,
        file2: SiblingFile,
    ) -> float:
        """Calculate content similarity using file contents."""
        try:
            start_time = time.time()

            with open(file1.filepath, "r", encoding="utf-8", errors="ignore") as f1:
                content1 = f1.read(MAX_CONTENT_SIZE)  # Limit read size
            with open(file2.filepath, "r", encoding="utf-8", errors="ignore") as f2:
                content2 = f2.read(MAX_CONTENT_SIZE)  # Limit read size

            # Skip if content is empty
            if not content1 or not content2:
                return 0.0 if (not content1 and not content2) else 0.1

            # For very large content, use quick_ratio first
            if len(content1) > 50000 or len(content2) > 50000:
                matcher = difflib.SequenceMatcher(None, content1, content2)
                quick = matcher.quick_ratio()
                # Only do full comparison if quick_ratio suggests similarity
                if quick < 0.3:
                    return quick
                # Check timeout before full comparison
                if time.time() - start_time > COMPARISON_TIMEOUT_SECONDS:
                    logger.warning(f"Content comparison timeout for {file1.filename}")
                    return quick
                return matcher.ratio()

            # Use difflib for sequence matching
            matcher = difflib.SequenceMatcher(None, content1, content2)
            return matcher.ratio()

        except Exception as e:
            logger.warning(f"Cannot calculate content similarity: {e}")
            # Fallback to size comparison
            if file1.size == 0 or file2.size == 0:
                return 0.0
            size_ratio = min(file1.size, file2.size) / max(file1.size, file2.size)
            return size_ratio * 0.5  # Penalize for not having actual content

    def _calculate_structure_similarity(
        self,
        file1: SiblingFile,
        file2: SiblingFile,
    ) -> float:
        """Calculate structural similarity based on parse results."""
        pr1 = file1.parse_result
        pr2 = file2.parse_result

        if pr1 is None or pr2 is None:
            return 0.5  # Neutral if no parse results

        scores = []

        # Compare function counts
        if isinstance(pr1, (ParseResult, JSParseResult)):
            funcs1 = set(f.name for f in pr1.functions) if hasattr(pr1, 'functions') else set()
            funcs2 = set(f.name for f in pr2.functions) if hasattr(pr2, 'functions') else set()

            if funcs1 or funcs2:
                intersection = len(funcs1 & funcs2)
                union = len(funcs1 | funcs2)
                scores.append(intersection / union if union > 0 else 1.0)

            # Compare class names
            classes1 = set(c.name for c in pr1.classes) if hasattr(pr1, 'classes') else set()
            classes2 = set(c.name for c in pr2.classes) if hasattr(pr2, 'classes') else set()

            if classes1 or classes2:
                intersection = len(classes1 & classes2)
                union = len(classes1 | classes2)
                scores.append(intersection / union if union > 0 else 1.0)

            # Compare import modules
            if hasattr(pr1, 'imports') and hasattr(pr2, 'imports'):
                imports1 = set(i.module for i in pr1.imports)
                imports2 = set(i.module for i in pr2.imports)

                if imports1 or imports2:
                    intersection = len(imports1 & imports2)
                    union = len(imports1 | imports2)
                    scores.append(intersection / union if union > 0 else 1.0)

        return sum(scores) / len(scores) if scores else 0.5

    def _calculate_dna_similarity(
        self,
        file1: SiblingFile,
        file2: SiblingFile,
    ) -> float:
        """Calculate DNA similarity based on data flow patterns."""
        dna1 = file1.dna
        dna2 = file2.dna

        if dna1 is None or dna2 is None:
            return 0.5  # Neutral if no DNA

        scores = []

        # Compare complexity scores
        if dna1.complexity_score > 0 or dna2.complexity_score > 0:
            max_complexity = max(dna1.complexity_score, dna2.complexity_score)
            min_complexity = min(dna1.complexity_score, dna2.complexity_score)
            complexity_sim = min_complexity / max_complexity if max_complexity > 0 else 1.0
            scores.append(complexity_sim)

        # Compare data flow variable names
        vars1 = set(df.variable for df in dna1.data_flows)
        vars2 = set(df.variable for df in dna2.data_flows)

        if vars1 or vars2:
            intersection = len(vars1 & vars2)
            union = len(vars1 | vars2)
            scores.append(intersection / union if union > 0 else 1.0)

        # Compare fingerprints (partial match)
        if dna1.fingerprint and dna2.fingerprint:
            # Compare first 8 chars of fingerprint
            fp_sim = sum(a == b for a, b in zip(dna1.fingerprint[:8], dna2.fingerprint[:8])) / 8
            scores.append(fp_sim)

        return sum(scores) / len(scores) if scores else 0.5

    def _get_affinity_level(self, affinity: float) -> AffinityLevel:
        """Get affinity level from score."""
        if affinity >= 1.0:
            return AffinityLevel.IDENTICAL
        elif affinity >= 0.9:
            return AffinityLevel.VERY_HIGH
        elif affinity >= 0.7:
            return AffinityLevel.HIGH
        elif affinity >= 0.5:
            return AffinityLevel.MEDIUM
        elif affinity >= 0.3:
            return AffinityLevel.LOW
        else:
            return AffinityLevel.MINIMAL

    def propose_master(
        self,
        group: SiblingGroup,
    ) -> MasterProposal:
        """
        Propose the best master file for a sibling group.

        Args:
            group: SiblingGroup with files to evaluate

        Returns:
            MasterProposal with recommended master
        """
        if len(group.files) < 2:
            raise ValueError("Need at least 2 files to propose master")

        n_files = len(group.files)
        total_comparisons = n_files * (n_files - 1) // 2

        logger.info(f"Proposing master for '{group.filename}' ({n_files} siblings, {total_comparisons} comparisons)")

        # Calculate affinity matrix with limits for large groups
        affinity_matrix = []
        comparison_count = 0

        # For very large groups, sample files instead of comparing all
        files_to_compare = group.files
        if total_comparisons > MAX_COMPARISONS_PER_GROUP:
            # Sort by complexity/size and take representative sample
            sorted_files = sorted(group.files, key=lambda f: (f.complexity, f.size), reverse=True)
            # Take sqrt(MAX_COMPARISONS_PER_GROUP) * 2 files to get ~MAX comparisons
            sample_size = min(len(sorted_files), int((MAX_COMPARISONS_PER_GROUP * 2) ** 0.5) + 1)
            files_to_compare = sorted_files[:sample_size]
            logger.warning(f"Large group '{group.filename}': sampling {len(files_to_compare)} of {n_files} files")

        for i, file1 in enumerate(files_to_compare):
            for file2 in files_to_compare[i + 1:]:
                if comparison_count >= MAX_COMPARISONS_PER_GROUP:
                    logger.warning(f"Reached max comparisons ({MAX_COMPARISONS_PER_GROUP}) for '{group.filename}'")
                    break
                affinity = self.calculate_affinity(file1, file2)
                affinity_matrix.append(affinity)
                comparison_count += 1
            if comparison_count >= MAX_COMPARISONS_PER_GROUP:
                break

        # Score each file as potential master
        scores: dict[str, dict] = {}
        for sibling in group.files:
            scores[sibling.filepath] = {
                "file": sibling,
                "score": 0.0,
                "reasons": [],
            }

            # Factor 1: Complexity (more complete)
            scores[sibling.filepath]["score"] += sibling.complexity * 0.1
            if sibling.complexity > 0:
                scores[sibling.filepath]["reasons"].append(
                    f"Complexity: {sibling.complexity:.1f}"
                )

            # Factor 2: Function count
            scores[sibling.filepath]["score"] += sibling.function_count * 2
            if sibling.function_count > 0:
                scores[sibling.filepath]["reasons"].append(
                    f"Functions: {sibling.function_count}"
                )

            # Factor 3: Class count
            scores[sibling.filepath]["score"] += sibling.class_count * 3
            if sibling.class_count > 0:
                scores[sibling.filepath]["reasons"].append(
                    f"Classes: {sibling.class_count}"
                )

            # Factor 4: File size (larger often more complete)
            scores[sibling.filepath]["score"] += sibling.size / 1000

            # Factor 5: Path depth (prefer shallower paths)
            depth = len(Path(sibling.filepath).parts)
            scores[sibling.filepath]["score"] -= depth * 0.5

            # Factor 6: Not in archive/temp paths
            path_lower = sibling.filepath.lower()
            if "temp" in path_lower or "tmp" in path_lower or "backup" in path_lower:
                scores[sibling.filepath]["score"] -= 10
                scores[sibling.filepath]["reasons"].append("Temp/backup path penalty")

        # Find best candidate
        best = max(scores.values(), key=lambda x: x["score"])
        best_file = best["file"]
        others = [s for s in group.files if s.filepath != best_file.filepath]

        # Calculate confidence based on score difference
        sorted_scores = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        if len(sorted_scores) >= 2:
            score_diff = sorted_scores[0]["score"] - sorted_scores[1]["score"]
            max_score = sorted_scores[0]["score"]
            confidence = min(0.5 + (score_diff / max_score) * 0.5, 1.0) if max_score > 0 else 0.5
        else:
            confidence = 0.5

        proposal = MasterProposal(
            proposed_master=best_file,
            siblings=others,
            confidence=round(confidence, 2),
            reasons=best["reasons"],
            affinity_matrix=affinity_matrix,
        )

        group.master_proposal = proposal

        logger.info(f"Proposed master: {best_file.filename} from {best_file.directory} "
                   f"(confidence: {confidence:.0%})")

        return proposal

    def consolidate_group(
        self,
        group: SiblingGroup,
    ) -> MasterProposal:
        """
        Full consolidation process for a sibling group.

        Args:
            group: SiblingGroup to consolidate

        Returns:
            MasterProposal with complete analysis
        """
        return self.propose_master(group)

    def get_consolidation_report(
        self,
        groups: dict[str, SiblingGroup],
    ) -> list[dict]:
        """Generate consolidation report for all groups."""
        report = []

        for filename, group in groups.items():
            if group.master_proposal is None:
                continue

            proposal = group.master_proposal

            # Calculate average affinity
            avg_affinity = (
                sum(a.overall_affinity for a in proposal.affinity_matrix)
                / len(proposal.affinity_matrix)
                if proposal.affinity_matrix else 0.0
            )

            report.append({
                "filename": filename,
                "sibling_count": len(group.files),
                "proposed_master": proposal.proposed_master.filepath,
                "master_directory": proposal.proposed_master.directory,
                "confidence": proposal.confidence,
                "reasons": proposal.reasons,
                "average_affinity": round(avg_affinity, 4),
                "siblings": [
                    {
                        "path": s.filepath,
                        "directory": s.directory,
                        "size": s.size,
                    }
                    for s in proposal.siblings
                ],
            })

        return sorted(report, key=lambda x: x["confidence"], reverse=True)
