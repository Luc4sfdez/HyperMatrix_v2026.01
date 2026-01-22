"""
HyperMatrix v2026 - Phase 1.5: Deduplication
Identifies and groups duplicate files by content hash.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import defaultdict

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from .phase1_discovery import FileMetadata, DiscoveryResult

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """Group of duplicate files."""
    hash_sha256: str
    original: FileMetadata
    duplicates: list[FileMetadata] = field(default_factory=list)
    total_wasted_bytes: int = 0

    @property
    def count(self) -> int:
        """Total number of files in group (original + duplicates)."""
        return 1 + len(self.duplicates)


@dataclass
class DeduplicationResult:
    """Result of the deduplication phase."""
    total_files: int = 0
    unique_files: int = 0
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    total_duplicate_count: int = 0
    total_wasted_bytes: int = 0
    hash_map: dict[str, list[FileMetadata]] = field(default_factory=dict)
    original_map: dict[str, str] = field(default_factory=dict)  # duplicate_path -> original_path


class Phase1_5Deduplication:
    """Phase 1.5: File deduplication by content hash."""

    def __init__(
        self,
        hash_algorithm: str = "sha256",
        chunk_size: int = 8192,
        skip_small_files: bool = False,
        min_file_size: int = 100,  # bytes
    ):
        self.hash_algorithm = hash_algorithm
        self.chunk_size = chunk_size
        self.skip_small_files = skip_small_files
        self.min_file_size = min_file_size
        self.result = DeduplicationResult()

        logger.info(f"Phase1_5Deduplication initialized with algorithm: {hash_algorithm}")

    def calculate_hash_sha256(self, filepath: str) -> Optional[str]:
        """
        Calculate SHA256 hash for a file.

        Args:
            filepath: Path to the file

        Returns:
            SHA256 hash string or None if error
        """
        try:
            sha256_hash = hashlib.sha256()

            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b""):
                    sha256_hash.update(chunk)

            hash_value = sha256_hash.hexdigest()
            logger.debug(f"Computed hash for {Path(filepath).name}: {hash_value[:16]}...")
            return hash_value

        except (OSError, IOError) as e:
            logger.error(f"Cannot compute hash for {filepath}: {e}")
            return None

    def calculate_hash(self, filepath: str) -> Optional[str]:
        """
        Calculate hash using configured algorithm.

        Args:
            filepath: Path to the file

        Returns:
            Hash string or None if error
        """
        if self.hash_algorithm == "sha256":
            return self.calculate_hash_sha256(filepath)

        try:
            hasher = hashlib.new(self.hash_algorithm)

            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b""):
                    hasher.update(chunk)

            return hasher.hexdigest()

        except (OSError, IOError, ValueError) as e:
            logger.error(f"Cannot compute {self.hash_algorithm} hash for {filepath}: {e}")
            return None

    def group_by_hash(
        self,
        files: list[FileMetadata],
        recompute_hash: bool = False,
    ) -> dict[str, list[FileMetadata]]:
        """
        Group files by their content hash.

        Args:
            files: List of FileMetadata from discovery phase
            recompute_hash: Whether to recompute hashes or use existing

        Returns:
            Dictionary mapping hash -> list of files
        """
        logger.info(f"Grouping {len(files)} files by hash")
        hash_groups: dict[str, list[FileMetadata]] = defaultdict(list)

        # Filter files if needed
        files_to_process = files
        if self.skip_small_files:
            files_to_process = [f for f in files if f.size >= self.min_file_size]
            logger.info(f"Filtered to {len(files_to_process)} files (>= {self.min_file_size} bytes)")

        # Process files with progress bar
        iterator = tqdm(files_to_process, desc="Computing hashes", unit="file") if TQDM_AVAILABLE else files_to_process

        for file_meta in iterator:
            # Get or compute hash
            if recompute_hash or not file_meta.hash_sha256:
                file_hash = self.calculate_hash_sha256(file_meta.filepath)
                if file_hash:
                    file_meta.hash_sha256 = file_hash
            else:
                file_hash = file_meta.hash_sha256

            if file_hash:
                hash_groups[file_hash].append(file_meta)
            else:
                logger.warning(f"Skipping file without hash: {file_meta.filepath}")

        logger.info(f"Found {len(hash_groups)} unique hashes")
        return dict(hash_groups)

    def map_originals_to_duplicates(
        self,
        hash_groups: dict[str, list[FileMetadata]],
        prefer_shorter_path: bool = True,
        prefer_non_archive: bool = True,
    ) -> DeduplicationResult:
        """
        Map duplicate files to their originals.

        Args:
            hash_groups: Dictionary from group_by_hash()
            prefer_shorter_path: Prefer files with shorter paths as original
            prefer_non_archive: Prefer non-archive files as original

        Returns:
            DeduplicationResult with deduplication analysis
        """
        logger.info("Mapping originals to duplicates")

        self.result = DeduplicationResult()
        self.result.hash_map = hash_groups
        self.result.total_files = sum(len(files) for files in hash_groups.values())

        duplicate_groups = []
        total_duplicates = 0
        total_wasted = 0

        for file_hash, files in hash_groups.items():
            if len(files) == 1:
                # Unique file
                self.result.unique_files += 1
                continue

            # Sort to determine original
            sorted_files = self._sort_files_for_original(
                files,
                prefer_shorter_path,
                prefer_non_archive,
            )

            original = sorted_files[0]
            duplicates = sorted_files[1:]

            # Calculate wasted space
            wasted_bytes = sum(f.size for f in duplicates)

            # Create duplicate group
            group = DuplicateGroup(
                hash_sha256=file_hash,
                original=original,
                duplicates=duplicates,
                total_wasted_bytes=wasted_bytes,
            )
            duplicate_groups.append(group)

            # Update maps
            for dup in duplicates:
                self.result.original_map[dup.filepath] = original.filepath

            total_duplicates += len(duplicates)
            total_wasted += wasted_bytes

            logger.debug(f"Duplicate group: {len(duplicates)} copies of {original.filename}")

        self.result.duplicate_groups = duplicate_groups
        self.result.total_duplicate_count = total_duplicates
        self.result.total_wasted_bytes = total_wasted
        self.result.unique_files = len(hash_groups) - len(duplicate_groups) + len(duplicate_groups)

        logger.info(f"Deduplication complete: {len(duplicate_groups)} duplicate groups, "
                   f"{total_duplicates} duplicate files, "
                   f"{total_wasted / 1024 / 1024:.2f} MB wasted")

        return self.result

    def _sort_files_for_original(
        self,
        files: list[FileMetadata],
        prefer_shorter_path: bool,
        prefer_non_archive: bool,
    ) -> list[FileMetadata]:
        """Sort files to determine which should be the original."""

        def sort_key(f: FileMetadata) -> tuple:
            # Lower values = better candidate for original
            archive_penalty = 1 if f.is_from_archive and prefer_non_archive else 0
            path_length = len(f.filepath) if prefer_shorter_path else 0
            # Prefer older files (earlier modified)
            timestamp = f.modified_at.timestamp()

            return (archive_penalty, path_length, timestamp)

        return sorted(files, key=sort_key)

    def process(
        self,
        discovery_result: DiscoveryResult,
        recompute_hash: bool = False,
    ) -> DeduplicationResult:
        """
        Process discovery result and perform deduplication.

        Args:
            discovery_result: Result from Phase1Discovery
            recompute_hash: Whether to recompute all hashes

        Returns:
            DeduplicationResult
        """
        logger.info(f"Starting deduplication for {len(discovery_result.files)} files")

        # Group by hash
        hash_groups = self.group_by_hash(discovery_result.files, recompute_hash)

        # Map originals to duplicates
        result = self.map_originals_to_duplicates(hash_groups)

        return result

    def get_original_path(self, filepath: str) -> str:
        """
        Get the original file path for a potentially duplicate file.

        Args:
            filepath: Path to check

        Returns:
            Original file path (same as input if not a duplicate)
        """
        return self.result.original_map.get(filepath, filepath)

    def is_duplicate(self, filepath: str) -> bool:
        """Check if a file is a duplicate."""
        return filepath in self.result.original_map

    def get_duplicates_of(self, filepath: str) -> list[FileMetadata]:
        """Get all duplicates of a file."""
        for group in self.result.duplicate_groups:
            if group.original.filepath == filepath:
                return group.duplicates
            for dup in group.duplicates:
                if dup.filepath == filepath:
                    # Return original + other duplicates
                    return [group.original] + [d for d in group.duplicates if d.filepath != filepath]
        return []

    def get_summary(self) -> dict:
        """Get deduplication summary."""
        return {
            "total_files": self.result.total_files,
            "unique_files": self.result.unique_files,
            "duplicate_groups": len(self.result.duplicate_groups),
            "total_duplicates": self.result.total_duplicate_count,
            "wasted_bytes": self.result.total_wasted_bytes,
            "wasted_mb": round(self.result.total_wasted_bytes / 1024 / 1024, 2),
            "deduplication_ratio": round(
                self.result.total_duplicate_count / self.result.total_files * 100, 2
            ) if self.result.total_files > 0 else 0,
            "largest_duplicate_group": max(
                (g.count for g in self.result.duplicate_groups),
                default=0
            ),
        }

    def get_duplicate_report(self) -> list[dict]:
        """Generate detailed duplicate report."""
        report = []
        for group in sorted(
            self.result.duplicate_groups,
            key=lambda g: g.total_wasted_bytes,
            reverse=True
        ):
            report.append({
                "hash": group.hash_sha256[:16] + "...",
                "original": group.original.filepath,
                "original_size": group.original.size,
                "duplicate_count": len(group.duplicates),
                "duplicates": [d.filepath for d in group.duplicates],
                "wasted_bytes": group.total_wasted_bytes,
                "wasted_mb": round(group.total_wasted_bytes / 1024 / 1024, 4),
            })
        return report
