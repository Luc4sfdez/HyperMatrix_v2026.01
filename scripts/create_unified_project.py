#!/usr/bin/env python
"""
Create Unified Project - Mass Fusion Script

This script analyzes all file versions in the database, identifies common
directory structures, and creates a unified "golden" project with fused
versions of all files in their proper locations.

Usage:
    python create_unified_project.py [--output-dir <path>] [--min-versions 2]
"""

import argparse
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.fusion import IntelligentFusion, ConflictResolution


@dataclass
class FileGroup:
    """Group of file versions with same relative path."""
    relative_path: str
    versions: List[str]  # Full file paths
    hashes: Set[str]     # Unique hashes

    @property
    def version_count(self) -> int:
        return len(self.versions)

    @property
    def unique_count(self) -> int:
        return len(self.hashes)

    @property
    def needs_fusion(self) -> bool:
        """True if there are multiple unique versions."""
        return self.unique_count > 1

    @property
    def is_python(self) -> bool:
        return self.relative_path.endswith('.py')


@dataclass
class FusionStats:
    """Statistics for the fusion process."""
    total_files: int = 0
    files_with_versions: int = 0
    files_fused: int = 0
    files_copied: int = 0
    files_skipped: int = 0
    fusion_errors: int = 0
    directories_created: int = 0


