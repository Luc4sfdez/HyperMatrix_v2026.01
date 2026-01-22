# HyperMatrix v2026.01

**AI-Powered Code Analysis Dashboard** - Analiza, compara y consolida código con inteligencia artificial local.

## Características

- **Escaneo de proyectos**: Analiza estructura, funciones, clases y dependencias
- **Detección de duplicados**: Encuentra archivos idénticos y similares
- **Comparación cross-project**: Compara código entre múltiples proyectos
- **Análisis de código muerto**: Detecta imports y funciones no utilizadas
- **IA Local (Ollama)**: Análisis inteligente sin enviar código a la nube
  - Explicación de código
  - Sugerencias de merge
  - Detección de problemas
  - Chat sobre código

## Quick Start con Docker

```bash
# Clonar repositorio
git clone https://github.com/Luc4sfdez/HyperMatrix_v2026.git
cd HyperMatrix_v2026

# Iniciar stack completo (HyperMatrix + Ollama)
docker-compose up -d

# Ver logs
docker-compose logs -f

# Acceder a la interfaz
# http://localhost:26020
```

## URLs

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Web UI | http://localhost:26020 | Dashboard principal |
| API Docs | http://localhost:26020/api/docs | Swagger UI |
| Ollama | http://localhost:11434 | API de LLM local |

## Configuración

### Variables de entorno

```bash
# .env
OLLAMA_MODEL=qwen2.5-coder:7b  # Modelo por defecto
PROJECTS_PATH=./projects        # Carpeta de proyectos a analizar
```

### Modelos recomendados para CPU

| Modelo | RAM | Uso |
|--------|-----|-----|
| `qwen2.5-coder:7b` | 8 GB | Análisis de código (recomendado) |
| `deepseek-coder:6.7b` | 8 GB | Comparación y refactoring |
| `llama3.2:3b` | 4 GB | Rápido, resúmenes |
| `mistral:7b` | 8 GB | Balanceado, español |

### Cambiar modelo

```bash
# Descargar nuevo modelo
docker exec hypermatrix-ollama ollama pull mistral:7b

# Actualizar variable
OLLAMA_MODEL=mistral:7b docker-compose up -d
```

## Desarrollo Local

```bash
# Backend
cd HyperMatrix_v2026.01
pip install -r requirements.txt
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 26020

# Frontend
cd frontend
npm install
npm run dev

# Ollama (local)
ollama serve
ollama pull qwen2.5-coder:7b
```

## API Endpoints

### Escaneo
- `POST /api/scan/start` - Iniciar escaneo
- `GET /api/scan/list` - Listar proyectos
- `GET /api/scan/status/{id}` - Estado del escaneo

### Análisis
- `GET /api/db/search` - Buscar funciones/clases
- `GET /api/analysis/dependencies/{id}/{file}` - Dependencias
- `GET /api/consolidation/cross-project/different` - Archivos diferentes

### IA (Ollama)
- `GET /api/ai/status` - Estado de Ollama
- `POST /api/ai/explain-code` - Explicar código
- `POST /api/ai/analyze-diff` - Analizar diferencias
- `POST /api/ai/find-issues` - Detectar problemas
- `POST /api/ai/chat` - Chat sobre código

## Estructura del Proyecto

```
HyperMatrix_v2026.01/
├── src/
│   ├── core/           # Lógica de negocio
│   ├── phases/         # Fases de escaneo
│   └── web/            # FastAPI app
│       └── routes/     # Endpoints API
│           └── ai.py   # Integración Ollama
├── frontend/           # React dashboard
├── docker-compose.yml  # Stack completo
├── Dockerfile          # Imagen multi-stage
└── docs/               # Documentación
```

## Licencia

MIT License - Libre para uso comercial y personal.
