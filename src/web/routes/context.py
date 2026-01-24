"""
HyperMatrix v2026 - Context Document Aggregator
Upload and link loose documents (specs, requirements, notes) to projects.
Supports: .txt, .md, .pdf, .html, .json, .yaml, .zip
"""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import hashlib

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

router = APIRouter(prefix="/api/context", tags=["context"])

# Paths
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
CONTEXT_PATH = Path(DATA_DIR) / "context"

# Supported file types
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".html", ".json", ".yaml", ".yml", ".zip"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class ContextDocument(BaseModel):
    id: int
    project_id: int
    filename: str
    original_name: str
    file_type: str
    size_bytes: int
    description: Optional[str] = None
    uploaded_at: str
    indexed: bool = False


class ContextUploadResponse(BaseModel):
    success: bool
    document_id: int
    filename: str
    message: str


def ensure_context_table():
    """Create context_documents table if not exists."""
    from ..app import db_manager
    if not db_manager:
        return

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS context_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                description TEXT,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                indexed INTEGER DEFAULT 0,
                content_hash TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


def get_file_hash(content: bytes) -> str:
    """Generate SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()[:16]


@router.on_event("startup")
async def startup():
    """Initialize context storage."""
    CONTEXT_PATH.mkdir(parents=True, exist_ok=True)
    ensure_context_table()


@router.get("/projects")
async def get_projects_for_context():
    """
    Get list of projects available for linking context documents.
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    ensure_context_table()

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.name, p.root_path,
                   COUNT(cd.id) as context_count
            FROM projects p
            LEFT JOIN context_documents cd ON cd.project_id = p.id
            GROUP BY p.id
            ORDER BY p.name
        """)

        projects = []
        for row in cursor.fetchall():
            projects.append({
                "id": row["id"],
                "name": row["name"],
                "root_path": row["root_path"],
                "context_count": row["context_count"]
            })

    return {"projects": projects}


@router.post("/upload", response_model=ContextUploadResponse)
async def upload_context_document(
    file: UploadFile = File(...),
    project_id: int = Form(...),
    description: Optional[str] = Form(None)
):
    """
    Upload a context document and link it to a project.
    Supports: .txt, .md, .pdf, .html, .json, .yaml, .zip
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    ensure_context_table()

    # Validate file extension
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {ext} not supported. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # Verify project exists
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Create project context directory
    project_context_dir = CONTEXT_PATH / str(project_id)
    project_context_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with hash
    content_hash = get_file_hash(content)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_name)
    filename = f"{timestamp}_{content_hash}_{safe_name}"

    # Handle ZIP files - extract contents
    extracted_files = []
    if ext == ".zip":
        zip_dir = project_context_dir / f"{timestamp}_{content_hash}_extracted"
        zip_dir.mkdir(parents=True, exist_ok=True)

        # Save zip temporarily
        temp_zip = project_context_dir / f"temp_{filename}"
        temp_zip.write_bytes(content)

        try:
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                for member in zf.namelist():
                    member_ext = Path(member).suffix.lower()
                    # Only extract supported file types
                    if member_ext in SUPPORTED_EXTENSIONS - {".zip"}:
                        zf.extract(member, zip_dir)
                        extracted_files.append(member)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP file")
        finally:
            temp_zip.unlink()

        # Store metadata about the zip
        file_path = zip_dir
        size_bytes = sum(
            (zip_dir / f).stat().st_size
            for f in extracted_files
            if (zip_dir / f).exists()
        )
    else:
        # Save regular file
        file_path = project_context_dir / filename
        file_path.write_bytes(content)
        size_bytes = len(content)

    # Save to database
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO context_documents
            (project_id, filename, original_name, file_type, size_bytes, description, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (project_id, filename, original_name, ext, size_bytes, description, content_hash))
        conn.commit()
        doc_id = cursor.lastrowid

    return ContextUploadResponse(
        success=True,
        document_id=doc_id,
        filename=original_name,
        message=f"Uploaded to project '{project['name']}'"
        + (f" ({len(extracted_files)} files extracted)" if extracted_files else "")
    )


