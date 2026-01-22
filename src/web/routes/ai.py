"""
HyperMatrix v2026.01 - AI Routes (Ollama Integration)
Endpoints for AI-powered code analysis using local LLMs.
With full database and file access for intelligent assistance.
"""

import os
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from glob import glob

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
import httpx

# Import app module to access scan data and database
from .. import app as web_app
from ..app import active_scans, scan_results

router = APIRouter()

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}"


async def check_ollama_available() -> bool:
    """Check if Ollama server is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def get_available_models() -> List[str]:
    """Get list of available models from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
    except Exception:
        pass
    return []


async def generate_completion(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Generate a completion using Ollama."""
    model = model or OLLAMA_MODEL

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }

    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Ollama error: {response.text}"
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama request timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama")


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@router.get("/status")
async def ai_status():
    """Check AI service status and available models."""
    available = await check_ollama_available()
    models = await get_available_models() if available else []

    return {
        "available": available,
        "ollama_host": OLLAMA_HOST,
        "default_model": OLLAMA_MODEL,
        "models": models,
        "model_loaded": OLLAMA_MODEL in models,
    }


@router.get("/models")
async def list_models():
    """List all available Ollama models."""
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    models = await get_available_models()
    return {"models": models, "default": OLLAMA_MODEL}


# =============================================================================
# Code Analysis Endpoints
# =============================================================================

@router.post("/analyze-diff")
async def analyze_diff(
    file1_content: str = Body(..., description="Content of first file"),
    file2_content: str = Body(..., description="Content of second file"),
    file1_name: str = Body("file1.py", description="Name of first file"),
    file2_name: str = Body("file2.py", description="Name of second file"),
    model: Optional[str] = Body(None, description="Model to use"),
):
    """
    Analyze differences between two files and suggest how to merge them.
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    system_prompt = """Eres un experto en análisis de código Python. Tu tarea es:
1. Analizar las diferencias entre dos versiones de un archivo
2. Identificar qué cambios son importantes
3. Sugerir cómo hacer el merge de forma inteligente
4. Detectar posibles conflictos

Responde en español de forma concisa y estructurada."""

    prompt = f"""Analiza estas dos versiones de código y sugiere cómo hacer el merge:

=== {file1_name} ===
```python
{file1_content[:3000]}
```

=== {file2_name} ===
```python
{file2_content[:3000]}
```

Por favor proporciona:
1. Resumen de las diferencias principales
2. Qué versión parece más completa o actualizada
3. Sugerencia de merge (qué conservar de cada versión)
4. Posibles conflictos a revisar manualmente"""

    response = await generate_completion(prompt, model, system_prompt)

    return {
        "analysis": response,
        "file1": file1_name,
        "file2": file2_name,
        "model_used": model or OLLAMA_MODEL,
    }


@router.post("/explain-code")
async def explain_code(
    code: str = Body(..., description="Code to explain"),
    language: str = Body("python", description="Programming language"),
    detail_level: str = Body("medium", description="Detail level: brief, medium, detailed"),
    model: Optional[str] = Body(None, description="Model to use"),
):
    """
    Explain what a piece of code does in natural language.
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    detail_instructions = {
        "brief": "Explica brevemente en 2-3 oraciones.",
        "medium": "Explica con detalle moderado, incluyendo las funciones principales.",
        "detailed": "Explica en detalle cada parte del código, incluyendo patrones y posibles mejoras.",
    }

    system_prompt = f"""Eres un experto programador que explica código de forma clara.
{detail_instructions.get(detail_level, detail_instructions['medium'])}
Responde en español."""

    prompt = f"""Explica qué hace este código {language}:

```{language}
{code[:4000]}
```"""

    response = await generate_completion(prompt, model, system_prompt)

    return {
        "explanation": response,
        "language": language,
        "detail_level": detail_level,
        "model_used": model or OLLAMA_MODEL,
    }


@router.post("/find-issues")
async def find_issues(
    code: str = Body(..., description="Code to analyze"),
    language: str = Body("python", description="Programming language"),
    model: Optional[str] = Body(None, description="Model to use"),
):
    """
    Find potential issues, bugs, and improvements in code.
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    system_prompt = """Eres un revisor de código experto. Analiza el código buscando:
1. Bugs potenciales
2. Problemas de seguridad
3. Código muerto o no utilizado
4. Oportunidades de mejora
5. Violaciones de buenas prácticas

Sé específico y menciona las líneas donde encuentres problemas.
Responde en español."""

    prompt = f"""Revisa este código {language} y encuentra problemas:

```{language}
{code[:4000]}
```

Lista los problemas encontrados con su severidad (alta/media/baja) y sugerencia de corrección."""

    response = await generate_completion(prompt, model, system_prompt, temperature=0.3)

    return {
        "issues": response,
        "language": language,
        "model_used": model or OLLAMA_MODEL,
    }


@router.post("/generate-report")
async def generate_report(
    project_name: str = Body(..., description="Project name"),
    stats: Dict[str, Any] = Body(..., description="Project statistics"),
    findings: List[str] = Body(default=[], description="Key findings"),
    model: Optional[str] = Body(None, description="Model to use"),
):
    """
    Generate a consolidation report in natural language.
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    system_prompt = """Eres un analista técnico que genera informes ejecutivos.
Genera un informe claro y profesional basado en los datos proporcionados.
Incluye recomendaciones accionables.
Responde en español."""

    stats_text = json.dumps(stats, indent=2, ensure_ascii=False)
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No hay hallazgos específicos."

    prompt = f"""Genera un informe de consolidación para el proyecto "{project_name}":

ESTADÍSTICAS:
{stats_text}

HALLAZGOS:
{findings_text}

El informe debe incluir:
1. Resumen ejecutivo
2. Estado actual del proyecto
3. Principales hallazgos
4. Recomendaciones
5. Próximos pasos sugeridos"""

    response = await generate_completion(prompt, model, system_prompt, temperature=0.5)

    return {
        "report": response,
        "project": project_name,
        "model_used": model or OLLAMA_MODEL,
    }


@router.post("/chat")
async def chat_about_code(
    message: str = Body(..., description="User message"),
    context: Optional[str] = Body(None, description="Code context"),
    history: List[Dict[str, str]] = Body(default=[], description="Chat history"),
    model: Optional[str] = Body(None, description="Model to use"),
    system_prompt: Optional[str] = Body(None, description="Custom system prompt for personality"),
    scan_id: Optional[str] = Body(None, description="Current scan ID for context"),
):
    """
    Chat about code with AI assistant.
    Supports custom personality via system_prompt parameter.
    Supports special commands starting with / for database and file access.

    Special commands:
    - /proyecto - Get project summary
    - /archivos <pattern> - Search files
    - /hermanos [filename] - Get sibling files
    - /duplicados - Get duplicate groups
    - /leer <path> - Read file content
    - /comparar <path1> <path2> - Compare two files
    - /ayuda - Show help
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    # Process special commands
    command_result = await process_special_command(message)

    # Use custom system prompt if provided, otherwise use enhanced default
    if not system_prompt:
        system_prompt = """Eres un asistente experto en programación y análisis de código para HyperMatrix.
Tienes acceso a la base de datos del proyecto y puedes ver archivos, duplicados y estructura.
Ayudas a los desarrolladores a entender, mejorar, consolidar y depurar su código.
Responde de forma clara y concisa en español.
Si el usuario usa comandos especiales (/proyecto, /archivos, etc.), analiza la información proporcionada.
Si el usuario proporciona código, analízalo cuidadosamente antes de responder."""

    # Build conversation context
    conversation = ""
    for msg in history[-5:]:  # Last 5 messages for context
        role = "Usuario" if msg.get("role") == "user" else "Asistente"
        conversation += f"{role}: {msg.get('content', '')}\n\n"

    # Build prompt with command context if available
    if command_result:
        prompt_addition = command_result.get("prompt_addition", "")
        prompt = f"""{prompt_addition}

{conversation}Usuario: {message}

Basándote en la información anterior, responde al usuario."""
    else:
        prompt = f"{conversation}Usuario: {message}"

    # Add code context if provided
    if context:
        prompt = f"""Código de contexto:
```
{context[:2000]}
```

{prompt}"""

    # Auto-add project context for better awareness
    if not command_result and scan_id:
        try:
            project_ctx = await get_project_context(scan_id=scan_id)
            if project_ctx.get("has_project"):
                project_info = f"""
[Proyecto actual: {project_ctx.get('project_name')} - {project_ctx.get('total_files')} archivos, {project_ctx.get('sibling_groups')} grupos de hermanos]
"""
                prompt = project_info + prompt
        except:
            pass

    response = await generate_completion(prompt, model, system_prompt)

    result = {
        "response": response,
        "model_used": model or OLLAMA_MODEL,
    }

    # Include command data if a special command was processed
    if command_result:
        result["command"] = command_result.get("command")
        result["command_data"] = command_result.get("data")

    return result


@router.post("/suggest-refactor")
async def suggest_refactor(
    code: str = Body(..., description="Code to refactor"),
    goal: str = Body("improve readability", description="Refactoring goal"),
    language: str = Body("python", description="Programming language"),
    model: Optional[str] = Body(None, description="Model to use"),
):
    """
    Suggest refactoring improvements for code.
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    system_prompt = f"""Eres un experto en refactorización de código {language}.
Tu objetivo es: {goal}
Proporciona el código refactorizado con explicaciones de los cambios.
Responde en español."""

    prompt = f"""Refactoriza este código {language}:

```{language}
{code[:4000]}
```

Objetivo: {goal}

Proporciona:
1. Código refactorizado
2. Explicación de cada cambio
3. Beneficios de la refactorización"""

    response = await generate_completion(prompt, model, system_prompt, temperature=0.4)

    return {
        "suggestions": response,
        "goal": goal,
        "language": language,
        "model_used": model or OLLAMA_MODEL,
    }


# =============================================================================
# Context Access Endpoints - Database & File Access for AI
# =============================================================================

@router.get("/context/project")
async def get_project_context(scan_id: Optional[str] = Query(None, description="Scan ID")):
    """
    Get current project context including stats and summary.
    This gives the AI awareness of what project is being analyzed.
    """
    # If no scan_id provided, get the most recent scan
    if not scan_id and active_scans:
        scan_id = list(active_scans.keys())[-1]

    if not scan_id:
        return {
            "has_project": False,
            "message": "No hay proyecto cargado. Escanea un proyecto primero."
        }

    if scan_id not in active_scans:
        return {"has_project": False, "message": f"Scan {scan_id} no encontrado"}

    progress = active_scans[scan_id]
    result = scan_results.get(scan_id, {})

    # Build context summary
    context = {
        "has_project": True,
        "scan_id": scan_id,
        "project_name": result.get("project_name", "Unknown"),
        "status": str(progress.status),
        "total_files": progress.total_files,
        "analyzed_files": result.get("analyzed_files", 0),
        "duplicate_groups": result.get("duplicate_groups", 0),
        "sibling_groups": result.get("sibling_groups", 0),
    }

    # Add consolidation info if available
    consolidation = result.get("consolidation")
    if consolidation and hasattr(consolidation, 'groups'):
        context["sibling_filenames"] = list(consolidation.groups.keys())[:50]

    # Add analysis summary if available
    analysis = result.get("analysis")
    if analysis:
        context["total_functions"] = getattr(analysis, "total_functions", 0)
        context["total_classes"] = getattr(analysis, "total_classes", 0)
        context["errors"] = getattr(analysis, "errors", [])[:10]

    return context


@router.get("/context/files")
async def get_files_context(
    pattern: str = Query("*", description="File name pattern (e.g., 'config.py', '*.js')"),
    scan_id: Optional[str] = Query(None, description="Scan ID"),
    limit: int = Query(50, description="Max files to return"),
):
    """
    Get list of files matching a pattern in the scanned project.
    Allows the AI to see what files exist.
    """
    if not scan_id and active_scans:
        scan_id = list(active_scans.keys())[-1]

    if not scan_id or scan_id not in scan_results:
        return {"files": [], "message": "No hay proyecto cargado"}

    result = scan_results.get(scan_id, {})
    consolidation = result.get("consolidation")

    matching_files = []

    if consolidation and hasattr(consolidation, 'groups'):
        # Search in sibling groups
        for filename, group in consolidation.groups.items():
            if pattern == "*" or pattern in filename or filename.endswith(pattern.replace("*", "")):
                if hasattr(group, 'files'):
                    for file_info in group.files[:limit]:
                        matching_files.append({
                            "filename": filename,
                            "path": getattr(file_info, 'path', str(file_info)),
                            "group_size": len(group.files)
                        })

    return {
        "pattern": pattern,
        "files": matching_files[:limit],
        "total_matches": len(matching_files),
    }


@router.get("/context/duplicates")
async def get_duplicates_context(
    scan_id: Optional[str] = Query(None, description="Scan ID"),
    limit: int = Query(20, description="Max duplicate groups to return"),
):
    """
    Get duplicate file groups from the scan.
    Allows the AI to understand what files are duplicated.
    """
    if not scan_id and active_scans:
        scan_id = list(active_scans.keys())[-1]

    if not scan_id or scan_id not in scan_results:
        return {"duplicates": [], "message": "No hay proyecto cargado"}

    result = scan_results.get(scan_id, {})

    return {
        "scan_id": scan_id,
        "total_duplicate_groups": result.get("duplicate_groups", 0),
        "message": "Usa /context/siblings para ver grupos de archivos hermanos (mismo nombre, diferentes ubicaciones)"
    }


@router.get("/context/siblings")
async def get_siblings_context(
    filename: Optional[str] = Query(None, description="Specific filename to get siblings for"),
    scan_id: Optional[str] = Query(None, description="Scan ID"),
    limit: int = Query(20, description="Max sibling groups to return"),
):
    """
    Get sibling file groups (same filename, different locations).
    This is key for consolidation analysis.
    """
    if not scan_id and active_scans:
        scan_id = list(active_scans.keys())[-1]

    if not scan_id or scan_id not in scan_results:
        return {"siblings": [], "message": "No hay proyecto cargado"}

    result = scan_results.get(scan_id, {})
    consolidation = result.get("consolidation")

    siblings = []

    if consolidation and hasattr(consolidation, 'groups'):
        for fname, group in consolidation.groups.items():
            if filename and filename != fname:
                continue

            if hasattr(group, 'files'):
                file_paths = [getattr(f, 'path', str(f)) for f in group.files]
                siblings.append({
                    "filename": fname,
                    "count": len(group.files),
                    "paths": file_paths[:10],  # Limit paths shown
                })

        # Sort by count descending
        siblings.sort(key=lambda x: x["count"], reverse=True)

    return {
        "scan_id": scan_id,
        "siblings": siblings[:limit] if not filename else siblings,
        "total_groups": len(siblings),
    }


@router.get("/context/file-content")
async def get_file_content_context(
    path: str = Query(..., description="File path to read"),
    max_lines: int = Query(200, description="Max lines to return"),
):
    """
    Read content of a specific file.
    Allows the AI to see actual file contents for analysis.
    """
    try:
        file_path = Path(path)

        # Security: Only allow reading from known project directories
        # Check if path is within allowed directories
        allowed_prefixes = ["/projects", "/app", "E:", "C:"]
        path_str = str(file_path)
        if not any(path_str.startswith(prefix) for prefix in allowed_prefixes):
            raise HTTPException(status_code=403, detail="Acceso denegado a esta ruta")

        if not file_path.exists():
            return {"error": f"Archivo no encontrado: {path}"}

        if file_path.stat().st_size > 1_000_000:  # 1MB limit
            return {"error": "Archivo demasiado grande (máx 1MB)"}

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()[:max_lines]
                content = ''.join(lines)
        except Exception as e:
            return {"error": f"Error leyendo archivo: {str(e)}"}

        return {
            "path": path,
            "filename": file_path.name,
            "content": content,
            "lines": len(lines),
            "truncated": len(lines) >= max_lines,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/context/compare-files")
async def compare_files_context(
    path1: str = Body(..., description="First file path"),
    path2: str = Body(..., description="Second file path"),
):
    """
    Get content of two files for comparison.
    """
    file1 = await get_file_content_context(path1)
    file2 = await get_file_content_context(path2)

    return {
        "file1": file1,
        "file2": file2,
    }


# =============================================================================
# Enhanced Chat with Special Commands
# =============================================================================

async def process_special_command(message: str) -> Optional[Dict[str, Any]]:
    """
    Process special commands starting with /
    Returns context data or None if not a command.
    """
    message = message.strip()

    if not message.startswith('/'):
        return None

    parts = message.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == '/proyecto' or command == '/project':
        # Get project summary
        context = await get_project_context()
        return {
            "command": "proyecto",
            "data": context,
            "prompt_addition": f"""
CONTEXTO DEL PROYECTO:
- Nombre: {context.get('project_name', 'N/A')}
- Archivos totales: {context.get('total_files', 0)}
- Archivos analizados: {context.get('analyzed_files', 0)}
- Grupos de duplicados: {context.get('duplicate_groups', 0)}
- Grupos de hermanos: {context.get('sibling_groups', 0)}
- Funciones: {context.get('total_functions', 0)}
- Clases: {context.get('total_classes', 0)}
"""
        }

    elif command == '/archivos' or command == '/files':
        # Search files by pattern
        pattern = args or "*"
        files = await get_files_context(pattern=pattern, limit=30)
        file_list = "\n".join([f"- {f['filename']} ({f['group_size']} copias): {f['path']}"
                               for f in files.get('files', [])])
        return {
            "command": "archivos",
            "data": files,
            "prompt_addition": f"""
ARCHIVOS ENCONTRADOS (patrón: {pattern}):
{file_list or 'No se encontraron archivos'}
Total: {files.get('total_matches', 0)} archivos
"""
        }

    elif command == '/duplicados' or command == '/duplicates':
        # Get duplicates
        duplicates = await get_duplicates_context(limit=20)
        return {
            "command": "duplicados",
            "data": duplicates,
            "prompt_addition": f"""
DUPLICADOS EN EL PROYECTO:
Total de grupos duplicados: {duplicates.get('total_duplicate_groups', 0)}
"""
        }

    elif command == '/hermanos' or command == '/siblings':
        # Get sibling files
        filename = args if args else None
        siblings = await get_siblings_context(filename=filename, limit=20)
        sibling_list = "\n".join([
            f"- {s['filename']}: {s['count']} copias\n  Ubicaciones: {', '.join(s['paths'][:3])}"
            for s in siblings.get('siblings', [])
        ])
        return {
            "command": "hermanos",
            "data": siblings,
            "prompt_addition": f"""
ARCHIVOS HERMANOS (mismo nombre, diferentes ubicaciones):
{sibling_list or 'No se encontraron hermanos'}
Total grupos: {siblings.get('total_groups', 0)}
"""
        }

    elif command == '/leer' or command == '/read':
        # Read a specific file
        if not args:
            return {
                "command": "leer",
                "error": "Debes especificar una ruta de archivo",
                "prompt_addition": "Error: Usa /leer <ruta_archivo> para leer un archivo"
            }
        content = await get_file_content_context(path=args)
        if "error" in content:
            return {
                "command": "leer",
                "error": content["error"],
                "prompt_addition": f"Error leyendo archivo: {content['error']}"
            }
        return {
            "command": "leer",
            "data": content,
            "prompt_addition": f"""
CONTENIDO DEL ARCHIVO: {content.get('filename', args)}
Ruta: {content.get('path', args)}
Líneas: {content.get('lines', 0)} {'(truncado)' if content.get('truncated') else ''}

```
{content.get('content', '')[:4000]}
```
"""
        }

    elif command == '/comparar' or command == '/compare':
        # Compare two files
        file_args = args.split()
        if len(file_args) < 2:
            return {
                "command": "comparar",
                "error": "Debes especificar dos rutas de archivo",
                "prompt_addition": "Error: Usa /comparar <ruta1> <ruta2> para comparar dos archivos"
            }

        file1 = await get_file_content_context(path=file_args[0])
        file2 = await get_file_content_context(path=file_args[1])

        return {
            "command": "comparar",
            "data": {"file1": file1, "file2": file2},
            "prompt_addition": f"""
COMPARACIÓN DE ARCHIVOS:

=== ARCHIVO 1: {file1.get('filename', file_args[0])} ===
{file1.get('content', file1.get('error', 'Error'))[:2000]}

=== ARCHIVO 2: {file2.get('filename', file_args[1])} ===
{file2.get('content', file2.get('error', 'Error'))[:2000]}

Analiza las diferencias y sugiere cómo consolidarlos.
"""
        }

    elif command == '/ayuda' or command == '/help':
        return {
            "command": "ayuda",
            "prompt_addition": """
COMANDOS DISPONIBLES:
- /proyecto - Ver resumen del proyecto actual
- /archivos <patrón> - Buscar archivos (ej: /archivos config.py)
- /hermanos [archivo] - Ver archivos con mismo nombre en diferentes ubicaciones
- /duplicados - Ver grupos de archivos duplicados
- /leer <ruta> - Leer contenido de un archivo
- /comparar <ruta1> <ruta2> - Comparar dos archivos
- /ayuda - Mostrar esta ayuda

Ejemplos:
- /archivos *.py
- /hermanos config.py
- /leer E:/proyecto/config.py
- /comparar archivo1.py archivo2.py
"""
        }

    return None


# =============================================================================
# Conversation Persistence
# =============================================================================

import sqlite3
from datetime import datetime
import uuid

# Database path for conversations
CONVERSATIONS_DB = os.path.join(os.getenv("DATA_DIR", "/app/data"), "ai_conversations.db")


def init_conversations_db():
    """Initialize the conversations database."""
    os.makedirs(os.path.dirname(CONVERSATIONS_DB), exist_ok=True)
    conn = sqlite3.connect(CONVERSATIONS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            personality TEXT DEFAULT 'default',
            model TEXT,
            created_at TEXT,
            updated_at TEXT,
            messages TEXT
        )
    """)
    conn.commit()
    conn.close()


