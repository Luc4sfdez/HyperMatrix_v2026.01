"""HyperMatrix v2026 - File Browser API"""

from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import os

router = APIRouter(prefix="/api/browse", tags=["browse"])


@router.get("")
async def browse_directory(
    path: str = Query("C:/", description="Directory path to browse")
):
    """
    Browse a directory and return its contents.
    Returns files and subdirectories with metadata.
    """
    try:
        # Normalize path
        target_path = Path(path)

        # Handle Windows drive letters
        if len(path) <= 3 and path.endswith(('/', '\\')):
            # Root of drive (e.g., "C:/")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
