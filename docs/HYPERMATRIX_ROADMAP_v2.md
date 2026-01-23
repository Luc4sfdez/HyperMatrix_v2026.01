# 🚀 HYPERMATRIX ROADMAP v2026.02

**Fecha:** 2026-01-23  
**Estado actual:** MVP funcional con escaneo, duplicados, linaje y IA (Ollama)

---

## 🔴 URGENTE - Bugs y Fixes

### 1. Persistencia de Base de Datos
**Problema:** Los análisis se pierden al reiniciar contenedores  
**Solución:**
```yaml
# docker-compose.yml
volumes:
  hypermatrix_data:
    driver: local

services:
  hypermatrix:
    volumes:
      - hypermatrix_data:/app/data  # BD persiste aquí
      - ./projects:/projects:ro      # Zona intercambio (solo lectura)
```
**Archivos afectados:** `docker-compose.yml`, `config.py`

---

### 2. Error 504 en Análisis IA
**Problema:** Ollama tarda más que el timeout del proxy  
**Solución:**
- Aumentar timeout en nginx/uvicorn
- Añadir streaming de respuestas
- Indicador de progreso en frontend

---

### 3. Panel IA no redimensiona contenido
**Problema:** Sidebar derecho se superpone en vez de empujar  
**Solución CSS:**
```css
/* Contenedor principal debe ser flex */
.main-container {
  display: flex;
  transition: margin-right 0.3s ease;
}

.main-container.ia-panel-open {
  margin-right: 350px; /* Ancho del panel IA */
}
```

---

### 4. Líneas desfasadas header/sidebar
**Problema:** Unión visual descuadrada  
**Solución:** Revisar `border`, `box-sizing` y alturas fijas

---

### 5. Contraste texto/fondo ilegible
**Problema:** Warnings amarillos/naranjas con texto oscuro  
**Solución:**
```css
.warning-box {
  background: #f59e0b;
  color: #000;  /* Negro sobre naranja */
  font-weight: 600;
}

.error-box {
  background: #dc2626;
  color: #fff;  /* Blanco sobre rojo */
}
```

---

### 6. Merge Wizard solo soporta Python
**Problema:** El sistema detecta hermanos de HTML, CSS, JS, MD, JSON, YAML... pero el Merge Wizard dice "Need at least 2 valid Python files"  
**Solución:** Ampliar el wizard para soportar todos los tipos que el sistema ya analiza

