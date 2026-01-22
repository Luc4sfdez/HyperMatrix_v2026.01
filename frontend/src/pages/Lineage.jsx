import { useState, useCallback, useEffect, useRef } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Nodo del grafo de dependencias
function DependencyNode({ file, type, depth, isCircular, onClick, isSelected }) {
  const getTypeColor = () => {
    if (isCircular) return 'border-[var(--color-error)]'
    switch (type) {
      case 'center': return 'border-[var(--color-primary)] bg-[var(--color-primary)] bg-opacity-10'
      case 'import': return 'border-[var(--color-success)]'
      case 'imported_by': return 'border-[var(--color-warning)]'
      case 'external': return 'border-[var(--color-fg-tertiary)]'
      default: return 'border-[var(--color-border)]'
    }
  }

  const getTypeIcon = () => {
    if (isCircular) return '🔄'
    switch (type) {
      case 'center': return '📍'
      case 'import': return '📥'
      case 'imported_by': return '📤'
      case 'external': return '📦'
      default: return '📄'
    }
  }

  const filename = file.split('/').pop() || file.split('\\').pop() || file

  return (
    <div
      onClick={onClick}
      className={`
        p-3 rounded-lg border-2 cursor-pointer transition-all
        hover:shadow-md hover:scale-102
        ${getTypeColor()}
        ${isSelected ? 'ring-2 ring-[var(--color-primary)] ring-offset-2' : ''}
        bg-[var(--color-bg-secondary)]
      `}
      style={{ marginLeft: `${depth * 20}px` }}
    >
      <div className="flex items-center gap-2">
        <span>{getTypeIcon()}</span>
        <span className="font-mono text-sm text-[var(--color-fg-primary)] truncate max-w-[200px]" title={file}>
          {filename}
        </span>
      </div>
      {isCircular && (
        <span className="text-xs text-[var(--color-error)] mt-1 block">Circular</span>
      )}
    </div>
  )
}

