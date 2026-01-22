"""
HyperMatrix v2026 - Phase 1: Discovery
Scans directories, extracts metadata, and handles compressed files.
"""

import os
import hashlib
import zipfile
import tarfile
import tempfile
import shutil
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FileMetadata:
    """Metadata for a discovered file."""
    filepath: str
    filename: str
    extension: str
    size: int
    created_at: datetime
    modified_at: datetime
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    is_from_archive: bool = False
    archive_source: Optional[str] = None


@dataclass
class ArchiveInfo:
    """Information about an extracted archive."""
    archive_path: str
    extract_path: str
    file_count: int
    total_size: int
    archive_type: str


@dataclass
class DiscoveryResult:
    """Result of the discovery phase."""
    root_path: str
    files: list[FileMetadata] = field(default_factory=list)
    archives: list[ArchiveInfo] = field(default_factory=list)
    total_files: int = 0
    total_size: int = 0
    skipped_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scan_duration: float = 0.0


class Phase1Discovery:
    """Phase 1: File discovery and metadata extraction."""

    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".md", ".markdown", ".json", ".yaml", ".yml",
        ".html", ".css", ".scss", ".less",
        ".java", ".go", ".rs", ".c", ".cpp", ".h",
        ".sh", ".bash", ".zsh",
        ".sql", ".graphql",
        ".xml", ".toml", ".ini", ".cfg",
        ".txt", ".rst",
    }

    ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2"}

    IGNORE_DIRS = {
        "__pycache__", "node_modules", ".git", ".svn", ".hg",
        ".venv", "venv", "env", ".env",
        "dist", "build", "out", "target",
        ".idea", ".vscode", ".vs",
        "coverage", ".nyc_output", ".pytest_cache",
        ".tox", ".eggs", "*.egg-info",
    }

    IGNORE_FILES = {
        ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes",
        "package-lock.json", "yarn.lock", "poetry.lock",
    }

    def __init__(
        self,
        temp_dir: Optional[str] = None,
        compute_hash: bool = True,
        extract_archives: bool = True,
        max_file_size: int = 50 * 1024 * 1024,  # 50MB
    ):
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="hypermatrix_")
        self.compute_hash = compute_hash
        self.extract_archives = extract_archives
        self.max_file_size = max_file_size
        self.result = DiscoveryResult(root_path="")

        logger.info(f"Phase1Discovery initialized with temp_dir: {self.temp_dir}")

    def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
        extensions: Optional[set[str]] = None,
    ) -> DiscoveryResult:
        """
        Scan directory recursively and discover all files.

        Args:
            directory: Root directory to scan
            recursive: Whether to scan subdirectories
            extensions: File extensions to include (None = all supported)

        Returns:
            DiscoveryResult with all discovered files
        """
        start_time = datetime.now()
        directory = Path(directory).resolve()

        self.result = DiscoveryResult(root_path=str(directory))
        extensions = extensions or self.SUPPORTED_EXTENSIONS

        logger.info(f"Starting directory scan: {directory}")
        logger.info(f"Recursive: {recursive}, Extensions: {len(extensions)}")

        if not directory.exists():
            error = f"Directory not found: {directory}"
            logger.error(error)
            self.result.errors.append(error)
            return self.result

        # Collect all files first
        all_files = list(self._walk_directory(directory, recursive))
        logger.info(f"Found {len(all_files)} total items to process")

        # Process files with progress bar
        iterator = tqdm(all_files, desc="Scanning files", unit="file") if TQDM_AVAILABLE else all_files

        for filepath in iterator:
            try:
                self._process_file(filepath, extensions)
            except Exception as e:
                error = f"Error processing {filepath}: {e}"
                logger.warning(error)
                self.result.errors.append(error)

        # Calculate totals
        self.result.total_files = len(self.result.files)
        self.result.total_size = sum(f.size for f in self.result.files)
        self.result.scan_duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Scan complete: {self.result.total_files} files, "
                   f"{self.result.total_size / 1024 / 1024:.2f} MB, "
                   f"{self.result.scan_duration:.2f}s")

        return self.result

    def _walk_directory(
        self,
        directory: Path,
        recursive: bool,
    ) -> Generator[Path, None, None]:
        """Walk directory and yield file paths."""
        if recursive:
            for root, dirs, files in os.walk(directory):
                # Filter ignored directories
                dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

                for filename in files:
                    if filename not in self.IGNORE_FILES:
                        yield Path(root) / filename
        else:
            for item in directory.iterdir():
                if item.is_file() and item.name not in self.IGNORE_FILES:
                    yield item

    def _process_file(self, filepath: Path, extensions: set[str]):
        """Process a single file."""
        ext = filepath.suffix.lower()

        # Check if archive
        if self.extract_archives and self._is_archive(filepath):
            logger.debug(f"Found archive: {filepath}")
            self._handle_archive(filepath, extensions)
            return

        # Check extension
        if ext not in extensions:
            self.result.skipped_files.append(str(filepath))
            return

        # Check file size
        try:
            size = filepath.stat().st_size
            if size > self.max_file_size:
                logger.warning(f"File too large, skipping: {filepath} ({size / 1024 / 1024:.2f} MB)")
                self.result.skipped_files.append(str(filepath))
                return
        except OSError as e:
            logger.warning(f"Cannot stat file {filepath}: {e}")
            return

        # Extract metadata
        metadata = self.extract_metadata(str(filepath))
        if metadata:
            self.result.files.append(metadata)
            logger.debug(f"Discovered: {filepath.name} ({metadata.size} bytes)")

    def extract_metadata(
        self,
        filepath: str,
        compute_hash: Optional[bool] = None,
    ) -> Optional[FileMetadata]:
        """
        Extract metadata from a file.

        Args:
            filepath: Path to the file
            compute_hash: Override instance setting for hash computation

        Returns:
            FileMetadata or None if file cannot be read
        """
        filepath = Path(filepath)
        compute_hash = compute_hash if compute_hash is not None else self.compute_hash

        try:
            stat = filepath.stat()

            metadata = FileMetadata(
                filepath=str(filepath.resolve()),
                filename=filepath.name,
                extension=filepath.suffix.lower(),
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )

            if compute_hash and stat.st_size <= self.max_file_size:
                hashes = self._compute_file_hashes(filepath)
                metadata.hash_md5 = hashes.get("md5")
                metadata.hash_sha256 = hashes.get("sha256")

            logger.debug(f"Extracted metadata for: {filepath.name}")
            return metadata

        except (OSError, IOError) as e:
            logger.error(f"Cannot extract metadata from {filepath}: {e}")
            return None

    def _compute_file_hashes(self, filepath: Path) -> dict[str, str]:
        """Compute MD5 and SHA256 hashes for a file."""
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()

        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5_hash.update(chunk)
                    sha256_hash.update(chunk)

            return {
                "md5": md5_hash.hexdigest(),
                "sha256": sha256_hash.hexdigest(),
            }
        except (OSError, IOError) as e:
            logger.warning(f"Cannot compute hash for {filepath}: {e}")
            return {}

    def _is_archive(self, filepath: Path) -> bool:
        """Check if file is a supported archive."""
        name = filepath.name.lower()
        return any(name.endswith(ext) for ext in self.ARCHIVE_EXTENSIONS)

    def handle_zips(
        self,
        archive_path: str,
        extensions: Optional[set[str]] = None,
    ) -> ArchiveInfo:
        """
        Extract and process a ZIP archive.

        Args:
            archive_path: Path to the archive
            extensions: File extensions to include from archive

        Returns:
            ArchiveInfo with extraction details
        """
        return self._handle_archive(Path(archive_path), extensions)

    def _handle_archive(
        self,
        archive_path: Path,
        extensions: Optional[set[str]] = None,
    ) -> Optional[ArchiveInfo]:
        """Handle archive extraction and processing."""
        extensions = extensions or self.SUPPORTED_EXTENSIONS
        extract_dir = Path(self.temp_dir) / f"extract_{archive_path.stem}"

        logger.info(f"Extracting archive: {archive_path}")

        try:
            extract_dir.mkdir(parents=True, exist_ok=True)

            # Extract based on type
            if archive_path.suffix.lower() == ".zip":
                self._extract_zip(archive_path, extract_dir)
            elif ".tar" in archive_path.name.lower():
                self._extract_tar(archive_path, extract_dir)
            else:
                logger.warning(f"Unsupported archive type: {archive_path}")
                return None

            # Scan extracted files
            extracted_files = []
            total_size = 0

            for root, _, files in os.walk(extract_dir):
                for filename in files:
                    filepath = Path(root) / filename
                    ext = filepath.suffix.lower()

                    if ext in extensions:
                        metadata = self.extract_metadata(str(filepath))
                        if metadata:
                            metadata.is_from_archive = True
                            metadata.archive_source = str(archive_path)
                            extracted_files.append(metadata)
                            total_size += metadata.size

            self.result.files.extend(extracted_files)

            archive_info = ArchiveInfo(
                archive_path=str(archive_path),
                extract_path=str(extract_dir),
                file_count=len(extracted_files),
                total_size=total_size,
                archive_type=archive_path.suffix.lower(),
            )
            self.result.archives.append(archive_info)

            logger.info(f"Extracted {len(extracted_files)} files from {archive_path.name}")
            return archive_info

        except Exception as e:
            error = f"Failed to extract {archive_path}: {e}"
            logger.error(error)
            self.result.errors.append(error)
            return None

    def _extract_zip(self, archive_path: Path, extract_dir: Path):
        """Extract a ZIP archive."""
        with zipfile.ZipFile(archive_path, "r") as zf:
            # Get list of files for progress
            members = zf.namelist()
            iterator = tqdm(members, desc=f"Extracting {archive_path.name}", unit="file") if TQDM_AVAILABLE else members

            for member in iterator:
                try:
                    zf.extract(member, extract_dir)
                except Exception as e:
                    logger.warning(f"Cannot extract {member}: {e}")

    def _extract_tar(self, archive_path: Path, extract_dir: Path):
        """Extract a TAR archive (including .tar.gz, .tgz, .tar.bz2)."""
        mode = "r:*"  # Auto-detect compression
        with tarfile.open(archive_path, mode) as tf:
            members = tf.getmembers()
            iterator = tqdm(members, desc=f"Extracting {archive_path.name}", unit="file") if TQDM_AVAILABLE else members

            for member in iterator:
                try:
                    tf.extract(member, extract_dir)
                except Exception as e:
                    logger.warning(f"Cannot extract {member.name}: {e}")

    def cleanup(self):
        """Clean up temporary files."""
        if Path(self.temp_dir).exists():
            logger.info(f"Cleaning up temp directory: {self.temp_dir}")
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def get_files_by_extension(self) -> dict[str, list[FileMetadata]]:
        """Group discovered files by extension."""
        by_ext: dict[str, list[FileMetadata]] = {}
        for file in self.result.files:
            ext = file.extension
            if ext not in by_ext:
                by_ext[ext] = []
            by_ext[ext].append(file)
        return by_ext

    def get_summary(self) -> dict:
        """Get discovery summary."""
        by_ext = self.get_files_by_extension()
        return {
            "root_path": self.result.root_path,
            "total_files": self.result.total_files,
            "total_size_mb": round(self.result.total_size / 1024 / 1024, 2),
            "archives_processed": len(self.result.archives),
            "files_from_archives": sum(1 for f in self.result.files if f.is_from_archive),
            "skipped_files": len(self.result.skipped_files),
            "errors": len(self.result.errors),
            "scan_duration_seconds": round(self.result.scan_duration, 2),
            "files_by_extension": {ext: len(files) for ext, files in by_ext.items()},
        }