class UnifiedProjectBuilder:
    """
    Builds a unified project by fusing multiple versions of files.
    """

    def __init__(self, db_path: str, output_dir: str, min_versions: int = 2):
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        self.min_versions = min_versions
        self.stats = FusionStats()
        self.file_groups: Dict[str, FileGroup] = {}
        self.fusion_log: List[Dict] = []

    def analyze_structure(self) -> Dict[str, FileGroup]:
        """Analyze database to find file groups and their versions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all files with their paths and hashes
        cursor.execute('''
            SELECT filepath, hash FROM files
            WHERE filepath LIKE '%TGD%' OR filepath LIKE '%tgd%'
        ''')

        # Group by relative path
        path_versions = defaultdict(lambda: {'files': [], 'hashes': set()})

        for filepath, file_hash in cursor.fetchall():
            p = Path(filepath)
            rel_path = self._extract_relative_path(p)

            if rel_path:
                path_versions[rel_path]['files'].append(filepath)
                if file_hash:
                    path_versions[rel_path]['hashes'].add(file_hash)

        conn.close()

        # Create FileGroup objects
        for rel_path, data in path_versions.items():
            if len(data['files']) >= self.min_versions:
                self.file_groups[rel_path] = FileGroup(
                    relative_path=rel_path,
                    versions=data['files'],
                    hashes=data['hashes']
                )

        self.stats.total_files = len(path_versions)
        self.stats.files_with_versions = len(self.file_groups)

        return self.file_groups

    def _extract_relative_path(self, filepath: Path) -> Optional[str]:
        """Extract relative path within project from full path."""
        parts = filepath.parts

        # Find project root marker
        for i, part in enumerate(parts):
            if 'CONSOLIDACION' in part.upper():
                # Next part is project name, rest is relative path
                if i + 2 < len(parts):
                    rel_parts = parts[i + 2:]
                    return '/'.join(rel_parts)
                break

        return None

    def _determine_best_structure(self) -> str:
        """Determine the most common/best directory structure."""
        # Count directory structures
        structures = defaultdict(int)

        for rel_path in self.file_groups.keys():
            parts = rel_path.split('/')
            if len(parts) > 1:
                # Use first level directory as structure indicator
                structures[parts[0]] += 1

        # Return most common structure
        if structures:
            return max(structures, key=structures.get)
        return "Python"

    def build(self, dry_run: bool = False) -> FusionStats:
        """
        Build the unified project.

        Args:
            dry_run: If True, only analyze without creating files.
        """
        print("=" * 70)
        print("UNIFIED PROJECT BUILDER")
        print("=" * 70)
        print(f"Database: {self.db_path}")
        print(f"Output: {self.output_dir}")
        print(f"Min versions: {self.min_versions}")
        print()

        # Analyze structure
        print("Analyzing file structure...")
        self.analyze_structure()
        print(f"  Total unique paths: {self.stats.total_files}")
        print(f"  Paths with {self.min_versions}+ versions: {self.stats.files_with_versions}")
        print()

        if dry_run:
            self._show_analysis()
            return self.stats

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Process each file group
        print("Processing files...")
        print("-" * 70)

        for rel_path, group in sorted(self.file_groups.items()):
            self._process_file_group(group)

        # Generate report
        self._generate_report()

        print()
        print("=" * 70)
        print("BUILD COMPLETE")
        print("=" * 70)
        print(f"  Files fused: {self.stats.files_fused}")
        print(f"  Files copied (single version): {self.stats.files_copied}")
        print(f"  Files skipped (non-Python): {self.stats.files_skipped}")
        print(f"  Errors: {self.stats.fusion_errors}")
        print(f"  Output directory: {self.output_dir}")

        return self.stats

    def _process_file_group(self, group: FileGroup):
        """Process a single file group."""
        output_path = self.output_dir / group.relative_path

        # Create parent directories
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check which files actually exist
        existing_files = [f for f in group.versions if Path(f).exists()]

        if not existing_files:
            print(f"  [SKIP] {group.relative_path} - no files exist")
            self.stats.files_skipped += 1
            return

        # For Python files with multiple unique versions: fuse
        if group.is_python and group.needs_fusion and len(existing_files) > 1:
            self._fuse_files(group, existing_files, output_path)
        else:
            # Just copy the best version
            self._copy_best_version(group, existing_files, output_path)

    def _fuse_files(self, group: FileGroup, files: List[str], output_path: Path):
        """Fuse multiple Python file versions."""
        try:
            fusion = IntelligentFusion(conflict_resolution=ConflictResolution.KEEP_LARGEST)

            # Analyze all versions
            for fp in files:
                fusion.analyze_file(fp)

            if len(fusion.versions) < 2:
                # Not enough valid versions to fuse
                self._copy_best_version(group, files, output_path)
                return

            # Perform fusion
            result = fusion.fuse()

            if result.success:
                output_path.write_text(result.fused_code, encoding='utf-8')
                self.stats.files_fused += 1

                status = f"FUSED {len(fusion.versions)} versions"
                if result.functions_added:
                    status += f", +{len(result.functions_added)} funcs"
                if result.classes_added:
                    status += f", +{len(result.classes_added)} classes"

                print(f"  [OK] {group.relative_path} - {status}")

                self.fusion_log.append({
                    'path': group.relative_path,
                    'action': 'fused',
                    'versions': len(files),
                    'unique': group.unique_count,
                    'functions_added': result.functions_added,
                    'classes_added': result.classes_added,
                    'stats': result.stats
                })
            else:
                # Fusion failed, copy best version
                self._copy_best_version(group, files, output_path)
                self.stats.fusion_errors += 1

        except Exception as e:
            print(f"  [ERR] {group.relative_path} - {str(e)[:50]}")
            self.stats.fusion_errors += 1
            # Try to copy best version as fallback
            try:
                self._copy_best_version(group, files, output_path)
            except:
                pass

    def _copy_best_version(self, group: FileGroup, files: List[str], output_path: Path):
        """Copy the best (largest/most complete) version."""
        # Select best file by size
        best_file = max(files, key=lambda f: Path(f).stat().st_size if Path(f).exists() else 0)

        try:
            shutil.copy2(best_file, output_path)
            self.stats.files_copied += 1

            print(f"  [CP] {group.relative_path} - copied best of {len(files)}")

            self.fusion_log.append({
                'path': group.relative_path,
                'action': 'copied',
                'source': best_file,
                'versions': len(files)
            })
        except Exception as e:
            print(f"  [ERR] {group.relative_path} - copy failed: {e}")
            self.stats.fusion_errors += 1

    def _show_analysis(self):
        """Show analysis without building."""
        print("ANALYSIS (dry run)")
        print("-" * 70)

        # Group by action needed
        to_fuse = []
        to_copy = []

        for rel_path, group in sorted(self.file_groups.items()):
            existing = sum(1 for f in group.versions if Path(f).exists())

            if group.is_python and group.needs_fusion and existing > 1:
                to_fuse.append((rel_path, group, existing))
            else:
                to_copy.append((rel_path, group, existing))

        print(f"\nFILES TO FUSE ({len(to_fuse)}):")
        for rel_path, group, existing in to_fuse[:20]:
            print(f"  {rel_path}")
            print(f"    {existing} existing, {group.unique_count} unique versions")
        if len(to_fuse) > 20:
            print(f"  ... and {len(to_fuse) - 20} more")

        print(f"\nFILES TO COPY ({len(to_copy)}):")
        for rel_path, group, existing in to_copy[:10]:
            print(f"  {rel_path} ({existing} versions)")
        if len(to_copy) > 10:
            print(f"  ... and {len(to_copy) - 10} more")

    def _generate_report(self):
        """Generate JSON report of the build process."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'output_dir': str(self.output_dir),
            'stats': {
                'total_files': self.stats.total_files,
                'files_with_versions': self.stats.files_with_versions,
                'files_fused': self.stats.files_fused,
                'files_copied': self.stats.files_copied,
                'files_skipped': self.stats.files_skipped,
                'fusion_errors': self.stats.fusion_errors
            },
            'files': self.fusion_log
        }

        report_path = self.output_dir / '_fusion_report.json'
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
        print(f"\nReport saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Create unified project from multiple versions',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--output-dir', '-o',
                        default='E:/TGD_UNIFIED_PROJECT',
                        help='Output directory for unified project')
    parser.add_argument('--db',
                        default='hypermatrix.db',
                        help='Path to HyperMatrix database')
    parser.add_argument('--min-versions', '-m',
                        type=int, default=2,
                        help='Minimum versions required to include file')
    parser.add_argument('--dry-run', '-n',
                        action='store_true',
                        help='Only analyze, do not create files')

    args = parser.parse_args()

    # Find database
    db_path = Path(args.db)
    if not db_path.exists():
        db_path = Path(__file__).parent.parent / 'hypermatrix.db'

    if not db_path.exists():
        print(f"ERROR: Database not found: {args.db}")
        sys.exit(1)

    builder = UnifiedProjectBuilder(
        db_path=str(db_path),
        output_dir=args.output_dir,
        min_versions=args.min_versions
    )

    builder.build(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
