# HyperMatrix v2026 - Manual de API

## Inicio Rapido

### Requisitos
- Python 3.11+
- Node.js 18+

### Iniciar el Sistema

```bash
# Backend (puerto 26020)
cd E:\HyperMatrix_v2026
python -c "import uvicorn; uvicorn.run('src.web.app:app', host='127.0.0.1', port=26020)"

# Frontend (puerto 5173 o 5175)
cd E:\HyperMatrix_v2026\frontend
npm run dev
```

### URLs
- **Backend API**: http://127.0.0.1:26020
- **Frontend UI**: http://localhost:5173

---

## Endpoints de la API

### 1. Proyectos y Scans

#### Listar Scans/Proyectos
```
GET /api/scan/list
```
**Respuesta:**
```json
{
  "scans": [
    {
      "scan_id": "16",
      "status": "completed",
      "files": 2102,
      "project": "HyperMatrix_self"
    }
  ]
}
```

#### Listar Proyectos con Detalles
```
GET /api/db/projects
```
**Respuesta:**
```json
{
  "projects": [
    {
      "id": 16,
      "name": "HyperMatrix_self",
      "path": "E:\\HyperMatrix_v2026",
      "file_count": 2102
    }
  ]
}
```

#### Estadisticas de la Base de Datos
```
GET /api/db/stats
```
**Respuesta:**
```json
{
  "total_projects": 2,
  "total_files": 3871,
  "total_functions": 51818,
  "total_classes": 8799,
  "total_variables": 180067,
  "total_imports": 33386
}
```

---

### 2. Busqueda

#### Busqueda Unificada (funciones, clases, variables, imports)
```
GET /api/db/search?q={query}&type={type}&limit={limit}
```
**Parametros:**
- `q` (requerido): Texto a buscar
- `type` (opcional): `all`, `functions`, `classes`, `variables`, `imports`
- `limit` (opcional): Numero maximo de resultados (default: 50)

**Ejemplo:**
```
GET /api/db/search?q=parse&type=functions&limit=10
```
**Respuesta:**
```json
{
  "query": "parse",
  "total": 20,
  "results": {
    "functions": [
      {"name": "parse_data", "line": 45, "file": "...", "project": "..."}
    ],
    "classes": [...],
    "variables": [...],
    "imports": [...]
  }
}
```

---

### 3. Analisis de Dependencias (Lineage)

#### Obtener Dependencias de un Archivo
```
GET /api/analysis/dependencies/{project_id}/{filename}
```
**Ejemplo:**
```
GET /api/analysis/dependencies/16/ef_0002.py
```
**Respuesta:**
```json
{
  "filepath": "E:\\...\\ef_0002.py",
  "imports": ["os", "sys", "typing"],
  "imported_by": ["tgd_parser.py", "test_suite.py"],
  "circular_dependencies": [],
  "external_dependencies": ["os", "sys"],
  "coupling_score": 0.8
}
```

#### Obtener Grupos de Archivos Hermanos
```
GET /api/db/siblings/{project_id}?limit={limit}
```
**Ejemplo:**
```
GET /api/db/siblings/16?limit=10
```
**Respuesta:**
```json
{
  "total": 247,
  "groups": [
    {
      "filename": "__init__.py",
      "file_count": 115,
      "files": [
        {"filepath": "...", "directory": "..."}
      ]
    }
  ]
}
```

---

### 4. Analisis de Codigo Muerto

#### Analizar Archivos
```
POST /api/advanced/dead-code/analyze?files={filepath1}&files={filepath2}
```
**Ejemplo:**
```
POST /api/advanced/dead-code/analyze?files=E:/HyperMatrix_v2026/src/web/app.py
```
**Respuesta:**
```json
{
  "files_analyzed": 1,
  "total_definitions": 93,
  "summary": {
    "dead_functions": 0,
    "dead_classes": 0,
    "dead_imports": 15,
    "dead_variables": 0
  },
  "dead_imports": [
    {"file": "...", "name": "asyncio", "line": 6, "confidence": 0.95}
  ]
}
```

