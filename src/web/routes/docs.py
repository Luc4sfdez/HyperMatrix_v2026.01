"""
HyperMatrix v2026 - Documentation API
Endpoints for documentation detection and management.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..app import scan_results
from ...core.docs_detector import (
    detect_documentation,
    get_docs_summary,
    DocumentInfo,
    DocsDetectionResult,
)

router = APIRouter(prefix="/api/docs", tags=["documentation"])
logger = logging.getLogger(__name__)

# Store linked documents per scan
linked_docs: dict[str, List[dict]] = {}

# Store pasted text content
pasted_content: dict[str, List[dict]] = {}


class DocumentResponse(BaseModel):
    """Response model for a document."""
    filepath: str
    filename: str
    doc_type: str
    size_bytes: int
    modified_at: str
    title: Optional[str] = None
    preview: Optional[str] = None
    linked: bool = False


class DocsDetectionResponse(BaseModel):
    """Response for docs detection."""
    project_path: str
    total_count: int
    documents: List[DocumentResponse]
    by_type: dict[str, int]
    detected_at: str


class LinkDocRequest(BaseModel):
    """Request to link a document."""
    filepath: str
    doc_type: Optional[str] = None
    custom_title: Optional[str] = None


class PasteTextRequest(BaseModel):
    """Request to paste text content."""
    content: str
    title: str
    doc_type: str = "notes"
    source: Optional[str] = None  # e.g., "email", "chat", "notes"


class PastedContentResponse(BaseModel):
    """Response for pasted content."""
    id: str
    title: str
    content: str
    doc_type: str
    source: Optional[str]
    created_at: str


@router.get("/{scan_id}/detect")
async def detect_project_docs(scan_id: str, max_files: int = 500):
    """
    Detect documentation files in a project.

    Scans the project directory for README, CHANGELOG, docs folders,
    markdown files, PDFs, and other documentation.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan = scan_results[scan_id]

    # Get project path from scan result
    project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="Project path not found in scan")

    try:
        result = detect_documentation(project_path, max_files=max_files)

        # Mark already linked documents
        scan_linked = linked_docs.get(scan_id, [])
        linked_paths = {d["filepath"] for d in scan_linked}

        for doc in result.documents:
            if doc.filepath in linked_paths:
                doc.linked = True

        return {
            "scan_id": scan_id,
            "project_path": result.project_path,
            "total_count": result.total_count,
            "documents": [
                {
                    "filepath": d.filepath,
                    "filename": d.filename,
                    "doc_type": d.doc_type,
                    "size_bytes": d.size_bytes,
                    "modified_at": d.modified_at,
                    "title": d.title,
                    "preview": d.preview,
                    "linked": d.linked,
                }
                for d in result.documents
            ],
            "by_type": {
                doc_type: len(docs)
                for doc_type, docs in result.by_type.items()
            },
            "detected_at": result.detected_at,
        }

    except Exception as e:
        logger.error(f"Error detecting docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scan_id}/summary")
async def get_docs_summary_endpoint(scan_id: str):
    """
    Get a summary of documentation for a project.

    Returns counts by type and flags for common docs (README, LICENSE, etc).
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan = scan_results[scan_id]
    project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")

    if not project_path:
        raise HTTPException(status_code=400, detail="Project path not found")

    result = detect_documentation(project_path, max_files=100)  # Quick scan
    summary = get_docs_summary(result)

    # Add linked and pasted counts
    summary["linked_count"] = len(linked_docs.get(scan_id, []))
    summary["pasted_count"] = len(pasted_content.get(scan_id, []))

    return summary


@router.get("/{scan_id}/linked")
async def get_linked_docs(scan_id: str):
    """Get all manually linked documents for a scan."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "scan_id": scan_id,
        "documents": linked_docs.get(scan_id, []),
        "total": len(linked_docs.get(scan_id, [])),
    }


