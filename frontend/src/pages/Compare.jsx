import { useState, useCallback, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Selector de archivos desde BD o filesystem
function FileSelector({ hypermatrixUrl, value, onChange, placeholder, label }) {
  const [showModal, setShowModal] = useState(false)
  const [activeTab, setActiveTab] = useState('db')  // 'db' o 'browse'
  const [dbFiles, setDbFiles] = useState([])
  const [loadingDb, setLoadingDb] = useState(false)
  const [browsePath, setBrowsePath] = useState('C:/')
  const [browseItems, setBrowseItems] = useState([])
  const [loadingBrowse, setLoadingBrowse] = useState(false)
  const [searchFilter, setSearchFilter] = useState('')

  // Cargar archivos de BD
  const loadDbFiles = useCallback(async () => {
    setLoadingDb(true)
    try {
      const response = await fetch(`${hypermatrixUrl}/api/db/files?limit=200`)
      if (response.ok) {
        const data = await response.json()
        setDbFiles(data.files || [])
      }
    } catch (err) {
      console.error('Error loading files:', err)
    } finally {
      setLoadingDb(false)
    }
  }, [hypermatrixUrl])

  // Cargar directorio
  const loadDirectory = useCallback(async (path) => {
    setLoadingBrowse(true)
    try {
      const response = await fetch(`${hypermatrixUrl}/api/browse?path=${encodeURIComponent(path)}`)
      if (response.ok) {
        const data = await response.json()
        setBrowsePath(data.path)
        setBrowseItems(data.items || [])
      }
    } catch (err) {
      console.error('Error browsing:', err)
    } finally {
      setLoadingBrowse(false)
    }
  }, [hypermatrixUrl])

  // Abrir modal
  const openModal = () => {
    setShowModal(true)
    if (activeTab === 'db' && dbFiles.length === 0) {
      loadDbFiles()
    } else if (activeTab === 'browse' && browseItems.length === 0) {
      loadDirectory(browsePath)
    }
  }

  // Cambiar tab
  const changeTab = (tab) => {
    setActiveTab(tab)
    if (tab === 'db' && dbFiles.length === 0) {
      loadDbFiles()
    } else if (tab === 'browse' && browseItems.length === 0) {
      loadDirectory(browsePath)
    }
  }

  // Filtrar archivos
  const filteredDbFiles = dbFiles.filter(f =>
    f.filepath.toLowerCase().includes(searchFilter.toLowerCase()) ||
    f.project.toLowerCase().includes(searchFilter.toLowerCase())
  )

  // Navegar a carpeta padre
  const goUp = () => {
    const parts = browsePath.replace(/\\/g, '/').split('/').filter(Boolean)
    if (parts.length > 1) {
      parts.pop()
      const newPath = parts.join('/') || 'C:/'
      loadDirectory(newPath)
    }
  }

  return (
    <div>
      <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
        />
        <Button variant="secondary" onClick={openModal}>
          📂
        </Button>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowModal(false)}>
          <div
            className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
              <h3 className="font-semibold text-[var(--color-fg-primary)]">Seleccionar Archivo</h3>
              <button onClick={() => setShowModal(false)} className="p-1 hover:bg-[var(--color-bg-secondary)] rounded">✕</button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-[var(--color-border)]">
              <button
                onClick={() => changeTab('db')}
                className={`flex-1 py-2 text-sm font-medium ${activeTab === 'db'
                  ? 'text-[var(--color-primary)] border-b-2 border-[var(--color-primary)]'
                  : 'text-[var(--color-fg-secondary)]'}`}
              >
                🗄️ Archivos Analizados
              </button>
              <button
                onClick={() => changeTab('browse')}
                className={`flex-1 py-2 text-sm font-medium ${activeTab === 'browse'
                  ? 'text-[var(--color-primary)] border-b-2 border-[var(--color-primary)]'
                  : 'text-[var(--color-fg-secondary)]'}`}
              >
                📁 Explorar Sistema
              </button>
            </div>

            {/* Search */}
            {activeTab === 'db' && (
              <div className="p-3 border-b border-[var(--color-border)]">
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Filtrar archivos..."
                  className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)]"
                />
              </div>
            )}

            {/* Browse path */}
            {activeTab === 'browse' && (
              <div className="p-3 border-b border-[var(--color-border)] flex items-center gap-2">
                <button onClick={goUp} className="px-2 py-1 bg-[var(--color-bg-secondary)] rounded hover:bg-[var(--color-bg-tertiary)]">⬆️</button>
                <span className="text-sm text-[var(--color-fg-secondary)] truncate">{browsePath}</span>
              </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-2">
              {activeTab === 'db' && (
                loadingDb ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin w-6 h-6 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
                  </div>
                ) : filteredDbFiles.length === 0 ? (
                  <p className="text-center text-[var(--color-fg-tertiary)] py-8">
                    {dbFiles.length === 0 ? 'No hay archivos analizados' : 'No hay resultados'}
                  </p>
                ) : (
                  <div className="space-y-1">
                    {filteredDbFiles.map((file) => (
                      <button
                        key={file.id}
                        onClick={() => { onChange(file.filepath); setShowModal(false) }}
                        className="w-full text-left p-2 hover:bg-[var(--color-bg-secondary)] rounded text-sm group"
                      >
                        <div className="font-mono text-[var(--color-fg-primary)] truncate group-hover:text-[var(--color-primary)]">
                          {file.filepath.split(/[/\\]/).pop()}
                        </div>
                        <div className="text-xs text-[var(--color-fg-tertiary)] truncate">
                          {file.project} • {file.filepath}
                        </div>
                      </button>
                    ))}
                  </div>
                )
              )}

              {activeTab === 'browse' && (
                loadingBrowse ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin w-6 h-6 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {browseItems.map((item, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          if (item.is_dir) {
                            loadDirectory(item.path)
                          } else {
                            onChange(item.path)
                            setShowModal(false)
                          }
                        }}
                        className="w-full text-left p-2 hover:bg-[var(--color-bg-secondary)] rounded text-sm flex items-center gap-2"
                      >
                        <span>{item.is_dir ? '📁' : '📄'}</span>
                        <span className={`truncate ${item.is_dir ? 'text-[var(--color-primary)]' : 'text-[var(--color-fg-primary)]'}`}>
                          {item.name}
                        </span>
                      </button>
                    ))}
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Barra de similitud con gradiente de color
function SimilarityBar({ label, value, description }) {
  const getColor = (v) => {
    if (v >= 0.8) return 'bg-[var(--color-success)]'
    if (v >= 0.5) return 'bg-[var(--color-warning)]'
    return 'bg-[var(--color-error)]'
  }

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-[var(--color-fg-secondary)]">{label}</span>
        <span className="font-bold text-[var(--color-fg-primary)]">
          {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor(value)} transition-all duration-500`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      {description && (
        <p className="text-xs text-[var(--color-fg-tertiary)]">{description}</p>
      )}
    </div>
  )
}

// Panel de código con números de línea
function CodePanel({ title, code, lines, filepath, onScroll, scrollRef }) {
  const codeLines = code?.split('\n') || []

  return (
    <div className="flex-1 min-w-0 border border-[var(--color-border)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)]">
        <h4 className="font-medium text-[var(--color-fg-primary)] truncate">{title}</h4>
        <p className="text-xs text-[var(--color-fg-tertiary)] truncate">{filepath}</p>
        <p className="text-xs text-[var(--color-fg-secondary)]">{lines} líneas</p>
      </div>

      {/* Code */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="h-96 overflow-auto bg-[var(--color-bg-primary)]"
      >
        {code ? (
          <pre className="text-xs font-mono">
            {codeLines.map((line, idx) => (
              <div
                key={idx}
                className="flex hover:bg-[var(--color-bg-secondary)] transition-colors"
              >
                <span className="select-none w-12 flex-shrink-0 text-right pr-3 py-0.5 text-[var(--color-fg-tertiary)] bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)]">
                  {idx + 1}
                </span>
                <code className="flex-1 pl-3 py-0.5 whitespace-pre text-[var(--color-fg-primary)] overflow-x-auto">
                  {line || ' '}
                </code>
              </div>
            ))}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--color-fg-tertiary)]">
            Sin contenido
          </div>
        )}
      </div>
    </div>
  )
}

export default function Compare({ hypermatrixUrl }) {
  const [file1, setFile1] = useState('')
  const [file2, setFile2] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [content1, setContent1] = useState(null)
  const [content2, setContent2] = useState(null)

  // Comparar archivos
  const compare = useCallback(async () => {
    if (!file1.trim() || !file2.trim()) {
      setError('Ingresa las rutas de los dos archivos')
      return
    }

    setLoading(true)
    setError(null)
    setComparison(null)
    setContent1(null)
    setContent2(null)

    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/consolidation/compare?file1=${encodeURIComponent(file1)}&file2=${encodeURIComponent(file2)}`
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setComparison(data)

      // Cargar contenido de los archivos
      setLoadingContent(true)
      try {
        // Intentar cargar contenido via API de análisis de archivo
        const [res1, res2] = await Promise.all([
          fetch(`${hypermatrixUrl}/api/analysis/quality/file?filepath=${encodeURIComponent(file1)}`),
          fetch(`${hypermatrixUrl}/api/analysis/quality/file?filepath=${encodeURIComponent(file2)}`),
        ])

        if (res1.ok) {
          const d1 = await res1.json()
          setContent1(d1.source_code || null)
        }
        if (res2.ok) {
          const d2 = await res2.json()
          setContent2(d2.source_code || null)
        }
      } catch (err) {
        console.error('Error loading file contents:', err)
      } finally {
        setLoadingContent(false)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, file1, file2])

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      compare()
    }
  }

  // Navegar a merge
  const proposeMerge = () => {
    // Redirigir o mostrar modal de merge
    alert(`Proponer merge de:\n${file1}\n${file2}\n\n(Implementar en página de Merge)`)
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          🔀 Comparador Visual
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Compara dos archivos lado a lado con métricas de similitud
        </p>
      </div>

      {/* Inputs */}
      <Card>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FileSelector
              hypermatrixUrl={hypermatrixUrl}
              value={file1}
              onChange={setFile1}
              label="Archivo 1"
              placeholder="Selecciona o escribe la ruta..."
            />
            <FileSelector
              hypermatrixUrl={hypermatrixUrl}
              value={file2}
              onChange={setFile2}
              label="Archivo 2"
              placeholder="Selecciona o escribe la ruta..."
            />
          </div>

          <Button
            variant="primary"
            onClick={compare}
            disabled={loading || !file1.trim() || !file2.trim()}
          >
            {loading ? '⏳ Comparando...' : '🔍 Comparar Archivos'}
          </Button>

          {error && (
            <p className="text-[var(--color-error)] text-sm bg-[var(--color-error)] bg-opacity-10 p-3 rounded">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {comparison && (
        <>
          {/* Métricas de similitud */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>📊 Métricas de Similitud</span>
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                  comparison.affinity.overall >= 0.8
                    ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
                    : comparison.affinity.overall >= 0.5
                      ? 'bg-[var(--color-warning)] bg-opacity-20 text-[var(--color-warning)]'
                      : 'bg-[var(--color-error)] bg-opacity-20 text-[var(--color-error)]'
                }`}>
                  {comparison.affinity.level.toUpperCase()}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <SimilarityBar
                  label="Overall"
                  value={comparison.affinity.overall}
                  description="Similitud combinada"
                />
                <SimilarityBar
                  label="Contenido"
                  value={comparison.affinity.content}
                  description="Similitud del texto"
                />
                <SimilarityBar
                  label="Estructura"
                  value={comparison.affinity.structure}
                  description="Funciones y clases"
                />
                <SimilarityBar
                  label="DNA"
                  value={comparison.affinity.dna}
                  description="Patrones de código"
                />
              </div>

              {/* Info adicional */}
              <div className="mt-4 flex flex-wrap gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`w-3 h-3 rounded-full ${comparison.affinity.hash_match ? 'bg-[var(--color-success)]' : 'bg-[var(--color-fg-tertiary)]'}`}></span>
                  <span className="text-[var(--color-fg-secondary)]">
                    {comparison.affinity.hash_match ? 'Archivos idénticos (mismo hash)' : 'Archivos diferentes'}
                  </span>
                </div>
                <div className="text-[var(--color-fg-secondary)]">
                  <span className="font-mono">{comparison.file1_lines}</span> vs <span className="font-mono">{comparison.file2_lines}</span> líneas
                </div>
              </div>

              {/* Botón proponer merge */}
              {comparison.affinity.overall >= 0.3 && !comparison.affinity.hash_match && (
                <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
                  <Button variant="secondary" onClick={proposeMerge}>
                    🔗 Proponer Merge
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Paneles de código lado a lado */}
          <Card>
            <CardHeader>
              <CardTitle>📄 Código Lado a Lado</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingContent ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
                </div>
              ) : (
                <div className="flex gap-4">
                  <CodePanel
                    title="Archivo 1"
                    filepath={comparison.file1}
                    lines={comparison.file1_lines}
                    code={content1}
                  />
                  <CodePanel
                    title="Archivo 2"
                    filepath={comparison.file2}
                    lines={comparison.file2_lines}
                    code={content2}
                  />
                </div>
              )}
              {!content1 && !content2 && !loadingContent && (
                <p className="text-center text-[var(--color-fg-tertiary)] py-4">
                  No se pudo cargar el contenido de los archivos.
                  Las métricas de similitud están calculadas correctamente.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
