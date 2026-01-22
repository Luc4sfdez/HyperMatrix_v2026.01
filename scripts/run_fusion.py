#!/usr/bin/env python
"""
CLI script for running intelligent fusion on file versions.

Usage:
    python run_fusion.py <filename_pattern> [--output <output_file>]

Examples:
    python run_fusion.py tgd_parser.py
    python run_fusion.py config.py --output fused_config.py
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.fusion import IntelligentFusion, ConflictResolution


def get_file_versions_from_db(filename_pattern: str, db_path: str) -> list:
    """Query database to find all versions of a file."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT f.filepath, f.hash
        FROM files f
        WHERE f.filepath LIKE ?
        ORDER BY f.filepath
    ''', (f'%{filename_pattern}%',))

    # Deduplicate by hash (keep first occurrence)
    seen_hashes = set()
    unique_files = []

    for filepath, file_hash in cursor.fetchall():
        if file_hash not in seen_hashes:
            seen_hashes.add(file_hash)
            unique_files.append(filepath)

    conn.close()
    return unique_files


def main():
    parser = argparse.ArgumentParser(
        description='Intelligent fusion of multiple file versions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s tgd_parser.py
  %(prog)s config.py --output fused_config.py
  %(prog)s main.py --report-only
        """
    )

    parser.add_argument('pattern', help='Filename pattern to search for')
    parser.add_argument('--output', '-o', help='Output file for fused code')
    parser.add_argument('--report-only', '-r', action='store_true',
                        help='Only show analysis report, do not generate fused code')
    parser.add_argument('--db', default='hypermatrix.db',
                        help='Path to HyperMatrix database')
    parser.add_argument('--conflict-strategy', '-c',
                        choices=['keep_largest', 'keep_complex', 'manual'],
                        default='keep_largest',
                        help='Conflict resolution strategy')

    args = parser.parse_args()

    # Find database
    db_path = Path(args.db)
    if not db_path.exists():
        db_path = Path(__file__).parent.parent / 'hypermatrix.db'
        if not db_path.exists():
            print(f"ERROR: Database not found: {args.db}")
            sys.exit(1)

    print(f"=" * 70)
    print(f"HYPERMATRIX INTELLIGENT FUSION")
    print(f"=" * 70)
    print(f"Pattern: {args.pattern}")
    print(f"Database: {db_path}")
    print()

    # Get file versions from database
    file_versions = get_file_versions_from_db(args.pattern, str(db_path))

    if not file_versions:
        print(f"No files found matching pattern: {args.pattern}")
        sys.exit(1)

    print(f"Found {len(file_versions)} unique versions:")
    for i, fp in enumerate(file_versions, 1):
        print(f"  {i}. {Path(fp).name[:50]}...")
    print()

    # Check which files actually exist
    existing_files = [fp for fp in file_versions if Path(fp).exists()]

    if not existing_files:
        print("ERROR: None of the files exist on disk.")
        print("The database contains references to files that may have been moved/deleted.")
        sys.exit(1)

    if len(existing_files) < len(file_versions):
        print(f"WARNING: Only {len(existing_files)} of {len(file_versions)} files exist on disk.")
        print()

    # Initialize fusion engine
    conflict_strategy = {
        'keep_largest': ConflictResolution.KEEP_LARGEST,
        'keep_complex': ConflictResolution.KEEP_MOST_COMPLEX,
        'manual': ConflictResolution.MANUAL
    }[args.conflict_strategy]

    fusion = IntelligentFusion(conflict_resolution=conflict_strategy)

    # Analyze all versions
    print("Analyzing versions...")
    for fp in existing_files:
        analysis = fusion.analyze_file(fp)
        if analysis:
            print(f"  [OK] {Path(fp).name}: {len(analysis.functions)} funcs, {len(analysis.classes)} classes")
        else:
            print(f"  [FAIL] {Path(fp).name}")
    print()

    # Generate and show report
    report = fusion.generate_fusion_report()
    print(report)
    print()

    if args.report_only:
        print("Report-only mode. Exiting.")
        return

    # Perform fusion
    print("=" * 70)
    print("PERFORMING FUSION...")
    print("=" * 70)

    result = fusion.fuse()

    if result.success:
        print(f"\nFUSION SUCCESSFUL!")
        print(f"-" * 40)
        print(f"Base version: {Path(result.base_version).name}")
        print(f"Versions merged: {len(result.versions_merged)}")
        print(f"Functions in base: {result.stats['base_functions']}")
        print(f"Functions added: {result.stats['functions_added']}")
        print(f"  -> {', '.join(result.functions_added) if result.functions_added else 'none'}")
        print(f"Classes added: {result.stats['classes_added']}")
        print(f"  -> {', '.join(result.classes_added) if result.classes_added else 'none'}")
        print(f"Total functions: {result.stats['total_functions']}")
        print(f"Total classes: {result.stats['total_classes']}")
        print(f"Fused code lines: {result.stats['fused_lines']}")

        conflicts_detected = result.stats.get('conflicts_detected', 0)
        if conflicts_detected:
            print(f"\nConflicts: {conflicts_detected}")
            print(f"  Resolved: {result.stats['conflicts_resolved']}")
            print(f"  Pending: {result.stats['conflicts_pending']}")

        # Save fused code
        if args.output:
            output_path = Path(args.output)
        else:
            # Generate default output name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = Path(__file__).parent.parent / 'output' / f'fused_{args.pattern}_{timestamp}.py'

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.fused_code, encoding='utf-8')

        print(f"\nFused code saved to: {output_path}")
        print(f"File size: {len(result.fused_code):,} bytes")

    else:
        print(f"\nFUSION FAILED!")
        for warning in result.warnings:
            print(f"  - {warning}")
        sys.exit(1)


if __name__ == '__main__':
    main()
