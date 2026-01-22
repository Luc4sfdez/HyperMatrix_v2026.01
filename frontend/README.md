# HyperMatrix UI

Interfaz web moderna para HyperMatrix, construida con React + @tacolu/design-system.

## 🎯 Propósito

Dashboard profesional para analizar proyectos de código, detectar duplicados, clones y código muerto.

## 🏗️ Stack tecnológico

- **Frontend**: React 18 + Vite
- **UI Framework**: @tacolu/design-system (Tailwind CSS)
- **Estilo**: VS Code Design (azul #007ACC, Segoe UI)
- **State**: React Hooks
- **HTTP**: Axios
- **API Backend**: HyperMatrix (FastAPI)

## 📦 Estructura

```
src/
├── App.jsx              # Componente raíz con Layout
├── index.css            # Estilos globales
├── pages/
│   ├── Dashboard.jsx    # Nuevo análisis + últimos
│   ├── ScanResults.jsx  # Resultados detallados
│   ├── Analysis.jsx     # Análisis avanzado
│   └── Settings.jsx     # Configuración
```

## 🚀 Primeros pasos

### 1. Instalar dependencias

Desde la raíz del monorepo:

```bash
pnpm install
```

### 2. Asegurar que HyperMatrix backend está corriendo

```bash
# En otra terminal
python run_web.py --port 26020
```

### 3. Ejecutar HyperMatrix UI

```bash
pnpm -C packages/hypermatrix-ui dev
```

Se abrirá en: **http://localhost:5175**

## 📖 Uso

### Dashboard
- Ingresa la ruta a un proyecto
- HyperMatrix lo analiza
- Ver últimos análisis

### Resultados
- Lista de análisis completados
- Métricas por scan
- Grupos de archivos duplicados
- Fragmentos clonados

### Análisis Avanzado
- Búsqueda natural
- Detección de código muerto
- Análisis de impacto
- Similitud semántica

### Configuración
- URL de API (por defecto: http://127.0.0.1:26020)
- Información del sistema
- Links a documentación

## 🎨 Estética

El proyecto usa componentes del design-system:

- **Button**: Primary, Secondary, Ghost, Danger
- **Card**: Con header, title, content, footer
- **Sidebar**: Navegación jerárquica
- **Layout**: Estructura completa

Todo con tema VS Code (luz/oscuro automático).

## 🔗 Integración con HyperMatrix API

La UI consume estos endpoints:

```
POST   /api/scan/start                    # Iniciar escaneo
GET    /api/scan/list                     # Listar scans
GET    /api/scan/result/{id}/summary      # Resumen
GET    /api/analysis/clones               # Clones
GET    /api/advanced/dead-code            # Código muerto
GET    /api/advanced/natural-search       # Búsqueda natural
```

Configurable en Settings → URL de HyperMatrix API

## 🧪 Testing

En desarrollo, prueba con:

```bash
# Dashboard
- Ingresa: C:/HyperMatrix_v2026
- Nombre: "HyperMatrix Self Analysis"
- Click: Iniciar Análisis

# Resultados
- Ver último scan
- Explorar duplicados/clones
```

## 📝 Notas

- Proxy a HyperMatrix configurado en `vite.config.js`
- Hot reload automático
- Estilos globales en `index.css`
- Componentes del design-system sin duplicación

## 🚀 Próximos pasos

- [ ] Conectar real a endpoints de HyperMatrix
- [ ] Agregar state management (Zustand)
- [ ] Implementar exportación (CSV, JSON)
- [ ] Agregar acciones en lote (consolidar duplicados)
- [ ] Gráficos de dependencias
- [ ] Soporte para múltiples proyectos
