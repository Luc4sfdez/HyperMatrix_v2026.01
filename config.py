"""
HyperMatrix v2026 - Configuration Module
"""


class Config:
    """Application configuration."""

    APP_NAME = "HyperMatrix"
    VERSION = "2026"
    DEBUG = False

    def __init__(self):
        self.settings = {}

    def get(self, key, default=None):
        """Get a configuration value."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a configuration value."""
        self.settings[key] = value