@router.post("/{scan_id}/link")
async def link_document(scan_id: str, request: LinkDocRequest):
    """
    Link a document to a scan/project.

    This creates a manual association between a documentation file
    and the analyzed project.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan_id not in linked_docs:
        linked_docs[scan_id] = []

    # Check if already linked
    existing = [d for d in linked_docs[scan_id] if d["filepath"] == request.filepath]
    if existing:
        return {
            "status": "exists",
            "message": "Document already linked",
            "document": existing[0],
        }

    from datetime import datetime

    doc_entry = {
        "filepath": request.filepath,
        "doc_type": request.doc_type or "documentation",
        "custom_title": request.custom_title,
        "linked_at": datetime.now().isoformat(),
    }

    linked_docs[scan_id].append(doc_entry)

    return {
        "status": "linked",
        "document": doc_entry,
        "total_linked": len(linked_docs[scan_id]),
    }


@router.delete("/{scan_id}/link")
async def unlink_document(scan_id: str, filepath: str):
    """Unlink a document from a scan."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan_id not in linked_docs:
        return {"status": "not_found", "message": "No linked documents"}

    initial_count = len(linked_docs[scan_id])
    linked_docs[scan_id] = [d for d in linked_docs[scan_id] if d["filepath"] != filepath]

    if len(linked_docs[scan_id]) < initial_count:
        return {"status": "unlinked", "filepath": filepath}

    return {"status": "not_found", "filepath": filepath}


@router.get("/{scan_id}/pasted")
async def get_pasted_content(scan_id: str):
    """Get all pasted text content for a scan."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "scan_id": scan_id,
        "content": pasted_content.get(scan_id, []),
        "total": len(pasted_content.get(scan_id, [])),
    }


@router.post("/{scan_id}/paste")
async def paste_text_content(scan_id: str, request: PasteTextRequest):
    """
    Paste text content (email, notes, chat) and link to project.

    This allows users to add context that isn't in the codebase,
    like emails, chat conversations, or meeting notes.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan_id not in pasted_content:
        pasted_content[scan_id] = []

    import uuid
    from datetime import datetime

    content_id = str(uuid.uuid4())[:8]

    entry = {
        "id": content_id,
        "title": request.title,
        "content": request.content,
        "doc_type": request.doc_type,
        "source": request.source,
        "created_at": datetime.now().isoformat(),
        "char_count": len(request.content),
        "word_count": len(request.content.split()),
    }

    pasted_content[scan_id].append(entry)

    return {
        "status": "created",
        "entry": entry,
        "total_pasted": len(pasted_content[scan_id]),
    }


@router.delete("/{scan_id}/paste/{content_id}")
async def delete_pasted_content(scan_id: str, content_id: str):
    """Delete pasted content by ID."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan_id not in pasted_content:
        return {"status": "not_found"}

    initial_count = len(pasted_content[scan_id])
    pasted_content[scan_id] = [c for c in pasted_content[scan_id] if c["id"] != content_id]

    if len(pasted_content[scan_id]) < initial_count:
        return {"status": "deleted", "content_id": content_id}

    return {"status": "not_found", "content_id": content_id}


@router.get("/{scan_id}/all")
async def get_all_documentation(scan_id: str):
    """
    Get all documentation for a project: detected, linked, and pasted.

    This provides a complete view of all documentation context.
    """
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan = scan_results[scan_id]
    project_path = scan.get("root_path") or scan.get("discovery", {}).get("root_path")

    detected = []
    if project_path:
        try:
            result = detect_documentation(project_path, max_files=200)
            detected = [
                {
                    "filepath": d.filepath,
                    "filename": d.filename,
                    "doc_type": d.doc_type,
                    "title": d.title,
                    "preview": d.preview,
                    "source": "detected",
                }
                for d in result.documents
            ]
        except Exception as e:
            logger.warning(f"Could not detect docs: {e}")

    return {
        "scan_id": scan_id,
        "detected": detected,
        "linked": linked_docs.get(scan_id, []),
        "pasted": pasted_content.get(scan_id, []),
        "totals": {
            "detected": len(detected),
            "linked": len(linked_docs.get(scan_id, [])),
            "pasted": len(pasted_content.get(scan_id, [])),
        },
    }
