"""
HyperMatrix v2026 - File Watcher
Monitors file changes for incremental analysis.
"""

import hashlib
import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from queue import Queue, Empty


@dataclass
class FileChange:
    """Represents a file change event."""
    filepath: str
    change_type: str  # created, modified, deleted
    timestamp: datetime
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None


@dataclass
class WatcherConfig:
    """Configuration for the file watcher."""
    watch_patterns: list[str] = field(default_factory=lambda: ["*.py", "*.js", "*.ts"])
    ignore_patterns: list[str] = field(default_factory=lambda: [
        "__pycache__", "*.pyc", ".git", "node_modules", ".venv", "venv",
        "*.egg-info", "dist", "build", ".pytest_cache"
    ])
    debounce_ms: int = 500
    recursive: bool = True
    poll_interval: float = 1.0


class FileHashCache:
    """Cache for file hashes to detect changes."""

    def __init__(self):
        self._cache: dict[str, tuple[str, float]] = {}  # filepath -> (hash, mtime)

    def get_hash(self, filepath: str) -> Optional[str]:
        """Get cached hash for a file."""
        if filepath in self._cache:
            return self._cache[filepath][0]
        return None

    def update(self, filepath: str, file_hash: str, mtime: float):
        """Update cache for a file."""
        self._cache[filepath] = (file_hash, mtime)

    def remove(self, filepath: str):
        """Remove file from cache."""
        self._cache.pop(filepath, None)

    def get_mtime(self, filepath: str) -> Optional[float]:
        """Get cached modification time."""
        if filepath in self._cache:
            return self._cache[filepath][1]
        return None

    def clear(self):
        """Clear the cache."""
        self._cache.clear()


