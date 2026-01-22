"""
HyperMatrix v2026 - Global Configuration
Centralized configuration and global variables.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GlobalConfig:
    """Global configuration for HyperMatrix."""

    # Application info
    APP_NAME: str = "HyperMatrix"
    VERSION: str = "2026.1.0"
    DEBUG: bool = False

    # Paths
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    DATA_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data")
    CACHE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / ".cache")
    DB_PATH: str = "hypermatrix.db"

    # Parser settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    SUPPORTED_EXTENSIONS: tuple = (".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json")

    # Analysis settings
    MAX_DEPTH: int = 10
    IGNORE_PATTERNS: tuple = (
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "dist",
        "build",
    )

    # Database settings
    DB_TIMEOUT: int = 30
    DB_ISOLATION_LEVEL: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __post_init__(self):
        """Initialize paths after dataclass creation."""
        self.BASE_DIR = Path(self.BASE_DIR)
        self.DATA_DIR = Path(self.DATA_DIR)
        self.CACHE_DIR = Path(self.CACHE_DIR)

    def ensure_dirs(self):
        """Ensure required directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return getattr(self, key, default)

    def set(self, key: str, value: Any):
        """Set configuration value."""
        if hasattr(self, key):
            setattr(self, key, value)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "APP_NAME": self.APP_NAME,
            "VERSION": self.VERSION,
            "DEBUG": self.DEBUG,
            "BASE_DIR": str(self.BASE_DIR),
            "DATA_DIR": str(self.DATA_DIR),
            "CACHE_DIR": str(self.CACHE_DIR),
            "DB_PATH": self.DB_PATH,
            "MAX_FILE_SIZE": self.MAX_FILE_SIZE,
            "SUPPORTED_EXTENSIONS": self.SUPPORTED_EXTENSIONS,
            "MAX_DEPTH": self.MAX_DEPTH,
            "IGNORE_PATTERNS": self.IGNORE_PATTERNS,
            "LOG_LEVEL": self.LOG_LEVEL,
        }

    @classmethod
    def from_env(cls) -> "GlobalConfig":
        """Create configuration from environment variables."""
        return cls(
            DEBUG=os.getenv("HYPERMATRIX_DEBUG", "false").lower() == "true",
            DB_PATH=os.getenv("HYPERMATRIX_DB_PATH", "hypermatrix.db"),
            LOG_LEVEL=os.getenv("HYPERMATRIX_LOG_LEVEL", "INFO"),
            MAX_DEPTH=int(os.getenv("HYPERMATRIX_MAX_DEPTH", "10")),
        )


# Global instance
config = GlobalConfig()


# Convenience functions
def get_config() -> GlobalConfig:
    """Get the global configuration instance."""
    return config


def init_config(**kwargs) -> GlobalConfig:
    """Initialize configuration with custom values."""
    global config
    config = GlobalConfig(**kwargs)
    config.ensure_dirs()
    return config


def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return config.DEBUG


def get_version() -> str:
    """Get application version."""
    return config.VERSION


def get_db_path() -> str:
    """Get database path."""
    return config.DB_PATH


def should_ignore(path: str) -> bool:
    """Check if a path should be ignored."""
    path_obj = Path(path)
    for pattern in config.IGNORE_PATTERNS:
        if pattern in path_obj.parts:
            return True
    return False


def is_supported_file(filepath: str) -> bool:
    """Check if a file type is supported."""
    return Path(filepath).suffix.lower() in config.SUPPORTED_EXTENSIONS
