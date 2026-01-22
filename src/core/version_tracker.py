"""
HyperMatrix v2026 - Version Tracker
Tracks file versions and evolution history.
"""

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os

logger = logging.getLogger(__name__)


@dataclass
class FileVersion:
    """Represents a single version of a file."""
    filepath: str
    hash_sha256: str
    size: int
    modified_time: datetime
    created_time: Optional[datetime] = None

    # Git info if available
    git_commit: Optional[str] = None
    git_author: Optional[str] = None
    git_date: Optional[datetime] = None
    git_message: Optional[str] = None

    # Analysis info
    function_count: int = 0
    class_count: int = 0
    line_count: int = 0


@dataclass
class VersionHistory:
    """Complete version history for a file."""
    filename: str
    versions: List[FileVersion] = field(default_factory=list)
    oldest_version: Optional[str] = None
    newest_version: Optional[str] = None
    likely_original: Optional[str] = None
    evolution_chain: List[str] = field(default_factory=list)


@dataclass
class EvolutionAnalysis:
    """Analysis of how sibling files evolved from each other."""
    filename: str
    files: List[str]
    evolution_tree: Dict = field(default_factory=dict)
    likely_original: str = ""
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


class VersionTracker:
    """
    Tracks and analyzes version history of files.

    Features:
    - Git history integration
    - File modification time tracking
    - Content hash tracking
    - Evolution chain detection
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self._git_available = self._check_git()

    def _check_git(self) -> bool:
        """Check if git is available and this is a git repo."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_file_version(self, filepath: str) -> FileVersion:
        """Get version info for a single file."""
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Basic file info
        stat = path.stat()
        content = path.read_bytes()

        version = FileVersion(
            filepath=str(path.resolve()),
            hash_sha256=hashlib.sha256(content).hexdigest(),
            size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            created_time=datetime.fromtimestamp(stat.st_ctime) if hasattr(stat, 'st_ctime') else None,
        )

        # Count lines
        try:
            text_content = content.decode("utf-8", errors="ignore")
            version.line_count = len(text_content.splitlines())
        except Exception:
            pass

        # Git info if available
        if self._git_available:
            git_info = self._get_git_info(filepath)
            if git_info:
                version.git_commit = git_info.get("commit")
                version.git_author = git_info.get("author")
                version.git_message = git_info.get("message")
                if git_info.get("date"):
                    try:
                        version.git_date = datetime.fromisoformat(git_info["date"])
                    except Exception:
                        pass

        return version

    def _get_git_info(self, filepath: str) -> Optional[Dict]:
        """Get git info for a file."""
        try:
            # Get last commit info
            result = subprocess.run(
                ["git", "log", "-1", "--format=%H|%an|%aI|%s", "--", filepath],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|", 3)
                if len(parts) >= 4:
                    return {
                        "commit": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    }
        except Exception as e:
            logger.debug(f"Git info failed for {filepath}: {e}")

        return None

    def get_git_history(self, filepath: str, limit: int = 20) -> List[Dict]:
        """Get git commit history for a file."""
        if not self._git_available:
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--format=%H|%an|%aI|%s", "--", filepath],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return []

            history = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        history.append({
                            "commit": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3]
                        })

            return history

        except Exception as e:
            logger.debug(f"Git history failed: {e}")
            return []

    def build_version_history(self, sibling_files: List[str]) -> VersionHistory:
        """
        Build version history for a group of sibling files.

        Analyzes modification times, git history, and content
        to determine which file is oldest/newest.
        """
        filename = Path(sibling_files[0]).name if sibling_files else "unknown"
        history = VersionHistory(filename=filename)

        versions = []
        for filepath in sibling_files:
            try:
                version = self.get_file_version(filepath)
                versions.append(version)
            except Exception as e:
                logger.warning(f"Could not get version for {filepath}: {e}")

        if not versions:
            return history

        history.versions = versions

        # Sort by modification time
        sorted_by_mtime = sorted(versions, key=lambda v: v.modified_time)
        history.oldest_version = sorted_by_mtime[0].filepath
        history.newest_version = sorted_by_mtime[-1].filepath

        # Try to determine likely original
        history.likely_original = self._determine_likely_original(versions)

        # Build evolution chain
        history.evolution_chain = self._build_evolution_chain(versions)

        return history

    def _determine_likely_original(self, versions: List[FileVersion]) -> str:
        """
        Determine which file is likely the original.

        Factors:
        - Oldest modification time
        - Oldest git commit (if available)
        - Path depth (shallower often = original)
        - Path content (not in backup/temp folders)
        """
        scores = {}

        for v in versions:
            score = 0

            # Modification time (oldest gets points)
            all_mtimes = [ver.modified_time for ver in versions]
            if v.modified_time == min(all_mtimes):
                score += 30

            # Git date if available
            git_dates = [ver.git_date for ver in versions if ver.git_date]
            if git_dates and v.git_date == min(git_dates):
                score += 40

            # Path depth (shallower = more points)
            depth = len(Path(v.filepath).parts)
            min_depth = min(len(Path(ver.filepath).parts) for ver in versions)
            if depth == min_depth:
                score += 15

            # Path content penalties
            path_lower = v.filepath.lower()
            if any(p in path_lower for p in ["backup", "temp", "old", "archive", "copy"]):
                score -= 20

            # Bonus for src/ or lib/ paths
            if any(p in path_lower for p in ["/src/", "/lib/", "/core/"]):
                score += 10

            scores[v.filepath] = score

        # Return file with highest score
        return max(scores, key=scores.get)

    def _build_evolution_chain(self, versions: List[FileVersion]) -> List[str]:
        """
        Build likely evolution chain based on timestamps.
        """
        # Sort by modification time
        sorted_versions = sorted(versions, key=lambda v: v.modified_time)
        return [v.filepath for v in sorted_versions]

    def analyze_evolution(self, sibling_files: List[str]) -> EvolutionAnalysis:
        """
        Analyze how sibling files evolved from each other.

        Returns detailed analysis with evidence.
        """
        filename = Path(sibling_files[0]).name if sibling_files else "unknown"
        analysis = EvolutionAnalysis(
            filename=filename,
            files=sibling_files
        )

        if len(sibling_files) < 2:
            return analysis

        # Get versions
        versions = []
        for fp in sibling_files:
            try:
                versions.append(self.get_file_version(fp))
            except Exception:
                pass

        if len(versions) < 2:
            return analysis

        # Build evolution tree
        sorted_by_time = sorted(versions, key=lambda v: v.modified_time)

        tree = {"root": None, "children": {}}

        # Determine root (likely original)
        root_version = sorted_by_time[0]
        tree["root"] = root_version.filepath
        analysis.likely_original = root_version.filepath

        # Add children in order
        for v in sorted_by_time[1:]:
            tree["children"][v.filepath] = {
                "time_delta": str(v.modified_time - root_version.modified_time),
                "size_delta": v.size - root_version.size,
                "line_delta": v.line_count - root_version.line_count,
            }

        analysis.evolution_tree = tree

        # Build evidence
        analysis.evidence.append(f"Oldest modification: {root_version.filepath} ({root_version.modified_time})")

        if root_version.git_date:
            analysis.evidence.append(f"Git date: {root_version.git_date}")

        # Calculate confidence
        time_spread = (sorted_by_time[-1].modified_time - sorted_by_time[0].modified_time).total_seconds()
        if time_spread > 86400:  # More than 1 day spread
            analysis.confidence = 0.8
            analysis.evidence.append(f"Time spread: {time_spread / 86400:.1f} days")
        elif time_spread > 3600:  # More than 1 hour
            analysis.confidence = 0.6
        else:
            analysis.confidence = 0.4
            analysis.evidence.append("Files were modified close together in time")

        # Check path patterns
        original_path = root_version.filepath.lower()
        if "/src/" in original_path or "/lib/" in original_path:
            analysis.confidence += 0.1
            analysis.evidence.append("Original in standard source directory")

        return analysis

    def get_modification_timeline(self, sibling_files: List[str]) -> List[Dict]:
        """
        Get a timeline of modifications across sibling files.

        Useful for visualizing when each file was last changed.
        """
        timeline = []

        for filepath in sibling_files:
            try:
                version = self.get_file_version(filepath)
                entry = {
                    "filepath": filepath,
                    "filename": Path(filepath).name,
                    "directory": str(Path(filepath).parent),
                    "modified": version.modified_time.isoformat(),
                    "size": version.size,
                    "hash": version.hash_sha256[:12],
                }

                if version.git_date:
                    entry["git_date"] = version.git_date.isoformat()
                    entry["git_commit"] = version.git_commit
                    entry["git_author"] = version.git_author

                timeline.append(entry)

            except Exception as e:
                logger.warning(f"Could not get timeline for {filepath}: {e}")

        # Sort by modification time
        timeline.sort(key=lambda x: x["modified"])

        return timeline

    def find_common_ancestor(self, file1: str, file2: str) -> Optional[str]:
        """
        Try to find a common ancestor commit for two files using git.

        This works if both files were at some point the same file
        that was copied and modified.
        """
        if not self._git_available:
            return None

        try:
            # This is a simplified approach - in reality, finding
            # common ancestors for copied files is complex
            result = subprocess.run(
                ["git", "log", "--all", "--format=%H", "-1", "--", file1],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        except Exception:
            pass

        return None