# Initialize DB on module load
try:
    init_conversations_db()
except Exception:
    pass


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(50, description="Max conversations to return"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """List all saved conversations."""
    try:
        conn = sqlite3.connect(CONVERSATIONS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, personality, model, created_at, updated_at,
                   (SELECT COUNT(*) FROM json_each(messages)) as message_count
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()
        conn.close()

        return {
            "conversations": [dict(row) for row in rows],
            "total": len(rows),
        }
    except Exception as e:
        return {"conversations": [], "total": 0, "error": str(e)}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation by ID."""
    try:
        conn = sqlite3.connect(CONVERSATIONS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM conversations WHERE id = ?
        """, (conversation_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        result = dict(row)
        result["messages"] = json.loads(result["messages"]) if result["messages"] else []
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations")
async def save_conversation(
    id: Optional[str] = Body(None, description="Conversation ID (auto-generated if not provided)"),
    title: str = Body("Nueva conversación", description="Conversation title"),
    personality: str = Body("default", description="AI personality used"),
    model: str = Body(None, description="Model used"),
    messages: List[Dict[str, Any]] = Body(default=[], description="Conversation messages"),
):
    """Save or update a conversation."""
    try:
        conn = sqlite3.connect(CONVERSATIONS_DB)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        conv_id = id or str(uuid.uuid4())[:8]
        messages_json = json.dumps(messages, ensure_ascii=False)

        # Check if conversation exists
        cursor.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
        exists = cursor.fetchone()

        if exists:
            # Update existing
            cursor.execute("""
                UPDATE conversations
                SET title = ?, personality = ?, model = ?, updated_at = ?, messages = ?
                WHERE id = ?
            """, (title, personality, model, now, messages_json, conv_id))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO conversations (id, title, personality, model, created_at, updated_at, messages)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (conv_id, title, personality, model, now, now, messages_json))

        conn.commit()
        conn.close()

        return {
            "id": conv_id,
            "title": title,
            "saved": True,
            "updated_at": now,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    try:
        conn = sqlite3.connect(CONVERSATIONS_DB)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"deleted": True, "id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
