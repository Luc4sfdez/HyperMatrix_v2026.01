import { useState, useEffect, useCallback } from 'react'

// Icono por tipo de archivo
function FileIcon({ name, isDir }) {
  if (isDir) return <span>📁</span>

  const ext = name.split('.').pop()?.toLowerCase()
  const icons = {
    py: '🐍',
    js: '📜',
    jsx: '⚛️',
    ts: '📘',
    tsx: '⚛️',
    json: '📋',
    md: '📝',
    txt: '📄',
    css: '🎨',
    html: '🌐',
    yml: '⚙️',
    yaml: '⚙️',
    git: '🔀',
    env: '🔒',
  }
  return <span>{icons[ext] || '📄'}</span>
}

export default function FileBrowser({
  isOpen,
  onClose,
  onSelect,
  initialPath = '',
  mode = 'file', // 'file' | 'directory' | 'both'
  filter = null, // e.g. '.py' or ['.py', '.js']
  multiple = false,
  title = 'Seleccionar Archivo',
  hypermatrixUrl,
}) {
  const [currentPath, setCurrentPath] = useState(initialPath || '/projects')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(multiple ? [] : null)
  const [pathInput, setPathInput] = useState(currentPath)

  // Cargar contenido del directorio
  const loadDirectory = useCallback(async (path) => {
    setLoading(true)
    setError(null)

    try {
      // Usar endpoint del backend para listar directorio
      const response = await fetch(
        `${hypermatrixUrl}/api/browse?path=${encodeURIComponent(path)}`
      )

      if (!response.ok) {
        // Si no existe el endpoint, simular con datos básicos
        if (response.status === 404) {
          setError('Endpoint de navegación no disponible')
          setItems([])
          return
        }
        throw new Error(`Error ${response.status}`)
      }

      const data = await response.json()
      setItems(data.items || [])
      setCurrentPath(path)
      setPathInput(path)
    } catch (err) {
      setError(err.message)
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl])

  useEffect(() => {
    if (isOpen && hypermatrixUrl) {
      loadDirectory(currentPath)
    }
  }, [isOpen, hypermatrixUrl])

  const navigateTo = (path) => {
    loadDirectory(path)
  }

  const navigateUp = () => {
    const parts = currentPath.replace(/\\/g, '/').split('/').filter(Boolean)
    if (parts.length > 0) {
      parts.pop()
      const newPath = '/' + parts.join('/')
      navigateTo(newPath || '/')
    }
  }

  // Quick navigation locations
  const quickLocations = [
    { path: '/projects', label: '📂 Proyectos', desc: 'Solo lectura' },
    { path: '/workspace', label: '📁 Workspace', desc: '20GB disponibles' },
  ]

  const handleItemClick = (item) => {
    if (item.is_dir) {
      navigateTo(item.path)
    } else {
      if (mode === 'directory') return // Solo directorios

      if (multiple) {
        setSelected(prev => {
          const exists = prev.find(p => p === item.path)
          if (exists) {
            return prev.filter(p => p !== item.path)
          }
          return [...prev, item.path]
        })
      } else {
        setSelected(item.path)
      }
    }
  }

  const handleSelectDirectory = () => {
    if (mode === 'file') return
    onSelect(currentPath)
    onClose()
  }

  const handleConfirm = () => {
    if (mode === 'directory') {
      onSelect(currentPath)
    } else if (multiple) {
      onSelect(selected)
    } else if (selected) {
      onSelect(selected)
    }
    onClose()
  }

  const handlePathSubmit = (e) => {
    e.preventDefault()
    navigateTo(pathInput)
  }

  const isSelected = (path) => {
    if (multiple) {
      return selected.includes(path)
    }
    return selected === path
  }

  const shouldShowItem = (item) => {
    if (!filter) return true
    if (item.is_dir) return true

    const filters = Array.isArray(filter) ? filter : [filter]
    return filters.some(f => item.name.endsWith(f))
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="font-bold text-[var(--color-fg-primary)]">{title}</h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[var(--color-bg-secondary)] rounded"
          >
            ✕
          </button>
        </div>

        {/* Quick locations */}
        <div className="px-3 pt-3 flex gap-2">
          {quickLocations.map(loc => (
            <button
              key={loc.path}
              onClick={() => navigateTo(loc.path)}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                currentPath.startsWith(loc.path)
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
              title={loc.desc}
            >
              {loc.label}
            </button>
          ))}
        </div>

        {/* Path bar */}
        <form onSubmit={handlePathSubmit} className="p-3 border-b border-[var(--color-border)] flex gap-2">
          <button
            type="button"
            onClick={navigateUp}
            className="px-3 py-1.5 bg-[var(--color-bg-secondary)] rounded hover:bg-[var(--color-bg-tertiary)] text-[var(--color-fg-primary)]"
          >
            ↑
          </button>
          <input
            type="text"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            className="flex-1 px-3 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] font-mono text-sm focus:outline-none focus:border-[var(--color-primary)]"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded hover:opacity-90"
          >
            Ir
          </button>
        </form>

        {/* File list */}
        <div className="flex-1 overflow-auto p-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-[var(--color-error)] mb-4">{error}</p>
              <p className="text-sm text-[var(--color-fg-tertiary)]">
                Ingresa la ruta manualmente o verifica que el backend esté corriendo
              </p>
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-[var(--color-fg-tertiary)]">
              Directorio vacío
            </div>
          ) : (
            <div className="space-y-1">
              {items
                .filter(shouldShowItem)
                .sort((a, b) => {
                  // Directorios primero
                  if (a.is_dir && !b.is_dir) return -1
                  if (!a.is_dir && b.is_dir) return 1
                  return a.name.localeCompare(b.name)
                })
                .map((item) => (
                  <div
                    key={item.path}
                    onClick={() => handleItemClick(item)}
                    className={`
                      flex items-center gap-3 px-3 py-2 rounded cursor-pointer transition-colors
                      ${isSelected(item.path)
                        ? 'bg-[var(--color-primary)] bg-opacity-20 border border-[var(--color-primary)]'
                        : 'hover:bg-[var(--color-bg-secondary)]'
                      }
                      ${item.is_dir && mode === 'file' ? 'cursor-pointer' : ''}
                    `}
                  >
                    <FileIcon name={item.name} isDir={item.is_dir} />
                    <span className="flex-1 truncate text-[var(--color-fg-primary)]">
                      {item.name}
                    </span>
                    {item.is_dir && (
                      <span className="text-xs text-[var(--color-fg-tertiary)]">→</span>
                    )}
                    {!item.is_dir && item.size && (
                      <span className="text-xs text-[var(--color-fg-tertiary)]">
                        {(item.size / 1024).toFixed(1)} KB
                      </span>
                    )}
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--color-border)] flex items-center justify-between">
          <div className="text-sm text-[var(--color-fg-tertiary)]">
            {multiple && selected.length > 0 && (
              <span>{selected.length} archivo(s) seleccionado(s)</span>
            )}
            {!multiple && selected && (
              <span className="truncate max-w-xs">{selected}</span>
            )}
          </div>
          <div className="flex gap-2">
            {mode !== 'file' && (
              <button
                onClick={handleSelectDirectory}
                className="px-4 py-2 bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] rounded hover:bg-[var(--color-bg-tertiary)]"
              >
                Usar Este Directorio
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] rounded hover:bg-[var(--color-bg-tertiary)]"
            >
              Cancelar
            </button>
            {mode !== 'directory' && (
              <button
                onClick={handleConfirm}
                disabled={multiple ? selected.length === 0 : !selected}
                className="px-4 py-2 bg-[var(--color-primary)] text-white rounded hover:opacity-90 disabled:opacity-50"
              >
                Seleccionar
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
