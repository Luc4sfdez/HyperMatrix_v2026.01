"""
HyperMatrix v2026 - API Dependencies
Shared dependencies for API routes.
"""

import os
from pathlib import Path
from ..core.db_manager import DBManager


def _get_data_dir() -> str:
    """
    Get data directory path, with fallback for local development.

    Priority:
    1. DATA_DIR environment variable
    2. /app/data if it exists (Docker)
    3. ./data in current directory (local development)
    """
    # Check environment variable first
    env_data_dir = os.getenv("DATA_DIR")
    if env_data_dir:
        Path(env_data_dir).mkdir(parents=True, exist_ok=True)
        return env_data_dir

    # Check if Docker path exists
    docker_path = Path("/app/data")
    if docker_path.exists():
        return str(docker_path)

    # Fallback to local ./data directory
    local_path = Path("./data")
    local_path.mkdir(parents=True, exist_ok=True)
    return str(local_path)


# Database path - works in both Docker and local environments
DATA_DIR = _get_data_dir()
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "hypermatrix.db")

# Global database manager
_db_manager: DBManager = None


def get_db() -> DBManager:
    """Get database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DBManager(DEFAULT_DB_PATH)
    return _db_manager


def set_db(db_manager: DBManager):
    """Set database manager instance."""
    global _db_manager
    _db_manager = db_manager
