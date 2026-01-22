import { useState, useEffect, useCallback } from 'react'

// Agregar proyecto al historial via API
export async function addRecentProject(hypermatrixUrl, path, name = null) {
  try {
    const params = new URLSearchParams({ path })
    if (name) params.append('name', name)

    await fetch(`${hypermatrixUrl}/api/history/projects?${params.toString()}`, {
      method: 'POST',
    })
  } catch (err) {
    console.error('Error adding to history:', err)
  }
}

export default function ProjectSelector({
  value,
  onChange,
  placeholder = "Selecciona o ingresa ruta del proyecto",
  label = "Proyecto",
  showFavorites = true,
  hypermatrixUrl,
}) {
  const [inputValue, setInputValue] = useState(value || '')
  const [isOpen, setIsOpen] = useState(false)
  const [recentProjects, setRecentProjects] = useState([])
  const [favoriteProjects, setFavoriteProjects] = useState([])
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(false)

  // Cargar historial desde API
  const loadHistory = useCallback(async () => {
    if (!hypermatrixUrl) return

    setLoading(true)
    try {
      const response = await fetch(`${hypermatrixUrl}/api/history/projects?limit=10`)
      if (response.ok) {
        const data = await response.json()
        setRecentProjects(data.recent || [])
        setFavoriteProjects(data.favorites || [])
      }
    } catch (err) {
      console.error('Error loading history:', err)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl])

  // Cargar scans del backend
  const loadScans = useCallback(async () => {
    if (!hypermatrixUrl) return

    try {
      const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
      if (response.ok) {
        const data = await response.json()
        setScans(data.scans || [])
      }
    } catch (err) {
      console.error('Error loading scans:', err)
    }
  }, [hypermatrixUrl])

  // Cargar datos solo al montar el componente
  useEffect(() => {
    if (hypermatrixUrl) {
      loadHistory()
      loadScans()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hypermatrixUrl])

  // Sincronizar valor externo
  useEffect(() => {
    setInputValue(value || '')
  }, [value])

  const handleInputChange = (e) => {
    setInputValue(e.target.value)
    setIsOpen(true)
  }

  const handleSelect = async (path, name) => {
    setInputValue(path)
    onChange(path, name)
    setIsOpen(false)

    // Agregar al historial
    if (hypermatrixUrl) {
      await addRecentProject(hypermatrixUrl, path, name)
      loadHistory() // Recargar
    }
  }

  const handleBlur = () => {
    setTimeout(() => setIsOpen(false), 200)
  }

  const handleKeyDown = async (e) => {
    if (e.key === 'Enter') {
      onChange(inputValue)
      setIsOpen(false)
      if (inputValue && hypermatrixUrl) {
        await addRecentProject(hypermatrixUrl, inputValue)
        loadHistory()
      }
    }
    if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  const toggleFavorite = async (path, e) => {
    e.stopPropagation()
    if (!hypermatrixUrl) return

    try {
      await fetch(`${hypermatrixUrl}/api/history/projects/favorite?path=${encodeURIComponent(path)}`, {
        method: 'POST',
      })
      loadHistory()
    } catch (err) {
      console.error('Error toggling favorite:', err)
    }
  }

  const isFavorite = (path) => {
    return favoriteProjects.some(f => f.path === path)
  }

  // Filtrar opciones basado en input
  const getFilteredOptions = () => {
    const search = inputValue.toLowerCase()
    const options = []

    // Favoritos primero
    if (showFavorites && favoriteProjects.length > 0) {
      const filtered = favoriteProjects.filter(p =>
        (p.path || '').toLowerCase().includes(search) ||
        (p.name || '').toLowerCase().includes(search)
      )
      if (filtered.length > 0) {
        options.push({ type: 'header', label: 'Favoritos' })
        filtered.forEach(p => options.push({ type: 'project', ...p, isFav: true }))
      }
    }

    // Recientes
    if (recentProjects.length > 0) {
      const filtered = recentProjects.filter(p =>
        !isFavorite(p.path) && (
          (p.path || '').toLowerCase().includes(search) ||
          (p.name || '').toLowerCase().includes(search)
        )
      )
      if (filtered.length > 0) {
        options.push({ type: 'header', label: 'Recientes' })
        filtered.forEach(p => options.push({ type: 'project', ...p }))
      }
    }

    // Scans del backend
    if (scans.length > 0) {
      const filtered = scans.filter(s => {
        const scanSearch = (s.project || s.scan_id || '').toLowerCase()
        return scanSearch.includes(search)
      })
      if (filtered.length > 0) {
        options.push({ type: 'header', label: 'Scans Anteriores' })
        filtered.forEach(s => options.push({
          type: 'scan',
          scan_id: s.scan_id,
          path: s.project || s.scan_id,
          name: s.project ? s.project.split(/[/\\]/).pop() : `Scan ${s.scan_id.slice(0,8)}`,
          files: s.files,
          timestamp: s.timestamp
        }))
      }
    }

    return options
  }

  const options = isOpen ? getFilteredOptions() : []

  return (
    <div className="relative">
      {label && (
        <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
          {label}
        </label>
      )}

      <div className="relative">
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full px-4 py-2 pr-10 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
        />
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[var(--color-fg-tertiary)] hover:text-[var(--color-fg-primary)]"
        >
          {loading ? '...' : isOpen ? '▲' : '▼'}
        </button>
      </div>

      {/* Dropdown */}
      {isOpen && options.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-md shadow-lg max-h-64 overflow-auto">
          {options.map((option, idx) => {
            if (option.type === 'header') {
              return (
                <div
                  key={`header-${idx}`}
                  className="px-3 py-2 text-xs font-medium text-[var(--color-fg-tertiary)] bg-[var(--color-bg-secondary)] sticky top-0"
                >
                  {option.label}
                </div>
              )
            }

            if (option.type === 'scan') {
              return (
                <div
                  key={option.scan_id}
                  onClick={() => handleSelect(option.path, option.name)}
                  className="px-3 py-2 cursor-pointer hover:bg-[var(--color-bg-secondary)] flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-[var(--color-fg-primary)] truncate">
                      {option.name}
                    </div>
                    <div className="text-xs text-[var(--color-fg-tertiary)]">
                      {option.files} archivos • {option.timestamp ? new Date(option.timestamp).toLocaleDateString() : ''}
                    </div>
                  </div>
                  <span className="text-xs text-[var(--color-primary)] ml-2">scan</span>
                </div>
              )
            }

            return (
              <div
                key={option.path}
                onClick={() => handleSelect(option.path, option.name)}
                className="px-3 py-2 cursor-pointer hover:bg-[var(--color-bg-secondary)] flex items-center justify-between group"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-[var(--color-fg-primary)] truncate">
                    {option.name}
                  </div>
                  <div className="text-xs text-[var(--color-fg-tertiary)] truncate">
                    {option.path}
                  </div>
                  {option.use_count > 1 && (
                    <div className="text-xs text-[var(--color-fg-tertiary)]">
                      Usado {option.use_count}x
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => toggleFavorite(option.path, e)}
                  className={`ml-2 p-1 rounded transition-colors ${
                    isFavorite(option.path)
                      ? 'text-yellow-500'
                      : 'text-[var(--color-fg-tertiary)] opacity-0 group-hover:opacity-100'
                  }`}
                >
                  {isFavorite(option.path) ? '★' : '☆'}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* Empty state */}
      {isOpen && options.length === 0 && inputValue && (
        <div className="absolute z-50 w-full mt-1 bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-md shadow-lg p-3 text-center text-sm text-[var(--color-fg-tertiary)]">
          Presiona Enter para usar esta ruta
        </div>
      )}
    </div>
  )
}
