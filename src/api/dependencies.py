"""
HyperMatrix v2026 - API Dependencies
Shared dependencies for API routes.
"""

from ..core.db_manager import DBManager


# Global database manager
_db_manager: DBManager = None


def get_db() -> DBManager:
    """Get database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DBManager("hypermatrix.db")
    return _db_manager


def set_db(db_manager: DBManager):
    """Set database manager instance."""
    global _db_manager
    _db_manager = db_manager
