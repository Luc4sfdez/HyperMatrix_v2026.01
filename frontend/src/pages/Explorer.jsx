import { useState, useCallback, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Tipos de búsqueda disponibles
const SEARCH_TYPES = [
  { id: 'all', label: 'Todo', icon: '🔍' },
  { id: 'functions', label: 'Funciones', icon: '⚡' },
  { id: 'classes', label: 'Clases', icon: '📦' },
  { id: 'variables', label: 'Variables', icon: '📝' },
  { id: 'imports', label: 'Imports', icon: '📥' },
]

// Componente de detalle expandible
function DetailPanel({ item, type, onClose, onAnalyzeWithAI }) {
  if (!item) return null

  const renderDetail = () => {
    switch (type) {
      case 'functions':
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">⚡</span>
              <span className="font-mono text-lg font-bold text-[var(--color-primary)]">
                {item.is_async ? 'async ' : ''}{item.name}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-[var(--color-fg-secondary)]">Archivo:</span>
                <p className="font-mono text-xs break-all">{item.filepath}</p>
              </div>
              <div>
                <span className="text-[var(--color-fg-secondary)]">Línea:</span>
                <p className="font-bold">{item.lineno}</p>
              </div>
            </div>
            {item.args && item.args.length > 0 && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Argumentos:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.args.map((arg, i) => (
                    <span key={i} className="px-2 py-0.5 bg-[var(--color-bg-tertiary)] rounded text-xs font-mono">
                      {arg}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {item.returns && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Retorna:</span>
                <span className="ml-2 font-mono text-sm text-[var(--color-success)]">{item.returns}</span>
              </div>
            )}
            {item.docstring && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Documentación:</span>
                <p className="mt-1 text-sm bg-[var(--color-bg-secondary)] p-2 rounded italic">
                  {item.docstring}
                </p>
              </div>
            )}
          </div>
        )

      case 'classes':
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">📦</span>
              <span className="font-mono text-lg font-bold text-[var(--color-primary)]">
                class {item.name}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-[var(--color-fg-secondary)]">Archivo:</span>
                <p className="font-mono text-xs break-all">{item.filepath}</p>
              </div>
              <div>
                <span className="text-[var(--color-fg-secondary)]">Línea:</span>
                <p className="font-bold">{item.lineno}</p>
              </div>
            </div>
            {item.bases && item.bases.length > 0 && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Hereda de:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.bases.map((base, i) => (
                    <span key={i} className="px-2 py-0.5 bg-[var(--color-warning)] bg-opacity-20 text-[var(--color-warning)] rounded text-xs font-mono">
                      {base}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {item.methods && item.methods.length > 0 && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Métodos ({item.methods.length}):</span>
                <div className="flex flex-wrap gap-1 mt-1 max-h-32 overflow-y-auto">
                  {item.methods.map((method, i) => (
                    <span key={i} className="px-2 py-0.5 bg-[var(--color-bg-tertiary)] rounded text-xs font-mono">
                      {method}()
                    </span>
                  ))}
                </div>
              </div>
            )}
            {item.docstring && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Documentación:</span>
                <p className="mt-1 text-sm bg-[var(--color-bg-secondary)] p-2 rounded italic">
                  {item.docstring}
                </p>
              </div>
            )}
          </div>
        )

      case 'variables':
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">📝</span>
              <span className="font-mono text-lg font-bold text-[var(--color-primary)]">
                {item.name}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-[var(--color-fg-secondary)]">Archivo:</span>
                <p className="font-mono text-xs break-all">{item.filepath}</p>
              </div>
              <div>
                <span className="text-[var(--color-fg-secondary)]">Línea:</span>
                <p className="font-bold">{item.lineno}</p>
              </div>
            </div>
            {item.type_annotation && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Tipo:</span>
                <span className="ml-2 font-mono text-sm text-[var(--color-success)]">{item.type_annotation}</span>
              </div>
            )}
            {item.scope && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Scope:</span>
                <span className="ml-2 font-mono text-sm">{item.scope}</span>
              </div>
            )}
          </div>
        )

      case 'imports':
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">📥</span>
              <span className="font-mono text-lg font-bold text-[var(--color-primary)]">
                {item.is_from_import ? `from ${item.module}` : `import ${item.module}`}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-[var(--color-fg-secondary)]">Archivo:</span>
                <p className="font-mono text-xs break-all">{item.filepath}</p>
              </div>
              <div>
                <span className="text-[var(--color-fg-secondary)]">Línea:</span>
                <p className="font-bold">{item.lineno}</p>
              </div>
            </div>
            {item.names && item.names.length > 0 && (
              <div>
                <span className="text-[var(--color-fg-secondary)] text-sm">Nombres importados:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.names.map((name, i) => (
                    <span key={i} className="px-2 py-0.5 bg-[var(--color-bg-tertiary)] rounded text-xs font-mono">
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )

      default:
        return <pre className="text-xs">{JSON.stringify(item, null, 2)}</pre>
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
          <h3 className="font-semibold text-[var(--color-fg-primary)]">Detalles</h3>
          <div className="flex items-center gap-2">
            {onAnalyzeWithAI && (
              <button
                onClick={() => onAnalyzeWithAI(item, type)}
                className="px-3 py-1 text-sm bg-[var(--color-primary)] text-white rounded hover:bg-[var(--color-primary-hover)] transition-colors"
                title="Analizar con IA"
              >
                🤖 Analizar con IA
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 hover:bg-[var(--color-bg-secondary)] rounded"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="p-4">
          {renderDetail()}
        </div>
      </div>
    </div>
  )
}

// Fila de resultado
function ResultRow({ item, type, onClick }) {
  const getIcon = () => {
    switch (type) {
      case 'functions': return '⚡'
      case 'classes': return '📦'
      case 'variables': return '📝'
      case 'imports': return '📥'
      default: return '📄'
    }
  }

  const getName = () => {
    if (type === 'imports') return item.module
    return item.name
  }

  const getExtra = () => {
    if (type === 'functions' && item.is_async) return '(async)'
    if (type === 'classes' && item.bases?.length > 0) return `extends ${item.bases.join(', ')}`
    if (type === 'imports' && item.is_from_import) return `import ${item.names?.join(', ') || ''}`
    if (type === 'variables' && item.type_annotation) return `: ${item.type_annotation}`
    return ''
  }

  return (
    <tr
      className="hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
      onClick={() => onClick(item, type)}
    >
      <td className="px-4 py-2 whitespace-nowrap">
        <span className="mr-2">{getIcon()}</span>
        <span className="font-mono font-medium text-[var(--color-fg-primary)]">{getName()}</span>
        {getExtra() && (
          <span className="ml-2 text-xs text-[var(--color-fg-tertiary)]">{getExtra()}</span>
        )}
      </td>
      <td className="px-4 py-2 text-sm text-[var(--color-fg-secondary)] truncate max-w-xs">
        {item.filepath}
      </td>
      <td className="px-4 py-2 text-sm text-[var(--color-fg-secondary)] text-center">
        {item.lineno}
      </td>
    </tr>
  )
}

export default function Explorer({ hypermatrixUrl, ai }) {
  const [searchType, setSearchType] = useState('all')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)
  const [selectedType, setSelectedType] = useState(null)
  const [pagination, setPagination] = useState({ offset: 0, limit: 50 })
  const [stats, setStats] = useState(null)
  const [loadingStats, setLoadingStats] = useState(true)

  // Función para analizar con IA
  const handleAnalyzeWithAI = useCallback((item, type) => {
    if (!ai) return

    // Construir información del elemento para la IA
    let codeInfo = ''
    let language = 'python'

    switch (type) {
      case 'functions':
        codeInfo = `# Función: ${item.name}\n`
        codeInfo += `# Archivo: ${item.filepath}:${item.lineno}\n`
        if (item.is_async) codeInfo += `# Tipo: async function\n`
        if (item.args?.length) codeInfo += `# Argumentos: ${item.args.join(', ')}\n`
        if (item.returns) codeInfo += `# Retorna: ${item.returns}\n`
        if (item.docstring) codeInfo += `# Docstring: ${item.docstring}\n`
        codeInfo += `\n${item.is_async ? 'async ' : ''}def ${item.name}(${item.args?.join(', ') || ''}):`
        if (item.returns) codeInfo += ` -> ${item.returns}`
        codeInfo += `\n    ${item.docstring ? '"""' + item.docstring + '"""' : 'pass'}`
        break

      case 'classes':
        codeInfo = `# Clase: ${item.name}\n`
        codeInfo += `# Archivo: ${item.filepath}:${item.lineno}\n`
        if (item.bases?.length) codeInfo += `# Hereda de: ${item.bases.join(', ')}\n`
        if (item.methods?.length) codeInfo += `# Métodos: ${item.methods.join(', ')}\n`
        if (item.docstring) codeInfo += `# Docstring: ${item.docstring}\n`
        codeInfo += `\nclass ${item.name}${item.bases?.length ? '(' + item.bases.join(', ') + ')' : ''}:\n`
        codeInfo += `    ${item.docstring ? '"""' + item.docstring + '"""' : 'pass'}`
        break

      case 'variables':
        codeInfo = `# Variable: ${item.name}\n`
        codeInfo += `# Archivo: ${item.filepath}:${item.lineno}\n`
        if (item.type_annotation) codeInfo += `# Tipo: ${item.type_annotation}\n`
        if (item.scope) codeInfo += `# Scope: ${item.scope}\n`
        codeInfo += `\n${item.name}${item.type_annotation ? ': ' + item.type_annotation : ''} = ...`
        break

      case 'imports':
        codeInfo = `# Import: ${item.module}\n`
        codeInfo += `# Archivo: ${item.filepath}:${item.lineno}\n`
        if (item.is_from_import) {
          codeInfo += `\nfrom ${item.module} import ${item.names?.join(', ') || '*'}`
        } else {
          codeInfo += `\nimport ${item.module}`
        }
        break

      default:
        codeInfo = JSON.stringify(item, null, 2)
    }

    // Abrir panel de IA con el código
    if (ai?.openWithCode) {
      ai.openWithCode(codeInfo, `${item.name || item.module} (${item.filepath})`, language)
    }
  }, [ai])

  // Cargar estadísticas al montar
  useEffect(() => {
    const loadStats = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/db/stats`)
        if (response.ok) {
          const data = await response.json()
          setStats(data)
        }
      } catch (err) {
        console.error('Error loading stats:', err)
      } finally {
        setLoadingStats(false)
      }
    }
    if (hypermatrixUrl) {
      loadStats()
    }
  }, [hypermatrixUrl])

  const search = useCallback(async (newOffset = 0) => {
    if (!query.trim()) {
      setError('Ingresa un término de búsqueda')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Use the new unified DB search endpoint
      const url = `${hypermatrixUrl}/api/db/search?q=${encodeURIComponent(query)}&type=${searchType}&limit=${pagination.limit}`

      const response = await fetch(url)

      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      // Transform response to expected format
      if (searchType === 'all') {
        setResults({
          functions: data.results?.functions || [],
          classes: data.results?.classes || [],
          variables: data.results?.variables || [],
          imports: data.results?.imports || [],
          total: data.total || 0
        })
      } else {
        setResults({
          results: data.results?.[searchType] || [],
          count: data.results?.[searchType]?.length || 0
        })
      }
      setPagination((prev) => ({ ...prev, offset: newOffset }))
    } catch (err) {
      setError(err.message)
      setResults(null)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, query, searchType, pagination.limit])

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      search(0)
    }
  }

  const handleItemClick = (item, type) => {
    setSelectedItem(item)
    setSelectedType(type)
  }

  const closeDetail = () => {
    setSelectedItem(null)
    setSelectedType(null)
  }

  // Renderizar resultados según el tipo de búsqueda
  const renderResults = () => {
    if (!results) return null

    if (searchType === 'all') {
      // Resultados combinados
      const allResults = []

      if (results.functions?.length > 0) {
        results.functions.forEach((item) => {
          allResults.push({ ...item, _type: 'functions' })
        })
      }
      if (results.classes?.length > 0) {
        results.classes.forEach((item) => {
          allResults.push({ ...item, _type: 'classes' })
        })
      }
      if (results.variables?.length > 0) {
        results.variables.forEach((item) => {
          allResults.push({ ...item, _type: 'variables' })
        })
      }
      if (results.imports?.length > 0) {
        results.imports.forEach((item) => {
          allResults.push({ ...item, _type: 'imports' })
        })
      }

      if (allResults.length === 0) {
        return (
          <p className="text-center text-[var(--color-fg-secondary)] py-8">
            No se encontraron resultados para "{query}"
          </p>
        )
      }

      return (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--color-bg-secondary)]">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-medium text-[var(--color-fg-secondary)]">Nombre</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-[var(--color-fg-secondary)]">Archivo</th>
                <th className="px-4 py-2 text-center text-sm font-medium text-[var(--color-fg-secondary)]">Línea</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {allResults.map((item, idx) => (
                <ResultRow
                  key={`${item._type}-${idx}`}
                  item={item}
                  type={item._type}
                  onClick={handleItemClick}
                />
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    // Resultados específicos por tipo
    const items = results.results || []

    if (items.length === 0) {
      return (
        <p className="text-center text-[var(--color-fg-secondary)] py-8">
          No se encontraron resultados para "{query}"
        </p>
      )
    }

    return (
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-[var(--color-bg-secondary)]">
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium text-[var(--color-fg-secondary)]">Nombre</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-[var(--color-fg-secondary)]">Archivo</th>
              <th className="px-4 py-2 text-center text-sm font-medium text-[var(--color-fg-secondary)]">Línea</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {items.map((item, idx) => (
              <ResultRow
                key={idx}
                item={item}
                type={searchType}
                onClick={handleItemClick}
              />
            ))}
          </tbody>
        </table>

        {/* Paginación */}
        {items.length >= pagination.limit && (
          <div className="flex justify-center gap-2 p-4 border-t border-[var(--color-border)]">
            <Button
              variant="ghost"
              size="sm"
              disabled={pagination.offset === 0}
              onClick={() => search(Math.max(0, pagination.offset - pagination.limit))}
            >
              ← Anterior
            </Button>
            <span className="px-4 py-1 text-sm text-[var(--color-fg-secondary)]">
              Mostrando {pagination.offset + 1} - {pagination.offset + items.length}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => search(pagination.offset + pagination.limit)}
            >
              Siguiente →
            </Button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          🗄️ Explorador de Base de Datos
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Busca funciones, clases, variables e imports en todos los proyectos analizados
        </p>
      </div>

      {/* Filtros y búsqueda */}
      <Card>
        <CardContent className="space-y-4">
          {/* Selector de tipo */}
          <div className="flex flex-wrap gap-2">
            {SEARCH_TYPES.map((type) => (
              <button
                key={type.id}
                onClick={() => setSearchType(type.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  searchType === type.id
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                }`}
              >
                {type.icon} {type.label}
              </button>
            ))}
          </div>

          {/* Input de búsqueda */}
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                searchType === 'imports'
                  ? 'Nombre del módulo (ej: fastapi, react, os)'
                  : 'Término de búsqueda (ej: get_user, MyClass)'
              }
              className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-opacity-20"
            />
            <Button
              variant="primary"
              onClick={() => search(0)}
              disabled={loading || !query.trim()}
            >
              {loading ? '⏳' : '🔍'} Buscar
            </Button>
          </div>

          {error && (
            <p className="text-[var(--color-error)] text-sm bg-[var(--color-error)] bg-opacity-10 p-2 rounded">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Estadísticas de la BD */}
      {!results && (
        <Card>
          <CardHeader>
            <CardTitle>📊 Estadísticas de la Base de Datos</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingStats ? (
              <div className="flex items-center justify-center py-4">
                <div className="animate-spin w-6 h-6 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
              </div>
            ) : stats ? (
              <div className="space-y-4">
                {/* Grid de stats */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                  <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--color-primary)]">
                      {stats.total_projects || 0}
                    </div>
                    <div className="text-xs text-[var(--color-fg-secondary)]">Proyectos</div>
                  </div>
                  <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                      {stats.total_files || 0}
                    </div>
                    <div className="text-xs text-[var(--color-fg-secondary)]">Archivos</div>
                  </div>
                  <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--color-warning)]">
                      {stats.total_functions || 0}
                    </div>
                    <div className="text-xs text-[var(--color-fg-secondary)]">⚡ Funciones</div>
                  </div>
                  <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--color-success)]">
                      {stats.total_classes || 0}
                    </div>
                    <div className="text-xs text-[var(--color-fg-secondary)]">📦 Clases</div>
                  </div>
                  <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                      {stats.total_variables || 0}
                    </div>
                    <div className="text-xs text-[var(--color-fg-secondary)]">📝 Variables</div>
                  </div>
                  <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                      {stats.total_imports || 0}
                    </div>
                    <div className="text-xs text-[var(--color-fg-secondary)]">📥 Imports</div>
                  </div>
                </div>

                {/* Proyectos recientes */}
                {stats.recent_projects && stats.recent_projects.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-[var(--color-fg-secondary)] mb-2">
                      Proyectos Analizados Recientemente
                    </h4>
                    <div className="space-y-1">
                      {stats.recent_projects.map((project, idx) => (
                        <div
                          key={idx}
                          className="text-sm p-2 bg-[var(--color-bg-tertiary)] rounded flex justify-between items-center"
                        >
                          <span className="font-medium text-[var(--color-fg-primary)]">{project.name}</span>
                          <span className="text-xs text-[var(--color-fg-tertiary)] truncate max-w-xs ml-2">
                            {project.path}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {stats.total_files === 0 && (
                  <p className="text-center text-[var(--color-fg-tertiary)] py-2">
                    No hay datos analizados aún. Ejecuta un escaneo para poblar la base de datos.
                  </p>
                )}
              </div>
            ) : (
              <p className="text-center text-[var(--color-fg-tertiary)] py-4">
                No se pudieron cargar las estadísticas
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Resultados */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Resultados</span>
            {results && (
              <span className="text-sm font-normal text-[var(--color-fg-secondary)]">
                {searchType === 'all'
                  ? `${results.total || 0} encontrados`
                  : `${results.count || 0} encontrados`}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
            </div>
          ) : results ? (
            renderResults()
          ) : (
            <p className="text-center text-[var(--color-fg-secondary)] py-8">
              Realiza una búsqueda para ver resultados
            </p>
          )}
        </CardContent>
      </Card>

      {/* Panel de detalle */}
      {selectedItem && (
        <DetailPanel
          item={selectedItem}
          type={selectedType}
          onClose={closeDetail}
          onAnalyzeWithAI={ai ? handleAnalyzeWithAI : null}
        />
      )}
    </div>
  )
}