| Tipo | Parser | Merge por |
|------|--------|-----------|
| Python | AST completo | Funciones, clases |
| JS/TS | Regex/básico | Funciones, exports |
| HTML | DOM parser | Secciones, divs |
| CSS | Regex | Selectores, reglas |
| MD | Texto | Secciones por headers (#) |
| JSON/YAML | Nativo | Keys, estructuras |

**Archivos afectados:** `MergeWizard.jsx`, `src/core/merger.py`

---

## 🟡 MEJORAS UI/UX

### 7. Breadcrumbs mejorados
- Añadir navegación clickeable
- Mostrar contexto del proyecto actual

### 8. Temas claro/oscuro
- Toggle en header
- Persistir preferencia en localStorage

### 9. Responsive design
- Mobile-friendly para consultas rápidas
- Colapsar sidebar en pantallas pequeñas

---

## 🟢 FEATURES NUEVAS

### 10. Sistema de Embeddings Ligero

**Objetivo:** Búsqueda semántica sin depender de Ollama

**Stack propuesto:**
```
sentence-transformers (all-MiniLM-L6-v2) → 80MB, CPU
ChromaDB / FAISS → Vector store local
SQLite → Metadata y relaciones
```

**Arquitectura:**
```
┌─────────────────────────────────────────────────────────┐
│                    HYPERMATRIX                          │
├─────────────────────────────────────────────────────────┤
│  CAPA DE ANÁLISIS                                       │
│  ├─ AST Parser (Python) ──→ funciones, clases, imports │
│  ├─ Regex Parser (otros) ──→ patrones, estructuras     │
│  └─ Text Parser (md/txt) ──→ contenido semántico       │
├─────────────────────────────────────────────────────────┤
│  CAPA DE EMBEDDINGS                                     │
│  ├─ sentence-transformers ──→ vectores 384-dim         │
│  ├─ ChromaDB ──→ almacén vectorial                     │
│  └─ Búsqueda híbrida ──→ keyword + semántica           │
├─────────────────────────────────────────────────────────┤
│  CAPA DE IA (bajo demanda)                              │
│  ├─ Ollama (qwen/mistral) ──→ explicaciones            │
│  ├─ Resúmenes ──→ bitácoras, conversaciones            │
│  └─ Chat contextual ──→ preguntas sobre código         │
└─────────────────────────────────────────────────────────┘
```

**Implementación:**
```python
# src/embeddings/engine.py
from sentence_transformers import SentenceTransformer
import chromadb

class EmbeddingEngine:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.chroma = chromadb.PersistentClient(path="./data/vectors")
        self.collection = self.chroma.get_or_create_collection("code_docs")
    
    def index_file(self, file_path: str, content: str, metadata: dict):
        """Indexa un archivo con su embedding"""
        embedding = self.model.encode(content).tolist()
        self.collection.add(
            ids=[file_path],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )
    
    def search(self, query: str, n_results: int = 10):
        """Búsqueda semántica"""
        query_embedding = self.model.encode(query).tolist()
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
```

**Dependencias nuevas:**
```txt
# requirements.txt
sentence-transformers==2.2.2
chromadb==0.4.22
```

---

### 11. Zona de Intercambio Inteligente

**Concepto:**
```
/projects (20GB)          → Carpeta temporal, se puede vaciar
/data/database.db         → SQLite persistente (NO se borra)
/data/vectors/            → ChromaDB persistente (NO se borra)
```

**Flujo:**
1. Usuario sube carpeta a `/projects`
2. HyperMatrix escanea → guarda en BD
3. Usuario puede borrar `/projects` para liberar espacio
4. Análisis permanece en BD

---

### 12. Vinculación de Documentación

**Problema:** Bitácoras, conversaciones, emails están desconectados del código

**Solución:**
```python
# Detectar automáticamente en carpeta del proyecto
DOCS_PATTERNS = [
    "*.md", "*.txt", "README*", "CHANGELOG*",
    "docs/**/*", "notes/**/*", "bitacora*",
    "*.pdf", "*.doc", "*.docx"
]

# Tipos de documento
DOC_TYPES = {
    "bitacora": "Registro de desarrollo",
    "conversacion": "Chat con IA/equipo", 
    "especificacion": "Requisitos/diseño",
    "readme": "Documentación principal",
    "notas": "Apuntes sueltos"
}
```

**UI propuesta:**
```
Proyecto: tgd-viewer-v10
├── 📁 Código (994 archivos)
├── 📄 Documentación
│   ├── README.md (vinculado auto)
│   ├── CHANGELOG.md (vinculado auto)
│   ├── + Añadir documento...
│   └── + Pegar texto (email, notas)
└── 💬 Contexto IA
    ├── Resumen generado
    └── Conversaciones guardadas
```

---

### 13. Resúmenes Automáticos

**Trigger:** Al completar escaneo de proyecto

**Genera:**
- Resumen ejecutivo (1 párrafo)
- Tecnologías detectadas
- Estructura principal
- Puntos de entrada
- Dependencias externas
- Áreas de mejora sugeridas

**Implementación:**
```python
# Usa Ollama solo para esto (bajo demanda)
SUMMARY_PROMPT = """
Analiza este proyecto y genera un resumen ejecutivo:

Archivos: {file_count}
Funciones: {function_count}
Clases: {class_count}
Imports principales: {top_imports}

Estructura:
{tree_structure}

Genera:
1. Resumen (2-3 frases)
2. Propósito principal
3. Tecnologías clave
4. Sugerencias de mejora
"""
```

---

### 14. Dashboard ML Mejorado

**Métricas adicionales:**
- Complejidad ciclomática por archivo
- Deuda técnica estimada
- Cobertura de documentación
- Archivos "calientes" (más modificados)
- Dependencias circulares

---

## 📊 PRIORIDADES SUGERIDAS

### Fase 1 - Estabilidad (1-2 días)
- [x] Escaneo funcional
- [ ] Fix persistencia BD (#1)
- [x] ~~Fix timeout IA (#2)~~ (arreglado - leía archivos en vez de BD)
- [ ] Fix contraste CSS (#5)
- [ ] Merge Wizard multi-lenguaje (#6)

### Fase 2 - UI Polish (2-3 días)
- [ ] Panel IA redimensionable (#3)
- [ ] Líneas alineadas (#4)
- [ ] Breadcrumbs (#7)

### Fase 3 - Embeddings (3-5 días)
- [ ] Integrar sentence-transformers (#10)
- [ ] ChromaDB setup
- [ ] Búsqueda híbrida en UI
- [ ] Indexación automática al escanear

### Fase 4 - Documentación (3-5 días)
- [ ] Detección automática docs (#12)
- [ ] UI vinculación manual
- [ ] Resúmenes automáticos (#13)
- [ ] Pegar texto/emails

### Fase 5 - Optimización
- [ ] Zona intercambio inteligente (#11)
- [ ] Dashboard ML (#14)
- [ ] Exportación de informes

---

## 💡 IDEAS EXTRA (Backlog)

- **Webhooks:** Notificar cuando termine análisis
- **API REST completa:** Para integrar con otros sistemas
- **Comparador visual de código:** Diff lado a lado
- **Timeline de proyecto:** Ver evolución entre versiones
- **Integración Git:** Analizar commits, blame
- **Plugin VSCode:** Lanzar análisis desde el editor
- **Modo offline:** Todo funciona sin conexión
- **Multi-usuario:** Compartir análisis con equipo

---

## 🛠️ STACK TECNOLÓGICO

**Backend:**
- FastAPI (actual)
- SQLite → PostgreSQL (futuro)
- ChromaDB (nuevo)
- sentence-transformers (nuevo)

**Frontend:**
- React (actual)
- TailwindCSS (mejorar)

**IA:**
- Ollama (chat, explicaciones, resúmenes)
- sentence-transformers (embeddings)

**Infraestructura:**
- Docker Compose
- Volúmenes persistentes
- Zona intercambio montada

---

**Documento generado:** 2026-01-23  
**Próxima revisión:** Tras completar Fase 1
