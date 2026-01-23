"""
HyperMatrix v2026 - Auto Summary Generator
Generates project summaries using Ollama AI.
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:7b")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}"

SUMMARY_PROMPT = """Analyze this software project and generate a concise summary in Spanish.

**Project Statistics:**
- Total files: {file_count}
- Python files: {python_count}
- JavaScript/TypeScript files: {js_count}
- Other files: {other_count}
- Total functions: {function_count}
- Total classes: {class_count}

**Top Imports/Dependencies:**
{top_imports}

**Directory Structure:**
{tree_structure}

**Generate the following (in Spanish):**

1. **Resumen Ejecutivo** (2-3 sentences describing what this project does)
2. **Tecnologías Clave** (list the main technologies/frameworks detected)
3. **Arquitectura** (brief description of the project structure)
4. **Puntos de Entrada** (main entry points if detectable)
5. **Sugerencias** (1-2 improvement suggestions based on the structure)

Format your response with clear headers using **bold** markdown."""


@dataclass
class ProjectSummary:
    """Generated project summary."""
    scan_id: str
    project_path: str
    summary_text: str
    file_count: int
    function_count: int
    class_count: int
    technologies: List[str]
    generated_at: str


class SummaryGenerator:
    """Generates AI-powered project summaries."""

    def __init__(self):
        self.timeout = 120.0  # 2 minutes for summary generation

    async def check_ollama_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def _extract_technologies(self, scan_result: dict) -> List[str]:
        """Extract detected technologies from scan results."""
        technologies = set()

        # From file extensions
        file_types = scan_result.get("file_types", {})
        tech_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "React",
            ".ts": "TypeScript",
            ".tsx": "React/TypeScript",
            ".vue": "Vue.js",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "Sass/SCSS",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".md": "Markdown",
            ".sql": "SQL",
            ".dockerfile": "Docker",
        }
        for ext, count in file_types.items():
            if ext.lower() in tech_map and count > 0:
                technologies.add(tech_map[ext.lower()])

        # From imports
        imports = scan_result.get("top_imports", [])
        import_tech_map = {
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "react": "React",
            "express": "Express.js",
            "numpy": "NumPy",
            "pandas": "Pandas",
            "tensorflow": "TensorFlow",
            "torch": "PyTorch",
            "sqlalchemy": "SQLAlchemy",
            "pytest": "Pytest",
            "requests": "Requests",
            "aiohttp": "Aiohttp",
        }
        for imp in imports:
            imp_lower = imp.lower().split(".")[0]
            if imp_lower in import_tech_map:
                technologies.add(import_tech_map[imp_lower])

        return sorted(list(technologies))

    def _build_tree_structure(self, files: List[dict], max_depth: int = 3) -> str:
        """Build a simplified directory tree from file list."""
        if not files:
            return "(empty)"

        # Extract unique directories
        dirs = set()
        for f in files[:200]:  # Limit for performance
            path = f.get("filepath", "")
            parts = path.replace("\\", "/").split("/")
            for i in range(1, min(len(parts), max_depth + 1)):
                dirs.add("/".join(parts[:i]))

        # Sort and format
        sorted_dirs = sorted(dirs)[:30]  # Limit output
        return "\n".join(f"  {d}/" for d in sorted_dirs) if sorted_dirs else "(flat structure)"

    def _get_top_imports(self, analysis_result: dict) -> str:
        """Get top imports from analysis."""
        imports = []

        # Extract from parse results if available
        for file_result in analysis_result.get("results", [])[:100]:
            parse_result = file_result.get("parse_result")
            if parse_result and hasattr(parse_result, "imports"):
                for imp in parse_result.imports:
                    imports.append(imp.module)

        # Count and get top 15
        counter = Counter(imports)
        top = counter.most_common(15)

        if not top:
            return "(no imports detected)"

        return "\n".join(f"  - {name} ({count}x)" for name, count in top)

    async def generate_summary(
        self,
        scan_id: str,
        scan_result: dict,
        analysis_result: Optional[dict] = None
    ) -> Optional[ProjectSummary]:
        """
        Generate a summary for a completed scan.

        Args:
            scan_id: ID of the scan
            scan_result: Result from phase 1 discovery
            analysis_result: Result from phase 2 analysis (optional)

        Returns:
            ProjectSummary or None if generation fails
        """
        # Check Ollama availability
        if not await self.check_ollama_available():
            logger.warning("Ollama not available for summary generation")
            return None

        try:
            # Extract statistics
            discovery = scan_result.get("discovery", {})
            files = discovery.get("files", [])
            file_types = Counter(f.get("extension", "") for f in files)

            file_count = len(files)
            python_count = file_types.get(".py", 0)
            js_count = file_types.get(".js", 0) + file_types.get(".jsx", 0) + file_types.get(".ts", 0) + file_types.get(".tsx", 0)
            other_count = file_count - python_count - js_count

            # Get function/class counts from analysis
            function_count = 0
            class_count = 0
            if analysis_result:
                function_count = analysis_result.get("total_functions", 0)
                class_count = analysis_result.get("total_classes", 0)

            # Build prompt
            prompt = SUMMARY_PROMPT.format(
                file_count=file_count,
                python_count=python_count,
                js_count=js_count,
                other_count=other_count,
                function_count=function_count,
                class_count=class_count,
                top_imports=self._get_top_imports(analysis_result or {}),
                tree_structure=self._build_tree_structure(files),
            )

            # Call Ollama
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 1000,
                        }
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Ollama error: {response.text}")
                    return None

                result = response.json()
                summary_text = result.get("response", "")

                if not summary_text:
                    logger.warning("Empty summary from Ollama")
                    return None

                # Extract technologies
                technologies = self._extract_technologies({
                    "file_types": dict(file_types),
                    "top_imports": [imp.split(".")[0] for imp in self._get_top_imports(analysis_result or {}).split("\n") if imp.strip().startswith("-")]
                })

                from datetime import datetime
                return ProjectSummary(
                    scan_id=scan_id,
                    project_path=discovery.get("root_path", ""),
                    summary_text=summary_text,
                    file_count=file_count,
                    function_count=function_count,
                    class_count=class_count,
                    technologies=technologies,
                    generated_at=datetime.now().isoformat(),
                )

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return None

    def generate_quick_summary(self, scan_result: dict) -> dict:
        """
        Generate a quick summary without AI (just statistics).

        Args:
            scan_result: Scan result dict

        Returns:
            Quick summary dict
        """
        discovery = scan_result.get("discovery", {})
        files = discovery.get("files", [])
        file_types = Counter(f.get("extension", "") for f in files)

        return {
            "file_count": len(files),
            "file_types": dict(file_types.most_common(10)),
            "technologies": self._extract_technologies({"file_types": dict(file_types)}),
            "directories": len(set(f.get("filepath", "").rsplit("/", 1)[0] for f in files)),
        }


# Global instance
_summary_generator: Optional[SummaryGenerator] = None


def get_summary_generator() -> SummaryGenerator:
    """Get the global summary generator instance."""
    global _summary_generator
    if _summary_generator is None:
        _summary_generator = SummaryGenerator()
    return _summary_generator
