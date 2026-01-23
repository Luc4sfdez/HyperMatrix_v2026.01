"""HyperMatrix v2026 - File Browser API"""

import os
import platform
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/browse", tags=["browse"])

# Maximum path length to prevent DoS
MAX_PATH_LENGTH = 400

# Allowed base paths (security whitelist)
# In Docker: /projects and /app/data
# In Windows: allow drive letters
ALLOWED_PATHS_DOCKER = ["/projects", "/app/data", "/app", "/"]
FORBIDDEN_PATHS = [
    "/etc", "/root", "/var", "/usr", "/bin", "/sbin",
    "/proc", "/sys", "/dev", "/boot", "/lib", "/lib64",
    "/home", "/tmp", "/run", "/srv", "/opt", "/mnt",
]


def _is_path_allowed(path_str: str) -> bool:
    """Check if path is allowed based on security rules."""
    # Normalize path
    normalized = path_str.replace('\\', '/').lower()

    # Block path traversal attempts
    if '..' in normalized:
        return False

    # Check for forbidden paths
    for forbidden in FORBIDDEN_PATHS:
        if normalized.startswith(forbidden.lower()):
            return False

    return True


def _validate_path(path: str) -> Path:
    """
    Validate and sanitize path input.
    Raises HTTPException on invalid/forbidden paths.
    """
    # Check path length
    if len(path) > MAX_PATH_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Path too long (max {MAX_PATH_LENGTH} characters)"
        )

    # Check for empty path
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Path cannot be empty")

    # Normalize path and check for traversal
    normalized = path.replace('\\', '/')

    # Block obvious traversal attempts
    if '..' in normalized:
        raise HTTPException(status_code=403, detail="Path traversal not allowed")

    # Check against forbidden paths
    if not _is_path_allowed(normalized):
        raise HTTPException(status_code=403, detail="Access to this path is forbidden")

    return Path(path)


@router.get("")
async def browse_directory(
    path: str = Query("C:/", description="Directory path to browse")
):
    """
    Browse a directory and return its contents.
    Returns files and subdirectories with metadata.

    Security:
    - Path traversal (..) is blocked
    - Sensitive system directories are forbidden
    - Maximum path length enforced
    """
    try:
        # Validate and sanitize path
        target_path = _validate_path(path)

        # Handle Windows drive letters
        if len(path) <= 3 and path.endswith(('/', '\\')):
            target_path = Path(path.rstrip('/\\') + '/')

        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")

        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")

        items = []

        try:
            for entry in os.scandir(target_path):
                try:
                    item = {
                        "name": entry.name,
                        "path": str(entry.path).replace('\\', '/'),
                        "is_dir": entry.is_dir()
                    }

                    # Get file size for files
                    if not entry.is_dir():
                        try:
                            item["size"] = entry.stat().st_size
                        except (OSError, PermissionError):
                            item["size"] = 0

                    items.append(item)
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue

        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

        return {
            "path": str(target_path).replace('\\', '/'),
            "items": items
        }

    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    except OSError as e:
        # Handle OS-level errors gracefully
        raise HTTPException(status_code=400, detail=f"Cannot access path: {str(e)}")
    except Exception as e:
        # Log unexpected errors but don't expose internals
        import logging
        logging.getLogger(__name__).error(f"Browse error for {path}: {e}")
        raise HTTPException(status_code=500, detail="Internal error browsing path")


@router.get("/drives")
async def list_drives():
    """
    List available drives (Windows only).
    """
    import platform

    if platform.system() != "Windows":
        return {"drives": ["/"]}

    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:/"
        if Path(drive).exists():
            drives.append(drive)

    return {"drives": drives}
