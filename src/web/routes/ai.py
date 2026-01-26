"""
HyperMatrix v2026.01 - AI Routes (Multi-Provider Support)
Endpoints for AI-powered code analysis using local or cloud LLMs.
Supports: Ollama (local), OpenAI, Anthropic, Groq

With full database and file access for intelligent assistance.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from glob import glob

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
import httpx

# Import app module to access scan data and database
from .. import app as web_app
from ..app import active_scans, scan_results

# Import context builder for SQLite + ChromaDB queries
from ...core.context_builder import build_ai_context, get_context_builder

router = APIRouter()
logger = logging.getLogger(__name__)

# =============================================================================
# AI Provider Configuration
# =============================================================================
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()  # ollama | openai | anthropic | groq

# Ollama (local)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "openhermes:latest")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}"

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = "https://api.openai.com/v1"

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"

# Groq (very fast)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def get_default_model() -> str:
    """Get default model based on provider."""
    if AI_PROVIDER == "openai":
        return OPENAI_MODEL
    elif AI_PROVIDER == "anthropic":
        return ANTHROPIC_MODEL
    elif AI_PROVIDER == "groq":
        return GROQ_MODEL
    return OLLAMA_MODEL


async def check_ollama_available() -> bool:
    """Check if Ollama server is available."""
    if AI_PROVIDER != "ollama":
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def check_ai_available() -> Dict[str, Any]:
    """Check if current AI provider is available."""
    if AI_PROVIDER == "ollama":
        available = await check_ollama_available()
        return {"available": available, "provider": "ollama", "model": OLLAMA_MODEL}
    elif AI_PROVIDER == "openai":
        return {"available": bool(OPENAI_API_KEY), "provider": "openai", "model": OPENAI_MODEL}
    elif AI_PROVIDER == "anthropic":
        return {"available": bool(ANTHROPIC_API_KEY), "provider": "anthropic", "model": ANTHROPIC_MODEL}
    elif AI_PROVIDER == "groq":
        return {"available": bool(GROQ_API_KEY), "provider": "groq", "model": GROQ_MODEL}
    return {"available": False, "provider": AI_PROVIDER, "error": "Unknown provider"}


async def get_available_models() -> List[str]:
    """Get list of available models based on provider."""
    if AI_PROVIDER == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model["name"] for model in data.get("models", [])]
        except Exception:
            pass
        return []
    elif AI_PROVIDER == "openai":
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
    elif AI_PROVIDER == "anthropic":
        return ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
    elif AI_PROVIDER == "groq":
        return ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
    return []


async def generate_completion_ollama(
    prompt: str,
    model: str,
    system: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Generate completion using Ollama (local)."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens}
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, read=300.0)) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        if response.status_code == 200:
            return response.json().get("response", "")
        raise HTTPException(status_code=response.status_code, detail=f"Ollama error: {response.text}")


async def generate_completion_openai(
    prompt: str,
    model: str,
    system: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Generate completion using OpenAI API."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        raise HTTPException(status_code=response.status_code, detail=f"OpenAI error: {response.text}")


async def generate_completion_anthropic(
    prompt: str,
    model: str,
    system: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Generate completion using Anthropic API."""
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ANTHROPIC_BASE_URL}/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json=payload
        )
        if response.status_code == 200:
            return response.json()["content"][0]["text"]
        raise HTTPException(status_code=response.status_code, detail=f"Anthropic error: {response.text}")


