# HyperMatrix v2026 - Guia de Usuario

## Introduccion

HyperMatrix es una herramienta de analisis de codigo que detecta, compara y consolida archivos duplicados o similares en proyectos de software.

---

## Iniciar la Aplicacion

```bash
cd E:\HyperMatrix_v2026
python run_web.py --port 26020
```

Acceder a: **http://127.0.0.1:26020**

---

## Interfaz de Usuario

La interfaz sigue el estilo Visual Studio Code con las siguientes areas:

```
+------------------+------------------------+
|    Title Bar     |   HyperMatrix v2026    |
+------+-----------+------------------------+
|      |           |                        |
| Act. | Sidebar   |     Editor Area        |
| Bar  |           |                        |
|      |           |                        |
+------+-----------+------------------------+
|           Status Bar                      |
+-------------------------------------------+
```

### Activity Bar (Barra Lateral Izquierda)

| Icono | Funcion | Descripcion |
|-------|---------|-------------|
| Lupa | Scan | Iniciar nuevo escaneo |
| Documento | Results | Ver resultados del analisis |
| Barras | Compare | Comparar dos archivos |
| Engranaje | Settings | Configurar reglas |
| ? | API Docs | Documentacion de la API |

### Sidebar (Panel Lateral)

Muestra informacion contextual segun la vista activa:
- **Scan**: Escaneos recientes
- **Results**: Lista de grupos de hermanos
- **Settings**: Presets de configuracion

### Editor Area (Area Principal)

Contenido principal donde se realizan las acciones.

### Status Bar (Barra Inferior)

Muestra el estado actual del sistema y la conexion con la API.

---

## Funcionalidades

### 1. Escanear un Proyecto

1. Hacer clic en el icono de **Lupa** en la Activity Bar
2. Completar el formulario:
   - **Path to analyze**: Ruta del proyecto (ej: `E:\MiProyecto`)
   - **Project name**: Nombre identificativo
   - **Opciones**:
     - Include archives: Analizar ZIP/TAR
     - Detect duplicates: Buscar archivos identicos
     - Calculate similarities: Calcular afinidad entre archivos
3. Clic en **Start Scan**

El progreso se muestra en tiempo real con las fases:
- Discovery: Descubrimiento de archivos
- Deduplication: Deteccion de duplicados
- Analysis: Analisis de codigo
- Consolidation: Calculo de similitudes

### 2. Ver Resultados

1. Hacer clic en el icono de **Documento** en la Activity Bar
2. Ver estadisticas:
   - **Files**: Total de archivos analizados
   - **Functions**: Funciones detectadas
   - **Classes**: Clases detectadas
   - **Siblings**: Grupos de archivos hermanos

3. Usar filtros:
   - Buscar por nombre de archivo
   - Filtrar por nivel de afinidad (>90%, 70-90%, etc.)

4. Hacer clic en un grupo para ver detalles

### 3. Comparar Archivos

1. Hacer clic en el icono de **Barras** en la Activity Bar
2. Ingresar las rutas de dos archivos
3. Clic en **Compare**
4. Ver resultados:
   - Porcentaje de similitud total
   - Desglose: Contenido, Estructura, DNA

### 4. Configurar Reglas

1. Hacer clic en el icono de **Engranaje** en la Activity Bar
2. Ajustar configuracion:
   - **Minimum affinity threshold**: Umbral minimo para considerar similitud
   - **Conflict resolution**: Como resolver conflictos (keep_largest, keep_complex, etc.)
   - **Prefer paths**: Rutas prioritarias para seleccionar maestro
   - **Never master from**: Rutas que nunca deben ser maestro
   - **Ignore patterns**: Patrones a ignorar

3. Usar **Presets** para configuracion rapida:
   - Conservative: Configuracion segura
   - Aggressive: Detectar mas similitudes
   - Prioritize src/: Preferir archivos en src/

### 5. Exportar Resultados

1. En la vista de Results, clic en **Export**
2. Seleccionar formato:
   - **JSON**: Para integracion con otras herramientas
   - **CSV**: Para analisis en Excel
   - **Markdown**: Para documentacion

### 6. Acciones en Lote

1. En la vista de Results, clic en **Batch Actions**
2. Seleccionar grupos a procesar
3. Elegir accion para cada grupo:
   - Merge: Fusionar en archivo maestro
   - Keep master: Conservar solo el maestro
   - Ignore: No hacer nada
4. Activar **Simulacion** para ver preview sin cambios reales
5. Clic en **Execute**

---

## API REST

Documentacion completa disponible en: **http://127.0.0.1:26020/api/docs**

### Endpoints Principales

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | /api/scan/start | Iniciar escaneo |
| GET | /api/scan/status/{id} | Estado del escaneo |
| GET | /api/scan/result/{id}/summary | Resumen de resultados |
| GET | /api/scan/list | Listar escaneos |
| GET | /api/export/{id}/{format} | Exportar resultados |
| GET | /api/rules | Obtener reglas |
| POST | /api/rules | Guardar reglas |

### Ejemplo: Iniciar Escaneo via API

```bash
curl -X POST http://127.0.0.1:26020/api/scan/start \
  -H "Content-Type: application/json" \
  -d '{
    "path": "E:/MiProyecto",
    "project_name": "mi-proyecto",
    "detect_duplicates": true,
    "calculate_similarities": true
  }'
```

### Ejemplo: Obtener Resumen

```bash
curl http://127.0.0.1:26020/api/scan/result/{scan_id}/summary
```

---

## Conceptos Clave

### Archivos Hermanos (Siblings)

Archivos con el mismo nombre pero en rutas diferentes. Ejemplo:
- `src/utils.py`
- `backup/utils.py`
- `old/utils.py`

### Afinidad

Porcentaje de similitud entre archivos, calculado mediante:
- **Contenido**: Comparacion de texto
- **Estructura**: Comparacion de AST (funciones, clases)
- **DNA**: Firma unica del archivo

### Archivo Maestro

El archivo propuesto como "version principal" basado en:
- Complejidad del codigo
- Ubicacion (preferencia por src/)
- Calidad (docstrings, typing, tests)

---

## Atajos de Teclado

| Atajo | Accion |
|-------|--------|
| Ctrl+1 | Ir a Scan |
| Ctrl+2 | Ir a Results |
| Ctrl+3 | Ir a Compare |
| Ctrl+4 | Ir a Settings |

---

## Solucion de Problemas

### El servidor no inicia

```bash
# Verificar si el puerto esta en uso
netstat -ano | findstr 26020

# Si hay proceso, matarlo
taskkill /F /PID {pid}
```

### Error "Path not found"

Verificar que la ruta existe y es accesible. Usar barras `/` o `\\`.

### Escaneo muy lento

- Reducir el tamaño del directorio a analizar
- Desactivar "Calculate similarities" para escaneo rapido
- Excluir carpetas grandes en "Ignore patterns" (node_modules, .git)

---

## Proximas Funcionalidades

- [ ] Tema claro/oscuro
- [ ] Extension VSCode
- [ ] Integracion CI/CD
- [ ] Comparador visual lado a lado

---

## Soporte

- API Docs: http://127.0.0.1:26020/api/docs
- GitHub: https://github.com/Luc4sfdez/HyperMatrix_v2026
