#!/usr/bin/env python
"""
Create TRUE Unified Project - Intelligent Merge of All Versions

This script:
1. Gets all consolidation groups from the database
2. For each group, runs intelligent fusion combining ALL unique capabilities
3. Creates a SINGLE clean project structure with merged files
"""

import sqlite3
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.fusion import IntelligentFusion, ConflictResolution

# Target project structure
TARGET_STRUCTURE = {
    'parsers': ['ef_*.py', 'tgd_parser.py', 'vu_parser.py', '*_parser.py'],
    'models': ['*.py'],
    'core': ['*.py'],
    'api': ['*.py', '*_controller.py'],
    'crypto': ['*.py', '*_validator.py'],
    'utils': ['*.py'],
    'frontend/js': ['*.js'],
    'frontend/css': ['*.css'],
    'tests': ['test_*.py'],
}


def get_consolidation_groups(db_path: str) -> list:
    """Get all consolidation groups with their siblings from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get proposals with siblings
    cursor.execute('''
        SELECT p.id, p.filename, p.master_path, p.confidence, p.sibling_count, p.average_affinity
        FROM consolidation_proposals p
        WHERE p.sibling_count > 1
        ORDER BY p.average_affinity DESC
    ''')

    proposals = cursor.fetchall()

    groups = []
    for prop_id, filename, master_path, confidence, sibling_count, avg_affinity in proposals:
        # Get all siblings for this group
        cursor.execute('''
            SELECT sibling_path, affinity_to_master
            FROM consolidation_siblings
            WHERE proposal_id = ?
        ''', (prop_id,))

        siblings = cursor.fetchall()

        # Collect all file paths (master + siblings)
        all_paths = [master_path] + [s[0] for s in siblings]

        groups.append({
            'filename': filename,
            'master_path': master_path,
            'confidence': confidence,
            'sibling_count': sibling_count,
            'avg_affinity': avg_affinity,
            'all_paths': all_paths
        })

    conn.close()
    return groups


def determine_target_folder(filename: str, filepath: str) -> str:
    """Determine the target folder based on filename and path patterns."""

    filepath_lower = filepath.lower()
    filename_lower = filename.lower()

    # Parsers
    if '/parsers/' in filepath_lower or filename_lower.startswith('ef_') or 'parser' in filename_lower:
        return 'parsers'

    # Models
    if '/models/' in filepath_lower:
        return 'models'

    # Core
    if '/core/' in filepath_lower:
        return 'core'

    # API
    if '/api/' in filepath_lower or 'controller' in filename_lower:
        return 'api'

    # Crypto/Validators
    if 'validator' in filename_lower or 'crypto' in filename_lower or '/crypto/' in filepath_lower:
        return 'crypto'

    # Utils
    if '/utils/' in filepath_lower or 'util' in filename_lower:
        return 'utils'

    # Frontend JS
    if filename_lower.endswith('.js'):
        return 'frontend/js'

    # Frontend CSS
    if filename_lower.endswith('.css'):
        return 'frontend/css'

    # Tests
    if filename_lower.startswith('test_') or '/tests/' in filepath_lower:
        return 'tests'

    # Default: root src
    return 'src'


def fuse_group(group: dict, output_dir: Path) -> dict:
    """Fuse a single group of files and return result info."""

    filename = group['filename']
    all_paths = group['all_paths']

    # Filter to existing Python files
    existing_paths = [p for p in all_paths if Path(p).exists() and p.endswith('.py')]

    if not existing_paths:
        return {'status': 'skipped', 'reason': 'no existing Python files'}

    if len(existing_paths) == 1:
        # Only one version, just copy it
        target_folder = determine_target_folder(filename, existing_paths[0])
        target_path = output_dir / target_folder / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(existing_paths[0], target_path)
        return {
            'status': 'copied',
            'source': existing_paths[0],
            'target': str(target_path)
        }

    # Multiple versions - run fusion
    fusion = IntelligentFusion(conflict_resolution=ConflictResolution.KEEP_LARGEST)

    for fp in existing_paths:
        fusion.analyze_file(fp)

    if len(fusion.versions) < 2:
        # Couldn't analyze enough versions, copy best
        best = max(existing_paths, key=lambda p: Path(p).stat().st_size)
        target_folder = determine_target_folder(filename, best)
        target_path = output_dir / target_folder / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, target_path)
        return {
            'status': 'copied_best',
            'source': best,
            'target': str(target_path),
            'versions_tried': len(existing_paths)
        }

    # Perform fusion
    result = fusion.fuse()

    if result.success:
        target_folder = determine_target_folder(filename, group['master_path'])
        target_path = output_dir / target_folder / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(result.fused_code, encoding='utf-8')

        return {
            'status': 'fused',
            'target': str(target_path),
            'versions_merged': len(result.versions_merged),
            'functions_added': result.functions_added,
            'classes_added': result.classes_added,
            'stats': result.stats
        }
    else:
        # Fusion failed, copy best
        best = max(existing_paths, key=lambda p: Path(p).stat().st_size)
        target_folder = determine_target_folder(filename, best)
        target_path = output_dir / target_folder / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, target_path)
        return {
            'status': 'fusion_failed',
            'source': best,
            'target': str(target_path),
            'warnings': result.warnings
        }


def create_init_files(output_dir: Path):
    """Create __init__.py files in all Python package directories."""
    for subdir in output_dir.rglob('*'):
        if subdir.is_dir() and any(subdir.glob('*.py')):
            init_file = subdir / '__init__.py'
            if not init_file.exists():
                init_file.write_text('# Auto-generated\n', encoding='utf-8')


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Create TRUE unified project')
    parser.add_argument('--output', '-o', default='E:/TGD_UNIFIED_v2',
                        help='Output directory')
    parser.add_argument('--db', default='hypermatrix.db',
                        help='Database path')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be done')

    args = parser.parse_args()

    # Find database
    db_path = Path(args.db)
    if not db_path.exists():
        db_path = Path(__file__).parent.parent / 'hypermatrix.db'

    print('='*70)
    print('TRUE UNIFIED PROJECT BUILDER')
    print('='*70)
    print(f'Database: {db_path}')
    print(f'Output: {args.output}')
    print()

    # Get consolidation groups
    print('Loading consolidation groups...')
    groups = get_consolidation_groups(str(db_path))
    print(f'Found {len(groups)} groups to process')
    print()

    if args.dry_run:
        print('DRY RUN - showing what would be merged:')
        print('-'*70)
        for g in groups[:30]:
            target = determine_target_folder(g['filename'], g['master_path'])
            print(f"  {g['filename']} -> {target}/")
            print(f"    {g['sibling_count']} versions, {g['avg_affinity']:.0%} affinity")
        if len(groups) > 30:
            print(f'  ... and {len(groups)-30} more')
        return

    # Create output directory
    output_dir = Path(args.output)
    if output_dir.exists():
        print(f'Removing existing {output_dir}...')
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Process each group
    print('Processing groups...')
    print('-'*70)

    results = []
    stats = {'fused': 0, 'copied': 0, 'copied_best': 0, 'skipped': 0, 'failed': 0}

    for i, group in enumerate(groups, 1):
        filename = group['filename']
        print(f'[{i:3d}/{len(groups)}] {filename}...', end=' ')

        try:
            result = fuse_group(group, output_dir)
            results.append({'filename': filename, **result})

            status = result['status']
            if status == 'fused':
                added = len(result.get('functions_added', [])) + len(result.get('classes_added', []))
                print(f'FUSED ({result["versions_merged"]} versions, +{added} elements)')
                stats['fused'] += 1
            elif status == 'copied':
                print('copied (single version)')
                stats['copied'] += 1
            elif status == 'copied_best':
                print(f'copied best of {result["versions_tried"]}')
                stats['copied_best'] += 1
            elif status == 'skipped':
                print(f'skipped ({result["reason"]})')
                stats['skipped'] += 1
            else:
                print(f'{status}')
                stats['failed'] += 1

        except Exception as e:
            print(f'ERROR: {str(e)[:50]}')
            stats['failed'] += 1
            results.append({'filename': filename, 'status': 'error', 'error': str(e)})

    # Create __init__.py files
    print()
    print('Creating __init__.py files...')
    create_init_files(output_dir)

    # Save report
    report = {
        'timestamp': datetime.now().isoformat(),
        'output_dir': str(output_dir),
        'stats': stats,
        'files': results
    }

    report_path = output_dir / '_unification_report.json'
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')

    print()
    print('='*70)
    print('UNIFICATION COMPLETE')
    print('='*70)
    print(f'  Fused (merged): {stats["fused"]}')
    print(f'  Copied (single): {stats["copied"]}')
    print(f'  Copied (best): {stats["copied_best"]}')
    print(f'  Skipped: {stats["skipped"]}')
    print(f'  Failed: {stats["failed"]}')
    print(f'  Output: {output_dir}')
    print(f'  Report: {report_path}')


if __name__ == '__main__':
    main()
