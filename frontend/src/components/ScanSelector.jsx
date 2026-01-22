import { useState, useEffect } from 'react'

export default function ScanSelector({
  value,
  onChange,
  hypermatrixUrl,
  label = "Scan",
  placeholder = "Seleccionar scan...",
  showDetails = true,
  emptyMessage = "No hay scans disponibles",
}) {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [isOpen, setIsOpen] = useState(false)

  // Cargar scans
  useEffect(() => {
    const loadScans = async () => {
      setLoading(true)
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        if (response.ok) {
          const data = await response.json()
          setScans(data.scans || [])
        }
      } catch (err) {
        console.error('Error loading scans:', err)
      } finally {
        setLoading(false)
      }
    }
    loadScans()
  }, [hypermatrixUrl])

  const selectedScan = scans.find(s => s.scan_id === value)

  const handleSelect = (scan) => {
    onChange(scan.scan_id, scan)
    setIsOpen(false)
  }

  const formatDate = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const getProjectName = (scan) => {
    if (scan.project) {
      // Extraer nombre del directorio
      const parts = scan.project.replace(/\\/g, '/').split('/').filter(Boolean)
      return parts[parts.length - 1] || scan.project
    }
    return `Scan ${scan.scan_id.slice(0, 8)}`
  }

  return (
    <div className="relative">
      {label && (
        <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
          {label}
        </label>
      )}

      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        className="w-full px-4 py-2 text-left border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50 flex items-center justify-between"
      >
        {loading ? (
          <span className="text-[var(--color-fg-tertiary)]">Cargando...</span>
        ) : selectedScan ? (
          <div className="flex-1 min-w-0">
            <div className="font-medium truncate">{getProjectName(selectedScan)}</div>
            {showDetails && (
              <div className="text-xs text-[var(--color-fg-tertiary)]">
                {selectedScan.files} archivos • {formatDate(selectedScan.timestamp)}
              </div>
            )}
          </div>
        ) : (
          <span className="text-[var(--color-fg-tertiary)]">{placeholder}</span>
        )}
        <span className="ml-2 text-[var(--color-fg-tertiary)]">{isOpen ? '▲' : '▼'}</span>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-md shadow-lg max-h-64 overflow-auto">
          {scans.length === 0 ? (
            <div className="p-4 text-center text-[var(--color-fg-tertiary)]">
              {emptyMessage}
            </div>
          ) : (
            scans.map(scan => (
              <div
                key={scan.scan_id}
                onClick={() => handleSelect(scan)}
                className={`px-4 py-3 cursor-pointer transition-colors ${
                  scan.scan_id === value
                    ? 'bg-[var(--color-primary)] bg-opacity-10 border-l-4 border-[var(--color-primary)]'
                    : 'hover:bg-[var(--color-bg-secondary)]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-[var(--color-fg-primary)] truncate">
                      {getProjectName(scan)}
                    </div>
                    {scan.project && (
                      <div className="text-xs text-[var(--color-fg-tertiary)] truncate">
                        {scan.project}
                      </div>
                    )}
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-sm text-[var(--color-fg-secondary)]">
                      {scan.files} archivos
                    </div>
                    <div className="text-xs text-[var(--color-fg-tertiary)]">
                      {formatDate(scan.timestamp)}
                    </div>
                  </div>
                </div>

                {/* Status badge */}
                <div className="mt-2 flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    scan.status === 'completed'
                      ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
                      : scan.status === 'running'
                        ? 'bg-[var(--color-warning)] bg-opacity-20 text-[var(--color-warning)]'
                        : 'bg-[var(--color-fg-tertiary)] bg-opacity-20 text-[var(--color-fg-tertiary)]'
                  }`}>
                    {scan.status === 'completed' ? '✓ Completado' :
                     scan.status === 'running' ? '⏳ En progreso' : scan.status}
                  </span>
                  <span className="text-xs text-[var(--color-fg-tertiary)] font-mono">
                    {scan.scan_id.slice(0, 8)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  )
}
