"""HyperMatrix v2026 - Workspace Management API"""

import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
import zipfile
import tempfile

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

WORKSPACE_PATH = Path("/workspace")
MAX_WORKSPACE_SIZE = 20 * 1024 * 1024 * 1024  # 20GB limit


def get_workspace_size() -> int:
    """Calculate total size of workspace in bytes."""
    total = 0
    if WORKSPACE_PATH.exists():
        for entry in WORKSPACE_PATH.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except:
                    pass
    return total


def get_folder_size(path: Path) -> int:
    """Calculate size of a folder in bytes."""
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except:
                pass
    return total


@router.get("")
async def workspace_status():
    """Get workspace status and contents."""
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)

    items = []
    for entry in WORKSPACE_PATH.iterdir():
        try:
            if entry.is_dir():
                size = get_folder_size(entry)
                file_count = sum(1 for _ in entry.rglob("*") if _.is_file())
            else:
                size = entry.stat().st_size
                file_count = 1

            items.append({
                "name": entry.name,
                "path": str(entry),
                "is_dir": entry.is_dir(),
                "size": size,
                "size_human": f"{size / 1024 / 1024:.1f} MB",
                "file_count": file_count
            })
        except Exception as e:
            continue

    used = get_workspace_size()

    return {
        "path": str(WORKSPACE_PATH),
        "items": items,
        "used_bytes": used,
        "used_human": f"{used / 1024 / 1024 / 1024:.2f} GB",
        "limit_bytes": MAX_WORKSPACE_SIZE,
        "limit_human": "20 GB",
        "available_bytes": MAX_WORKSPACE_SIZE - used,
        "available_human": f"{(MAX_WORKSPACE_SIZE - used) / 1024 / 1024 / 1024:.2f} GB"
    }


@router.post("/upload")
async def upload_to_workspace(
    file: UploadFile = File(...),
    extract: bool = Form(True),
    folder_name: Optional[str] = Form(None)
):
    """
    Upload a file or zip to workspace.
    If extract=True and file is a zip, it will be extracted.
    """
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)

    # Check space
    current_size = get_workspace_size()
    if current_size >= MAX_WORKSPACE_SIZE:
        raise HTTPException(status_code=507, detail="Workspace full (20GB limit)")

    filename = file.filename or "uploaded"

    # Save uploaded file
    temp_path = WORKSPACE_PATH / f".temp_{filename}"
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            # Check if this upload would exceed limit
            if current_size + len(content) > MAX_WORKSPACE_SIZE:
                raise HTTPException(status_code=507,
                    detail=f"Upload would exceed 20GB limit. Available: {(MAX_WORKSPACE_SIZE - current_size) / 1024 / 1024:.0f} MB")
            f.write(content)

        # Handle zip extraction
        if extract and filename.endswith('.zip'):
            target_name = folder_name or filename[:-4]
            target_path = WORKSPACE_PATH / target_name

            # Ensure unique name
            counter = 1
            while target_path.exists():
                target_path = WORKSPACE_PATH / f"{target_name}_{counter}"
                counter += 1

            target_path.mkdir(parents=True)

            with zipfile.ZipFile(temp_path, 'r') as zf:
                zf.extractall(target_path)

            temp_path.unlink()

            return {
                "success": True,
                "type": "extracted",
                "path": str(target_path),
                "name": target_path.name
            }
        else:
            # Just move the file
            final_path = WORKSPACE_PATH / filename
            counter = 1
            while final_path.exists():
                name, ext = os.path.splitext(filename)
                final_path = WORKSPACE_PATH / f"{name}_{counter}{ext}"
                counter += 1

            temp_path.rename(final_path)

            return {
                "success": True,
                "type": "file",
                "path": str(final_path),
                "name": final_path.name
            }

    except HTTPException:
        raise
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/copy-from-projects")
async def copy_from_projects(
    source: str = Form(..., description="Path relative to /projects"),
    name: Optional[str] = Form(None, description="Name in workspace")
):
    """Copy a folder from /projects to workspace for editing."""
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)

    source_path = Path("/projects") / source.lstrip("/")

    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Source not found: {source}")

    # Check source size
    if source_path.is_dir():
        source_size = get_folder_size(source_path)
    else:
        source_size = source_path.stat().st_size

    current_size = get_workspace_size()
    if current_size + source_size > MAX_WORKSPACE_SIZE:
        raise HTTPException(status_code=507,
            detail=f"Would exceed 20GB limit. Need {source_size / 1024 / 1024:.0f} MB, available: {(MAX_WORKSPACE_SIZE - current_size) / 1024 / 1024:.0f} MB")

    # Determine target name
    target_name = name or source_path.name
    target_path = WORKSPACE_PATH / target_name

    # Ensure unique name
    counter = 1
    while target_path.exists():
        target_path = WORKSPACE_PATH / f"{target_name}_{counter}"
        counter += 1

    try:
        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            shutil.copy2(source_path, target_path)

        return {
            "success": True,
            "source": str(source_path),
            "target": str(target_path),
            "name": target_path.name,
            "size": source_size,
            "size_human": f"{source_size / 1024 / 1024:.1f} MB"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{item_name}")
async def delete_from_workspace(item_name: str):
    """Delete an item from workspace."""
    target = WORKSPACE_PATH / item_name

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {item_name}")

    # Safety check - must be inside workspace
    try:
        target.resolve().relative_to(WORKSPACE_PATH.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid path")

    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

        return {"success": True, "deleted": item_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def clear_workspace():
    """Clear entire workspace."""
    try:
        if WORKSPACE_PATH.exists():
            for item in WORKSPACE_PATH.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        return {"success": True, "message": "Workspace cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-folder")
async def create_folder(name: str = Form(...)):
    """Create a folder in workspace for uploading files."""
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)

    # Sanitize folder name
    safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")
    if not safe_name:
        safe_name = "uploaded"

    target_path = WORKSPACE_PATH / safe_name

    # Ensure unique name
    counter = 1
    while target_path.exists():
        target_path = WORKSPACE_PATH / f"{safe_name}_{counter}"
        counter += 1

    target_path.mkdir(parents=True)

    return {
        "success": True,
        "name": target_path.name,
        "path": str(target_path)
    }


@router.post("/upload-file")
async def upload_single_file(
    file: UploadFile = File(...),
    path: str = Form(..., description="Relative path including folder name")
):
    """Upload a single file to workspace, preserving directory structure."""
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)

    # Check space
    current_size = get_workspace_size()
    if current_size >= MAX_WORKSPACE_SIZE:
        raise HTTPException(status_code=507, detail="Workspace full (20GB limit)")

    # Build target path - path includes folder name like "myproject/src/file.py"
    safe_path = path.replace("\\", "/").lstrip("/")
    target_path = WORKSPACE_PATH / safe_path

    # Ensure parent directories exist
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()

        # Check if this upload would exceed limit
        if current_size + len(content) > MAX_WORKSPACE_SIZE:
            raise HTTPException(status_code=507,
                detail=f"Upload would exceed 20GB limit")

        with open(target_path, "wb") as f:
            f.write(content)

        return {
            "success": True,
            "path": str(target_path),
            "size": len(content)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
