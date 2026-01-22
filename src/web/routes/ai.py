"""
HyperMatrix v2026.01 - AI Routes (Ollama Integration)
Endpoints for AI-powered code analysis using local LLMs.
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
import httpx

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
):
    """
    Chat about code with AI assistant.
    """
    if not await check_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    system_prompt = """Eres un asistente experto en programación y análisis de código.
Ayudas a los desarrolladores a entender, mejorar y depurar su código.
Responde de forma clara y concisa en español.
Si el usuario proporciona código, analízalo cuidadosamente antes de responder."""

    # Build conversation context
    conversation = ""
    for msg in history[-5:]:  # Last 5 messages for context
        role = "Usuario" if msg.get("role") == "user" else "Asistente"
        conversation += f"{role}: {msg.get('content', '')}\n\n"

    prompt = f"{conversation}Usuario: {message}"

    if context:
        prompt = f"""Código de contexto:
```
{context[:2000]}
```

{prompt}"""

    response = await generate_completion(prompt, model, system_prompt)

    return {
        "response": response,
        "model_used": model or OLLAMA_MODEL,
    }


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