async def generate_completion_groq(
    prompt: str,
    model: str,
    system: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Generate completion using Groq API (OpenAI-compatible)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        raise HTTPException(status_code=response.status_code, detail=f"Groq error: {response.text}")


async def generate_completion(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Generate a completion using configured AI provider."""
    model = model or get_default_model()

    try:
        if AI_PROVIDER == "openai":
            return await generate_completion_openai(prompt, model, system, temperature, max_tokens)
        elif AI_PROVIDER == "anthropic":
            return await generate_completion_anthropic(prompt, model, system, temperature, max_tokens)
        elif AI_PROVIDER == "groq":
            return await generate_completion_groq(prompt, model, system, temperature, max_tokens)
        else:  # ollama (default)
            return await generate_completion_ollama(prompt, model, system, temperature, max_tokens)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"{AI_PROVIDER} request timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to {AI_PROVIDER}")


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@router.get("/status")
async def ai_status():
    """Check AI service status and available models."""
    status = await check_ai_available()
    models = await get_available_models() if status["available"] else []
    default_model = get_default_model()

    result = {
        "available": status["available"],
        "provider": AI_PROVIDER,
        "default_model": default_model,
        "models": models,
        "model_loaded": default_model in models if AI_PROVIDER == "ollama" else status["available"],
    }

    # Add provider-specific info
    if AI_PROVIDER == "ollama":
        result["ollama_host"] = OLLAMA_HOST
    else:
        result["api_configured"] = status["available"]

    return result


@router.get("/models")
async def list_models():
    """List all available models for current provider."""
    status = await check_ai_available()
    if not status["available"]:
        raise HTTPException(status_code=503, detail=f"{AI_PROVIDER} not available")

    models = await get_available_models()
    return {"models": models, "default": get_default_model(), "provider": AI_PROVIDER}


@router.get("/help")
async def ai_help():
    """
    Get AI assistant help - commands, APIs, personalities.
    This endpoint works WITHOUT AI being loaded.
    """
    return {
        "assistant": {
            "name": "Elena",
            "description": "Asistente experta en analisis de codigo de HyperMatrix",
            "personalities": [
                {"id": "elena", "name": "Elena", "icon": "👩‍💻", "description": "Asistente amigable y profesional"},
                {"id": "code_reviewer", "name": "Code Reviewer", "icon": "🔍", "description": "Revisor de codigo estricto"},
                {"id": "architect", "name": "Architect", "icon": "🏗️", "description": "Arquitecto de software"},
                {"id": "debugger", "name": "Debugger", "icon": "🐛", "description": "Especialista en depuracion"},
            ]
        },
        "commands": {
            "description": "Comandos especiales disponibles en el chat",
            "list": [
                {"command": "/proyecto", "description": "Resumen del proyecto actual"},
                {"command": "/archivos <patron>", "description": "Buscar archivos (ej: /archivos config.py)"},
                {"command": "/hermanos", "description": "Archivos con mismo nombre en distintas carpetas"},
                {"command": "/duplicados", "description": "Archivos duplicados (mismo hash)"},
                {"command": "/funciones <nombre>", "description": "Buscar funciones por nombre"},
                {"command": "/clases <nombre>", "description": "Buscar clases por nombre"},
                {"command": "/imports <archivo>", "description": "Ver imports de un archivo"},
                {"command": "/impacto <archivo>", "description": "Analizar impacto de eliminar archivo"},
                {"command": "/leer <ruta>", "description": "Leer contenido de un archivo"},
                {"command": "/comparar <ruta1> <ruta2>", "description": "Comparar dos archivos"},
                {"command": "/stats", "description": "Estadisticas del proyecto"},
                {"command": "/help", "description": "Mostrar esta ayuda"},
            ]
        },
        "tabs": {
            "description": "Pestanas disponibles en HyperMatrix",
            "list": [
                {"id": 1, "name": "Dashboard", "description": "Iniciar analisis, ver proyectos"},
                {"id": 2, "name": "Resultados", "description": "Ver archivos analizados, duplicados, hermanos"},
                {"id": 3, "name": "Analisis Avanzado", "description": "Busqueda en lenguaje natural"},
                {"id": 4, "name": "Explorador BD", "description": "Buscar funciones, clases, variables"},
                {"id": 5, "name": "Codigo Muerto", "description": "Detectar codigo no usado"},
                {"id": 6, "name": "Comparador", "description": "Comparar 2 archivos lado a lado"},
                {"id": 7, "name": "Merge Wizard", "description": "Fusionar versiones de archivos"},
                {"id": 8, "name": "Acciones Lote", "description": "Operaciones masivas"},
                {"id": 9, "name": "Comparar Proyectos", "description": "Comparar 2 proyectos"},
                {"id": 10, "name": "Refactoring", "description": "Sugerencias de mejora"},
                {"id": 11, "name": "Grafo Linaje", "description": "Ver dependencias visuales"},
                {"id": 12, "name": "Analisis Impacto", "description": "Que se rompe si elimino X"},
                {"id": 13, "name": "Webhooks", "description": "Notificaciones externas"},
                {"id": 14, "name": "Dashboard ML", "description": "Metricas de embeddings"},
                {"id": 15, "name": "Contexto", "description": "Subir documentacion adicional"},
                {"id": 16, "name": "Reglas", "description": "Configurar reglas de analisis"},
                {"id": 17, "name": "Gestion", "description": "Eliminar workspace/analisis"},
                {"id": 18, "name": "Configuracion", "description": "Ajustes generales"},
            ]
        },
        "api_endpoints": {
            "ai": [
                {"method": "GET", "path": "/api/ai/status", "description": "Estado del proveedor de IA"},
                {"method": "GET", "path": "/api/ai/models", "description": "Modelos disponibles"},
                {"method": "GET", "path": "/api/ai/help", "description": "Esta ayuda"},
                {"method": "POST", "path": "/api/ai/chat", "description": "Chat con Elena"},
                {"method": "POST", "path": "/api/ai/explain-code", "description": "Explicar codigo"},
                {"method": "POST", "path": "/api/ai/find-issues", "description": "Encontrar problemas"},
            ],
            "scan": [
                {"method": "POST", "path": "/api/scan/start", "description": "Iniciar escaneo"},
                {"method": "GET", "path": "/api/scan/list", "description": "Listar escaneos"},
                {"method": "GET", "path": "/api/scan/status/{id}", "description": "Estado de escaneo"},
            ],
            "db": [
                {"method": "GET", "path": "/api/db/stats", "description": "Estadisticas de BD"},
                {"method": "GET", "path": "/api/db/search", "description": "Buscar en BD"},
                {"method": "GET", "path": "/api/db/files", "description": "Listar archivos"},
            ]
        },
        "current_provider": {
            "name": AI_PROVIDER,
            "model": get_default_model(),
        },
        "troubleshooting": [
            {"problem": "Error 504 Timeout", "solution": "El modelo tarda mucho. Usa preguntas especificas o cambia a GPU/API cloud"},
            {"problem": "Ollama no responde", "solution": "Verificar que el contenedor hypermatrix-ollama esta corriendo"},
            {"problem": "No veo funciones", "solution": "Re-escanear el proyecto para indexar archivos"},
            {"problem": "ChromaDB vacio", "solution": "El escaneo no incluyo embeddings. Re-escanear"},
        ]
    }


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
    project_id: Optional[int] = Body(None, description="Project ID for database context"),
    use_context_builder: bool = Body(True, description="Whether to query SQLite+ChromaDB for context"),
):
    """
    Chat about code with AI assistant.
    Now with automatic SQLite + ChromaDB context building!

    The AI can now answer questions like:
    - "Where is function X?" -> Shows exact file and line number
    - "What depends on Y?" -> Lists files that import/use Y
    - "If I delete Z, what breaks?" -> Shows dependent files

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

    # Build rich context from SQLite + ChromaDB
    # Skip heavy context for general/greeting messages UNLESS they mention specific components
    db_context = ""
    general_patterns = ['hola', 'hello', 'hi', 'hey', 'buenos', 'buenas', 'saludos',
                        'que tal', 'como estas', 'ayuda', 'help', 'que puedes',
                        'que sabes', 'quien eres', 'presentate']
    # Patterns that indicate a technical query (should use context even with greeting)
    technical_patterns = ['parser', 'ef_', 'ef0', 'componente', 'versiones', 'gen1', 'gen2',
                          'funcion', 'clase', 'archivo', 'codigo', 'analizar']
    is_general_query = any(p in message.lower() for p in general_patterns)
    has_technical_content = any(p in message.lower() for p in technical_patterns)

    # Use context if: technical content OR (not general query)
    should_use_context = has_technical_content or not is_general_query

    if use_context_builder and not command_result and should_use_context:
        try:
            # Try to get project_id from scan_id if not provided
            effective_project_id = project_id
            if not effective_project_id and scan_id:
                try:
                    effective_project_id = int(scan_id)
                except ValueError:
                    pass

            db_context = build_ai_context(message, project_id=effective_project_id)
        except Exception as e:
            db_context = f"[Error building context: {str(e)}]\n"

    # Use custom system prompt if provided, otherwise use Elena personality
    if not system_prompt:
        system_prompt = """Eres Elena, la asistente virtual de HyperMatrix.

TU PERSONALIDAD:
- Eres amigable, profesional y resolutiva
- Saludas cordialmente cuando el usuario dice "hola"
- Usas un tono cercano pero técnicamente preciso
- Celebras los logros del usuario y le animas cuando hay problemas
- NUNCA eres grosera ni sarcástica

TU ROL:
- Asistente experta en análisis de código para HyperMatrix
- Tienes acceso a la base de datos SQLite y ChromaDB del proyecto
- Puedes ver funciones, clases, imports y dependencias

CÓMO RESPONDER:
- Si preguntan "¿dónde está X?": Da archivo y línea EXACTA
- Si preguntan "¿qué se rompe si borro X?": Lista archivos dependientes
- Si no encuentras algo: Sugiere amablemente usar comandos como /funciones o /archivos
- Responde en español, de forma clara y concisa

COMANDOS DISPONIBLES:
- /proyecto - Resumen del proyecto
- /archivos <patron> - Buscar archivos
- /funciones <nombre> - Buscar funciones
- /leer <ruta> - Ver contenido de archivo
- /help - Ver todos los comandos"""

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

    # Add SQLite + ChromaDB context if available
    if db_context:
        prompt = f"""{db_context}

{prompt}"""

    # Add code context if provided
    if context:
        prompt = f"""Código de contexto:
```
{context[:2000]}
```

{prompt}"""

    # Auto-add project context for better awareness (skip for general queries)
    if not command_result and scan_id and not is_general_query:
        try:
            project_ctx = await get_project_context(scan_id=scan_id)
            if project_ctx.get("has_project"):
                # Get sibling filenames for context
                siblings_sample = project_ctx.get('sibling_filenames', [])[:20]
                siblings_str = ', '.join(siblings_sample) if siblings_sample else 'ninguno detectado'

                # Get top sibling groups with counts (exclude __init__.py which is usually boilerplate)
                siblings_data = _get_siblings_internal(scan_id=scan_id, limit=20)
                top_siblings = siblings_data.get('siblings', [])
                # Filter out __init__.py and sort by count
                interesting_siblings = [s for s in top_siblings if s['filename'] != '__init__.py'][:15]
                siblings_detail = '\n'.join([
                    f"  - {s['filename']}: {s['count']} copias"
                    for s in interesting_siblings
                ]) if interesting_siblings else '  (ninguno detectado)'

                project_info = f"""
=== CONTEXTO DEL PROYECTO (YA CARGADO) ===
Proyecto: {project_ctx.get('project_name')}
Archivos totales: {project_ctx.get('total_files')}
Archivos analizados: {project_ctx.get('analyzed_files', 0)}
Funciones detectadas: {project_ctx.get('total_functions', 0)}
Clases detectadas: {project_ctx.get('total_classes', 0)}
Grupos de hermanos: {project_ctx.get('sibling_groups')}

TOP ARCHIVOS HERMANOS (mismo nombre, múltiples ubicaciones):
{siblings_detail}

Archivos con hermanos: {siblings_str}

INSTRUCCIONES: Tienes acceso REAL a estos datos. Cuando te pregunten sobre el proyecto:
- USA directamente los datos de arriba, no digas "usa /comando"
- Si necesitas datos específicos que no están aquí, TÚ escribe el comando (ej: /leer ruta/archivo.py)
=============================

"""
                prompt = project_info + prompt
        except Exception as e:
            pass  # Silently continue if context injection fails

    response = await generate_completion(prompt, model, system_prompt)

    result = {
        "response": response,
        "model_used": model or OLLAMA_MODEL,
        "context_used": bool(db_context),
    }

    # Include command data if a special command was processed
    if command_result:
        result["command"] = command_result.get("command")
        result["command_data"] = command_result.get("data")

    # Include context info for debugging/transparency
    if db_context:
        # Count what was found in context
        result["context_info"] = {
            "sqlite_queried": True,
            "chromadb_queried": True,
            "keywords_extracted": len(db_context.split("FUNCIONES ENCONTRADAS:")) > 1,
        }

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


def _get_siblings_internal(scan_id: Optional[str], filename: Optional[str] = None, limit: int = 20) -> dict:
    """
    Internal function to get sibling file groups.
    Used by both HTTP endpoint and internal code.
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
                # Extract clean paths from SiblingFile objects
                file_paths = []
                for f in group.files:
                    if hasattr(f, 'filepath'):
                        file_paths.append(f.filepath)
                    elif hasattr(f, 'path'):
                        file_paths.append(f.path)
                    else:
                        file_paths.append(str(f))

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
    return _get_siblings_internal(scan_id, filename, limit)


@router.get("/context/file-content")
async def get_file_content_context(
    path: str = Query(..., description="File path to read"),
    max_lines: int = Query(200, description="Max lines to return"),
):
    """
    Read content of a specific file.
    Allows the AI to see actual file contents for analysis.
    Supports: absolute paths, relative paths, and filename search.
    """
    try:
        file_path = Path(path)

        # Security: allowed directories
        allowed_prefixes = ["/projects", "/app", "E:", "C:", "D:", "\\projects", "\\app"]
        path_str = str(file_path)

        # Check if it's an absolute path within allowed directories
        is_allowed = any(path_str.upper().startswith(p.upper()) for p in allowed_prefixes)

        # If not absolute/allowed, try to find the file by name
        if not file_path.is_absolute() or not is_allowed:
            import glob as glob_module
            # Search in /projects directory
            search_patterns = [
                f"/projects/**/{path}",
                f"/projects/**/*{path}*",
                f"/projects/**/{path}.*",
            ]
            found_files = []
            for pattern in search_patterns:
                matches = glob_module.glob(pattern, recursive=True)
                # Filter only files, not directories
                found_files.extend([f for f in matches if Path(f).is_file()])
                if found_files:
                    break

            if found_files:
                file_path = Path(found_files[0])
            else:
                return {"error": f"Archivo no encontrado: '{path}'. Usa ruta completa (ej: E:/proyecto/archivo.py) o nombre exacto."}

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
- /analizar <componente> - Análisis profundo de un componente/parser
- /ayuda - Mostrar esta ayuda

Ejemplos:
- /archivos *.py
- /hermanos config.py
- /leer E:/proyecto/config.py
- /comparar archivo1.py archivo2.py
- /analizar ef_0520
"""
        }

    elif command == '/analizar' or command == '/analyze':
        # Deep analysis of a component across versions
        if not args:
            return {
                "command": "analizar",
                "error": "Especifica el nombre del componente",
                "prompt_addition": """Error: Usa /analizar <nombre_componente>

Ejemplos:
- /analizar ef_0520
- /analizar identification
- /analizar parser_gen2

Este comando analiza un componente en todas las versiones del proyecto,
mostrando diferencias, estructura y comparativas."""
            }

        try:
            from ...core.deep_analyzer import analyze_component
            analysis_result = analyze_component(args)
            return {
                "command": "analizar",
                "data": {"component": args},
                "prompt_addition": f"""
ANÁLISIS PROFUNDO DEL COMPONENTE: {args}

{analysis_result}

Usa esta información para responder preguntas sobre el componente,
sus diferencias entre versiones, estructura y funcionalidades.
"""
            }
        except Exception as e:
            return {
                "command": "analizar",
                "error": str(e),
                "prompt_addition": f"Error al analizar componente '{args}': {str(e)}"
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