// Panel lateral con detalles
function DetailPanel({ data, onClose }) {
  if (!data) return null

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-[var(--color-bg-primary)] border-l border-[var(--color-border)] shadow-xl z-50 overflow-auto">
      <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <h3 className="font-bold text-[var(--color-fg-primary)]">Detalles</h3>
        <button
          onClick={onClose}
          className="p-2 hover:bg-[var(--color-bg-secondary)] rounded"
        >
          ✕
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <label className="text-xs text-[var(--color-fg-tertiary)]">Archivo</label>
          <p className="font-mono text-sm text-[var(--color-fg-primary)] break-all">{data.filepath}</p>
        </div>

        {data.coupling_score !== undefined && (
          <div>
            <label className="text-xs text-[var(--color-fg-tertiary)]">Acoplamiento</label>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
                <div
                  className={`h-full ${
                    data.coupling_score > 0.7 ? 'bg-[var(--color-error)]' :
                    data.coupling_score > 0.4 ? 'bg-[var(--color-warning)]' :
                    'bg-[var(--color-success)]'
                  }`}
                  style={{ width: `${data.coupling_score * 100}%` }}
                />
              </div>
              <span className="text-sm font-mono">{(data.coupling_score * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}

        {data.depth_from_root !== undefined && (
          <div>
            <label className="text-xs text-[var(--color-fg-tertiary)]">Profundidad</label>
            <p className="text-[var(--color-fg-primary)]">{data.depth_from_root} niveles desde raíz</p>
          </div>
        )}

        <div>
          <label className="text-xs text-[var(--color-fg-tertiary)]">Importa ({data.imports?.length || 0})</label>
          <ul className="mt-1 space-y-1 max-h-40 overflow-auto">
            {(data.imports || []).map((imp, idx) => (
              <li key={idx} className="text-sm font-mono text-[var(--color-fg-secondary)] flex items-center gap-2">
                <span className="text-[var(--color-success)]">→</span> {imp}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <label className="text-xs text-[var(--color-fg-tertiary)]">Importado por ({data.imported_by?.length || 0})</label>
          <ul className="mt-1 space-y-1 max-h-40 overflow-auto">
            {(data.imported_by || []).map((imp, idx) => (
              <li key={idx} className="text-sm font-mono text-[var(--color-fg-secondary)] flex items-center gap-2">
                <span className="text-[var(--color-warning)]">←</span> {imp}
              </li>
            ))}
          </ul>
        </div>

        {data.circular_dependencies?.length > 0 && (
          <div className="p-3 bg-[var(--color-error)] bg-opacity-10 rounded border border-[var(--color-error)] border-opacity-30">
            <label className="text-xs text-[var(--color-error)] font-medium">⚠️ Dependencias Circulares</label>
            <ul className="mt-1 space-y-1">
              {data.circular_dependencies.map((circ, idx) => (
                <li key={idx} className="text-sm font-mono text-[var(--color-error)]">
                  {circ}
                </li>
              ))}
            </ul>
          </div>
        )}

        {data.external_dependencies?.length > 0 && (
          <div>
            <label className="text-xs text-[var(--color-fg-tertiary)]">Dependencias Externas</label>
            <div className="flex flex-wrap gap-1 mt-1">
              {data.external_dependencies.map((ext, idx) => (
                <span key={idx} className="px-2 py-0.5 bg-[var(--color-bg-tertiary)] rounded text-xs font-mono">
                  {ext}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Lineage({ hypermatrixUrl, ai }) {
  const [scanId, setScanId] = useState('')
  const [availableScans, setAvailableScans] = useState([])
  const [selectedFile, setSelectedFile] = useState('')
  const [availableFiles, setAvailableFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [graphData, setGraphData] = useState(null)
  const [detailData, setDetailData] = useState(null)
  const [viewMode, setViewMode] = useState('tree') // 'tree' or 'radial'

  // Analizar linaje con IA
  const analyzeWithAI = useCallback(() => {
    if (!ai || !graphData) return

    const analysisText = `# Análisis de Dependencias

## Archivo Central
${graphData.filepath}

## Métricas
- **Acoplamiento**: ${graphData.coupling_score?.toFixed(2) || 'N/A'}
- **Profundidad desde raíz**: ${graphData.depth_from_root || 'N/A'}

## Importa (${graphData.imports?.length || 0} dependencias)
${graphData.imports?.map(i => `- ${i}`).join('\n') || 'Ninguna'}

## Importado por (${graphData.imported_by?.length || 0} archivos)
${graphData.imported_by?.map(i => `- ${i}`).join('\n') || 'Ninguno'}

## Dependencias Externas
${graphData.external_dependencies?.map(e => `- ${e}`).join('\n') || 'Ninguna'}

${graphData.circular_dependencies?.length > 0 ? `## ⚠️ Dependencias Circulares\n${graphData.circular_dependencies.map(c => `- ${c}`).join('\n')}` : ''}

Por favor, analiza este grafo de dependencias y recomienda:
1. Si hay problemas de acoplamiento alto
2. Cómo mejorar la arquitectura
3. Si las dependencias circulares (si existen) son problemáticas
4. Sugerencias de refactorización`

    ai?.openForReview?.(analysisText, `Linaje: ${graphData.filepath.split(/[/\\]/).pop()}`)
  }, [ai, graphData])

  // Cargar scans disponibles
  useEffect(() => {
    const loadScans = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        if (response.ok) {
          const data = await response.json()
          setAvailableScans(data.scans || [])
        }
      } catch (err) {
        console.error('Error loading scans:', err)
      }
    }
    loadScans()
  }, [hypermatrixUrl])

  // Cargar archivos cuando se selecciona un scan
  useEffect(() => {
    if (!scanId) {
      setAvailableFiles([])
      return
    }

    const loadFiles = async () => {
      try {
        // First try the summary endpoint
        const response = await fetch(`${hypermatrixUrl}/api/scan/result/${scanId}/summary`)
        if (response.ok) {
          const data = await response.json()
          // sibling_groups can be a number or an array
          if (Array.isArray(data.sibling_groups)) {
            const files = data.sibling_groups.map(g => g.filename)
            setAvailableFiles(files)
            return
          }
        }

        // Fallback: load from consolidation siblings endpoint
        const siblingsResponse = await fetch(`${hypermatrixUrl}/api/consolidation/siblings/${scanId}?limit=200`)
        if (siblingsResponse.ok) {
          const siblingsData = await siblingsResponse.json()
          const files = (siblingsData.groups || []).map(g => g.filename)
          setAvailableFiles(files)
        }
      } catch (err) {
        console.error('Error loading files:', err)
      }
    }
    loadFiles()
  }, [hypermatrixUrl, scanId])

  // Cargar grafo de dependencias
  const loadGraph = useCallback(async () => {
    if (!scanId || !selectedFile) {
      setError('Selecciona un scan y un archivo')
      return
    }

    setLoading(true)
    setError(null)
    setGraphData(null)

    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/analysis/dependencies/${scanId}/${encodeURIComponent(selectedFile)}`
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setGraphData(data)
      setDetailData(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, scanId, selectedFile])

  // Expandir nodo (cargar dependencias de otro archivo)
  const expandNode = useCallback(async (filepath) => {
    try {
      // Intentar cargar dependencias directamente por filepath
      const response = await fetch(
        `${hypermatrixUrl}/api/analysis/dependencies/${scanId}/${encodeURIComponent(filepath.split('/').pop() || filepath.split('\\').pop())}`
      )

      if (response.ok) {
        const data = await response.json()
        setDetailData(data)
      }
    } catch (err) {
      console.error('Error expanding node:', err)
    }
  }, [hypermatrixUrl, scanId])

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          🔗 Grafo de Linaje
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Visualiza las dependencias y relaciones entre archivos
        </p>
      </div>

      {/* Selectores */}
      <Card>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Scan
              </label>
              <select
                value={scanId}
                onChange={(e) => {
                  setScanId(e.target.value)
                  setSelectedFile('')
                  setGraphData(null)
                }}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              >
                <option value="">Seleccionar proyecto...</option>
                {availableScans.filter(s => s.files > 0).map(scan => (
                  <option key={scan.scan_id} value={scan.scan_id}>
                    {scan.project || scan.scan_id} ({scan.files} archivos)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Archivo Central
              </label>
              <select
                value={selectedFile}
                onChange={(e) => setSelectedFile(e.target.value)}
                disabled={!scanId}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
              >
                <option value="">Seleccionar archivo...</option>
                {availableFiles.map(file => (
                  <option key={file} value={file}>
                    {file}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={loadGraph}
              disabled={loading || !scanId || !selectedFile}
            >
              {loading ? '⏳ Cargando...' : '🔍 Cargar Grafo'}
            </Button>

            {graphData && (
              <div className="flex gap-2 ml-auto">
                {ai && (
                  <Button variant="secondary" onClick={analyzeWithAI}>
                    🤖 Analizar con IA
                  </Button>
                )}
                <button
                  onClick={() => setViewMode('tree')}
                  className={`px-3 py-2 rounded text-sm transition-colors ${
                    viewMode === 'tree'
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)]'
                  }`}
                >
                  🌲 Árbol
                </button>
                <button
                  onClick={() => setViewMode('radial')}
                  className={`px-3 py-2 rounded text-sm transition-colors ${
                    viewMode === 'radial'
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)]'
                  }`}
                >
                  ⭕ Radial
                </button>
              </div>
            )}
          </div>

          {error && (
            <p className="text-[var(--color-error)] text-sm bg-[var(--color-error)] bg-opacity-10 p-3 rounded">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Leyenda */}
      {graphData && (
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2 border-[var(--color-primary)] bg-[var(--color-primary)] bg-opacity-10"></div>
            <span className="text-[var(--color-fg-secondary)]">Archivo Central</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2 border-[var(--color-success)]"></div>
            <span className="text-[var(--color-fg-secondary)]">Importa (dependencias)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2 border-[var(--color-warning)]"></div>
            <span className="text-[var(--color-fg-secondary)]">Importado por</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2 border-[var(--color-error)]"></div>
            <span className="text-[var(--color-fg-secondary)]">Circular</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2 border-[var(--color-fg-tertiary)]"></div>
            <span className="text-[var(--color-fg-secondary)]">Externa</span>
          </div>
        </div>
      )}

      {/* Visualización del grafo */}
      {graphData && viewMode === 'tree' && (
        <Card>
          <CardHeader>
            <CardTitle>🌲 Vista de Árbol</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {/* Imported By (arriba) */}
              {graphData.imported_by?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-[var(--color-fg-secondary)] mb-3">
                    📤 Importado por ({graphData.imported_by.length})
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {graphData.imported_by.map((file, idx) => (
                      <DependencyNode
                        key={idx}
                        file={file}
                        type="imported_by"
                        depth={0}
                        onClick={() => expandNode(file)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Conector visual */}
              {graphData.imported_by?.length > 0 && (
                <div className="flex justify-center">
                  <div className="w-0.5 h-8 bg-[var(--color-border)]"></div>
                </div>
              )}

              {/* Archivo central */}
              <div className="flex justify-center">
                <div className="w-full max-w-md">
                  <DependencyNode
                    file={graphData.filepath}
                    type="center"
                    depth={0}
                    isSelected={true}
                    onClick={() => setDetailData(graphData)}
                  />
                </div>
              </div>

              {/* Conector visual */}
              {graphData.imports?.length > 0 && (
                <div className="flex justify-center">
                  <div className="w-0.5 h-8 bg-[var(--color-border)]"></div>
                </div>
              )}

              {/* Imports (abajo) */}
              {graphData.imports?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-[var(--color-fg-secondary)] mb-3">
                    📥 Importa ({graphData.imports.length})
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {graphData.imports.map((file, idx) => (
                      <DependencyNode
                        key={idx}
                        file={file}
                        type="import"
                        depth={0}
                        isCircular={graphData.circular_dependencies?.includes(file)}
                        onClick={() => expandNode(file)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Dependencias externas */}
              {graphData.external_dependencies?.length > 0 && (
                <div className="pt-4 border-t border-[var(--color-border)]">
                  <h4 className="text-sm font-medium text-[var(--color-fg-secondary)] mb-3">
                    📦 Dependencias Externas ({graphData.external_dependencies.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {graphData.external_dependencies.map((dep, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-[var(--color-bg-tertiary)] rounded-full text-sm font-mono text-[var(--color-fg-secondary)]"
                      >
                        {dep}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Vista radial */}
      {graphData && viewMode === 'radial' && (
        <Card>
          <CardHeader>
            <CardTitle>⭕ Vista Radial</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative min-h-[500px] flex items-center justify-center">
              {/* Centro */}
              <div className="absolute z-10">
                <DependencyNode
                  file={graphData.filepath}
                  type="center"
                  depth={0}
                  isSelected={true}
                  onClick={() => setDetailData(graphData)}
                />
              </div>

              {/* Anillo de imports */}
              {graphData.imports?.map((file, idx) => {
                const total = graphData.imports.length
                const angle = (idx / total) * 2 * Math.PI - Math.PI / 2
                const radius = 180
                const x = Math.cos(angle) * radius
                const y = Math.sin(angle) * radius

                return (
                  <div
                    key={`import-${idx}`}
                    className="absolute"
                    style={{
                      transform: `translate(${x}px, ${y}px)`,
                    }}
                  >
                    <DependencyNode
                      file={file}
                      type="import"
                      depth={0}
                      isCircular={graphData.circular_dependencies?.includes(file)}
                      onClick={() => expandNode(file)}
                    />
                  </div>
                )
              })}

              {/* Anillo de imported_by */}
              {graphData.imported_by?.map((file, idx) => {
                const total = graphData.imported_by.length
                const angle = (idx / total) * 2 * Math.PI - Math.PI / 2
                const radius = 320
                const x = Math.cos(angle) * radius
                const y = Math.sin(angle) * radius

                return (
                  <div
                    key={`imported-${idx}`}
                    className="absolute"
                    style={{
                      transform: `translate(${x}px, ${y}px)`,
                    }}
                  >
                    <DependencyNode
                      file={file}
                      type="imported_by"
                      depth={0}
                      onClick={() => expandNode(file)}
                    />
                  </div>
                )
              })}
            </div>

            {/* Dependencias externas debajo */}
            {graphData.external_dependencies?.length > 0 && (
              <div className="pt-4 border-t border-[var(--color-border)] mt-4">
                <h4 className="text-sm font-medium text-[var(--color-fg-secondary)] mb-3">
                  📦 Dependencias Externas
                </h4>
                <div className="flex flex-wrap gap-2">
                  {graphData.external_dependencies.map((dep, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-[var(--color-bg-tertiary)] rounded-full text-sm font-mono text-[var(--color-fg-secondary)]"
                    >
                      {dep}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Estadísticas */}
      {graphData && (
        <Card>
          <CardHeader>
            <CardTitle>📊 Estadísticas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-success)]">
                  {graphData.imports?.length || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Importa</div>
              </div>
              <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-warning)]">
                  {graphData.imported_by?.length || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Importado por</div>
              </div>
              <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-fg-tertiary)]">
                  {graphData.external_dependencies?.length || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Externas</div>
              </div>
              <div className={`text-center p-4 rounded-lg ${
                graphData.circular_dependencies?.length > 0
                  ? 'bg-[var(--color-error)] bg-opacity-10'
                  : 'bg-[var(--color-bg-secondary)]'
              }`}>
                <div className={`text-3xl font-bold ${
                  graphData.circular_dependencies?.length > 0
                    ? 'text-[var(--color-error)]'
                    : 'text-[var(--color-fg-primary)]'
                }`}>
                  {graphData.circular_dependencies?.length || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Circulares</div>
              </div>
            </div>

            {graphData.coupling_score !== undefined && (
              <div className="mt-4 p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-[var(--color-fg-secondary)]">Score de Acoplamiento</span>
                  <span className={`font-bold ${
                    graphData.coupling_score > 0.7 ? 'text-[var(--color-error)]' :
                    graphData.coupling_score > 0.4 ? 'text-[var(--color-warning)]' :
                    'text-[var(--color-success)]'
                  }`}>
                    {(graphData.coupling_score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      graphData.coupling_score > 0.7 ? 'bg-[var(--color-error)]' :
                      graphData.coupling_score > 0.4 ? 'bg-[var(--color-warning)]' :
                      'bg-[var(--color-success)]'
                    }`}
                    style={{ width: `${graphData.coupling_score * 100}%` }}
                  />
                </div>
                <p className="text-xs text-[var(--color-fg-tertiary)] mt-2">
                  {graphData.coupling_score > 0.7
                    ? 'Alto acoplamiento - considerar refactorización'
                    : graphData.coupling_score > 0.4
                      ? 'Acoplamiento moderado'
                      : 'Bajo acoplamiento - buena modularidad'}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!graphData && !loading && (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🔗</div>
              <h3 className="text-xl font-medium text-[var(--color-fg-primary)] mb-2">
                Visualiza el Linaje
              </h3>
              <p className="text-[var(--color-fg-secondary)] max-w-md mx-auto">
                Selecciona un scan y un archivo para ver sus dependencias.
                Podrás explorar qué archivos importa y cuáles lo importan.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Panel de detalles */}
      <DetailPanel data={detailData} onClose={() => setDetailData(null)} />
    </div>
  )
}
