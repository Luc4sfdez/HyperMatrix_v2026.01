import { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Colores de confianza
const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) return 'bg-[var(--color-error)]'
  if (confidence >= 0.5) return 'bg-[var(--color-warning)]'
  return 'bg-[var(--color-fg-tertiary)]'
}

const getConfidenceLabel = (confidence) => {
  if (confidence >= 0.8) return 'Alta'
  if (confidence >= 0.5) return 'Media'
  return 'Baja'
}

// Componente de item de código muerto
function DeadCodeItem({ item, type }) {
  const [expanded, setExpanded] = useState(false)

  const getIcon = () => {
    switch (type) {
      case 'function': return '⚡'
      case 'class': return '📦'
      case 'import': return '📥'
      case 'variable': return '📝'
      default: return '💀'
    }
  }

  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 text-left hover:bg-[var(--color-bg-secondary)] flex items-center gap-3"
      >
        <span className="text-lg">{getIcon()}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono font-medium text-[var(--color-fg-primary)]">
              {item.name}
            </span>
            {item.confidence !== undefined && (
              <span className={`px-2 py-0.5 text-xs text-white rounded ${getConfidenceColor(item.confidence)}`}>
                {getConfidenceLabel(item.confidence)} ({(item.confidence * 100).toFixed(0)}%)
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--color-fg-tertiary)] truncate">
            {item.file}:{item.line}
          </p>
        </div>
        <span className="text-[var(--color-fg-tertiary)]">
          {expanded ? '▼' : '▶'}
        </span>
      </button>

      {expanded && (
        <div className="px-4 py-3 bg-[var(--color-bg-secondary)] border-t border-[var(--color-border)] space-y-2">
          <div className="text-sm">
            <span className="text-[var(--color-fg-secondary)]">Archivo: </span>
            <code className="text-[var(--color-fg-primary)] break-all">{item.file}</code>
          </div>
          <div className="text-sm">
            <span className="text-[var(--color-fg-secondary)]">Línea: </span>
            <span className="text-[var(--color-fg-primary)]">{item.line}</span>
          </div>
          {item.reason && (
            <div className="text-sm">
              <span className="text-[var(--color-fg-secondary)]">Razón: </span>
              <span className="text-[var(--color-fg-primary)]">{item.reason}</span>
            </div>
          )}
          {item.suggestion && (
            <div className="p-2 bg-[var(--color-success)] bg-opacity-10 border border-[var(--color-success)] border-opacity-30 rounded text-sm">
              <span className="text-[var(--color-success)] font-medium">Sugerencia: </span>
              <span className="text-[var(--color-fg-primary)]">{item.suggestion}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Sección de items
function DeadCodeSection({ title, icon, items, type, emptyMessage }) {
  const [showAll, setShowAll] = useState(false)
  const displayItems = showAll ? items : items.slice(0, 5)

  if (items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {icon} {title}
            <span className="text-sm font-normal text-[var(--color-success)]">(0)</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-[var(--color-fg-secondary)] py-4">
            {emptyMessage || 'No se encontraron elementos'}
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {icon} {title}
          <span className="text-sm font-normal text-[var(--color-error)]">({items.length})</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {displayItems.map((item, idx) => (
          <DeadCodeItem key={idx} item={item} type={type} />
        ))}
        {items.length > 5 && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="w-full py-2 text-center text-sm text-[var(--color-primary)] hover:underline"
          >
            {showAll ? 'Mostrar menos' : `Ver ${items.length - 5} más`}
          </button>
        )}
      </CardContent>
    </Card>
  )
}

export default function DeadCode({ hypermatrixUrl }) {
  const [scans, setScans] = useState([])
  const [selectedScan, setSelectedScan] = useState('')
  const [directoryPath, setDirectoryPath] = useState('')
  const [inputMode, setInputMode] = useState('scan') // 'scan' or 'directory'
  const [loading, setLoading] = useState(false)
  const [loadingScans, setLoadingScans] = useState(true)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  // Cargar lista de scans
  useEffect(() => {
    const loadScans = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        if (response.ok) {
          const data = await response.json()
          setScans(data.scans || [])
        }
      } catch (err) {
        console.error('Error cargando scans:', err)
      } finally {
        setLoadingScans(false)
      }
    }
    loadScans()
  }, [hypermatrixUrl])

  // Analizar código muerto
  const analyze = useCallback(async () => {
    setLoading(true)
    setError(null)
    setResults(null)

    try {
      let files = []

      if (inputMode === 'scan' && selectedScan) {
        // Intentar obtener archivos del scan
        try {
          const scanRes = await fetch(`${hypermatrixUrl}/api/scan/result/${selectedScan}`)
          if (scanRes.ok) {
            const scanData = await scanRes.json()
            // Extraer archivos Python del resultado
            if (scanData.files) {
              files = scanData.files
                .filter(f => f.filepath?.endsWith('.py'))
                .map(f => f.filepath)
            } else if (scanData.analysis) {
              files = Object.keys(scanData.analysis).filter(f => f.endsWith('.py'))
            }
          }
        } catch (e) {
          console.log('Scan result not available, trying DB endpoint')
        }

        // Fallback: cargar desde endpoint de BD
        if (files.length === 0) {
          const dbRes = await fetch(`${hypermatrixUrl}/api/db/files/${selectedScan}/python?limit=500`)
          if (dbRes.ok) {
            const dbData = await dbRes.json()
            files = (dbData.files || []).map(f => f.filepath)
          }
        }
      } else if (inputMode === 'directory' && directoryPath) {
        // Por ahora usar el directorio directamente (el backend puede expandirlo)
        files = [directoryPath]
      }

      if (files.length === 0) {
        throw new Error('No se encontraron archivos Python para analizar')
      }

      // Llamar al endpoint de dead code
      const response = await fetch(
        `${hypermatrixUrl}/api/advanced/dead-code/analyze?${files.map(f => `files=${encodeURIComponent(f)}`).join('&')}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, inputMode, selectedScan, directoryPath])

  // Calcular totales
  const getTotals = () => {
    if (!results) return { total: 0, highConfidence: 0 }

    const allItems = [
      ...(results.dead_functions || []),
      ...(results.dead_classes || []),
      ...(results.dead_imports || []),
      ...(results.dead_variables || []),
    ]

    return {
      total: allItems.length,
      highConfidence: allItems.filter(i => (i.confidence || 0) >= 0.8).length,
    }
  }

  const totals = getTotals()

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          💀 Detector de Código Muerto
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Encuentra funciones, clases, imports y variables no utilizadas
        </p>
      </div>

      {/* Selector de fuente */}
      <Card>
        <CardHeader>
          <CardTitle>📁 Seleccionar archivos a analizar</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Tabs de modo */}
          <div className="flex gap-2">
            <button
              onClick={() => setInputMode('scan')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                inputMode === 'scan'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              Desde Scan Existente
            </button>
            <button
              onClick={() => setInputMode('directory')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                inputMode === 'directory'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              Directorio
            </button>
          </div>

          {inputMode === 'scan' ? (
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Seleccionar análisis
              </label>
              {loadingScans ? (
                <p className="text-[var(--color-fg-secondary)]">Cargando...</p>
              ) : scans.length === 0 ? (
                <p className="text-[var(--color-fg-secondary)]">
                  No hay análisis disponibles. Ejecuta un scan primero.
                </p>
              ) : (
                <select
                  value={selectedScan}
                  onChange={(e) => setSelectedScan(e.target.value)}
                  className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Seleccionar...</option>
                  {scans.filter(s => s.files > 0).map((scan) => (
                    <option key={scan.scan_id} value={scan.scan_id}>
                      {scan.project || scan.project_name || scan.scan_id} ({scan.files || 0} archivos)
                    </option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Ruta del directorio
              </label>
              <input
                type="text"
                value={directoryPath}
                onChange={(e) => setDirectoryPath(e.target.value)}
                placeholder="ej: C:/proyectos/mi-app/src"
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          )}

          <Button
            variant="primary"
            onClick={analyze}
            disabled={loading || (inputMode === 'scan' ? !selectedScan : !directoryPath)}
          >
            {loading ? '⏳ Analizando...' : '🔍 Analizar Código Muerto'}
          </Button>

          {error && (
            <p className="text-[var(--color-error)] text-sm bg-[var(--color-error)] bg-opacity-10 p-3 rounded">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Resultados */}
      {results && (
        <>
          {/* Resumen */}
          <Card>
            <CardHeader>
              <CardTitle>📊 Resumen del Análisis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-primary)]">
                    {results.files_analyzed}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Archivos analizados</div>
                </div>
                <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                    {results.total_definitions || 0}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Definiciones totales</div>
                </div>
                <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-error)]">
                    {totals.total}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Código muerto detectado</div>
                </div>
                <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-warning)]">
                    {results.potential_savings_lines || 0}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Líneas a eliminar</div>
                </div>
              </div>

              {results.summary && (
                <p className="mt-4 text-[var(--color-fg-secondary)] text-sm bg-[var(--color-bg-secondary)] p-3 rounded">
                  {results.summary}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Secciones por tipo */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DeadCodeSection
              title="Funciones no utilizadas"
              icon="⚡"
              items={results.dead_functions || []}
              type="function"
              emptyMessage="No se detectaron funciones sin uso"
            />
            <DeadCodeSection
              title="Clases no utilizadas"
              icon="📦"
              items={results.dead_classes || []}
              type="class"
              emptyMessage="No se detectaron clases sin uso"
            />
            <DeadCodeSection
              title="Imports no utilizados"
              icon="📥"
              items={results.dead_imports || []}
              type="import"
              emptyMessage="No se detectaron imports sin uso"
            />
            <DeadCodeSection
              title="Variables no utilizadas"
              icon="📝"
              items={results.dead_variables || []}
              type="variable"
              emptyMessage="No se detectaron variables sin uso"
            />
          </div>
        </>
      )}
    </div>
  )
}
