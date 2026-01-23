"""
HyperMatrix v2026 - API Dependencies
Shared dependencies for API routes.
"""

import os
from ..core.db_manager import DBManager

# Database path - use DATA_DIR env var for persistence in Docker volume
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
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