#### Obtener Archivos Python de un Proyecto
```
GET /api/db/files/{project_id}/python?limit={limit}
```
**Ejemplo:**
```
GET /api/db/files/16/python?limit=100
```
**Respuesta:**
```json
{
  "files": [
    "E:\\HyperMatrix_v2026\\src\\web\\app.py",
    "E:\\HyperMatrix_v2026\\main.py"
  ]
}
```

---

### 5. Comparacion de Archivos

#### Comparar Dos Archivos
```
GET /api/consolidation/compare?file1={path1}&file2={path2}
```
**Ejemplo:**
```
GET /api/consolidation/compare?file1=E:/HyperMatrix_v2026/src/web/app.py&file2=E:/HyperMatrix_v2026/main.py
```
**Respuesta:**
```json
{
  "file1": "...",
  "file2": "...",
  "affinity": {
    "overall": 0.306,
    "level": "low",
    "content": 0.015,
    "structure": 0.5,
    "dna": 0.5,
    "hash_match": false
  },
  "file1_lines": 539,
  "file2_lines": 327
}
```

#### Listar Archivos para Selector
```
GET /api/db/files?limit={limit}
```
**Respuesta:**
```json
{
  "files": [
    {"id": 1, "filepath": "...", "file_type": "python", "project": "..."}
  ]
}
```

---

### 6. Historial de Proyectos

#### Obtener Proyectos Recientes
```
GET /api/history/projects?limit={limit}
```
**Respuesta:**
```json
{
  "recent": [
    {"path": "E:/HyperMatrix_v2026", "name": "HyperMatrix", "last_used": "..."}
  ],
  "favorites": [...]
}
```

---

### 7. Escaneo de Proyectos

#### Iniciar Escaneo
```
POST /api/scan/start
Content-Type: application/json

{
  "path": "E:/mi-proyecto",
  "project_name": "MiProyecto"
}
```

#### Estado del Escaneo
```
GET /api/scan/status/{scan_id}
```

#### Resultado del Escaneo
```
GET /api/scan/result/{scan_id}
```

#### Resumen del Escaneo
```
GET /api/scan/result/{scan_id}/summary
```

---

## Paginas del Frontend

| Pagina | URL | Descripcion |
|--------|-----|-------------|
| Dashboard | `/` | Iniciar scans, ver proyectos |
| Explorer | `/explorer` | Buscar funciones, clases, variables |
| Lineage | `/lineage` | Grafo de dependencias |
| Dead Code | `/dead-code` | Detectar codigo muerto |
| Compare | `/compare` | Comparar archivos |
| Batch Actions | `/batch` | Acciones en lote |
| Impact Analysis | `/impact` | Analisis de impacto |

---

## Base de Datos

La base de datos SQLite (`hypermatrix.db`) contiene:

| Tabla | Descripcion |
|-------|-------------|
| `projects` | Proyectos escaneados |
| `files` | Archivos analizados |
| `functions` | Funciones encontradas |
| `classes` | Clases encontradas |
| `variables` | Variables encontradas |
| `imports` | Importaciones encontradas |

---

## Ejemplos con cURL

```bash
# Listar proyectos
curl http://127.0.0.1:26020/api/scan/list

# Buscar funciones
curl "http://127.0.0.1:26020/api/db/search?q=parse&type=functions&limit=5"

# Obtener dependencias
curl "http://127.0.0.1:26020/api/analysis/dependencies/16/app.py"

# Analizar codigo muerto
curl -X POST "http://127.0.0.1:26020/api/advanced/dead-code/analyze?files=E:/HyperMatrix_v2026/main.py"

# Comparar archivos
curl "http://127.0.0.1:26020/api/consolidation/compare?file1=E:/file1.py&file2=E:/file2.py"
```

---

## Solucion de Problemas

### El servidor no inicia
```bash
# Verificar que el puerto no esta en uso
netstat -an | findstr 26020

# Iniciar con logs detallados
python -c "import uvicorn; uvicorn.run('src.web.app:app', host='127.0.0.1', port=26020, log_level='debug')"
```

### Dropdowns vacios
- Verifica que hay proyectos con archivos: `GET /api/scan/list`
- Los proyectos sin archivos (`files: 0`) se filtran automaticamente

### Error "No consolidation data"
- El endpoint usa la base de datos como fallback automaticamente
- Verifica que el proyecto existe: `GET /api/db/projects`