@router.get("/{project_id}")
async def get_project_context(project_id: int):
    """
    Get all context documents linked to a project.
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    ensure_context_table()

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()

        # Get project info
        cursor.execute("SELECT id, name FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # Get documents
        cursor.execute("""
            SELECT id, filename, original_name, file_type, size_bytes,
                   description, uploaded_at, indexed
            FROM context_documents
            WHERE project_id = ?
            ORDER BY uploaded_at DESC
        """, (project_id,))

        documents = []
        total_size = 0
        for row in cursor.fetchall():
            doc = {
                "id": row["id"],
                "filename": row["filename"],
                "original_name": row["original_name"],
                "file_type": row["file_type"],
                "size_bytes": row["size_bytes"],
                "size_human": format_size(row["size_bytes"]),
                "description": row["description"],
                "uploaded_at": row["uploaded_at"],
                "indexed": bool(row["indexed"])
            }
            documents.append(doc)
            total_size += row["size_bytes"]

    return {
        "project_id": project_id,
        "project_name": project["name"],
        "documents": documents,
        "total_documents": len(documents),
        "total_size_bytes": total_size,
        "total_size_human": format_size(total_size)
    }


@router.get("/document/{doc_id}/content")
async def get_document_content(doc_id: int):
    """
    Get the content of a context document (for text-based files).
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    ensure_context_table()

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT project_id, filename, original_name, file_type
            FROM context_documents WHERE id = ?
        """, (doc_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    project_id = row["project_id"]
    filename = row["filename"]
    file_type = row["file_type"]

    # Only return content for text-based files
    text_types = {".txt", ".md", ".html", ".json", ".yaml", ".yml"}
    if file_type not in text_types:
        return {
            "doc_id": doc_id,
            "filename": row["original_name"],
            "content": None,
            "message": f"Content preview not available for {file_type} files"
        }

    file_path = CONTEXT_PATH / str(project_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        # Limit content size for preview
        if len(content) > 100000:
            content = content[:100000] + "\n\n... [truncated]"
    except Exception as e:
        return {
            "doc_id": doc_id,
            "filename": row["original_name"],
            "content": None,
            "message": f"Error reading file: {str(e)}"
        }

    return {
        "doc_id": doc_id,
        "filename": row["original_name"],
        "file_type": file_type,
        "content": content
    }


@router.delete("/{doc_id}")
async def delete_context_document(doc_id: int, confirm: bool = False):
    """
    Delete a context document.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Add ?confirm=true to confirm deletion"
        )

    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    ensure_context_table()

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()

        # Get document info
        cursor.execute("""
            SELECT project_id, filename, original_name
            FROM context_documents WHERE id = ?
        """, (doc_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        project_id = row["project_id"]
        filename = row["filename"]
        original_name = row["original_name"]

        # Delete file from disk
        file_path = CONTEXT_PATH / str(project_id) / filename
        if file_path.exists():
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()

        # Delete from database
        cursor.execute("DELETE FROM context_documents WHERE id = ?", (doc_id,))
        conn.commit()

    return {
        "success": True,
        "message": f"Deleted '{original_name}'",
        "doc_id": doc_id
    }


@router.post("/{doc_id}/index")
async def index_context_document(doc_id: int):
    """
    Index a context document into ChromaDB for semantic search.
    """
    from ..app import db_manager

    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    ensure_context_table()

    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT project_id, filename, original_name, file_type
            FROM context_documents WHERE id = ?
        """, (doc_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    project_id = row["project_id"]
    filename = row["filename"]
    file_type = row["file_type"]

    # Only index text-based files
    text_types = {".txt", ".md", ".html", ".json", ".yaml", ".yml"}
    if file_type not in text_types:
        return {
            "success": False,
            "message": f"Cannot index {file_type} files (not text-based)"
        }

    file_path = CONTEXT_PATH / str(project_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    # Index in ChromaDB
    try:
        from ...embeddings import get_embedding_engine
        engine = get_embedding_engine()

        if engine and engine.collection:
            # Split content into chunks
            chunks = split_text_into_chunks(content, max_chars=1000)

            for i, chunk in enumerate(chunks):
                doc_id_str = f"context_{doc_id}_{i}"
                engine.collection.add(
                    ids=[doc_id_str],
                    documents=[chunk],
                    metadatas=[{
                        "type": "context_document",
                        "project_id": project_id,
                        "doc_id": doc_id,
                        "filename": row["original_name"],
                        "chunk_index": i
                    }]
                )

            # Mark as indexed
            with db_manager._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE context_documents SET indexed = 1 WHERE id = ?",
                    (doc_id,)
                )
                conn.commit()

            return {
                "success": True,
                "message": f"Indexed {len(chunks)} chunks from '{row['original_name']}'",
                "chunks_indexed": len(chunks)
            }
        else:
            return {
                "success": False,
                "message": "ChromaDB not available"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing error: {str(e)}")


def split_text_into_chunks(text: str, max_chars: int = 1000) -> List[str]:
    """Split text into chunks at paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chars:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:max_chars]]


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / 1024 / 1024:.2f} MB"