class FileWatcher:
    """Watch directory for file changes."""

    def __init__(
        self,
        root_path: str,
        config: Optional[WatcherConfig] = None,
        on_change: Optional[Callable[[FileChange], None]] = None,
    ):
        self.root_path = Path(root_path)
        self.config = config or WatcherConfig()
        self.on_change = on_change

        self._hash_cache = FileHashCache()
        self._change_queue: Queue[FileChange] = Queue()
        self._running = False
        self._watch_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None
        self._debounce_timers: dict[str, threading.Timer] = {}

    def start(self):
        """Start watching for file changes."""
        if self._running:
            return

        self._running = True

        # Initial scan to populate cache
        self._initial_scan()

        # Start watch thread
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

        # Start processing thread
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

    def stop(self):
        """Stop watching for file changes."""
        self._running = False

        # Cancel any pending timers
        for timer in self._debounce_timers.values():
            timer.cancel()
        self._debounce_timers.clear()

        # Wait for threads
        if self._watch_thread:
            self._watch_thread.join(timeout=2)
        if self._process_thread:
            self._process_thread.join(timeout=2)

    def _initial_scan(self):
        """Scan directory and populate hash cache."""
        for filepath in self._get_watched_files():
            try:
                file_hash = self._calculate_hash(filepath)
                mtime = os.path.getmtime(filepath)
                self._hash_cache.update(filepath, file_hash, mtime)
            except (OSError, IOError):
                pass

    def _get_watched_files(self) -> list[str]:
        """Get list of files matching watch patterns."""
        files = []

        for pattern in self.config.watch_patterns:
            if self.config.recursive:
                glob_pattern = f"**/{pattern}"
            else:
                glob_pattern = pattern

            for path in self.root_path.glob(glob_pattern):
                if path.is_file() and not self._should_ignore(path):
                    files.append(str(path))

        return files

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        path_str = str(path)

        for pattern in self.config.ignore_patterns:
            if pattern.startswith("*"):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True

        return False

    def _calculate_hash(self, filepath: str) -> str:
        """Calculate SHA256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return ""

    def _watch_loop(self):
        """Main watch loop using polling."""
        while self._running:
            try:
                self._check_for_changes()
                time.sleep(self.config.poll_interval)
            except Exception as e:
                print(f"[Watcher] Error: {e}")
                time.sleep(1)

    def _check_for_changes(self):
        """Check for file changes."""
        current_files = set(self._get_watched_files())
        cached_files = set(self._hash_cache._cache.keys())

        # Check for new and modified files
        for filepath in current_files:
            try:
                mtime = os.path.getmtime(filepath)
                cached_mtime = self._hash_cache.get_mtime(filepath)

                if cached_mtime is None:
                    # New file
                    self._schedule_change(filepath, "created")

                elif mtime > cached_mtime:
                    # Potentially modified - check hash
                    new_hash = self._calculate_hash(filepath)
                    old_hash = self._hash_cache.get_hash(filepath)

                    if new_hash != old_hash:
                        self._schedule_change(filepath, "modified", old_hash, new_hash)
                    else:
                        # Only mtime changed, update cache
                        self._hash_cache.update(filepath, new_hash, mtime)

            except (OSError, IOError):
                pass

        # Check for deleted files
        for filepath in cached_files - current_files:
            self._schedule_change(filepath, "deleted")

    def _schedule_change(
        self,
        filepath: str,
        change_type: str,
        old_hash: Optional[str] = None,
        new_hash: Optional[str] = None,
    ):
        """Schedule a change event with debouncing."""
        # Cancel existing timer for this file
        if filepath in self._debounce_timers:
            self._debounce_timers[filepath].cancel()

        def emit_change():
            change = FileChange(
                filepath=filepath,
                change_type=change_type,
                timestamp=datetime.now(),
                old_hash=old_hash,
                new_hash=new_hash,
            )
            self._change_queue.put(change)

            # Update cache
            if change_type == "deleted":
                self._hash_cache.remove(filepath)
            else:
                try:
                    file_hash = new_hash or self._calculate_hash(filepath)
                    mtime = os.path.getmtime(filepath)
                    self._hash_cache.update(filepath, file_hash, mtime)
                except (OSError, IOError):
                    pass

            # Remove timer reference
            self._debounce_timers.pop(filepath, None)

        # Schedule with debounce
        timer = threading.Timer(self.config.debounce_ms / 1000, emit_change)
        self._debounce_timers[filepath] = timer
        timer.start()

    def _process_loop(self):
        """Process change events."""
        while self._running:
            try:
                change = self._change_queue.get(timeout=1)

                if self.on_change:
                    self.on_change(change)

            except Empty:
                continue
            except Exception as e:
                print(f"[Watcher] Process error: {e}")


class IncrementalAnalyzer:
    """Incremental analyzer that responds to file changes."""

    def __init__(self, db_manager, project_id: int, root_path: str):
        self.db = db_manager
        self.project_id = project_id
        self.root_path = root_path

        self._watcher: Optional[FileWatcher] = None
        self._change_handlers: list[Callable[[FileChange], None]] = []

    def add_handler(self, handler: Callable[[FileChange], None]):
        """Add a change handler."""
        self._change_handlers.append(handler)

    def start_watching(self, config: Optional[WatcherConfig] = None):
        """Start watching for changes."""
        self._watcher = FileWatcher(
            root_path=self.root_path,
            config=config,
            on_change=self._handle_change,
        )
        self._watcher.start()
        print(f"[+] Watching {self.root_path} for changes...")

    def stop_watching(self):
        """Stop watching for changes."""
        if self._watcher:
            self._watcher.stop()
            print("[+] Stopped watching for changes")

    def _handle_change(self, change: FileChange):
        """Handle a file change event."""
        print(f"[*] {change.change_type.upper()}: {change.filepath}")

        # Re-analyze the file
        if change.change_type in ["created", "modified"]:
            self._reanalyze_file(change.filepath)
        elif change.change_type == "deleted":
            self._remove_file(change.filepath)

        # Notify handlers
        for handler in self._change_handlers:
            try:
                handler(change)
            except Exception as e:
                print(f"[!] Handler error: {e}")

    def _reanalyze_file(self, filepath: str):
        """Re-analyze a single file."""
        from ..phases.phase2_analysis import AnalysisPhase, FileInfo

        try:
            # Get file info
            path = Path(filepath)
            file_info = FileInfo(
                filepath=filepath,
                filename=path.name,
                extension=path.suffix,
                size=path.stat().st_size,
                modified_time=datetime.fromtimestamp(path.stat().st_mtime),
            )

            # Remove old data
            self._remove_file(filepath)

            # Re-analyze
            analysis = AnalysisPhase(self.db)
            analysis.analyze_file(file_info, self.project_id)

            print(f"    [+] Re-analyzed: {path.name}")

        except Exception as e:
            print(f"    [!] Analysis error: {e}")

    def _remove_file(self, filepath: str):
        """Remove file data from database."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                # Find file ID
                cursor.execute(
                    "SELECT id FROM files WHERE project_id = ? AND filepath = ?",
                    (self.project_id, filepath)
                )
                row = cursor.fetchone()

                if row:
                    file_id = row[0]

                    # Delete related records
                    cursor.execute("DELETE FROM functions WHERE file_id = ?", (file_id,))
                    cursor.execute("DELETE FROM classes WHERE file_id = ?", (file_id,))
                    cursor.execute("DELETE FROM variables WHERE file_id = ?", (file_id,))
                    cursor.execute("DELETE FROM imports WHERE file_id = ?", (file_id,))
                    cursor.execute("DELETE FROM data_flow WHERE file_id = ?", (file_id,))
                    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))

                    conn.commit()
                    print(f"    [+] Removed from database: {Path(filepath).name}")

        except Exception as e:
            print(f"    [!] Remove error: {e}")


def watch_project(db_path: str, project_id: int, root_path: str):
    """Convenience function to start watching a project."""
    from ..core.db_manager import DBManager

    db = DBManager(db_path)
    analyzer = IncrementalAnalyzer(db, project_id, root_path)

    analyzer.start_watching()

    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        analyzer.stop_watching()
