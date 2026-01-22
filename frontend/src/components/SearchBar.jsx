import { useState, useRef, useEffect, useCallback } from 'react'

export function SearchBar({ hypermatrixUrl, onNavigate }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [parsedQuery, setParsedQuery] = useState(null)
  const containerRef = useRef(null)
  const debounceRef = useRef(null)

  // Cerrar al hacer click fuera
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Búsqueda con debounce
  const search = useCallback(async (searchQuery) => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setResults(null)
      setIsOpen(false)
      return
    }

    setLoading(true)
    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/advanced/search?q=${encodeURIComponent(searchQuery)}&limit=10`
      )

      if (response.ok) {
        const data = await response.json()
        setResults(data.results || [])
        setParsedQuery(data.parsed_query || null)
        setIsOpen(true)
      } else {
        setResults([])
      }
    } catch (error) {
      console.error('Search error:', error)
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl])

  const handleInputChange = (e) => {
    const value = e.target.value
    setQuery(value)

    // Debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      search(value)
    }, 300)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setIsOpen(false)
    }
    if (e.key === 'Enter' && query.trim()) {
      search(query)
    }
  }

  const getTypeIcon = (type) => {
    switch (type?.toLowerCase()) {
      case 'function': return '⚡'
      case 'class': return '📦'
      case 'variable': return '📝'
      case 'import': return '📥'
      case 'file': return '📄'
      default: return '🔍'
    }
  }

  const getTypeColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'function': return 'text-[var(--color-primary)]'
      case 'class': return 'text-[var(--color-warning)]'
      case 'variable': return 'text-[var(--color-success)]'
      case 'import': return 'text-[var(--color-fg-secondary)]'
      default: return 'text-[var(--color-fg-primary)]'
    }
  }

  return (
    <div ref={containerRef} className="relative flex-1 max-w-md">
      {/* Input */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => results?.length > 0 && setIsOpen(true)}
          placeholder="Buscar en lenguaje natural... (ej: funciones async)"
          className="w-full pl-10 pr-4 py-2 text-sm border border-[var(--color-border)] rounded-lg bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-opacity-20 placeholder:text-[var(--color-fg-tertiary)]"
        />
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-fg-tertiary)]">
          {loading ? '⏳' : '🔍'}
        </span>
        {query && (
          <button
            onClick={() => {
              setQuery('')
              setResults(null)
              setIsOpen(false)
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-fg-tertiary)] hover:text-[var(--color-fg-primary)]"
          >
            ✕
          </button>
        )}
      </div>

      {/* Dropdown de resultados */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
          {/* Query parseada */}
          {parsedQuery && (parsedQuery.element_types?.length > 0 || parsedQuery.keywords?.length > 0) && (
            <div className="px-3 py-2 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)] text-xs">
              <span className="text-[var(--color-fg-tertiary)]">Buscando: </span>
              {parsedQuery.element_types?.map((t, i) => (
                <span key={i} className="inline-block px-1.5 py-0.5 mx-0.5 bg-[var(--color-primary)] bg-opacity-20 text-[var(--color-primary)] rounded">
                  {t}
                </span>
              ))}
              {parsedQuery.keywords?.map((k, i) => (
                <span key={i} className="inline-block px-1.5 py-0.5 mx-0.5 bg-[var(--color-bg-tertiary)] text-[var(--color-fg-secondary)] rounded">
                  {k}
                </span>
              ))}
            </div>
          )}

          {/* Resultados */}
          {results?.length > 0 ? (
            <ul>
              {results.map((result, idx) => (
                <li key={idx}>
                  <button
                    onClick={() => {
                      setIsOpen(false)
                      // Navegar a explorador con el resultado
                      if (onNavigate) {
                        onNavigate('explorer', result)
                      }
                    }}
                    className="w-full px-3 py-2 text-left hover:bg-[var(--color-bg-secondary)] flex items-start gap-3 border-b border-[var(--color-border)] last:border-b-0"
                  >
                    <span className="text-lg mt-0.5">{getTypeIcon(result.type)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`font-mono font-medium ${getTypeColor(result.type)}`}>
                          {result.name}
                        </span>
                        <span className="text-xs text-[var(--color-fg-tertiary)] bg-[var(--color-bg-secondary)] px-1.5 py-0.5 rounded">
                          {result.type}
                        </span>
                        {result.score && (
                          <span className="text-xs text-[var(--color-fg-tertiary)]">
                            {(result.score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[var(--color-fg-tertiary)] truncate">
                        {result.file}:{result.line}
                      </p>
                      {result.snippet && (
                        <p className="text-xs text-[var(--color-fg-secondary)] mt-1 font-mono bg-[var(--color-bg-secondary)] p-1 rounded truncate">
                          {result.snippet}
                        </p>
                      )}
                      {result.match_reasons?.length > 0 && (
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {result.match_reasons.slice(0, 3).map((reason, i) => (
                            <span key={i} className="text-xs text-[var(--color-success)] bg-[var(--color-success)] bg-opacity-10 px-1 rounded">
                              {reason}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="px-3 py-4 text-center text-sm text-[var(--color-fg-secondary)]">
              {loading ? 'Buscando...' : 'No se encontraron resultados'}
            </div>
          )}

          {/* Footer con ayuda */}
          <div className="px-3 py-2 bg-[var(--color-bg-secondary)] border-t border-[var(--color-border)] text-xs text-[var(--color-fg-tertiary)]">
            Ejemplos: "funciones async", "clases con metodo save", "imports de pandas"
          </div>
        </div>
      )}
    </div>
  )
}

export default SearchBar
