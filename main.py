"""
HyperMatrix v2026 - Main Entry Point
Orchestrates all analysis phases.
"""

import sys
import logging
import argparse
from pathlib import Path

from utils.config import config, init_config, get_version
from src.phases import (
    Phase1Discovery,
    Phase1_5Deduplication,
    Phase2Analysis,
    Phase3Consolidation,
)
from src.core.db_manager import DBManager


# Configure logging
def setup_logging(verbose: bool = False):
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def print_banner():
    """Print application banner."""
    banner = f"""
+===========================================================+
|                  HyperMatrix v{get_version()}                    |
|           Code Analysis & DNA Extraction Engine           |
+===========================================================+
    """
    print(banner)


def run_analysis(
    target_dir: str,
    project_name: str = "default",
    db_path: str = "hypermatrix.db",
    skip_duplicates: bool = True,
    extract_archives: bool = True,
    consolidate: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run complete analysis pipeline.

    Args:
        target_dir: Directory to analyze
        project_name: Name for the project
        db_path: Path to SQLite database
        skip_duplicates: Skip duplicate files
        extract_archives: Extract and analyze ZIP/TAR files
        consolidate: Run Phase 3 consolidation
        verbose: Enable verbose logging

    Returns:
        Dictionary with analysis summary
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    print_banner()
    print(f"Target directory: {target_dir}")
    print(f"Project name: {project_name}")
    print("-" * 60)

    # Initialize database
    db_manager = DBManager(db_path)
    logger.info(f"Database initialized: {db_path}")

    # ===========================================================
    # PHASE 1: Discovery
    # ===========================================================
    print("\n[PHASE 1] Discovery - Scanning directory...")

    phase1 = Phase1Discovery(
        compute_hash=True,
        extract_archives=extract_archives,
    )

    discovery_result = phase1.scan_directory(target_dir)

    phase1_summary = phase1.get_summary()
    print(f"  [+] Found {phase1_summary['total_files']} files")
    print(f"  [+] Total size: {phase1_summary['total_size_mb']} MB")
    print(f"  [+] Archives processed: {phase1_summary['archives_processed']}")
    print(f"  [+] Duration: {phase1_summary['scan_duration_seconds']}s")

    if phase1_summary['errors']:
        print(f"  [!] Errors: {phase1_summary['errors']}")

    # ===========================================================
    # PHASE 1.5: Deduplication
    # ===========================================================
    print("\n[PHASE 1.5] Deduplication - Identifying duplicates...")

    phase1_5 = Phase1_5Deduplication()

    dedup_result = phase1_5.process(discovery_result)

    dedup_summary = phase1_5.get_summary()
    print(f"  [+] Unique files: {dedup_summary['unique_files']}")
    print(f"  [+] Duplicate groups: {dedup_summary['duplicate_groups']}")
    print(f"  [+] Total duplicates: {dedup_summary['total_duplicates']}")
    print(f"  [+] Wasted space: {dedup_summary['wasted_mb']} MB")

    # ===========================================================
    # PHASE 2: Analysis
    # ===========================================================
    print("\n[PHASE 2] Analysis - Parsing and extracting DNA...")

    phase2 = Phase2Analysis(
        db_manager=db_manager,
        skip_duplicates=skip_duplicates,
        extract_dna=True,
    )

    analysis_result = phase2.analyze_all_files(
        discovery_result,
        dedup_result if skip_duplicates else None,
        project_name,
    )

    phase2_summary = phase2.get_summary()
    print(f"  [+] Analyzed: {phase2_summary['analyzed_files']} files")
    print(f"  [+] Functions found: {phase2_summary['total_functions']}")
    print(f"  [+] Classes found: {phase2_summary['total_classes']}")
    print(f"  [+] Imports found: {phase2_summary['total_imports']}")
    print(f"  [+] DNA profiles: {phase2_summary['dna_profiles']}")
    print(f"  [+] Duration: {phase2_summary['analysis_duration_seconds']}s")

    if phase2_summary['failed_files'] > 0:
        print(f"  [!] Failed: {phase2_summary['failed_files']} files")

    # ===========================================================
    # PHASE 3: Consolidation (optional)
    # ===========================================================
    phase3_summary = None
    if consolidate:
        print("\n[PHASE 3] Consolidation - Detecting siblings...")

        phase3 = Phase3Consolidation(
            db_manager=db_manager,
            min_affinity_threshold=0.3,
        )

        consolidation_result = phase3.consolidate(
            discovery_result,
            analysis_result,
            project_id=1,  # Assuming first project
        )

        phase3_summary = phase3.get_summary()
        print(f"  [+] Sibling groups: {phase3_summary['sibling_groups']}")
        print(f"  [+] Files with siblings: {phase3_summary['files_with_siblings']}")
        print(f"  [+] Proposals generated: {phase3_summary['proposals_generated']}")
        print(f"  [+] High confidence: {phase3_summary['high_confidence_proposals']}")
        print(f"  [+] Duration: {phase3_summary['consolidation_duration_seconds']}s")

        if phase3_summary['errors']:
            print(f"  [!] Errors: {len(phase3_summary['errors'])}")

        # Print consolidation report
        phase3.print_report()

    # ===========================================================
    # Summary
    # ===========================================================
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

    total_summary = {
        "project_name": project_name,
        "target_directory": target_dir,
        "phase1": phase1_summary,
        "phase1_5": dedup_summary,
        "phase2": phase2_summary,
        "phase3": phase3_summary,
    }

    # Cleanup
    phase1.cleanup()
    logger.info("Temporary files cleaned up")

    return total_summary


def main():
    """Application entry point with CLI arguments."""
    parser = argparse.ArgumentParser(
        description="HyperMatrix v2026 - Code Analysis & DNA Extraction Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to analyze (default: current directory)",
    )

    parser.add_argument(
        "-n", "--name",
        default="default",
        help="Project name (default: 'default')",
    )

    parser.add_argument(
        "-d", "--database",
        default="hypermatrix.db",
        help="Database path (default: hypermatrix.db)",
    )

    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Don't skip duplicate files",
    )

    parser.add_argument(
        "--no-archives",
        action="store_true",
        help="Don't extract archives",
    )

    parser.add_argument(
        "-c", "--consolidate",
        action="store_true",
        help="Run Phase 3: Consolidation (detect siblings, propose masters)",
    )

    parser.add_argument(
        "-w", "--watch",
        action="store_true",
        help="Watch mode: monitor for file changes and re-analyze incrementally",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"HyperMatrix v{get_version()}",
    )

    args = parser.parse_args()

    # Validate directory
    target_dir = Path(args.directory).resolve()
    if not target_dir.exists():
        print(f"Error: Directory not found: {target_dir}")
        sys.exit(1)

    # Run analysis
    try:
        summary = run_analysis(
            target_dir=str(target_dir),
            project_name=args.name,
            db_path=args.database,
            skip_duplicates=not args.no_dedup,
            extract_archives=not args.no_archives,
            consolidate=args.consolidate,
            verbose=args.verbose,
        )

        print(f"\nResults saved to: {args.database}")

        # Watch mode
        if args.watch:
            print("\n" + "=" * 60)
            print("WATCH MODE - Monitoring for file changes...")
            print("Press Ctrl+C to stop")
            print("=" * 60 + "\n")

            from src.core.watcher import IncrementalAnalyzer, WatcherConfig

            db_manager = DBManager(args.database)
            # Get project ID (assume last created or first)
            projects = db_manager.list_projects()
            project_id = projects[-1]["id"] if projects else 1

            analyzer = IncrementalAnalyzer(db_manager, project_id, str(target_dir))

            config = WatcherConfig(
                watch_patterns=["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.json", "*.yaml", "*.yml", "*.sql"],
                poll_interval=1.0,
            )

            analyzer.start_watching(config)

            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                analyzer.stop_watching()
                print("\n\nWatch mode stopped.")

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(130)

    except Exception as e:
        print(f"\nError: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
